"""Wilson score intervals shared by the human-key scorer and the deterministic checks.

The interval is the 95% Wilson score interval for a binomial proportion. It is a
statement about a counted ratio. It is not a model grade and not a finding that
a design complies with the building code.
"""
from __future__ import annotations

import math


Z_95 = 1.959963984540054  # scipy.stats.norm.ppf(0.975), fixed so the interval does not depend on SciPy


def wilson_interval(x: int, n: int, z: float = Z_95) -> list[float] | None:
    """Return ``[low, high]`` for ``x`` successes in ``n`` trials, or None when ``n`` is 0."""
    if n <= 0:
        return None
    if x < 0 or x > n:
        raise ValueError(f'x must be between 0 and n, got {x} of {n}')
    p = x / n
    z2 = z * z
    denom = 1.0 + z2 / n
    centre = (p + z2 / (2.0 * n)) / denom
    margin = z * math.sqrt(p * (1.0 - p) / n + z2 / (4.0 * n * n)) / denom
    return [max(0.0, centre - margin), min(1.0, centre + margin)]


def proportion(x: int, n: int, *, skipped: str | None = None) -> dict:
    """One ``x of n`` result with its Wilson 95% interval."""
    return {
        'x': x,
        'n': n,
        'label': f'{x} of {n}',
        'wilson_95': wilson_interval(x, n) if n else None,
        'skipped': skipped,
    }
