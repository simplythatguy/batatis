"""Replay development-only candidate experiments. Every model request is cache-only.

This intentionally does not select held-out cases or fit applicability thresholds.
The generated facets are lexical query expansion, not a dense HyDE reproduction.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from engine.identify.corpus import bm25_rank

from . import candidates_lexical as lex, candidates_llm as llm, metrics
from .cases import all_cases, select

RESULTS = Path(__file__).resolve().parent / 'results'


def experiments(case, suite: str) -> dict[str, list[str]]:
    toc = llm.luna_toc(case.description, effort='medium', picks=40, live_calls=False)['ranked']
    bm = bm25_rank(case.description, llm.DB)
    if suite == 'basic':
        wide = llm.luna_toc(case.description, effort='medium', picks=80, live_calls=False)['ranked']
        high = llm.luna_toc(case.description, effort='high', picks=40, live_calls=False)['ranked']
        return {'toc-medium-40': toc, 'toc-medium-80': wide, 'toc-high-40': high,
                'bm25-60': bm[:60], 'toc40-bm25-60': llm.interleave(toc, bm[:40])[:60],
                'toc80-bm25-100': llm.interleave(wide, bm[:60])[:100]}
    if suite == 'graph':
        graph, out = lex.build_graph(), {}
        for seeds in (5, 8):
            for mode in ('out', 'both'):
                for siblings in (0, 3):
                    grown = lex.pool(bm, 60, seeds=seeds, mode=mode, sibling_top=siblings, g=graph)
                    for cap in (60, 80):
                        out[f'toc40+bm25-{mode}{seeds}-sib{siblings}-pool{cap}'] = llm.interleave(toc, grown)[:cap]
        for seeds in (3, 5, 8):
            for mode in ('out', 'both'):
                grown = lex.expand(toc[:seeds], 1, mode, g=graph)[seeds:]
                for cap in (60, 80, 100):
                    out[f'toc40-ref{mode}{seeds}-pool{cap}'] = list(dict.fromkeys(
                        toc + llm.interleave(grown, bm[:40])))[:cap]
        return out
    wide = llm.luna_toc(case.description, effort='medium', picks=80, live_calls=False)['ranked']
    high = llm.luna_toc(case.description, effort='high', picks=40, live_calls=False)['ranked']
    facets, _ = llm.luna_facets(case.description, effort='low', live_calls=False)
    rankings = [bm[:60]]
    for facet in facets:
        for query in (facet.get('search_terms', ''), facet.get('passage', '')):
            if query.strip():
                rankings.append(bm25_rank(query, llm.DB)[:60])
    expanded = llm.rrf(rankings)
    combinations = {'toc40+toc80': llm.interleave(toc, wide),
                    'toc40+toc-high': llm.interleave(toc, high),
                    'toc40+facets': llm.interleave(toc, expanded),
                    'toc2+facets': llm.interleave(toc, wide, expanded),
                    'toc3+facets': llm.interleave(toc, wide, high, expanded)}
    return {f'{name}-cap{cap}': ranking[:cap]
            for name, ranking in combinations.items() for cap in (60, 80, 100)}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--suite', choices=('basic', 'graph', 'ensemble'), default='basic')
    args = parser.parse_args(argv)
    cases = select(all_cases(), fold='tune', sources=('dev', 'precedent'))
    records, errors = [], []
    for case in cases:
        try:
            ranking = experiments(case, args.suite)
        except Exception as error:
            errors.append({'case': case.id, 'category': type(error).__name__})
            ranking = {}
        records.append({'case': case.id, 'gold': list(case.gold), 'ranked': ranking})
    arms = sorted({name for record in records for name in record['ranked']})
    summary = {name: metrics.ranking_summary(
        [(r['ranked'].get(name, []), r['gold']) for r in records], ks=(10, 20, 40, 60, 80, 100)) for name in arms}
    document = {'scope': 'Development fold only; cached model requests, no gold insertion or threshold fit.',
                'suite': args.suite, 'attempted': len(cases), 'errors': errors,
                'corpus_sha256': hashlib.sha256(llm.DB.read_bytes()).hexdigest(),
                'summary': summary, 'records': records}
    filename = {'basic': 'cached_candidate_audit_tune.json', 'graph': 'fast_graph_candidate_tune.json',
                'ensemble': 'cached_ensemble_candidates_tune.json'}[args.suite]
    RESULTS.mkdir(exist_ok=True)
    (RESULTS / filename).write_text(json.dumps(document, indent=1) + '\n')
    for name, result in sorted(summary.items(), key=lambda row: (-(row[1]['complete@all'] or 0), row[1]['mean_list'])):
        print(name, result['complete@all'], result['recall@all'], result['mean_list'])
    print('attempted', len(cases), 'errors', len(errors))
    return int(bool(errors))


if __name__ == '__main__':
    raise SystemExit(main())
