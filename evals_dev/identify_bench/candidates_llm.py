"""LLM candidate generation for code identification (benchmark unit w2, never imported by the app).

Two cheap, high-recall generators for the low-request design (candidates -> Elephant scores a
small pool -> Luna verifies):

  toc   one gpt-6-luna call that reads the whole Division B table of contents (2,080 article ids
        and titles under their part/section/subsection headings, about 30k tokens) and returns a
        recall-first ranked list of ids with a role and a short reason.
  hyde  one gpt-6-luna call that splits the proposal into code-facing facets and writes a short
        hypothetical code-requirement passage per facet; each passage is retrieved with the
        shipped V3 search (and BM25), and the lists are fused by reciprocal rank fusion.

Every id the model returns is checked against the code database; unknown ids are dropped and
counted (the hallucination rate is a reported metric).

  .venv/bin/python -m evals_dev.identify_bench.candidates_llm toc --effort medium --picks 40
  .venv/bin/python -m evals_dev.identify_bench.candidates_llm report      # tune grid + test, writes results/
"""
from __future__ import annotations

import argparse
import json
import re
import sqlite3
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from functools import lru_cache
from pathlib import Path

from . import cases as bench_cases
from . import live, metrics

ROOT = Path(__file__).resolve().parents[2]
DB = ROOT / 'codedb' / 'build' / 'codedb.sqlite'
RESULTS = Path(__file__).resolve().parent / 'results'
MODEL = 'gpt-6-luna'
ROLES = ('departs_from', 'must_meet', 'scope', 'related')
_ID = re.compile(r'^\d+\.\d+\.\d+\.\d+\.$')

# Division B part headings (the database stores no part rows).
PART_TITLES = {
    1: 'General', 3: 'Fire Protection, Occupant Safety and Accessibility', 4: 'Structural Design',
    5: 'Environmental Separation', 6: 'Heating, Ventilating and Air-conditioning', 7: 'Plumbing Services',
    8: 'Safety Measures at Construction and Demolition Sites', 9: 'Housing and Small Buildings',
    10: 'Change of Use', 11: 'Renovation',
}


# ---------------------------------------------------------------- table of contents

def _key(pid: str) -> tuple[int, ...]:
    return tuple(int(n) for n in pid.strip('.').split('.'))


@lru_cache(maxsize=2)
def _rows(db: Path = DB) -> tuple[dict, ...]:
    con = sqlite3.connect(f'file:{db}?mode=ro', uri=True)
    try:
        rows = con.execute("select id, level, part, section, subsection, title from provisions where doc='NBC-AE' "
                           "and division='B' and level in ('section','subsection','article')").fetchall()
    finally:
        con.close()
    return tuple(dict(id=r[0], level=r[1], part=r[2], section=r[3], subsection=r[4], title=(r[5] or '').strip())
                 for r in rows)


@lru_cache(maxsize=2)
def article_ids(db: Path = DB) -> frozenset[str]:
    return frozenset(r['id'] for r in _rows(db) if r['level'] == 'article')


def toc_tree(db: Path = DB) -> dict:
    """{part: {section id: {'title', 'subsections': {subsection id: {'title', 'articles': [(id, title)]}}}}}.

    Built explicitly from each article's section/subsection columns, because sort_key order lists
    subsections before their section row."""
    rows = _rows(db)
    titles = {r['id']: r['title'] for r in rows if r['level'] != 'article'}
    tree: dict = {}
    for r in sorted((r for r in rows if r['level'] == 'article'), key=lambda r: _key(r['id'])):
        sec = r['section'] or '.'.join(r['id'].split('.')[:2]) + '.'
        sub = r['subsection'] or '.'.join(r['id'].split('.')[:3]) + '.'
        part = int(r['part'] or _key(r['id'])[0])
        s = tree.setdefault(part, {}).setdefault(sec, {'title': titles.get(sec, ''), 'subsections': {}})
        s['subsections'].setdefault(sub, {'title': titles.get(sub, ''), 'articles': []})['articles'].append(
            (r['id'], r['title']))
    return {p: dict(sorted(secs.items(), key=lambda kv: _key(kv[0]))) for p, secs in sorted(tree.items())}


