"""Shared identification used by the CLI and by POST /cases/{id}/identify.

A caller that passes `judge` keeps the Jev screen-and-rerank path the CLI tests use.
With no judge and no provider key, the run is BM25 only: nothing is suggested, and Jev
is not called. Citations that are not in the candidate articles are never returned.
`suggested` is a ranking hint for the benchmark. It does not accept an article onto a case.
"""
from __future__ import annotations

import os
import re
from pathlib import Path

from engine.codes import CodeDbMissing, Codes, default_db
from engine.identify import Judge, articles, bm25_rank, identify
from engine.identify.config import (COMMIT_PARTS, RERANK_MODEL, RERANK_N, SCREEN_MODEL, TOP_K,
                                    VERIFY_MODEL_ANTHROPIC, VERIFY_MODEL_OPENAI, VERIFY_N,
                                    commit_policy, has_live_model, provider, rerank_mode, screen_mode)
from engine.identify.corpus import card
from engine.identify.departure import assess_variance, detect_redirect
from engine.identify.questions import generate_questions
from engine.identify.offline import ProviderOutage, is_provider_outage
from engine.identify.verify import Pick, check_quotes
from engine.section_c import section_c_rows

_ARTICLE = re.compile(r'(\d+\.\d+\.\d+\.\d+\.)')


def _stage(on_stage, name: str, payload: dict | None = None) -> None:
    if on_stage:
        on_stage(name, {'stage': name, **(payload or {})})


def short_quote(text: str | None, limit: int = 200) -> str | None:
    flat = re.sub(r'\s+', ' ', text or '').strip()
    if not flat:
        return None
    if len(flat) <= limit:
        return flat
    cut = flat[:limit]
    return cut.rsplit(' ', 1)[0] if ' ' in cut else cut


def _rank_bm25(prose: str, db: Path | None, arts: dict) -> list[str]:
    if db is not None and Path(db).exists():
        return [a for a in bm25_rank(prose, Path(db)) if a in arts]
    words = set(re.findall(r'[a-z]{3,}', prose.lower()))
    scored = []
    for art, row in arts.items():
        blob = f"{row.get('title', '')} {row.get('text', '')}".lower()
        scored.append((sum(w in blob for w in words), art))
    scored.sort(key=lambda item: (-item[0], item[1]))
    return [art for _, art in scored]


def section_c_dicts(article_ids: list[str], codes: Codes) -> list[dict]:
    rows = []
    for row in section_c_rows(article_ids, codes):
        pairs, seen = [], set()
        for pair in row.pairs:
            key = (pair.function, pair.objective, pair.application_note)
            if key in seen:
                continue
            seen.add(key)
            pairs.append({'function': pair.function, 'objective': pair.objective, 'condition': pair.application_note})
        item = {'provision_id': row.provision_id, 'division': 'B', 'citation': row.citation,
                'attribution_status': row.attribution_status, 'pairs': pairs}
        if row.explainer:
            item['explainer'] = row.explainer.model_dump()
        rows.append(item)
    return rows


def _codes_for(db, codes):
    if codes is not None:
        return codes
    if db is not None and Path(db).exists():
        try:
            return Codes(db)
        except (FileNotFoundError, CodeDbMissing):
            return None
    return None


