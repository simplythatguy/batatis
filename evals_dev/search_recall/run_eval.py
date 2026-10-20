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


# The identify benchmark's first 20 evals_dev cases contain these 11 must_cite
# rows. That 11-case provision scoring is unchanged. Gold v2 adds five ask
# cases beside it and does not relabel scored_must_cite.
GOLD_V2_ELEVEN = (
    'dev-001', 'dev-002', 'dev-003', 'dev-004', 'dev-008', 'dev-013',
    'dev-014', 'dev-016', 'dev-017', 'dev-018', 'dev-019',
)
GOLD_V2_HIGH = {
    'dev-006': ['9.25.5.2.(1)'],
    'dev-010': ['9.10.15.5.(2)'],
    'dev-011': ['9.23.10.1.(1)'],
    'dev-015': ['9.9.9.1.(1)'],
}
GOLD_V2_ARTICLE = {'dev-009': '9.27.2.2.'}
GOLD_V2_LABEL = 'gold v2, 16 scored, article-level for 009'


def _case_description(case_id: str) -> str:
    path = HERE.parent / 'cases' / f'{case_id}.json'
    return json.loads(path.read_text())['description']


def _case_must_cite(case_id: str) -> list[str]:
    path = HERE.parent / 'cases' / f'{case_id}.json'
    gold = json.loads(path.read_text())['gold']['must_cite']
    return [row['provision'] for row in gold if row.get('division') == 'B' and row.get('provision')]


def score_part3(queries: list[dict]) -> list[dict]:
    """Held-out Part 3 block. Hit@8 is separate from must_not_return@8."""
    cases = [query for query in queries if query.get('pool') == 'part3-held-out']
    summary = []
    for variant in VARIANTS:
        hits = 0
        violations = 0
        analogue = 0
        nail = 0
        per_case = []
        for query in cases:
            ids = [row['id'] for row in ranks(query['query'], variant, limit=8)]
            if query.get('gold_any'):
                hit = any(covers(provision, gold) for gold in query['gold_any'] for provision in ids)
            else:
                hit = any(article_hit(ids, article) is not None for article in query['gold_articles'])
            found = sorted(set(query.get('distractors') or []) & {article_of(provision) for provision in ids})
            hits += int(hit)
            violations += int(bool(found))
            analogue += int(any(item != '9.29.9.3.' for item in found))
            nail += int('9.29.9.3.' in found)
            per_case.append({'id': query['id'], 'part3_hit@8': hit, 'must_not_return': found, 'top8': ids})
        n = len(cases)
        summary.append({
            'variant': variant,
            'split': 'held-out',
            'n': n,
            'label': 'model-checked, not human-verified',
            'part3_hit@8': hits / n if n else None,
            'must_not_return@8': violations / n if n else None,
            'part9_analogue@8': analogue / n if n else None,
            'distractor_9.29.9.3@8': nail / n if n else None,
            'cases': per_case,
        })
    return summary


def print_part3(rows: list[dict]) -> None:
    print('-- part3 held-out idr-022..026 (not tuned; model-checked, not human-verified)')
    for row in rows:
        print(f"{row['variant']:3} part3-held-out held-out n={row['n']} "
              f"part3_hit@8={row['part3_hit@8']:.3f} must_not_return@8={row['must_not_return@8']:.3f} "
              f"part9_analogue@8={row['part9_analogue@8']:.3f} 9.29.9.3@8={row['distractor_9.29.9.3@8']:.3f}")


def score_gold_v2() -> dict:
    """Additional table. The original 11 stay provision-level. dev-009 is the article."""
    items = []
    for case_id in GOLD_V2_ELEVEN:
        items.append({'id': case_id, 'query': _case_description(case_id), 'gold': _case_must_cite(case_id), 'gold_level': 'provision'})
    for case_id, gold in GOLD_V2_HIGH.items():
        items.append({'id': case_id, 'query': _case_description(case_id), 'gold': gold, 'gold_level': 'provision'})
    for case_id, article in GOLD_V2_ARTICLE.items():
        items.append({'id': case_id, 'query': _case_description(case_id), 'gold_articles': [article], 'gold_level': 'article'})
    per_variant = []
    for variant in VARIANTS:
        scored = []
        for item in items:
            ids = [row['id'] for row in ranks(item['query'], variant)]
            scored.append(score_query(item, ids))
        metrics = aggregate(scored)
        metrics.update({'variant': variant, 'label': GOLD_V2_LABEL, 'also': 'model-checked, not human-verified'})
        per_variant.append(metrics)
    return {'label': GOLD_V2_LABEL, 'also': 'model-checked, not human-verified', 'n': len(items), 'variants': per_variant}


def print_gold_v2(payload: dict) -> None:
    print(f"-- {payload['label']} ({payload['also']})")
    for row in payload['variants']:
        print(f"{row['variant']:3} gold-v2 n={row['n']} recall@5={row['recall@5']:.3f} "
              f"recall@8={row['recall@8']:.3f} MRR={row['mrr']:.3f}")


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
        window = int(query.get('top_k') or 5)
        for variant in VARIANTS:
            ids = [row['id'] for row in ranks(query['query'], variant, limit=max(8, window))]
            scored = score_query(query, ids)
            if query['id'] == 'mira-nailbase-long':
                arts = {article_of(provision) for provision in ids[:5]}
                got = len(arts & set(query['gold_articles']))
                print(f"{variant:3} {query['id']:32} articles_in_top5={got}/3 distractor929={scored['distractor_92993_at_5']} top5={ids[:5]}")
            elif query.get('gold'):
                print(f"{variant:3} {query['id']:32} r5={scored['recall_at'][5]:.2f} r8={scored['recall_at'][8]:.2f} "
                      f"d929={scored['distractor_92993_at_5']} top5={ids[:5]}")
            elif query.get('expected'):
                head = ids[:window]
                exact = set(query.get('exact') or [])
                def matched(item: str) -> bool:
                    if item in exact:
                        return item in head
                    return any(covers(provision, item) or article_of(provision) == item for provision in head)
                covered = [item for item in query['expected'] if matched(item)]
                plus = [item for item in (query.get('plus') or []) if any(covers(provision, item) for provision in head)]
                print(f"{variant:3} {query['id']:32} covered={covered} plus={plus} top{window}={head}")
    extra = {}
    if args.split == 'all':
        extra['part3_held_out'] = score_part3(queries)
        extra['gold_v2'] = score_gold_v2()
        print_part3(extra['part3_held_out'])
        print_gold_v2(extra['gold_v2'])
    if args.write and args.split == 'all':
        out = {
            'label': 'model-checked, not human-verified',
            'shipped': SHIPPED,
            'summary': summary,
            'detail': detail,
            **extra,
        }
        (HERE / 'results.json').write_text(json.dumps(out, indent=2) + '\n')
        print('wrote results.json')


if __name__ == '__main__':
    main()
