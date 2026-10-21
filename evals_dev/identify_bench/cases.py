"""Choosing which cases a run covers."""
from __future__ import annotations

import hashlib
from collections import defaultdict
from collections.abc import Iterable

from .datasets import BenchCase, load_all


def select(*, datasets: Iterable[str] | None = None, folds: Iterable[str] | None = None, gold_only: bool = False,
           ids: Iterable[str] | None = None, balanced: int | None = None, limit: int | None = None,
           seed: int = 20261021) -> list[BenchCase]:
    """Cases in dataset order. ``balanced`` picks that many gold-bearing cases spread over the Part groups."""
    cases = load_all(datasets=datasets or ('public53', 'dev', 'idr26'))
    if folds:
        wanted = set(folds)
        cases = [c for c in cases if c.fold in wanted]
    if gold_only or balanced:
        cases = [c for c in cases if c.gold]
    if ids:
        keep = set(ids)
        cases = [c for c in cases if c.id in keep]
    if balanced:
        cases = balanced_sample(cases, balanced, seed)
    if limit:
        cases = cases[:limit]
    return cases


def balanced_sample(cases: list[BenchCase], n: int, seed: int = 20261021) -> list[BenchCase]:
    """``n`` cases drawn round-robin from the Part groups (part9, other, mixed), each ordered by a seeded hash."""
    groups: dict[str, list[BenchCase]] = defaultdict(list)
    for c in sorted(cases, key=lambda c: hashlib.sha256(f'{seed}:{c.id}'.encode()).hexdigest()):
        groups[c.part_group].append(c)
    order = [g for g in ('part9', 'other', 'mixed') if g in groups]
    out: list[BenchCase] = []
    i = 0
    while len(out) < n and any(groups[g] for g in order):
        g = order[i % len(order)]
        if groups[g]:
            out.append(groups[g].pop(0))
        i += 1
    keep = {c.id for c in out}
    return [c for c in cases if c.id in keep]
