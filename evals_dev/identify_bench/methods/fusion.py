"""Reciprocal-rank fusion of several upstream rankings (A7). No model call, so no cost."""
from __future__ import annotations

from evals_dev.identify_bench.datasets import BenchCase
from evals_dev.identify_bench.rows import SCREEN_ORDER_KEEP, RowDraft

from .base import Arm, RunContext, UpstreamMissing, unique_in


class FuseArm(Arm):
    kind = 'fuse'

    def __init__(self, name: str, upstream: tuple[str, ...], *, k: int = 60, depth: int = 100):
        self.name, self.upstream_names, self.k, self.depth = name, tuple(upstream), k, depth

    def config(self) -> dict:
        return {'method': 'reciprocal rank fusion', 'k': self.k, 'depth': self.depth}

    def run(self, case: BenchCase, repeat: int, ctx: RunContext) -> RowDraft:
        rows, errors = {}, []
        for up in self.upstream_names:
            try:
                rows[up] = ctx.upstream(up, case, repeat, clamp=True)
            except UpstreamMissing as e:
                errors.append({'stage': 'fuse', 'category': 'upstream_missing', 'detail': str(e)})
        if not rows:
            return RowDraft(errors=errors)
        score: dict[str, float] = {}
        for row in rows.values():
            for i, a in enumerate(row['order'][:self.depth], start=1):
                score[a] = score.get(a, 0.0) + 1.0 / (self.k + i)
        order = unique_in(sorted(score, key=lambda a: (-score[a], a)), ctx.arts)
        top = max(score.values())
        return RowDraft(order=order, probabilities={a: score[a] / top for a in order},
                        upstream={n: r['key'] for n, r in rows.items()}, errors=errors, order_keep=SCREEN_ORDER_KEEP,
                        notes={'parallel_upstream': True, 'used': sorted(rows)})
