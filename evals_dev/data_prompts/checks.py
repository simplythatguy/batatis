"""Deterministic checks: the guardrails (hard gates, not part of accuracy) and gold-article coverage."""
from __future__ import annotations

import re

from .gold import TIER_KIND
from .render import provisions, system_text

_CLAIM = re.compile(
    r"\b(?:is|are|will\s+be|would\s+be|appears\s+to\s+be|seems)\s+(?:fully\s+)?(?:code[- ])?"
    r"(?:compliant|safe|approved|acceptable|adequate)\b"
    r"|\b(?:complies|comply)\s+with\b"
    r"|\bmeets?\s+(?:all\s+)?(?:of\s+)?(?:the\s+)?(?:code|requirements|NBC)\b"
    r"|\bsatisf(?:ies|y)\s+(?:all\s+)?(?:the\s+)?(?:code|requirements)\b", re.I)
# Negation, conditions, questions, attribution to a document or a party, and requirement modals: a sentence
# that reports what a source says, or what an application must show, is not Batatis's own verdict.
_HEDGE = re.compile(r"\b(?:not|never|no|cannot|can't|isn't|aren't|without|whether|if|nor|neither|unless|"
                    r"does\s+not|do\s+not|did\s+not|before|until|asks?|confirm|show(?:s|ing)?\s+that|"
                    r"demonstrate[sd]?|evidence\s+that|decides?|decided|determin\w+|found|finds|"
                    r"states?|stated|says?|said|reports?|reported|argued?|argues|asserts?|asserted|claims?|"
                    r"claimed|records?|recorded|according\s+to|opinion|considered|concluded|accepted|"
                    r"must|shall|should|required\s+to|requires?|need(?:s|ed)?\s+to|designed\s+to|intended|"
                    r"would|could|may|might|deemed)\b", re.I)


def claims(texts: list[str]) -> list[str]:
    """Sentences in Batatis's own voice that state compliance, safety, approval or adequacy outright."""
    out = []
    for text in texts:
        for sentence in re.split(r'(?<=[.!?])\s+', text):
            if sentence.rstrip().endswith('?'):
                continue
            for m in _CLAIM.finditer(sentence):
                if not _HEDGE.search(sentence[:m.start()]):
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
    return {
        'no_claims': (not found_claims, ' | '.join(found_claims[:3])),
        'citations_resolve': (not bad, ', '.join(bad[:10])),
        'no_alberta_commit_outside_alberta': (not (foreign and committed), ', '.join(committed)),
        'ran': (bool(result.get('case')) and not result.get('errors'), '; '.join(result.get('errors') or [])[:300]),
    }


def articles(gold_articles: tuple[str, ...], result: dict) -> list[tuple[str, bool]]:
    shown = provisions(result)
    return [(a, a in shown) for a in gold_articles]
