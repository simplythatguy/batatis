"""Score search variants on the frozen query split.

Numbers are model-checked, not human-verified. Pass --split in-sample to hide
held-out rows while a variant is still being compared.
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from codedb.search_rank import SHIPPED, article_of, covers, search_variant

HERE = Path(__file__).resolve().parent
QUERIES = HERE / 'queries.json'
VARIANTS = ('v0', 'v1', 'v2', 'v3')


def load() -> list[dict]:
    return json.loads(QUERIES.read_text())['queries']


def ranks(query: str, variant: str, limit: int = 20) -> list[dict]:
    return search_variant(query, variant, division='B', limit=limit)


def provision_hit(ids: list[str], gold: str) -> int | None:
    for index, provision in enumerate(ids):
        if covers(provision, gold):
            return index
    return None


def article_hit(ids: list[str], article: str) -> int | None:
    for index, provision in enumerate(ids):
        if article_of(provision) == article or covers(provision, article):
            return index
    return None


def score_query(query: dict, ids: list[str]) -> dict:
    if query.get('gold_level') == 'article' and query.get('gold_articles'):
        gold = query['gold_articles']
        found = [article_hit(ids, article) for article in gold]
    else:
        gold = query.get('gold') or []
        found = [provision_hit(ids, provision) for provision in gold]
    positions = [pos for pos in found if pos is not None]
    first = min(positions) + 1 if positions else None
    distractors = set(query.get('distractors') or [])
    top5_articles = {article_of(provision) for provision in ids[:5]}
    return {
        'n_gold': len(gold),
        'recall_at': {
            5: (sum(pos is not None and pos < 5 for pos in found) / len(gold)) if gold else None,
            8: (sum(pos is not None and pos < 8 for pos in found) / len(gold)) if gold else None,
        },
        'first': first,
        'distractor_at_5': bool(distractors & top5_articles) if distractors else None,
        'distractor_92993_at_5': '9.29.9.3.' in top5_articles,
        'top5': ids[:5],
    }


def aggregate(rows: list[dict]) -> dict:
    n = len(rows)
    if not n:
        return {'n': 0}
    out = {'n': n, 'label': 'model-checked, not human-verified'}
    for k in (5, 8):
        vals = [row['recall_at'][k] for row in rows if row['recall_at'][k] is not None]
        out[f'recall@{k}'] = sum(vals) / len(vals) if vals else None
    firsts = [1 / row['first'] if row['first'] else 0.0 for row in rows if row['n_gold']]
    out['mrr'] = sum(firsts) / len(firsts) if firsts else None
    flags = [row['distractor_at_5'] for row in rows if row['distractor_at_5'] is not None]
    out['distractor@5'] = sum(1 for flag in flags if flag) / len(flags) if flags else None
    return out


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--split', choices=('all', 'in-sample', 'held-out'), default='all')
    parser.add_argument('--write', action='store_true')
    args = parser.parse_args()
    queries = load()
    detail = []
    buckets = defaultdict(list)
    for query in queries:
        if not query.get('scored'):
            continue
        if args.split != 'all' and query['split'] != args.split:
            continue
        for variant in VARIANTS:
            ids = [row['id'] for row in ranks(query['query'], variant)]
            scored = score_query(query, ids)
            buckets[(query['pool'], query['split'], variant)].append(scored)
            if args.write:
                detail.append({'id': query['id'], 'pool': query['pool'], 'split': query['split'], 'variant': variant, **{
                    'recall@5': scored['recall_at'][5], 'recall@8': scored['recall_at'][8],
                    'first': scored['first'], 'distractor@5': scored['distractor_at_5'],
                    'top5': scored['top5'],
                }})
    summary = []
    for (pool, split, variant), rows in sorted(buckets.items()):
        metrics = aggregate(rows)
        metrics.update({'pool': pool, 'split': split, 'variant': variant})
        summary.append(metrics)
        rec5 = metrics.get('recall@5')
        rec8 = metrics.get('recall@8')
        mrr = metrics.get('mrr')
        dist = metrics.get('distractor@5')
        print(f"{variant:3} {pool:22} {split:10} n={metrics['n']:3} "
              f"recall@5={rec5:.3f} recall@8={rec8:.3f} MRR={mrr:.3f} "
              f"distractor@5={dist if dist is not None else 'n/a'}")
    # Regressions always, they are in-sample by construction.
    print('-- regressions (in-sample, not in the scored pools)')
    for query in queries:
        if query.get('pool') != 'regression':
            continue
        for variant in VARIANTS:
            ids = [row['id'] for row in ranks(query['query'], variant, limit=8)]
            scored = score_query(query, ids)
            if query['id'] == 'mira-nailbase-long':
                arts = {article_of(provision) for provision in ids[:5]}
                got = len(arts & set(query['gold_articles']))
                print(f"{variant:3} {query['id']:32} articles_in_top5={got}/3 distractor929={scored['distractor_92993_at_5']} top5={ids[:5]}")
            elif query.get('gold'):
                print(f"{variant:3} {query['id']:32} r5={scored['recall_at'][5]:.2f} r8={scored['recall_at'][8]:.2f} "
                      f"d929={scored['distractor_92993_at_5']} top5={ids[:5]}")
            elif query.get('expected'):
                covered = [item for item in query['expected'] if any(covers(provision, item) or article_of(provision) == item for provision in ids[:5])]
                print(f"{variant:3} {query['id']:32} covered={covered} top5={ids[:5]}")
    if args.write and args.split == 'all':
        out = {
            'label': 'model-checked, not human-verified',
            'shipped': SHIPPED,
            'summary': summary,
            'detail': detail,
        }
        (HERE / 'results.json').write_text(json.dumps(out, indent=2) + '\n')
        print('wrote results.json')


if __name__ == '__main__':
    main()
