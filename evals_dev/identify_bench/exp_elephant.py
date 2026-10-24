"""Parent-run live Elephant experiments on diagnostic pools (quota-aware, cached).

A diagnostic pool for a case = its gold and context articles plus the strongest lexical
distractors (bm25_v3 order, not gold/context) up to `size`, shuffled with a seed from the case
id. One pool is scored per request when it fits the model context. Scores answer: does Elephant
rank the governing articles above plausible distractors, and what threshold keeps all of them?
This measures the scorer conditional on the gold being in the pool, not the full pipeline.

  .venv/bin/python -m evals_dev.identify_bench.exp_elephant run --variant production --size 40 --max-calls 20
  .venv/bin/python -m evals_dev.identify_bench.exp_elephant report --variant production --size 40
"""
from __future__ import annotations

import argparse
import hashlib
import json
import random
import sys
from pathlib import Path

from engine.identify.corpus import articles, card
from engine.identify.screen import GOVERN, noul
from engine.identify.search_rank import rank_articles

from . import live
from .cases import Case, all_cases, select

DB = Path(__file__).resolve().parents[2] / 'codedb' / 'build' / 'codedb.sqlite'
RESULTS = Path(__file__).resolve().parent / 'results'
TOKEN_LIMIT = 15_000          # calibrated: bytes / 3.0 + 512 + 8 per question (measured 3.42 bytes/token)

CRITERIA = {
    'true': ('A complete alternative-solution application for this proposal must cite this article: the proposal '
             'departs from its requirement, must still meet it, or relies on it.'),
    'false': ('The article covers a different subject or situation, or only shares words with the proposal; '
              'the application would not need to cite it.'),
}


SELF_CONTAINED = ('A complete alternative-solution application for the proposal in `proposal` must cite this '
                  'building-code article: {card}')


def pool_for(case: Case, size: int, arts: dict) -> list[str]:
    keep = [a for a in (*case.gold, *case.context) if a in arts]
    for a in rank_articles(case.description, DB, limit=size * 3):
        if len(keep) >= size:
            break
        if a in arts and a not in keep:
            keep.append(a)
    seed = int(hashlib.sha256(case.id.encode()).hexdigest(), 16)
    random.Random(seed).shuffle(keep)
    return keep


def request(case: Case, pool: list[str], variant: str, arts: dict) -> tuple[dict, dict]:
    if variant == 'production':
        state = {'proposal': case.description, 'articles': {f'A{i}': card(arts[a], 700) for i, a in enumerate(pool)}}
        qs = {f'q{i}': noul(GOVERN.format(L=f'A{i}')) for i in range(len(pool))}
    elif variant == 'criteria':
        state = {'proposal': case.description, 'articles': {f'A{i}': card(arts[a], 700) for i, a in enumerate(pool)}}
        qs = {f'q{i}': {**noul(GOVERN.format(L=f'A{i}')), 'criteria': CRITERIA} for i in range(len(pool))}
    elif variant == 'selfcontained':
        # Vendor guidance: one item per question (no shared-list lookup) and one atomic claim per Noul.
        state = {'proposal': case.description}
        qs = {f'q{i}': noul(SELF_CONTAINED.format(card=card(arts[a], 700))) for i, a in enumerate(pool)}
    else:
        raise ValueError(f'unknown variant {variant}')
    return state, qs


def estimated_tokens(state, qs) -> int:
    body = json.dumps({'state': state, 'questions': qs}, ensure_ascii=False, separators=(',', ':')).encode('utf-8')
    return int(len(body) / 3.0) + 512 + 8 * len(qs)


def score(case: Case, pool: list[str], variant: str, arts: dict, budget) -> dict[str, float]:
    """One request when the pool fits the calibrated bound, else halves (recursively)."""
    state, qs = request(case, pool, variant, arts)
    if estimated_tokens(state, qs) > TOKEN_LIMIT and len(pool) > 1:
        half = len(pool) // 2
        return {**score(case, pool[:half], variant, arts, budget), **score(case, pool[half:], variant, arts, budget)}
    rep = live.elephant_ask_unbounded(state, qs, budget=budget, tag=f'E2-{variant}-{case.id}')
    return {a: rep['answers'][f'q{i}']['noul'] for i, a in enumerate(pool)}


def cached_scores(case: Case, pool: list[str], variant: str, arts: dict) -> dict[str, float] | None:
    class Never:
        def take(self):
            raise live.BudgetExhausted('cache only')
    try:
        return score(case, pool, variant, arts, Never())
    except live.BudgetExhausted:
        return None


