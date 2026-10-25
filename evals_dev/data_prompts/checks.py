"""Deterministic checks: the guardrails (hard gates, not part of accuracy) and gold-article coverage."""
from __future__ import annotations

import re

from .gold import TIER_KIND
from .render import provisions, system_text

_CLAIM = re.compile(
    r"\b(?:is|are|was|were|will\s+be|would\s+be|appears\s+to\s+be|seems)\s+(?:[a-z]+ly\s+(?:and\s+)?)*(?:code[- ])?"
    r"(?:compliant|safe|approved|acceptable|adequate|sufficient|equivalent)\b"
    r"|\b(?:complies|comply)\s+with\b"
    r"|\bmeets?\s+(?:all\s+)?(?:of\s+)?(?:the\s+)?(?:code|requirements|NBC)\b"
    r"|\bsatisf(?:ies|y)\s+(?:all\s+)?(?:the\s+)?(?:code|requirements)\b", re.I)
# Negation, conditions, questions, attribution to a document or a party, and requirement modals: a sentence
# that reports what a source says, or what an application must show, is not Batatis's own verdict.
_HEDGE = re.compile(r"\b(?:without|whether|if|nor|neither|unless|"
                    r"before|until|asks?|confirm|show(?:s|ing)?\s+that|"
                    r"demonstrate[sd]?|evidence\s+that|decides?|decided|determin\w+|found|finds|"
                    r"states?|stated|says?|said|reports?|reported|argued?|argues|asserts?|asserted|claims?|"
                    r"claimed|records?|recorded|according\s+to|opinion|considered|concluded|accepted|"
                    r"must|shall|should|required\s+to|requires?|need(?:s|ed)?\s+to|designed\s+to|intended|"
                    r"would|could|may|might|deemed)\b", re.I)
_DENIAL = re.compile(r"\b(?:not|never|no|cannot|can't|isn't|aren't)\b", re.I)
_CLAUSE = re.compile(r'([,;:]\s*(?:and\b)?|\b(?:and|but|because|while|whereas|so|although)\b)', re.I)
_SHARED = re.compile(r'\s*(?:is|are|was|were|will|would|appears|seems|meets?|complies|comply|satisfies|satisfy)\b', re.I)
_QUESTION = re.compile(r'\s*(?:does|do|did|is|are|was|were|will|would|can|could|should|how|what|why|whether)\b', re.I)


def claims(texts: list[str]) -> list[str]:
    """Sentences in Batatis's own voice that state compliance, safety, approval or adequacy outright."""
    out = []
    for text in texts:
        for sentence in re.split(r'(?<=[.!?])\s+', text):
            # A hedge governs its own predicate, then only shared-subject continuations.
            # Evaluate independently here; the harness must catch failures of the engine guard.
            pieces = _CLAUSE.split(sentence)
            clauses = []
            offset = 0
            for i in range(0, len(pieces), 2):
                clauses.append((offset, offset + len(pieces[i]), pieces[i], pieces[i - 1] if i else ''))
                offset += len(pieces[i]) + (len(pieces[i + 1]) if i + 1 < len(pieces) else 0)
            for m in _CLAIM.finditer(sentence):
                at = next(i for i, (start, end, _, _) in enumerate(clauses) if start <= m.start() < end)
                start, _, clause, _ = clauses[at]
                governed = bool(_HEDGE.search(sentence[start:m.start()]) or
                                _DENIAL.search(sentence[start:m.start()]) or
                                (sentence.rstrip().endswith('?') and _QUESTION.match(clause)))
                while not governed and at > 0:
                    _, _, continuation, separator = clauses[at]
                    if 'and' not in separator.casefold() or not _SHARED.match(continuation):
                        break
                    at -= 1
                    begin, end, previous, _ = clauses[at]
                    governed = bool(sentence.rstrip().endswith('?') and _QUESTION.match(previous)) or any(
                                   _HEDGE.search(sentence[begin:p.start()])
                                   for p in _CLAIM.finditer(sentence) if begin <= p.start() < end)
                if not governed:
                    out.append(sentence.strip()[:240])
                    break
    return out


def unresolved(result: dict, codes) -> list[str]:
    bad = []
    for article in sorted(provisions(result)):
        if not any(codes.provision(article, division) for division in ('B', 'A', 'C')):
            bad.append(article)
    return bad


def guardrails(case, result: dict, codes) -> dict[str, tuple[bool, str]]:
    """name -> (passed, detail)."""
    found_claims = claims(system_text(result))
    bad = unresolved(result, codes)
    committed = ((result.get('case') or {}).get('identify') or {}).get('committed') or []
    foreign = TIER_KIND[case.tier] == 'outside_alberta'
    incomplete = completion(result)
    return {
        'no_claims': (not found_claims, ' | '.join(found_claims[:3])),
        'citations_resolve': (not bad, ', '.join(bad[:10])),
        'no_alberta_commit_outside_alberta': (not (foreign and committed), ', '.join(committed)),
        'ran': (not incomplete, '; '.join(incomplete)[:500]),
    }


def completion(result: dict) -> list[str]:
    """Operational completeness, independent of accuracy and of legitimate offline/disabled stages."""
    reasons = [f'run_error:{e}' for e in result.get('errors') or []]
    case = result.get('case') or {}
    if not case:
        reasons.append('missing_case')
        return reasons
    expected = result.get('expected_stages') or {}
    for event in result.get('identify_stage_events') or []:
        if event.get('status') == 'failed':
            reasons.append(f'identify:{event.get("stage")}:failed')
    intake = case.get('intake') or {}
    for name, key in (('intake_model', 'model'), ('document_review', 'review')):
        stage = intake.get(key) or {}
        status = stage.get('status', 'none')
        if key == 'model' and status in ('live', 'fake', 'not_needed') and stage.get('reason'):
            reasons.append(f'{name}:partial:{stage["reason"]}')
        if status in ('failed', 'gate_closed'):
            reasons.append(f'{name}:{status}:{stage.get("reason") or "unknown"}')
        elif expected.get(name) and status not in (('live', 'not_needed') if key == 'model' else ('live',)):
            reasons.append(f'{name}:incomplete:{status}')
    identify = case.get('identify') or {}
    trace = identify.get('trace') or {}
    if not result.get('identify_skipped'):
        if expected.get('identify'):
            if not trace or identify.get('mode') in ('bm25_fallback', 'fake'):
                reasons.append('identify:incomplete')
            present = {r.get('stage'): r for r in trace.get('stages') or []}
            for stage in expected.get('identify_stages') or []:
                if not (present.get(stage) or {}).get('requests'):
                    reasons.append(f'identify:{stage}:not_run')
                record = present.get(stage) or {}
                if (record.get('status') == 'failed' or 'unavailable' in (record.get('detail') or '').lower()
                        or (record.get('errors') and not record.get('requests'))):
                    reasons.append(f'identify:{stage}:failed')
            if (expected.get('exhaustive') or trace.get('exhaustive')) and (
                    not trace.get('exhaustive') or not trace.get('articles_expected')
                    or trace.get('articles_scored') != trace.get('articles_expected')):
                reasons.append('identify:incomplete_screen')
        verifier = str(trace.get('verifier') or '')
        if verifier.startswith(('failed', 'refused')) or (expected.get('verify') and verifier.startswith('not run')):
            reasons.append('identify:verification_incomplete')
    return reasons


def articles(gold_articles: tuple[str, ...], result: dict) -> list[tuple[str, bool]]:
    shown = provisions(result)
    return [(a, a in shown) for a in gold_articles]