def toc_text(parts=None, db: Path = DB) -> str:
    """Compact Division B table of contents: ## part / ### section / #### subsection / article lines."""
    lines = []
    for part, sections in toc_tree(db).items():
        if parts is not None and part not in parts:
            continue
        lines.append(f'## Part {part} {PART_TITLES.get(part, "")}'.rstrip())
        for sid, s in sections.items():
            lines.append(f'### {sid} {s["title"]}'.rstrip())
            for subid, sub in sorted(s['subsections'].items(), key=lambda kv: _key(kv[0])):
                lines.append(f'#### {subid} {sub["title"]}'.rstrip())
                lines.extend(f'{aid} {title}'.rstrip() for aid, title in sub['articles'])
    return '\n'.join(lines)


# ---------------------------------------------------------------- validation

def validate_ids(ids, db: Path = DB) -> tuple[list[str], list[str]]:
    """(valid unique ids in order, invalid ids). Accepts ids missing the trailing dot."""
    known, valid, invalid = article_ids(db), [], []
    for raw in ids:
        pid = (raw or '').strip()
        if pid and not pid.endswith('.'):
            pid += '.'
        if _ID.match(pid) and pid in known:
            if pid not in valid:
                valid.append(pid)
        else:
            invalid.append(raw)
    return valid, invalid


# ---------------------------------------------------------------- toc screen

TOC_SCHEMA = {
    'type': 'object', 'additionalProperties': False, 'required': ['articles'],
    'properties': {'articles': {'type': 'array', 'items': {
        'type': 'object', 'additionalProperties': False, 'required': ['id', 'role', 'reason'],
        'properties': {'id': {'type': 'string'}, 'role': {'type': 'string', 'enum': list(ROLES)},
                       'reason': {'type': 'string'}}}}},
}


def toc_system(db: Path = DB) -> str:
    return (
        'You screen the National Building Code - 2023 Alberta Edition (2nd printing), Division B, for an '
        'alternative-solution (variance) application in Alberta. You never judge whether the design complies, '
        'is safe, or will be accepted; you only list the code articles the application must cite or address.\n\n'
        'The list is RECALL-FIRST: missing an article the applicant must cite is the costly failure, an extra '
        'article is cheap. Include every Division B article a complete application would need to cite or '
        'address: the article(s) the proposal departs from (departs_from), articles the alternative must still '
        'meet or that the departure triggers (must_meet), articles that set scope or applicability such as '
        'building classification, application of a Part, or definitions-driven limits (scope), and closely '
        'related articles a reviewer would expect to see considered (related).\n\n'
        'Read every title in the table of contents below. Choose ids ONLY from it, copied exactly (with the '
        'trailing dot). Never invent or guess an id. Rank the most certain departs_from articles first, then by '
        'how likely the application must cite each one. Reasons are at most 12 words.\n\n'
        'TABLE OF CONTENTS (Division B)\n' + toc_text(db=db))


def luna_toc(description: str, *, effort: str = 'medium', picks: int = 40, tag: str = 'w2-toc',
             live_calls: bool = True) -> dict:
    """{'ranked', 'roles', 'reasons', 'invalid', 'usage'} from one Luna read of the whole TOC."""
    user = (f'Proposal:\n{description.strip()}\n\nReturn up to {picks} articles (aim for about {picks}; fewer only '
            'if nothing else could plausibly need citing), ranked.')
    payload, usage = live.openai_json('toc_screen', TOC_SCHEMA, toc_system(), user, model=MODEL, effort=effort,
                                      max_output_tokens=24000 if effort in ('high', 'xhigh') else 16000,
                                      tag=tag, live=live_calls)
    return parse_toc(payload, usage)


def parse_toc(payload: dict, usage: dict | None = None) -> dict:
    items = payload.get('articles') or []
    ranked, invalid = validate_ids([i.get('id') for i in items])
    roles, reasons = {}, {}
    for i in items:
        valid, _ = validate_ids([i.get('id')])
        if valid and valid[0] not in roles:
            roles[valid[0]] = i.get('role') if i.get('role') in ROLES else 'related'
            reasons[valid[0]] = (i.get('reason') or '')[:200]
    return {'ranked': ranked, 'roles': roles, 'reasons': reasons, 'invalid': invalid, 'returned': len(items),
            'usage': usage or {}}


# ---------------------------------------------------------------- hyde facets

HYDE_SCHEMA = {
    'type': 'object', 'additionalProperties': False, 'required': ['facets'],
    'properties': {'facets': {'type': 'array', 'items': {
        'type': 'object', 'additionalProperties': False, 'required': ['facet', 'search_terms', 'passage'],
        'properties': {'facet': {'type': 'string'}, 'search_terms': {'type': 'string'},
                       'passage': {'type': 'string'}}}}},
}

