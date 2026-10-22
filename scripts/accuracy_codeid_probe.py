"""Read the code identification benchmark rows with the harness's own report code and print plain JSON.

Run by `scripts/accuracy_report.py` as a separate process whose working directory is the benchmark tree (this
checkout once the benchmark is merged, or an extracted copy of the benchmark branch before that):

    python scripts/accuracy_codeid_probe.py <bench root>

Nothing is run against a provider and nothing is written. Only stored rows, the frozen datasets and the decision rule
of `evals_dev/identify_bench` are used. The judge-only set and the test split are never read: `analyse()` loads the
public53, dev and idr26 datasets only.

The output keeps the harness's internal arm names. The report builder maps them to neutral labels before anything
reaches a page.
"""
from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path


def main(root: str) -> int:
    sys.path.insert(0, root)
    from evals_dev.accuracy.gates import evaluate_g1
    from evals_dev.identify_bench import decision as rule
    from evals_dev.identify_bench.analysis import SELECTION, analyse, chain_of, mrr_by_repeat, top1_by_part

    arts = None
    try:                                                   # the integrity recheck needs the code database
        from engine.identify.corpus import articles
        from evals_dev.identify_bench.live import db_path
        arts = articles(db_path())
    except Exception:                                      # noqa: BLE001 - reported as not rechecked
        arts = None
    an = analyse(arts=arts)

    def rate(r):
        return None if not r or not r.get('n') else {'x': r['x'], 'n': r['n'], 'rate': r['rate'],
                                                     'wilson_95': list(r['wilson_95'])}

    def arm_eval(e):
        return {'cases': e.n_cases, 'repeats': e.repeats, 'missing_rows': e.missing_rows, 'success': rate(e.sr),
                'by_group': {g: rate(v) for g, v in e.sr_by_group.items()},
                'by_repeat': e.by_repeat_sr,
                'ranking': {k: v for k, v in e.ranking.items() if k in ('mrr', 'hit@1', 'hit@3', 'hit@5', 'hit@10')},
                'top1_agreement': e.top1_agreement, 'usd_per_case_run': e.cost['usd_per_case_run'],
                'errors': {k: e.errors[k] for k in ('rows', 'rows_with_errors', 'rows_retried')},
                'fabricated_citations_shown': (e.verifier or {}).get('fabricated_citations_shown'),
                'quote_match_before_filtering': (e.verifier or {}).get('quote_match_rate_before_filtering')}

    gold_sel = [c for c in an.cases if c.fold in SELECTION and c.gold]
    pub = [c for c in an.cases if c.dataset == 'public53']
    gold = [c for c in an.cases if c.gold]
    d = an.decision
    live = [r for rows in an.L.by_key.values() for r in rows.values() if r['source'] == 'live']
    out = {
        'cases': {'total': len(an.cases), 'by_dataset': dict(Counter(c.dataset for c in an.cases)),
                  'selection_gold': len(gold_sel), 'selection_by_group': dict(Counter(c.part_group for c in gold_sel)),
                  'development_gold': sum(1 for c in an.cases if c.fold in ('calibration', 'validation') and c.gold),
                  'public53': len(pub)},
        'selection': {n: arm_eval(e) for n, e in an.selection.items()},
        'development': {n: arm_eval(e) for n, e in an.development.items()},
        'public53': {n: arm_eval(e) for n, e in an.public.items()},
        'kinds': {n: a.kind for n, a in an.arms.items()},
        'chains': {n: chain_of(an.arms, n) for n in an.selection},
        'latency': {n: v for n, v in an.latency.items()},
        'stage_latency': {n: v for n, v in an.stage_latency.items()},
        'g1': [{'id': c.id, 'status': c.status} for c in evaluate_g1(an)],
        'rerank_mrr_public53': mrr_by_repeat(an.L, 'R5-jev-screen-rerank60', pub) if 'R5-jev-screen-rerank60' in an.selection else None,
        'top1_by_part': {n: top1_by_part(an.L, n, gold) for n in an.selection if an.arms[n].kind == 'verify'},
        'decision': None if d is None else {
            'best': d.best, 'winner': d.winner, 'provisional': d.provisional,
            'rows': [{'arm': r.arm, 'tied': r.tied, 'p_worse': r.p_worse, 'cluster_ci': r.cluster_ci, 'complete': r.complete,
                      'filters': r.filters, 'robust': r.robust, 'usd': r.usd,
                      'notes': r.notes} for r in d.rows],
            'agreement_min': rule.AGREEMENT_MIN, 'tie_alpha': rule.TIE_ALPHA, 'tie_points': rule.TIE_POINTS},
        'rows': {'live': len(live), 'first': min((r['started_at'] for r in live), default=None),
                 'last': max((r['started_at'] for r in live), default=None)},
        'row_files': an.row_files,
        'integrity_rechecked': arts is not None,
    }
    json.dump(out, sys.stdout, sort_keys=True, default=str)
    return 0


if __name__ == '__main__':
    raise SystemExit(main(str(Path(sys.argv[1]).resolve())))
