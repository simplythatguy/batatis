"""Ranking metrics for article identification: hit@k, recall@k and reciprocal rank.

Same definitions as ``docs/research/2026-10-20-vision/jev-benchmark/scripts/metrics.py`` so the recorded
numbers reproduce, written per case so paired tests and intervals are possible.

A case is a hit@k if any gold article is among the first k ranked; recall@k is the share of its gold
articles found in the first k; the reciprocal rank is 1 over the 1-based position of the first gold
article, or 0 when none is ranked.
"""
from __future__ import annotations

import re
from collections.abc import Mapping, Sequence

__all__ = ['DEFAULT_KS', 'article_of', 'evaluate', 'first_gold_rank', 'hit_at_k', 'recall_at_k',
           'reciprocal_rank']

DEFAULT_KS = (1, 3, 5, 10, 20, 50, 100, 200)
_ARTICLE = re.compile(r'(\d+\.\d+\.\d+\.\d+\.)')


def article_of(provision: str | None) -> str | None:
    """Leading article id of a provision id: ``9.25.5.2.(1)`` and ``9.25.5.2.`` are both ``9.25.5.2.``."""
    match = _ARTICLE.match(provision or '')
    return match.group(1) if match else None


def first_gold_rank(order: Sequence[str], gold: Sequence[str]) -> int | None:
    """1-based rank of the first gold article, or None when no gold article is ranked."""
    gold_set = set(gold)
    for i, article in enumerate(order, start=1):
        if article in gold_set:
            return i
    return None


def hit_at_k(order: Sequence[str], gold: Sequence[str], k: int) -> bool:
    return bool(set(order[:k]) & set(gold))


def recall_at_k(order: Sequence[str], gold: Sequence[str], k: int) -> float:
    gold_set = set(gold)
    return (len(set(order[:k]) & gold_set) / len(gold_set)) if gold_set else 0.0


def reciprocal_rank(order: Sequence[str], gold: Sequence[str]) -> float:
    rank = first_gold_rank(order, gold)
    return (1.0 / rank) if rank else 0.0


def evaluate(rankings: Mapping[str, Sequence[str]], gold: Mapping[str, Sequence[str]],
             ks: Sequence[int] = DEFAULT_KS) -> dict:
    """Mean hit@k, recall@k and MRR over the cases in ``gold`` that have a ranking.

    A gold-bearing case with no ranking counts as a miss (an empty ranking), never as skipped.
    """
    cases = [c for c in gold if gold[c]]
    n = len(cases)
    out: dict = {'n': n, 'mrr': 0.0}
    for k in ks:
        out[f'hit@{k}'] = 0.0
        out[f'recall@{k}'] = 0.0
    for c in cases:
        order = rankings.get(c, ())
        out['mrr'] += reciprocal_rank(order, gold[c]) / n
        for k in ks:
            out[f'hit@{k}'] += hit_at_k(order, gold[c], k) / n
            out[f'recall@{k}'] += recall_at_k(order, gold[c], k) / n
    return out