HYDE_SYSTEM = (
    'You help find which National Building Code - 2023 Alberta Edition, Division B, requirements an '
    'alternative-solution (variance) proposal touches. Do not judge compliance. Decompose the proposal into '
    'between 3 and 8 distinct code-facing facets (each a separate regulated topic: e.g. spatial separation, '
    'fire-resistance rating, egress, guards, structural loads, ventilation, plumbing, energy, scope or '
    'classification). For each facet give: a short facet name; search_terms, 4 to 10 code vocabulary keywords '
    '(the words the code itself would use); and passage, 2 to 3 sentences written the way the code requirement '
    'itself would read (hypothetical wording, no article numbers). Be recall-first: include facets for '
    'requirements the departure triggers or that set scope, not only the one varied.')


def luna_facets(description: str, *, effort: str = 'low', tag: str = 'w2-hyde', live_calls: bool = True):
    payload, usage = live.openai_json('hyde_facets', HYDE_SCHEMA, HYDE_SYSTEM, f'Proposal:\n{description.strip()}',
                                      model=MODEL, effort=effort, max_output_tokens=8000, tag=tag, live=live_calls)
    return payload.get('facets') or [], usage


def rrf(lists, k: int = 60, limit: int | None = None) -> list[str]:
    score: dict[str, float] = {}
    for ranked in lists:
        for r, pid in enumerate(ranked, 1):
            score[pid] = score.get(pid, 0.0) + 1 / (k + r)
    out = sorted(score, key=lambda p: -score[p])
    return out[:limit] if limit else out


@lru_cache(maxsize=4096)
def _retrieve(query: str, per: int) -> tuple[tuple[str, ...], tuple[str, ...]]:
    from engine.identify.corpus import bm25_rank
    from engine.identify.search_rank import rank_articles
    v3 = tuple(rank_articles(query, DB, limit=per))
    bm = tuple(bm25_rank(query, DB, limit=3000)[:per])
    return v3, bm


def luna_hyde(description: str, *, effort: str = 'low', per: int = 40, limit: int = 200, tag: str = 'w2-hyde',
              live_calls: bool = True) -> dict:
    """Facet passages -> V3 search + BM25 per facet (terms and passage) -> RRF. Ranked, validated ids."""
    facets, usage = luna_facets(description, effort=effort, tag=tag, live_calls=live_calls)
    lists = []
    for f in facets:
        for q in (f.get('search_terms') or '', f.get('passage') or '', f'{f.get("facet", "")} {f.get("search_terms", "")}'):
            if q.strip():
                lists.extend(_retrieve(q.strip(), per))
    ranked, invalid = validate_ids(rrf(lists, limit=limit))
    return {'ranked': ranked, 'facets': facets, 'invalid': invalid, 'usage': usage}


def interleave(*lists) -> list[str]:
    """Round-robin union preserving each list's order (used for toc ∪ hyde)."""
    out, seen = [], set()
    for i in range(max((len(x) for x in lists), default=0)):
        for x in lists:
            if i < len(x) and x[i] not in seen:
                seen.add(x[i])
                out.append(x[i])
    return out


# ---------------------------------------------------------------- evaluation

def my_spend(prefix: str = 'w2-') -> float:
    _, _, spend = live._stores()
    return round(sum(r['response']['usd'] for r in spend.rows() if str(r['response'].get('tag', '')).startswith(prefix)), 6)


def run_arm(arm: str, cases, *, effort: str, picks: int = 40, workers: int = 6, live_calls: bool = True) -> dict:
    def one(c):
        t0 = time.monotonic()
        try:
            if arm == 'toc':
                r = luna_toc(c.description, effort=effort, picks=picks, tag=f'w2-toc-{effort}-{picks}',
                             live_calls=live_calls)
            else:
                r = luna_hyde(c.description, effort=effort, tag=f'w2-hyde-{effort}', live_calls=live_calls)
            r['error'] = None
        except Exception as error:          # counted, never silently dropped
            r = {'ranked': [], 'invalid': [], 'usage': {}, 'error': f'{type(error).__name__}: {error}'[:300]}
        r['wall'] = round(time.monotonic() - t0, 2)
        return c, r

    with ThreadPoolExecutor(workers) as pool:
        out = dict((c.id, r) for c, r in pool.map(one, cases))
    return out


