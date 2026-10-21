"""Binomial intervals for "x of n" claims: Wilson (two-sided) and exact Clopper-Pearson.

Standard library only, so the numbers do not depend on SciPy.

``wilson_interval`` is the repo's two-sided 95% Wilson interval (``evals_dev.stats``) and is re-exported
unchanged. The exact Clopper-Pearson bounds are added here. The plan quotes the one-sided 95% lower bound
(the "91%" of gate G4): 49 of 50 gives 0.9086 and 32 of 32 gives 0.9106.

An interval is a statement about a counted ratio. It is not a model grade and not a finding that a
design complies with the building code.
"""
from __future__ import annotations

import math

from evals_dev.stats import Z_95, proportion, wilson_interval

__all__ = ['Z_95', 'binom_cdf', 'binom_sf', 'clopper_pearson_interval', 'clopper_pearson_lower',
           'clopper_pearson_upper', 'proportion', 'rate', 'wilson_interval']

_ITERATIONS = 200          # bisection steps; the bracket is below 1e-15 long after ~55


def _check(x: int, n: int) -> None:
    if n < 0 or x < 0 or x > n:
        raise ValueError(f'need 0 <= x <= n, got {x} of {n}')


def _check_confidence(confidence: float) -> None:
    if not 0.0 < confidence < 1.0:
        raise ValueError(f'confidence must be strictly between 0 and 1, got {confidence}')


def _pmf(k: int, n: int, p: float) -> float:
    """Binomial probability mass at k, computed in log space so large n does not overflow."""
    if p <= 0.0:
        return 1.0 if k == 0 else 0.0
    if p >= 1.0:
        return 1.0 if k == n else 0.0
    log_choose = math.lgamma(n + 1) - math.lgamma(k + 1) - math.lgamma(n - k + 1)
    return math.exp(log_choose + k * math.log(p) + (n - k) * math.log1p(-p))


def binom_sf(k: int, n: int, p: float) -> float:
    """P(X >= k) for X ~ Binomial(n, p). A direct tail sum, so a tiny tail keeps its precision."""
    if k <= 0:
        return 1.0
    if k > n:
        return 0.0
    return min(1.0, sum(_pmf(i, n, p) for i in range(k, n + 1)))


def binom_cdf(k: int, n: int, p: float) -> float:
    """P(X <= k) for X ~ Binomial(n, p). A direct tail sum."""
    if k < 0:
        return 0.0
    if k >= n:
        return 1.0
    return min(1.0, sum(_pmf(i, n, p) for i in range(0, k + 1)))


def _bisect(f, increasing: bool) -> float:
    """Root of a monotone f on [0, 1]; f(0) and f(1) must straddle zero."""
    lo, hi = 0.0, 1.0
    for _ in range(_ITERATIONS):
        mid = (lo + hi) / 2.0
        value = f(mid)
        if (value < 0.0) == increasing:
            lo = mid
        else:
            hi = mid
        if hi - lo < 1e-15:
            break
    return (lo + hi) / 2.0


def clopper_pearson_lower(x: int, n: int, confidence: float = 0.95) -> float:
    """Exact one-sided lower confidence bound for the success probability.

    The p at which seeing ``x`` or more successes in ``n`` trials has probability ``1 - confidence``.
    ``clopper_pearson_lower(49, 50)`` is 0.9086 and ``clopper_pearson_lower(32, 32)`` is 0.9106.
    """
    _check(x, n)
    _check_confidence(confidence)
    if x == 0:
        return 0.0
    alpha = 1.0 - confidence
    return _bisect(lambda p: binom_sf(x, n, p) - alpha, increasing=True)


def clopper_pearson_upper(x: int, n: int, confidence: float = 0.95) -> float:
    """Exact one-sided upper confidence bound for the success probability."""
    _check(x, n)
    _check_confidence(confidence)
    if x == n:
        return 1.0
    alpha = 1.0 - confidence
    return _bisect(lambda p: binom_cdf(x, n, p) - alpha, increasing=False)


def clopper_pearson_interval(x: int, n: int, confidence: float = 0.95) -> list[float] | None:
    """Exact two-sided interval ``[low, high]``, or None when ``n`` is 0."""
    if n <= 0:
        return None
    _check(x, n)
    _check_confidence(confidence)
    tail = 1.0 - (1.0 - confidence) / 2.0
    return [clopper_pearson_lower(x, n, tail), clopper_pearson_upper(x, n, tail)]


def rate(x: int, n: int, *, skipped: str | None = None) -> dict:
    """One ``x of n`` result with every interval the reports use.

    ``wilson_95`` is the two-sided Wilson interval, ``clopper_pearson_95`` the exact two-sided interval, and
    ``cp_lower_95_one_sided`` the exact one-sided lower bound the gate G4 text quotes.
    """
    out = dict(proportion(x, n, skipped=skipped))
    out['rate'] = (x / n) if n else None
    out['clopper_pearson_95'] = clopper_pearson_interval(x, n) if n else None
    out['cp_lower_95_one_sided'] = clopper_pearson_lower(x, n) if n else None
    return out
