"""Provider-neutral judgments over article cards for exhaustive screening and reranking.

Ported from docs/research/2026-10-20-vision/jev-benchmark/scripts/jevrun.py (benchmark caching removed).
The default provider follows IdentifyConfig; explicit Jev uses its pinned model, never `jev-latest`.
"""
from __future__ import annotations

import json
import threading
import time
import contextvars
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from typing import Any, Callable, Mapping

from .corpus import card

JEV_MODEL = 'jev-1.13.0'
DECISIONS_MODEL = 'gpt-6-luna'
ELEPHANT_MODEL = 'baseten/elephant-1:free'
JEV_PROVIDER = 'typesafe'         # OpenRouter names the model differently (~typesafe/...); pin applies to TypeSafe
MAX_QUESTIONS = 400              # independent of state/card length (Decisions request limit)
GOVERN = ('Article {L} states a requirement that directly governs the situation described in `proposal`: '
          'the proposal must meet that requirement, relies on it, or departs from it.')
SELF_QUESTION = ('A complete alternative-solution application for the proposal in `proposal` must cite '
                 'this building-code article: {card}')

# ask(state, questions, timeout) -> {"answers": {name: {"noul": p, ...}}, "usage": {...}, "latency_ms": int}
Ask = Callable[[Any, Mapping[str, Mapping[str, Any]], float], Mapping[str, Any]]


class NoRetry(Exception):
    """A failure that retrying cannot fix (the spend gate is shut). Judge re-raises it at once,
    unless its code is one of TRANSIENT."""


TRANSIENT = frozenset({'timeout', 'network', 'rate_limited', 'http_500', 'http_502', 'http_503', 'http_504'})


def raw_jev_ask(model: str = JEV_MODEL) -> Ask:
    """Pinned TypeSafe model and verified Jev-only TLS. Use behind providers.metered_ask."""
    from .jev_runtime import raw_ask
    return raw_ask(model)


def jev_ask(model: str = JEV_MODEL) -> Ask:
    """The default adapter, metered: every request reserves and settles through engine.llm_gate.

    BATATIS_PROVIDER=fake uses the offline fake, so no request leaves the machine. Otherwise the gate
    refuses every request (before any network) unless BATATIS_LIVE=1 and the TypeSafe credential is
    present. Its verified TLS context is local to Jev and does not change other providers.
    """
    from engine import llm_gate
    from .providers import metered_ask
    if llm_gate.fake_providers():
        from .fakes import fake_jev_ask
        return metered_ask(fake_jev_ask(), model=model)
    return metered_ask(raw_jev_ask(model), model=model)


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
                 timeout: float = 60, attempts: int = 4, question: str = GOVERN,
                 model: str | None = None, method: str | None = None, question_style: str = 'shared'):
        self.config = None
        self.transports = None
        if ask is None:
            from .config import load_config
            from .providers import scoring_ask, transports
            config = load_config()
            self.config = config
            method, model, chars = config.screen, config.screen_model, config.card_chars
            question_style = config.question_style if method == 'elephant' else 'shared'
            self.transports = transports(scoring={config.screen, config.rerank})
            ask = scoring_ask(self.transports, method)
        # Metered adapters carry their identity through the injectable Ask seam. Plain
        # legacy test adapters keep the historical Jev identity unless specified.
        self.ask = ask
        self.model = model or getattr(ask, 'model', JEV_MODEL)
        self.method = method or getattr(ask, 'method', 'jev')
        if question_style not in ('shared', 'self') or (question_style == 'self' and self.method != 'elephant'):
            raise ValueError('self question style requires the supported scoring method')
        self.question_style = question_style
        self.chars, self.max_state, self.workers = chars, max_state, workers
        self.timeout, self.attempts, self.question = timeout, (1 if self.method == 'elephant' else attempts), question
        self.usage = Usage()
        self._lock = threading.Lock()

    def batches(self, query: str, arts: Mapping[str, dict], ids: list[str]) -> list[list[tuple[str, str]]]:
        if self.method == 'elephant':
            from .elephant_runtime import ElephantError, request_bytes
            out, cur = [], []
            for article in ids:
                candidate = (article, card(arts[article], self.chars))
                trial = [*cur, candidate]
                try:
                    request_bytes(*self._payload(query, trial), model=self.model)
                except ElephantError as error:
                    if error.code != 'request_too_large' or not cur:
                        raise
                    out.append(cur)
                    cur = [candidate]
                    request_bytes(*self._payload(query, cur), model=self.model)
                else:
                    cur = trial
            if cur:
                out.append(cur)
            return out
        out, cur, size = [], [], 0
        base = len(json.dumps(query)) + 300
        for a in ids:
            t = card(arts[a], self.chars)
            n = len(json.dumps(t)) + 12
            if cur and (base + size + n > self.max_state or len(cur) >= MAX_QUESTIONS):
                out.append(cur)
                cur, size = [], 0
            cur.append((a, t))
            size += n
        if cur:
            out.append(cur)
        return out

    def _payload(self, query, batch):
        if self.question_style == 'self':
            return {'proposal': query}, {f'q{i}': noul(SELF_QUESTION.format(card=text))
                                         for i, (_, text) in enumerate(batch)}
        state = {'proposal': query, 'articles': {f'A{i}': t for i, (_, t) in enumerate(batch)}}
        qs = {f'q{i}': noul(self.question.format(L=f'A{i}')) for i in range(len(batch))}
        return state, qs

    def judge(self, query: str, arts: Mapping[str, dict], ids: list[str]) -> dict[str, float]:
        probs: dict[str, float] = {}

        def run(batch):
            state, qs = self._payload(query, batch)
            last_error = None
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
                except NoRetry as error:
                    with self._lock:
                        self.usage.errors += 1
                    # A dropped connection, a timeout, a rate limit or a server error says nothing about the
                    # request; one of those may be retried within `attempts`. Anything else stops at once.
                    if getattr(error, 'code', None) not in TRANSIENT or attempt + 1 >= self.attempts:
                        raise
                    last_error = error
                    time.sleep(1.5 * (attempt + 1))
                except Exception as error:
                    last_error = error
                    with self._lock:
                        self.usage.errors += 1
                    status = getattr(getattr(error, 'response', None), 'status_code', None)
                    if isinstance(status, int) and 400 <= status < 500 and status != 429:
                        raise                       # a refused request fails the same way every time
                    if attempt + 1 < self.attempts:
                        time.sleep(1.5 * (attempt + 1))
            raise RuntimeError('scoring batch failed after retries') from last_error

        batches = self.batches(query, arts, ids)
        if self.method == 'elephant':
            # Free routing is quota-limited. No queued fan-out may keep sending
            # after a 429/timeout/malformed batch; partial results never return.
            for batch in batches:
                run(batch)
        elif len(batches) == 1:
            run(batches[0])
        elif batches:
            # Each batch runs in a copy of this request's context, so its AI access check sees the account.
            contexts = [contextvars.copy_context() for _ in batches]
            with ThreadPoolExecutor(max_workers=self.workers) as pool:
                list(pool.map(lambda context, batch: context.run(run, batch), contexts, batches))
        return {a: probs[a] for a in ids}