def summarize(arm_name: str, cases, results: dict) -> dict:
    rows = [(results[c.id]['ranked'], c.gold) for c in cases]
    s = metrics.ranking_summary(rows)
    usages = [results[c.id].get('usage') or {} for c in cases]
    returned = sum(results[c.id].get('returned', len(results[c.id]['ranked']) + len(results[c.id]['invalid']))
                   for c in cases)
    invalid = sum(len(results[c.id]['invalid']) for c in cases)
    n = len(cases)
    s.update({
        'arm': arm_name, 'errors': sum(1 for c in cases if results[c.id].get('error')),
        'empty_lists': sum(1 for c in cases if not results[c.id]['ranked']),
        'returned_ids': returned, 'invalid_ids': invalid,
        'invalid_rate': round(invalid / returned, 4) if returned else None,
        'usd_per_case': round(sum(u.get('usd') or 0 for u in usages) / n, 5) if n else None,
        'input_tokens_per_case': round(sum(u.get('input_tokens') or 0 for u in usages) / n) if n else None,
        'output_tokens_per_case': round(sum(u.get('output_tokens') or 0 for u in usages) / n) if n else None,
        'api_seconds_median': _median([u.get('seconds') for u in usages if u.get('seconds')]),
        'misses': {c.id: sorted(set(c.gold) - set(results[c.id]['ranked'])) for c in cases
                   if not set(c.gold) <= set(results[c.id]['ranked'])},
        'misses_at_40': {c.id: sorted(set(c.gold) - set(results[c.id]['ranked'][:40])) for c in cases
                         if not set(c.gold) <= set(results[c.id]['ranked'][:40])},
    })
    return s


# Arms evaluated on tune (cached; `report` replays them without new calls). RECOMMENDED also ran on test.
TUNE_ARMS = [('toc', 'medium', 40), ('toc', 'medium', 80), ('toc', 'high', 40), ('hyde', 'low', 0)]
RECOMMENDED = ('toc', 'medium', 40)
UNIONS = [(('toc', 'medium', 40), ('hyde', 'low', 0))]
MAIN_SOURCES = ('dev', 'precedent')
UNIT_CAP_USD = 2.50
GUARD_USD = 2.46           # stop new live calls here (parallel calls may each add ~$0.012)


def _name(arm) -> str:
    kind, effort, picks = arm
    return f'{kind}@{effort}' + (f'/{picks}' if kind == 'toc' else '')


def _evaluate(arm, cs, live_calls, workers: int = 6):
    kind, effort, picks = arm
    return run_arm(kind, cs, effort=effort, picks=picks or 40, live_calls=live_calls, workers=workers)


def _cached_only(arm, cs):
    """The cases whose call for this arm is already cached (no spend), and their results."""
    res = _evaluate(arm, cs, live_calls=False)
    kept = [c for c in cs if not res[c.id].get('error')]
    return kept, res


def report() -> int:
    allc = bench_cases.all_cases()
    tune = bench_cases.select(allc, fold='tune', sources=MAIN_SOURCES)
    test_all = bench_cases.select(allc, fold='test', sources=MAIN_SOURCES)
    out = {'model': MODEL, 'sources': list(MAIN_SOURCES), 'tune_cases': len(tune), 'test_cases_fold': len(test_all),
           'tune': {}, 'tune_web': {}, 'test': {}, 'recommended': _name(RECOMMENDED), 'notes': []}
    raw = {}
    for arm in TUNE_ARMS:
        raw[arm] = _evaluate(arm, tune, live_calls=False)
        out['tune'][_name(arm)] = summarize(_name(arm), tune, raw[arm])
    for a, b in UNIONS:
        merged = {c.id: {'ranked': interleave(raw[a][c.id]['ranked'], raw[b][c.id]['ranked']), 'invalid': [],
                         'returned': 0, 'usage': {'usd': (raw[a][c.id]['usage'].get('usd') or 0)
                                                  + (raw[b][c.id]['usage'].get('usd') or 0)}} for c in tune}
        name = f'{_name(a)} ∪ {_name(b)} (interleaved)'
        out['tune'][name] = summarize(name, tune, merged)
        for k in ('returned_ids', 'invalid_ids', 'invalid_rate', 'input_tokens_per_case', 'output_tokens_per_case',
                  'api_seconds_median'):
            out['tune'][name].pop(k, None)
    # Web sources: no budget for a fresh arm; report whatever is already cached (toc@high on the web-ab cases
    # that existed when that arm ran). Not the recommended setting.
    web = bench_cases.select(allc, fold='tune', sources=('web-ab', 'web-ca'))
    for arm in (RECOMMENDED, ('toc', 'high', 40)):
        kept, res = _cached_only(arm, web)
        if kept:
            out['tune_web'][f'{_name(arm)} (cached web cases only)'] = summarize(_name(arm), kept, res)
    # Test once, recommended setting. Budget allows only a fixed every-other subset of the fold.
    test = test_all[::2]
    out['test_cases'] = len(test)
    out['notes'].append(f'test = every other case of the {len(test_all)}-case dev+precedent test fold '
                        f'({len(test)} cases), to stay inside the unit cap of ${UNIT_CAP_USD}')
    # Rebuilding a report must never dispatch a paid request or discard cache misses.
    res = _evaluate(RECOMMENDED, test, live_calls=False)
    out['test_cases'] = len(test)
    out['test'][_name(RECOMMENDED)] = summarize(_name(RECOMMENDED), test, res)
    out['spend_w2_total_usd'] = my_spend()
    RESULTS.mkdir(exist_ok=True)
    (RESULTS / 'llm_candidates.json').write_text(json.dumps(out, indent=1, ensure_ascii=False) + '\n')
    (RESULTS / 'llm_candidates.md').write_text(_markdown(out))
    print(_markdown(out))
    return 0


