"""Deterministic precompute per case: the product's own intake plan, path, and code ranking. No model calls."""
from __future__ import annotations

import sys
import time

from common import RUNS, DB, article_map, codes, load_cases, write_json

from engine.identify.config import load_config
from engine.identify.corpus import bm25_rank
from engine.identify.pipeline import run as identify
from engine.intake import service
from engine.intake.plan import build_plan
from engine.models import Case
from engine.path_decision import decide_path

POOL = 60


def precompute(case: dict, config) -> dict:
    desc = case['description']
    t = time.monotonic()
    shell = Case()
    extraction = service.run(desc, [], codes=codes())
    service.apply(shell, desc, extraction)
    plan = build_plan(shell)
    path = decide_path(shell)
    ranked = [a.provision for a in identify(desc, codes=codes(), config=config).result.articles]
    arts = article_map()
    bm25 = [a for a in bm25_rank(desc, DB) if a in arts][:30]
    pool = list(dict.fromkeys(ranked[:45] + bm25[:20]))[:POOL]
    return {
        'id': case['id'], 'type': case['type'], 'gold': case['gold'], 'gold_path': case['gold_path'],
        'facts_read': sorted({f.field for f in shell.facts}),
        'scope': plan.scope.status,
        'fork': plan.fork.variance_needed,
        'planner': [{'id': q.id, 'field': q.field, 'text': q.text, 'priority': q.priority} for q in plan.questions],
        'path': {'path': path.path, 'source': path.source, 'rule_id': path.rule_id, 'article': path.article,
                 'missing': list(path.missing)},
        'prod_rank': ranked[:60],
        'bm25_rank': bm25,
        'pool': pool,
        'seconds': round(time.monotonic() - t, 2),
    }


def main(argv: list[str]) -> None:
    config = load_config()
    only = set(argv)
    for case in load_cases():
        if only and case['id'] not in only:
            continue
        out = RUNS / 'stage0' / f"{case['id']}.json"
        if out.exists():
            continue
        row = precompute(case, config)
        write_json(out, row)
        first = next((i + 1 for i, a in enumerate(row['prod_rank']) if a in case['gold']), None)
        in_pool = sum(g in row['pool'] for g in case['gold'])
        print(case['id'], row['path']['path'], row['path']['source'], 'planner', len(row['planner']),
              'first_gold', first, 'pool', f"{in_pool}/{len(case['gold'])}", flush=True)


if __name__ == '__main__':
    main(sys.argv[1:])