def auc(pos: list[float], neg: list[float]) -> float | None:
    if not pos or not neg:
        return None
    wins = sum((p > n) + 0.5 * (p == n) for p in pos for n in neg)
    return wins / (len(pos) * len(neg))


def report(cases: list[Case], variant: str, size: int) -> dict:
    arts = articles(DB)
    rows = []
    for case in cases:
        pool = pool_for(case, size, arts)
        scores = cached_scores(case, pool, variant, arts)
        if scores is None:
            continue
        ranked = sorted(pool, key=lambda a: -scores[a])
        gold = [a for a in case.gold if a in scores]
        neg = [a for a in pool if a not in case.gold and a not in case.context]
        rows.append({
            'case': case.id, 'source': case.source, 'gold': {a: round(scores[a], 4) for a in gold},
            'gold_ranks': {a: ranked.index(a) + 1 for a in gold},
            'min_gold': min(scores[a] for a in gold), 'auc': auc([scores[a] for a in gold], [scores[a] for a in neg]),
            'neg_over_05': sum(scores[a] >= 0.5 for a in neg), 'neg_over_02': sum(scores[a] >= 0.2 for a in neg),
            'top_neg': sorted(((round(scores[a], 3), a) for a in neg), reverse=True)[:3]})
    n = len(rows)
    out = {'variant': variant, 'size': size, 'cases': n}
    if n:
        aucs = [r['auc'] for r in rows if r['auc'] is not None]
        out['mean_auc'] = round(sum(aucs) / len(aucs), 4)
        out['gold_top1_rate'] = round(sum(min(r['gold_ranks'].values()) == 1 for r in rows) / n, 4)
        out['all_gold_in_top5'] = round(sum(max(r['gold_ranks'].values()) <= 5 for r in rows) / n, 4)
        out['all_gold_in_top10'] = round(sum(max(r['gold_ranks'].values()) <= 10 for r in rows) / n, 4)
        for t in (0.5, 0.3, 0.2, 0.1, 0.05, 0.02):
            out[f'complete_at_p>={t}'] = round(sum(r['min_gold'] >= t for r in rows) / n, 4)
        out['mean_neg_over_0.5'] = round(sum(r['neg_over_05'] for r in rows) / n, 2)
        out['mean_neg_over_0.2'] = round(sum(r['neg_over_02'] for r in rows) / n, 2)
    out['rows'] = rows
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('cmd', choices=('run', 'report', 'plan'))
    ap.add_argument('--variant', default='production')
    ap.add_argument('--size', type=int, default=40)
    ap.add_argument('--fold', default='tune')
    ap.add_argument('--max-calls', type=int, default=0)
    ap.add_argument('--reserve', type=int, default=4)
    ap.add_argument('--limit', type=int, default=None)
    ap.add_argument('--sources', default='dev,precedent,web-ab,web-ca')
    a = ap.parse_args(argv)
    cases = select(all_cases(), fold=a.fold, kinds=('benchmark',), sources=tuple(a.sources.split(',')), limit=a.limit)
    arts = articles(DB)
    if a.cmd == 'plan':
        for case in cases:
            pool = pool_for(case, a.size, arts)
            state, qs = request(case, pool, a.variant, arts)
            print(case.id, len(pool), estimated_tokens(state, qs))
        return 0
    if a.cmd == 'run':
        budget = live.ElephantBudget(reserve=a.reserve, max_calls=a.max_calls)
        done = 0
        for case in cases:
            pool = pool_for(case, a.size, arts)
            if cached_scores(case, pool, a.variant, arts) is not None:
                continue
            try:
                score(case, pool, a.variant, arts, budget)
                done += 1
                print(f'{case.id}: scored ({budget.sent} calls, ~{budget.remaining} left)', flush=True)
            except live.BudgetExhausted as error:
                print(f'stopped: {error}')
                break
            except Exception as error:
                print(f'{case.id}: ERROR {type(error).__name__}: {str(error)[:200]}')
                break
        print(f'scored {done} new cases; quota now {live.elephant_quota()}')
    out = report(cases, a.variant, a.size)
    RESULTS.mkdir(exist_ok=True)
    (RESULTS / f'elephant_{a.variant}_{a.size}_{a.fold}.json').write_text(json.dumps(out, indent=1))
    print(json.dumps({k: v for k, v in out.items() if k != 'rows'}, indent=1))
    return 0


if __name__ == '__main__':
    sys.exit(main())
