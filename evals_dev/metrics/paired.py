"""Paired comparisons of two methods run on the same cases.

The decision rule in ``docs/accuracy`` compares pipelines case by case: only the discordant cases (one
method right, the other wrong) carry information, and an exact sign test on them needs no distribution
assumption.
"""
from __future__ import annotations

from collections.abc import Mapping
from math import comb

__all__ = ['paired_counts', 'paired_counts_graded', 'sign_test', 'sign_test_cases']


def paired_counts(a: Mapping[str, bool], b: Mapping[str, bool]) -> dict[str, int]:
    """Cross-tabulate two per-case outcome maps over the cases both have.

    ``only_a`` counts cases where A succeeded and B did not, ``only_b`` the reverse.
    """
    cases = sorted(set(a) & set(b))
    both = sum(1 for c in cases if a[c] and b[c])
    only_a = sum(1 for c in cases if a[c] and not b[c])
    only_b = sum(1 for c in cases if b[c] and not a[c])
    neither = len(cases) - both - only_a - only_b
    return {'n': len(cases), 'both': both, 'only_a': only_a, 'only_b': only_b, 'neither': neither}


def paired_counts_graded(a: Mapping[str, float], b: Mapping[str, float], eps: float = 1e-9) -> dict[str, int]:
    """Like ``paired_counts`` for per-case success *fractions* (the share of a case's repeats that succeeded).

    A case is discordant when the two fractions differ: ``only_a`` counts cases where A's fraction is higher, ``only_b`` where B's is.
    Equal fractions (including both 0 and both 1) carry no information and are counted as ``same``. The sign test then applies as before.
    """
    cases = sorted(set(a) & set(b))
    only_a = sum(1 for c in cases if a[c] > b[c] + eps)
    only_b = sum(1 for c in cases if b[c] > a[c] + eps)
    return {'n': len(cases), 'only_a': only_a, 'only_b': only_b, 'same': len(cases) - only_a - only_b}


def sign_test(only_a: int, only_b: int, alternative: str = 'two-sided') -> float:
    """Exact sign-test p-value from the discordant counts.

    Under the null, each discordant case favours A or B with probability one half.

    ``alternative='less'``     H1: A succeeds less often than B.  p = P(X <= only_a)
    ``alternative='greater'``  H1: A succeeds more often than B.  p = P(X >= only_a)
    ``alternative='two-sided'`` twice the smaller one-sided p, capped at 1.
    With no discordant cases the p-value is 1.
    """
    if only_a < 0 or only_b < 0:
        raise ValueError('discordant counts cannot be negative')
    n = only_a + only_b
    if n == 0:
        return 1.0
    denom = 2 ** n
    p_less = sum(comb(n, k) for k in range(0, only_a + 1)) / denom
    p_greater = sum(comb(n, k) for k in range(only_a, n + 1)) / denom
    if alternative == 'less':
        return min(1.0, p_less)
    if alternative == 'greater':
        return min(1.0, p_greater)
    if alternative == 'two-sided':
        return min(1.0, 2.0 * min(p_less, p_greater))
    raise ValueError("alternative must be 'less', 'greater' or 'two-sided'")


def sign_test_cases(a: Mapping[str, bool], b: Mapping[str, bool], alternative: str = 'two-sided') -> dict:
    """Counts and the exact p-value for two per-case outcome maps."""
    counts = paired_counts(a, b)
    return {**counts, 'alternative': alternative,
            'p_value': sign_test(counts['only_a'], counts['only_b'], alternative)}
