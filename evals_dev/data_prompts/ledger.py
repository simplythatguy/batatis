"""Provider response cache and cost ledger for runs of the real engine.

The engine's OpenAI calls all go through httpx.Client.post. `install()` wraps that one method: a
request body seen before returns its stored response (so reruns are cheap and repeatable), anything
else goes to the provider once and is stored. Every response's usage is recorded against the case
that made it, priced at OpenAI's Standard-tier list prices; a cached response still records what it
cost when it ran, so a workflow's cost does not depend on the cache. Elephant requests are not cached:
they are free but quota-limited, and their transport is not httpx.Client.post.
"""
from __future__ import annotations

import contextvars
import hashlib
import json
import os
import tempfile
import threading
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path

CACHE = Path(os.environ.get('DPE_CACHE') or Path(__file__).resolve().parents[2] / '.dpe-cache') / 'http'
OPENAI = 'https://api.openai.com/'
LONG_CONTEXT = 272_000
# USD per 1M tokens: input, cached input, output (developers.openai.com/api/docs/pricing, read 2026-10-25).
PRICES = {
    'gpt-6-luna': ((0.10, 0.01, 0.50), (0.20, 0.02, 0.75)),
    'gpt-6.1-sol': ((2.00, 0.10, 10.00), (4.00, 0.20, 15.00)),
}


@dataclass
class Call:
    model: str
    effort: str | None
    stage: str
    input_tokens: int
    cached_input_tokens: int
    output_tokens: int
    reasoning_tokens: int
    usd: float
    from_cache: bool
    seconds: float


@dataclass
class Ledger:
    calls: list[Call] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    def summary(self) -> dict:
        live = [c for c in self.calls if not c.from_cache]
        return {'calls': len(self.calls), 'live_calls': len(live),
                'usd': round(sum(c.usd for c in self.calls), 6), 'live_usd': round(sum(c.usd for c in live), 6),
                'input_tokens': sum(c.input_tokens for c in self.calls),
                'output_tokens': sum(c.output_tokens for c in self.calls),
                'reasoning_tokens': sum(c.reasoning_tokens for c in self.calls),
                'by_stage': _by(self.calls, 'stage'), 'by_model': _by(self.calls, 'model'),
                'errors': list(self.errors)}


def _by(calls: list[Call], key: str) -> dict:
    out: dict = {}
    for c in calls:
        row = out.setdefault(getattr(c, key) or 'none', {'calls': 0, 'usd': 0.0})
        row['calls'] += 1
        row['usd'] = round(row['usd'] + c.usd, 6)
    return out


CURRENT: contextvars.ContextVar[Ledger | None] = contextvars.ContextVar('dpe_ledger', default=None)
# Calls made from a thread that did not inherit the case's context (an engine thread pool) land here,
# so spend is never silently dropped. A run reports this total next to the per-case costs.
UNATTRIBUTED = Ledger()
_lock = threading.Lock()
_installed = False


def price(model: str, input_tokens: int, cached: int, output_tokens: int) -> float:
    short, long = PRICES.get(model, ((10.0, 10.0, 30.0), (10.0, 10.0, 30.0)))
    p_in, p_cached, p_out = long if input_tokens > LONG_CONTEXT else short
    fresh = max(0, input_tokens - cached)
    return (fresh * p_in + cached * p_cached + output_tokens * p_out) / 1_000_000


def _stage(body: dict) -> str:
    fmt = (body.get('response_format') or {}).get('json_schema') or {}
    if fmt.get('name'):
        return fmt['name']
    for message in body.get('messages') or []:
        if message.get('role') == 'system':
            return 'chat:' + hashlib.sha256(str(message.get('content'))[:400].encode()).hexdigest()[:8]
    return 'unknown'


def _record(body: dict, data: dict, from_cache: bool, seconds: float) -> None:
    ledger = CURRENT.get() or UNATTRIBUTED
    usage = data.get('usage') or {}
    model = body.get('model') or data.get('model') or 'unknown'
    tokens_in = int(usage.get('prompt_tokens') or 0)
    cached = int((usage.get('prompt_tokens_details') or {}).get('cached_tokens') or 0)
    tokens_out = int(usage.get('completion_tokens') or 0)
    reasoning = int((usage.get('completion_tokens_details') or {}).get('reasoning_tokens') or 0)
    ledger.calls.append(Call(model, body.get('reasoning_effort'), _stage(body), tokens_in, cached, tokens_out,
                             reasoning, price(model, tokens_in, cached, tokens_out), from_cache, round(seconds, 3)))


def _key(url: str, body) -> str:
    return hashlib.sha256(json.dumps({'url': url, 'body': body}, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def _load(key: str) -> dict | None:
    path = CACHE / key[:2] / f'{key}.json'
    if not path.exists():
        return None
    return json.loads(path.read_text())


def _store(key: str, value: dict) -> None:
    folder = CACHE / key[:2]
    folder.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=folder, suffix='.tmp')
    with os.fdopen(fd, 'w') as handle:
        json.dump(value, handle)
    os.replace(tmp, folder / f'{key}.json')


def install(*, read: bool = True) -> None:
    """Wrap httpx.Client.post once per process. read=False forces fresh provider calls (still stored)."""
    global _installed
    import httpx
    with _lock:
        if _installed:
            return
        original = httpx.Client.post

        def post(self, url, *args, **kwargs):
            target = str(url)
            if not target.startswith(OPENAI):
                return original(self, url, *args, **kwargs)
            body = kwargs.get('json')
            key = _key(target, body)
            hit = _load(key) if read else None
            if hit is not None:
                _record(body or {}, hit['response'], True, hit.get('seconds', 0.0))
                return httpx.Response(200, json=hit['response'], request=httpx.Request('POST', target))
            if (body or {}).get('service_tier') not in (None, 'default', 'auto'):
                raise RuntimeError('priority or flex service tiers are not used in these runs')
            started = time.monotonic()
            response = original(self, url, *args, **kwargs)
            seconds = time.monotonic() - started
            if response.status_code == 200:
                data = response.json()
                _store(key, {'response': data, 'seconds': round(seconds, 3)})
                _record(body or {}, data, False, seconds)
            else:
                ledger = CURRENT.get()
                if ledger is not None:
                    ledger.errors.append(f'openai HTTP {response.status_code}')
            return response

        httpx.Client.post = post
        _installed = True


def as_dict(ledger: Ledger) -> dict:
    return {'summary': ledger.summary(), 'calls': [asdict(c) for c in ledger.calls]}
