"""Jev judgments over article cards: the exhaustive screen and the one-request rerank share this module.

Ported from docs/research/2026-10-20-vision/jev-benchmark/scripts/jevrun.py (benchmark caching removed).
The decision model is pinned: JEV_MODEL is sent as the request's `model`, never `jev-latest`.
"""
from __future__ import annotations

import json
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from typing import Any, Callable, Mapping

from ..llm_gate import OfflineLLM
from .corpus import card

JEV_MODEL = 'jev-1.13.0'
JEV_PROVIDER = 'typesafe'         # OpenRouter names the model differently (~typesafe/...); pin applies to TypeSafe
GOVERN = ('Article {L} states a requirement that directly governs the situation described in `proposal`: '
          'the proposal must meet that requirement, relies on it, or departs from it.')

# ask(state, questions, timeout) -> {"answers": {name: {"noul": p, ...}}, "usage": {...}, "latency_ms": int}
Ask = Callable[[Any, Mapping[str, Mapping[str, Any]], float], Mapping[str, Any]]


def jev_ask(model: str = JEV_MODEL) -> Ask:
    """The live adapter: vendored jevkit client, pinned model. Needs SSL_CERT_FILE=/etc/ssl/cert.pem on this Mac.

    The call goes through llm_gate. Offline (the default) raises OfflineLLM before any network use.
    """
    from ..llm_gate import OfflineLLM, authorize, record
    from .jevkit import client

    def ask(state, questions, timeout):
        encoded = json.dumps(state)
        decision = authorize(model=model, max_input_tokens=max(1, len(encoded) // 4),
                             max_output_tokens=200 * max(1, len(questions)))
        if not decision.allowed:
            raise OfflineLLM(decision.source)
        rep = client.ask(state, questions, timeout=timeout, model=model, provider=JEV_PROVIDER)
        usage = rep.get('usage') or {}
        record(model=model, input_tokens=int(usage.get('input_tokens') or 0),
               output_tokens=int(usage.get('output_tokens') or 0), reserved_usd=decision.reserved_usd)
        return rep
    return ask


def noul(text: str) -> dict:
    return {'type': 'noul', 'instructions': text}


@dataclass
class Usage:
    requests: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    errors: int = 0
    latency_ms: list[float] = field(default_factory=list)

    def summary(self) -> dict:
        lat = sorted(self.latency_ms)
        return {'requests': self.requests, 'input_tokens': self.input_tokens, 'output_tokens': self.output_tokens,
                'errors': self.errors, 'latency_p50_ms': lat[len(lat) // 2] if lat else None,
                'latency_max_ms': lat[-1] if lat else None}


class Judge:
    """Probability, per article, that it governs the proposal. One state per batch of article cards."""

    def __init__(self, ask: Ask | None = None, *, chars: int = 700, max_state: int = 56000, workers: int = 8,
                 timeout: float = 60, attempts: int = 4, question: str = GOVERN):
        self.ask = ask or jev_ask()
        self.chars, self.max_state, self.workers = chars, max_state, workers
        self.timeout, self.attempts, self.question = timeout, attempts, question
        self.usage = Usage()
        self._lock = threading.Lock()

    def batches(self, query: str, arts: Mapping[str, dict], ids: list[str]) -> list[list[tuple[str, str]]]:
        out, cur, size = [], [], 0
        base = len(json.dumps(query)) + 300
        for a in ids:
            t = card(arts[a], self.chars)
            n = len(json.dumps(t)) + 12
            if cur and base + size + n > self.max_state:
                out.append(cur)
                cur, size = [], 0
            cur.append((a, t))
            size += n
        if cur:
            out.append(cur)
        return out

    def judge(self, query: str, arts: Mapping[str, dict], ids: list[str]) -> dict[str, float]:
        probs: dict[str, float] = {}

        def run(batch):
            state = {'proposal': query, 'articles': {f'A{i}': t for i, (_, t) in enumerate(batch)}}
            qs = {f'q{i}': noul(self.question.format(L=f'A{i}')) for i in range(len(batch))}
            for attempt in range(self.attempts):
                try:
                    t0 = time.monotonic()
                    rep = self.ask(state, qs, self.timeout)
                    dt = (time.monotonic() - t0) * 1000
                    with self._lock:
                        u = rep.get('usage') or {}
                        self.usage.requests += 1
                        self.usage.input_tokens += u.get('input_tokens', 0)
                        self.usage.output_tokens += u.get('output_tokens', 0)
                        self.usage.latency_ms.append(dt)
                        for i, (a, _) in enumerate(batch):
                            probs[a] = rep['answers'][f'q{i}']['noul']
                    return
                except OfflineLLM:
                    raise
                except Exception:
                    with self._lock:
                        self.usage.errors += 1
                    if attempt + 1 < self.attempts:
                        time.sleep(1.5 * (attempt + 1))
            raise RuntimeError('Jev batch failed after retries')

        batches = self.batches(query, arts, ids)
        if len(batches) == 1:
            run(batches[0])
        elif batches:
            with ThreadPoolExecutor(max_workers=self.workers) as pool:
                list(pool.map(run, batches))
        return {a: probs[a] for a in ids}