def _benchmark(ranked, arts, prose, facts, codes, policy) -> dict:
    if not ranked or ranked[0][0] not in arts:
        return {
            'identified': False,
            'division': 'B',
            'role': 'benchmark_acceptable_solution',
            'explanation': 'No Division B article in the code database could be identified as the benchmark acceptable solution.',
            'question': 'Which Division B article should this proposal be measured against?',
            'quote': None,
            'citation': None,
            'section_c': [],
        }
    art, prob = ranked[0]
    row = arts[art]
    quote = short_quote(row.get('text'))
    fact_bits = []
    for fact in facts or []:
        data = fact.model_dump() if hasattr(fact, 'model_dump') else dict(fact)
        if data.get('status') == 'confirmed' and data.get('value') not in (None, ''):
            fact_bits.append(f"{data.get('field')}={data.get('value')}")
    tied = f" Confirmed facts used: {'; '.join(fact_bits[:6])}." if fact_bits else ' Tied to the proposal text as given.'
    citation = None
    section = []
    if codes is not None:
        try:
            citation = codes.citation(art, 'B')
        except Exception:
            citation = None
        try:
            section = section_c_dicts([art], codes)
        except Exception:
            section = []
    return {
        'identified': True,
        'provision': art,
        'division': 'B',
        'role': 'benchmark_acceptable_solution',
        'relation': 'measured_against',
        'explanation': (f'The proposal is measured against Division B Article {art} ({row.get("title") or "untitled"}), '
                        f'the benchmark acceptable solution.{tied}'),
        'quote': quote,
        'citation': citation,
        'confidence': {'probability': None if prob is None else round(prob, 4), 'calibration': policy['status']},
        'section_c': section,
    }


_COMPLIANCE = re.compile(r'\b(?:complies|compliant|compliance|safe)\b', re.I)


def overlay_ai_explainers(rows: list[dict], by_pick: dict) -> None:
    """Replace a deterministic explainer with the verifier's reason when its quote checked out.

    A reason that claims compliance is left off the row. The quote stays the codedb sentence.
    """
    for row in rows:
        match = _ARTICLE.search(row.get('provision_id') or '')
        pick = by_pick.get(match.group(1)) if match else None
        if pick is None:
            continue
        reason = (pick.reason or '').strip()
        if not reason or _COMPLIANCE.search(reason):
            continue
        existing = row.get('explainer') or {}
        quote = existing.get('quote') or short_quote(pick.quote, 240)
        if not quote:
            continue
        row['explainer'] = {'text': reason, 'quote': quote, 'source': 'ai_written'}


def _checked_verifier(verifier, prose, ranked_ids, arts):
    raw = verifier.verify(prose, ranked_ids)
    picks = getattr(raw, 'picks', raw) or []
    keep, dropped = check_quotes(list(picks), ranked_ids, arts)
    return keep, dropped


