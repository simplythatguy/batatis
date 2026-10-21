"""Precedent matcher (R2): find the 2023 articles the most similar earlier precedents varied.

There are 151 indexed precedents (STANDATA variances, interpretations, bulletins, Calgary SPVs; ``research/precedents/index.json``).
Each lists the articles it varied, mapped to NBC(AE) 2023. The matcher ranks precedents by BM25 over their title, summary,
applicability and conditions, takes the nearest few, and scores each article by the similarity of the precedents that cite it.

For a public benchmark case the case *is* one of the precedents, so evaluation hides its whole revision family
(``evals_dev/public_benchmark/families.py``, leave-one-family-out); otherwise the matcher would find its own answer. Applicant
prose cases (dev, idr26) are not precedents and hide nothing.

This is retrieval, not judgement: it can only return articles some precedent already cited, and the mapping of a
precedent's articles to 2023 includes entries whose cross-edition equivalence the index marks "unverified". That limit is
part of what the benchmark measures.
"""
from __future__ import annotations

import json
import math
import re
import time
from collections import Counter
from pathlib import Path

from evals_dev.identify_bench.datasets import REPO, BenchCase
from evals_dev.identify_bench.rows import RowDraft
from evals_dev.public_benchmark.families import excluded_precedents

from .base import Arm, RunContext, unique_in

INDEX = REPO / 'research' / 'precedents' / 'index.json'
_ART = re.compile(r'Article\s+(\d+\.\d+\.\d+\.\d+\.)')
_WORD = re.compile(r'[a-z][a-z0-9-]{2,}')
UNMAPPED = {'not-found', 'outside-nbc-scope'}


def tokens(text: str, stop: frozenset[str]) -> list[str]:
    return [w for w in _WORD.findall(text.lower()) if w not in stop]


class Bm25Index:
    def __init__(self, docs: dict[str, list[str]], k1: float = 1.5, b: float = 0.75):
        self.docs, self.k1, self.b = docs, k1, b
        self.tf = {d: Counter(t) for d, t in docs.items()}
        self.len = {d: len(t) for d, t in docs.items()}
        self.avg = (sum(self.len.values()) / len(docs)) if docs else 0.0
        df: Counter = Counter()
        for c in self.tf.values():
            df.update(c.keys())
        n = len(docs)
        self.idf = {w: math.log(1.0 + (n - c + 0.5) / (c + 0.5)) for w, c in df.items()}

    def score(self, query: list[str], doc: str) -> float:
        tf, dl, s = self.tf[doc], self.len[doc], 0.0
        for w in set(query):
            f = tf.get(w, 0)
            if f:
                s += self.idf[w] * f * (self.k1 + 1) / (f + self.k1 * (1 - self.b + self.b * dl / (self.avg or 1.0)))
        return s


class PrecedentArm(Arm):
    kind = 'rank'

    def __init__(self, name: str = 'R2-precedent', *, index_path: Path | str = INDEX, neighbours: int = 5,
                 entries: list[dict] | None = None, hide_family: bool = True):
        self.name, self.neighbours, self.hide_family = name, neighbours, hide_family
        self.index_path = Path(index_path)
        self._entries = entries
        self._built = None

    def config(self) -> dict:
        import hashlib
        sha = hashlib.sha256(self.index_path.read_bytes()).hexdigest() if self._entries is None and self.index_path.exists() else 'inline'
        return {'method': 'bm25 over precedent text, article votes weighted by similarity', 'neighbours': self.neighbours,
                'leave_one_family_out': self.hide_family, 'index_sha256': sha, 'unmapped_statuses': sorted(UNMAPPED)}

    def _build(self, arts: dict[str, dict]):
        if self._built is not None:
            return self._built
        from engine.identify.corpus import STOP
        stop = frozenset(STOP)
        entries = self._entries if self._entries is not None else json.loads(self.index_path.read_text())
        docs: dict[str, list[str]] = {}
        mapped: dict[str, list[str]] = {}
        for e in entries:
            articles = []
            for a in e.get('articles_varied') or []:
                if a.get('status') in UNMAPPED:
                    continue
                m = _ART.search(a.get('ae2023_provision') or '')
                if m and m.group(1) in arts and m.group(1) not in articles:
                    articles.append(m.group(1))
            if not articles:
                continue
            text = ' '.join([e.get('title') or '', e.get('summary') or '', e.get('applies_to') or '',
                             ' '.join(e.get('conditions') or [])])
            docs[e['id']] = tokens(text, stop)
            mapped[e['id']] = articles
        self._built = (Bm25Index(docs), mapped, stop)
        return self._built

    def run(self, case: BenchCase, repeat: int, ctx: RunContext) -> RowDraft:
        t0 = time.monotonic()
        index, mapped, stop = self._build(ctx.arts)
        hidden = set(excluded_precedents({'id': case.id, 'family': case.family})) if (
            self.hide_family and case.dataset == 'public53') else set()
        q = tokens(case.query, stop)
        scored = sorted(((index.score(q, d), d) for d in index.docs if d not in hidden), reverse=True)
        top = [(s, d) for s, d in scored[:self.neighbours] if s > 0]
        weights: dict[str, float] = {}
        first_seen: dict[str, int] = {}
        best = top[0][0] if top else 1.0
        for rank, (s, d) in enumerate(top):
            for a in mapped[d]:
                weights[a] = weights.get(a, 0.0) + s / best
                first_seen.setdefault(a, rank)
        order = unique_in(sorted(weights, key=lambda a: (-weights[a], first_seen[a], a)), ctx.arts)
        top_weight = max(weights.values()) if weights else 1.0
        return RowDraft(order=order, probabilities={a: min(1.0, weights[a] / top_weight) for a in order},
                        latency_ms={'rank': (time.monotonic() - t0) * 1000},
                        notes={'matched_precedents': [d for _, d in top], 'hidden': sorted(hidden)})