def _markdown(out) -> str:
    cols = ['complete@10', 'complete@20', 'complete@40', 'complete@60', 'complete@all', 'recall@40', 'recall@all',
            'mean_list', 'mrr', 'invalid_rate', 'errors', 'usd_per_case', 'api_seconds_median']
    lines = ['# LLM candidate generation (gpt-6-luna) — benchmark unit w2', '',
             f"Model {out['model']}, sources {', '.join(out['sources'])}. Tune {out['tune_cases']} cases; test "
             f"{out['test_cases']} cases (run once, recommended setting only). Headline: per-case complete recall. One "
             f"Luna call per case per arm; every returned id validated against codedb. w2 spend total "
             f"${out['spend_w2_total_usd']:.3f}.", ''] + [f'- {n}' for n in out['notes']] + ['']
    for fold in ('tune', 'tune_web', 'test'):
        if not out[fold]:
            continue
        lines += [f'## {fold}', '', '| arm | ' + ' | '.join(cols) + ' |', '|' + '---|' * (len(cols) + 1)]
        for name, s in out[fold].items():
            lines.append(f'| {name} | ' + ' | '.join('' if s.get(c) is None else str(s.get(c)) for c in cols) + ' |')
        lines.append('')
        for name, s in out[fold].items():
            if s['misses']:
                lines.append(f'**{fold} misses, {name}** ({len(s["misses"])} cases): ' + '; '.join(
                    f'{cid}: {", ".join(g)}' for cid, g in s['misses'].items()))
                lines.append('')
    lines.append(f"Recommended: **{out['recommended']}**.")
    return '\n'.join(lines) + '\n'


def _median(xs):
    xs = sorted(x for x in xs if x is not None)
    return xs[len(xs) // 2] if xs else None


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('arm', choices=['toc', 'hyde', 'toc-print', 'report'])
    ap.add_argument('--effort', default='medium')
    ap.add_argument('--picks', type=int, default=40)
    ap.add_argument('--fold', default='tune')
    ap.add_argument('--limit', type=int)
    ap.add_argument('--live', action='store_true', help='allow provider calls for toc/hyde; reports stay offline')
    a = ap.parse_args(argv)
    if a.arm == 'toc-print':
        print(toc_text())
        return 0
    if a.arm == 'report':
        saved = RESULTS / 'llm_candidates.json'
        if not saved.is_file():
            print('No saved LLM candidate report; use candidate_audit for cache-only replay.', file=sys.stderr)
            return 2
        print(_markdown(json.loads(saved.read_text())))
        return 0
    cs = bench_cases.select(bench_cases.all_cases(), fold=a.fold, limit=a.limit)
    before = my_spend()
    with live.live_mode(a.live):
        res = run_arm(a.arm, cs, effort=a.effort, picks=a.picks, live_calls=a.live)
    s = summarize(f'{a.arm}@{a.effort}/{a.picks}', cs, res)
    s['spend_this_run'] = round(my_spend() - before, 4)
    print(json.dumps({k: v for k, v in s.items() if not k.startswith('misses')}, indent=1))
    print('misses:', json.dumps(s['misses']))
    return int(bool(s['errors']))


if __name__ == '__main__':
    sys.exit(main())
