"""Code identification: which Division B articles govern a described situation.

Pipeline (measured in docs/research/2026-10-20-vision/jev-benchmark/): Jev screens every Division B
article in batches -> the top N are re-judged together in one request -> optional verifier
(verify.py) picks with word-for-word quotes. BM25 is kept as a cheap baseline and fallback.
Nothing here commits an article; callers decide (Part 9 commits, other Parts quoted choices).
"""
from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path

from .corpus import articles, bm25_rank
from .screen import JEV_MODEL, Judge


@dataclass
class Identification:
    ranked: list[tuple[str, float]]        # rerank order: (article id, rerank probability)
    screen: dict[str, float]               # exhaustive screen probability for every article
    usage: dict
    screen_seconds: float
    rerank_seconds: float
    model: str


def identify(query: str, db_path: Path | str, judge: Judge | None = None, *, rerank_n: int = 60,
             parts: set[int] | None = None) -> Identification:
    """Screen all Division B articles (optionally only `parts`), then rerank the top `rerank_n` in one request."""
    arts = articles(Path(db_path))
    ids = [a for a, v in arts.items() if parts is None or v['part'] in parts]
    judge = judge or Judge()
    t0 = time.monotonic()
    screen = judge.judge(query, arts, ids)
    t1 = time.monotonic()
    top = sorted(ids, key=lambda a: -screen[a])[:rerank_n]
    rerank_requests_before = judge.usage.requests
    rer = judge.judge(query, arts, top)
    t2 = time.monotonic()
    usage = judge.usage.summary() | {'rerank_requests': judge.usage.requests - rerank_requests_before}
    return Identification(ranked=sorted(((a, rer[a]) for a in top), key=lambda x: -x[1]), screen=screen,
                          usage=usage, screen_seconds=t1 - t0, rerank_seconds=t2 - t1, model=JEV_MODEL)


__all__ = ['identify', 'Identification', 'Judge', 'bm25_rank', 'articles', 'JEV_MODEL']