def run(prose: str, db_path: Path | str | None = None, judge: Judge | None = None, *, arts: dict | None = None,
        codes: Codes | None = None,         verifier=None, facts=None, on_stage=None, ranker: str | None = None,
        verify: bool = True, verify_chars: int | None = None) -> dict:
    policy = commit_policy()
    threshold = policy['threshold']
    max_commits = policy['max_commits']
    db = Path(db_path) if db_path else (None if arts is not None else default_db())
    if arts is None:
        if db is None or not Path(db).exists():
            raise CodeDbMissing()
        arts = articles(Path(db))
    codes = _codes_for(db, codes)
    trace: dict = {}
    usage = {'input_tokens': 0, 'output_tokens': 0, 'requests': 0}
    ranked: list[tuple[str, float | None]] = []
    mode = 'bm25_fallback'
    models = {'screen': None, 'rerank': None, 'verifier': None}

    def use_bm25(error: str | None, *, emit_screen: bool) -> None:
        nonlocal ranked, mode
        if emit_screen:
            _stage(on_stage, 'screen', {'method': 'bm25'})
        _stage(on_stage, 'rerank', {'method': 'bm25'})
        ranked = [(a, None) for a in _rank_bm25(prose, db, arts)[:RERANK_N]]
        trace.update(ranker='bm25 fallback')
        if error:
            trace['error'] = error[:300]
        mode = 'bm25_fallback'

    if judge is not None:
        _stage(on_stage, 'screen', {'method': 'jev'})
        try:
            ident = identify(prose, db, judge, rerank_n=RERANK_N)
            _stage(on_stage, 'rerank', {'method': 'jev'})
            ranked = [(a, p) for a, p in ident.ranked if a in arts]
            trace.update(ranker=f'jev screen+rerank ({ident.model})', usage=ident.usage)
            mode = 'jev'
            models['screen'] = models['rerank'] = ident.model
        except Exception as exc:
            use_bm25(f'{type(exc).__name__}: {exc}', emit_screen=False)
    elif ranker == 'bm25' or not has_live_model():
        use_bm25(None if ranker == 'bm25' else 'no model key; ranked with BM25 and suggested nothing', emit_screen=True)
    else:
        which = 'jev' if rerank_mode() == 'jev' and judge is None else provider()
        try:
            if which == 'jev':
                _stage(on_stage, 'screen', {'method': 'jev'})
                live = Judge(attempts=2)
                ident = identify(prose, db, live, rerank_n=RERANK_N)
                _stage(on_stage, 'rerank', {'method': 'jev'})
                ranked = [(a, p) for a, p in ident.ranked if a in arts]
                trace.update(ranker=f'jev screen+rerank ({ident.model})', usage=ident.usage)
                mode = 'jev'
                models['screen'] = models['rerank'] = ident.model
            else:
                from engine.identify import llm
                method = 'llm' if screen_mode() == 'llm' else 'bm25'
                _stage(on_stage, 'screen', {'method': method, 'model': SCREEN_MODEL if method == 'llm' else None})
                if method == 'llm':
                    screened = llm.score_candidates(prose, arts, list(arts), model=SCREEN_MODEL, usage=usage)
                    pool = [a for a, _ in screened][:RERANK_N] or _rank_bm25(prose, db, arts)[:RERANK_N]
                    models['screen'] = SCREEN_MODEL
                else:
                    pool = _rank_bm25(prose, db, arts)[:RERANK_N]
                _stage(on_stage, 'rerank', {'method': which, 'model': RERANK_MODEL})
                scored = llm.score_candidates(prose, arts, pool, model=RERANK_MODEL, usage=usage)
                scored_ids = {a for a, _ in scored}
                ranked = list(scored) + [(a, None) for a in pool if a not in scored_ids]
                trace.update(ranker=f'{which} rerank ({RERANK_MODEL})', usage=usage)
                mode = which
                models['rerank'] = RERANK_MODEL
        except Exception as exc:
            if is_provider_outage(exc):
                raise ProviderOutage(type(exc).__name__) from exc
            use_bm25(f'{type(exc).__name__}: {exc}', emit_screen=False)

    picks = None
    if verifier is not None:
        _stage(on_stage, 'verify', {'method': 'injected'})
        keep, dropped = _checked_verifier(verifier, prose, [a for a, _ in ranked], arts)
        picks = keep
        trace['verifier'] = {'picks': [p.article for p in keep], 'dropped': len(dropped)}
    elif mode == 'bm25_fallback' or not verify:
        _stage(on_stage, 'verify', {'skipped': True})
        if not verify and mode != 'bm25_fallback':
            trace['verifier'] = 'skipped: variant leaves the verifier off'
    elif mode == 'jev':
        _stage(on_stage, 'verify', {'method': 'anthropic'})
        if not os.environ.get('ANTHROPIC_API_KEY'):
            trace['verifier'] = 'skipped: ANTHROPIC_API_KEY not set'
        else:
            try:
                from engine.identify.verify import ClaudeVerifier
                checked = ClaudeVerifier(db).verify(prose, [a for a, _ in ranked][:VERIFY_N])
                picks = checked.picks
                trace['verifier'] = {'picks': [p.article for p in checked.picks], 'dropped': len(checked.dropped)}
                models['verifier'] = VERIFY_MODEL_ANTHROPIC
            except Exception as exc:
                if is_provider_outage(exc):
                    raise ProviderOutage(type(exc).__name__) from exc
                trace['verifier'] = f'failed: {type(exc).__name__}'
                picks = None
    else:
        _stage(on_stage, 'verify', {'method': mode})
        try:
            from engine.identify import llm
            vmodel = VERIFY_MODEL_OPENAI if mode == 'openai' else VERIFY_MODEL_ANTHROPIC
            checked = llm.verify_candidates(prose, arts, [a for a, _ in ranked][:VERIFY_N], model=vmodel,
                                            chars=verify_chars, usage=usage)
            picks = checked.picks
            trace['verifier'] = {'picks': [p.article for p in checked.picks], 'dropped': len(checked.dropped)}
            trace['usage'] = usage
            models['verifier'] = vmodel
        except Exception as exc:
            if is_provider_outage(exc):
                raise ProviderOutage(type(exc).__name__) from exc
            trace['verifier'] = f'failed: {type(exc).__name__}'
            picks = None

    if picks is not None:
        prob = dict(ranked)
        lead = [p.article for p in picks if p.article in arts]
        ranked = [(a, prob.get(a)) for a in lead] + [(a, p) for a, p in ranked if a not in lead]

    by_pick = {p.article: p for p in picks} if picks else {}
    out_articles, n_suggested = [], 0
    for art, prob in ranked[:TOP_K]:
        if art not in arts:
            continue
        # p >= threshold is a status hint only. The case citation waits for a user decision.
        suggested = (n_suggested < max_commits and prob is not None and prob >= threshold
                     and arts[art]['part'] in COMMIT_PARTS and (picks is None or art in by_pick))
        n_suggested += suggested
        pick: Pick | None = by_pick.get(art)
        quote = pick.quote if pick else short_quote(arts[art].get('text'))
        if quote and not pick:
            keep, _dropped = check_quotes([Pick(article=art, quote=quote, reason='codedb', confidence=1)], [art], arts)
            if not keep:
                quote = None
        out_articles.append({
            'provision': art, 'division': 'B', 'suggested': suggested,
            'title': arts[art]['title'], 'part': arts[art]['part'],
            'probability': None if prob is None else round(prob, 4),
            'confidence': {'probability': None if prob is None else round(prob, 4), 'calibration': policy['status']},
            'quote': quote,
            'reason': pick.reason if pick else f'The proposal is compared with "{arts[art]["title"]}" (Division B Article {art}).',
            'stage': 'verify' if pick else ('bm25' if mode == 'bm25_fallback' else 'rerank'),
        })

    redirect = detect_redirect(prose)
    if redirect:
        for art in out_articles:
            art['suggested'] = False
        n_suggested = 0
    suggested_ids = [a['provision'] for a in out_articles if a['suggested']]
    rows = section_c_dicts(suggested_ids, codes) if suggested_ids and codes is not None else []
    questions = generate_questions(prose, [
        {'provision': a['provision'], 'title': a['title'], 'text': arts[a['provision']].get('text', ''), 'part': a['part']}
        for a in out_articles
    ], facts)
    variance, explanation = assess_variance(prose, facts)
    if redirect:
        intake = 'redirect'
    elif suggested_ids:
        intake = 'proceed_conditionally'
    else:
        intake = 'ask'
    trace.setdefault('usage', usage)
    benchmark = _benchmark(ranked, arts, prose, facts, codes, policy)
    if by_pick:
        overlay_ai_explainers(rows, by_pick)
        overlay_ai_explainers(benchmark.get('section_c') or [], by_pick)
    result = {
        'articles': out_articles,
        'section_c': rows,
        'benchmark': benchmark,
        'engineering_required': 'depends',
        'intake_action': intake,
        'redirect_to': redirect,
        'variance_needed': variance,
        'variance_explanation': explanation,
        'questions': [q['text'] for q in questions],
        'open_questions': questions,
        'mode': mode,
        'persisted': False,
        'cached': False,
        'source': 'live',
        'model_ids': models,
        'commit_policy': policy,
        'trace': {**trace, 'commit_threshold': threshold, 'max_commits': max_commits,
                  'commit_parts': sorted(COMMIT_PARTS), 'commit_policy': policy,
                  'ranked_ids': [a for a, _ in ranked]},
    }
    _stage(on_stage, 'questions', {'questions': result['questions'], 'open_questions': questions})
    _stage(on_stage, 'done', result)
    return result
