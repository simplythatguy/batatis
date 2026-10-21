"""Lexical arms: BM25 (R0) and the #33 search ranking (R1).

R0 is the production BM25 (``engine.identify.corpus.bm25_rank``: SQLite FTS5, best provision per article).
R1 is PR #33's ``search_rank`` V3 ranking (id lookup, firestop fold, concept-aware heading boost). That module is
not on ``dev`` yet; WP-20 ports it to ``engine/identify/search_rank.py`` and PR #33 holds it as ``codedb/search_rank.py``.
The arm looks for it there and, failing that, at ``BATATIS_SEARCH_RANK_PATH``; its sha256 goes into the arm config so
the rows say which source produced them. With none of them present the arm reports itself unavailable.
"""
from __future__ import annotations

import hashlib
import importlib
import importlib.util
import os
import re
import sys
import time
from collections.abc import Callable
from pathlib import Path

from evals_dev.identify_bench.datasets import BenchCase
from evals_dev.identify_bench.rows import SCREEN_ORDER_KEEP, RowDraft

from .base import Arm, RunContext, unique_in

_ARTICLE = re.compile(r'(\d+\.\d+\.\d+\.\d+\.)')


class Bm25Arm(Arm):
    kind = 'rank'
    deterministic = True

    def __init__(self, name: str = 'R0-bm25', rank_fn: Callable[[str], list[str]] | None = None, limit: int = 3000):
        self.name, self.limit, self._rank_fn = name, limit, rank_fn

    def config(self) -> dict:
        return {'method': 'bm25-fts5-best-provision', 'limit': self.limit, 'bm25_weights': '0,0,0,4.0,1.0'}

    def run(self, case: BenchCase, repeat: int, ctx: RunContext) -> RowDraft:
        t0 = time.monotonic()
        if self._rank_fn is not None:
            ranked = self._rank_fn(case.query)
        else:
            from engine.identify.corpus import bm25_rank
            ranked = bm25_rank(case.query, ctx.db_path, self.limit)
        return RowDraft(order=unique_in(ranked, ctx.arts), latency_ms={'rank': (time.monotonic() - t0) * 1000},
                        order_keep=SCREEN_ORDER_KEEP)


def locate_search_rank(path: str | None = None):
    """(module, source description, sha256) for the #33 ranking module, or None when it is not present."""
    explicit = path or os.environ.get('BATATIS_SEARCH_RANK_PATH')
    if explicit:
        p = Path(explicit)
        if not p.is_file():
            return None
        spec = importlib.util.spec_from_file_location('batatis_search_rank_v3', p)
        module = importlib.util.module_from_spec(spec)
        sys.modules['batatis_search_rank_v3'] = module
        spec.loader.exec_module(module)
        return module, f'file:{p.name}', hashlib.sha256(p.read_bytes()).hexdigest()
    for dotted in ('engine.identify.search_rank', 'codedb.search_rank'):
        try:
            module = importlib.import_module(dotted)
        except ImportError:
            continue
        src = Path(module.__file__)
        return module, dotted, hashlib.sha256(src.read_bytes()).hexdigest()
    return None


class SearchRankArm(Arm):
    """R1: PR #33 V3 ranking over provisions, collapsed to articles in first-hit order."""
    kind = 'rank'
    deterministic = True

    def __init__(self, name: str = 'R1-searchrank-v3', module=None, source: str = '', source_sha256: str = '',
                 limit: int = 300):
        found = (module, source, source_sha256) if module is not None else locate_search_rank()
        self.available = found is not None
        self.module, self.source, self.source_sha256 = found if found else (None, 'absent', '')
        self.name, self.limit = name, limit

    def config(self) -> dict:
        return {'method': 'search_rank.search_variant v3, first hit per article', 'limit': self.limit,
                'source': self.source, 'source_sha256': self.source_sha256}

    def run(self, case: BenchCase, repeat: int, ctx: RunContext) -> RowDraft:
        if not self.available:
            return RowDraft(errors=[{'stage': 'rank', 'category': 'unavailable',
                                     'detail': 'search_rank module not found (WP-20 or PR #33, or BATATIS_SEARCH_RANK_PATH)'}])
        t0 = time.monotonic()
        try:
            rank_articles = getattr(self.module, 'rank_articles', None)
            if rank_articles is not None:
                ranked = rank_articles(case.query, ctx.db_path, limit=self.limit)
            else:
                rows = self.module.search_variant(case.query, 'v3', division='B', limit=min(1000, self.limit * 3),
                                                  db_path=ctx.db_path)
                ranked = []
                for row in rows:
                    m = _ARTICLE.match(row.get('id') or '')
                    if m and m.group(1) not in ranked:
                        ranked.append(m.group(1))
        except Exception as e:                                   # noqa: BLE001 - recorded, not raised
            return RowDraft(errors=[{'stage': 'rank', 'category': 'exception', 'detail': type(e).__name__}])
        return RowDraft(order=unique_in(ranked, ctx.arts), latency_ms={'rank': (time.monotonic() - t0) * 1000},
                        order_keep=SCREEN_ORDER_KEEP)
