"""Seeded percentile bootstrap, optionally resampling whole clusters (revision families).

The bootstrap units are cases, never repeats: repeats of one case stay together. Pass ``clusters`` (for
example the revision family of each public case) to resample families instead of single cases, so two
revisions of one variance cannot count as two independent observations.
"""
from __future__ import annotations

import random
from collections import defaultdict
from collections.abc import Callable, Hashable, Sequence

__all__ = ['DEFAULT_SEED', 'DEFAULT_RESAMPLES', 'bootstrap_ci', 'paired_bootstrap_ci']

DEFAULT_SEED = 20261021
DEFAULT_RESAMPLES = 10_000


def _mean(values: Sequence[float]) -> float:
    return sum(values) / len(values)


def _percentile(sorted_values: Sequence[float], q: float) -> float:
    """Linear-interpolated percentile of an already sorted sequence, q in [0, 1]."""
    if not sorted_values:
        raise ValueError('no values')
    pos = q * (len(sorted_values) - 1)
    low = int(pos)
    high = min(low + 1, len(sorted_values) - 1)
    frac = pos - low
    return sorted_values[low] * (1.0 - frac) + sorted_values[high] * frac


def _groups(n: int, clusters: Sequence[Hashable] | None) -> list[list[int]]:
    if clusters is None:
        return [[i] for i in range(n)]
    if len(clusters) != n:
        raise ValueError('clusters must be as long as the values')
    by_cluster: dict[Hashable, list[int]] = defaultdict(list)
    for i, c in enumerate(clusters):
        by_cluster[c].append(i)
    return list(by_cluster.values())


def bootstrap_ci(values: Sequence[float], *, stat: Callable[[Sequence[float]], float] = _mean,
                 resamples: int = DEFAULT_RESAMPLES, seed: int = DEFAULT_SEED, alpha: float = 0.05,
                 clusters: Sequence[Hashable] | None = None) -> dict:
    """Percentile interval for ``stat`` (default: the mean) with a fixed, disclosed seed."""
    if not values:
        return {'estimate': None, 'low': None, 'high': None, 'resamples': resamples, 'seed': seed,
                'units': 0, 'clustered': clusters is not None}
    groups = _groups(len(values), clusters)
    rng = random.Random(seed)
    draws = []
    for _ in range(resamples):
        picked: list[float] = []
        for _ in groups:
            picked.extend(values[i] for i in groups[rng.randrange(len(groups))])
        draws.append(stat(picked))
    draws.sort()
    return {'estimate': stat(list(values)), 'low': _percentile(draws, alpha / 2.0),
            'high': _percentile(draws, 1.0 - alpha / 2.0), 'resamples': resamples, 'seed': seed,
            'units': len(groups), 'clustered': clusters is not None}


def paired_bootstrap_ci(a: Sequence[float], b: Sequence[float], *, resamples: int = DEFAULT_RESAMPLES,
                        seed: int = DEFAULT_SEED, alpha: float = 0.05,
                        clusters: Sequence[Hashable] | None = None) -> dict:
    """Interval for mean(a) - mean(b) over the same cases, resampled together so pairs stay paired."""
    if len(a) != len(b):
        raise ValueError('paired samples must be the same length')
    return bootstrap_ci([x - y for x, y in zip(a, b)], resamples=resamples, seed=seed, alpha=alpha,
                        clusters=clusters)
