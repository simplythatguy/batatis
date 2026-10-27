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
import shutil
import tempfile
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass, field, replace
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit

from evals_dev.file_lock import file_lock

CACHE = Path(os.environ.get('DPE_CACHE') or Path(__file__).resolve().parents[2] / '.dpe-cache') / 'http'
ATTEMPTS = CACHE.parent / 'attempts.jsonl'
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
    usd: float | None
    from_cache: bool
    seconds: float
    request_hash: str | None = None
    status: str = 'succeeded'


@dataclass
class Ledger:
    calls: list[Call] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    def summary(self) -> dict:
        live = [c for c in self.calls if not c.from_cache]
        return {'calls': len(self.calls), 'live_calls': len(live),
                'usd': round(sum(c.usd for c in self.calls if c.usd is not None), 6),
                'live_usd': round(sum(c.usd for c in live if c.usd is not None), 6),
                'unknown_cost_attempts': sum(c.usd is None for c in self.calls),
                'live_unknown_cost_attempts': sum(c.usd is None for c in live),
                'input_tokens': sum(c.input_tokens for c in self.calls),
                'output_tokens': sum(c.output_tokens for c in self.calls),
                'reasoning_tokens': sum(c.reasoning_tokens for c in self.calls),
                'by_stage': _by(self.calls, 'stage'), 'by_model': _by(self.calls, 'model'),
                'errors': list(self.errors)}


def _by(calls: list[Call], key: str) -> dict:
    out: dict = {}
    for c in calls:
        row = out.setdefault(getattr(c, key) or 'none', {'calls': 0, 'usd': 0.0, 'unknown_cost_attempts': 0})
        row['calls'] += 1
        row['usd'] = round(row['usd'] + (c.usd if c.usd is not None else 0.0), 6)
        row['unknown_cost_attempts'] += c.usd is None
    return out


CURRENT: contextvars.ContextVar[Ledger | None] = contextvars.ContextVar('dpe_ledger', default=None)
# Calls made from a thread that did not inherit the case's context (an engine thread pool) land here,
# so spend is never silently dropped. A run reports this total next to the per-case costs.
UNATTRIBUTED = Ledger()
_lock = threading.Lock()
_attempt_lock = threading.Lock()
_installed = False


class CaseThreadPoolExecutor(ThreadPoolExecutor):
    """Carry the submitting case's ledger into each engine scoring batch."""

    def submit(self, fn, /, *args, **kwargs):
        context = contextvars.copy_context()
        return super().submit(context.run, fn, *args, **kwargs)


def attempt_event(event: str, *, request_hash: str, stage: str, model: str, effort: str,
                  attempt_id: str | None = None, **metadata) -> str:
    """Append counts/status only, locked across processes. A start without a finish has unknown cost.

    Callers must never pass headers, request/response bodies, exception messages, or document text.
    """
    attempt_id = attempt_id or uuid.uuid4().hex
    row = {'event': event, 'attempt_id': attempt_id, 'request_hash': request_hash, 'stage': stage,
           'model': model, 'effort': effort, 'at': datetime.now(timezone.utc).isoformat(), **metadata}
    ATTEMPTS.parent.mkdir(parents=True, exist_ok=True)
    with _attempt_lock, ATTEMPTS.open('a') as handle, file_lock(handle):
        handle.write(json.dumps(row, separators=(',', ':')) + '\n')
        handle.flush()
        os.fsync(handle.fileno())
    return attempt_id


def replay(calls: list[dict], book: Ledger) -> None:
    """Keep original workflow prices while attributing zero fresh provider spend to a cache hit."""
    book.calls.extend(replace(Call(**row), from_cache=True) for row in calls)


def write_artifact(path: Path, text: str) -> None:
    """Atomically replace an artifact, retaining the old bytes in history before any replacement."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, suffix='.tmp')
    try:
        with os.fdopen(fd, 'w') as handle:
            handle.write(text)
        if path.exists():
            history = path.parent / 'history'
            history.mkdir(exist_ok=True)
            shutil.copy2(path, history / f'{path.stem}.{uuid.uuid4().hex}{path.suffix}')
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


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


def _record(body: dict, data: dict, from_cache: bool, seconds: float, request_hash=None,
            status='succeeded', legacy=False, endpoint=None) -> Call:
    book = CURRENT.get() or UNATTRIBUTED
    usage = data.get('usage') if isinstance(data, dict) else None
    decisions = endpoint == '/v1/decisions'
    input_key, output_key = ('input_tokens', 'output_tokens') if decisions else ('prompt_tokens', 'completion_tokens')
    valid = isinstance(usage, dict) and all(type(usage.get(k)) is int and usage[k] >= 0
                                           for k in (input_key, output_key))
    valid = valid and endpoint in (None, '/v1/chat/completions', '/v1/decisions')
    usage = usage if isinstance(usage, dict) else {}
    count = lambda n: n if type(n) is int and n >= 0 else 0
    tokens_in, tokens_out = count(usage.get(input_key)), count(usage.get(output_key))
    if decisions or 'total_tokens' in usage:
        valid = valid and type(usage.get('total_tokens')) is int and usage['total_tokens'] == tokens_in + tokens_out
    counts = {}
    for field, names, total in (
        (input_key + '_details', ('cached_tokens', 'cache_write_tokens') if decisions else ('cached_tokens',), tokens_in),
        (output_key + '_details', ('reasoning_tokens',), tokens_out),
    ):
        details = usage.get(field)
        if decisions or field in usage:
            valid = valid and isinstance(details, dict)
        details = details if isinstance(details, dict) else {}
        for name in names:
            value = details.get(name)
            if decisions or name in details:
                valid = valid and type(value) is int and 0 <= value <= total
            counts[name] = count(value)
    cached, reasoning = counts['cached_tokens'], counts['reasoning_tokens']
    valid = valid and cached + counts.get('cache_write_tokens', 0) <= tokens_in
    model = body.get('model') or 'unknown'
    usd = price(model, tokens_in, cached, tokens_out) if valid and not legacy else None
    call = Call(model, body.get('reasoning_effort'), _stage(body), tokens_in, cached, tokens_out,
                reasoning, usd, from_cache, round(seconds, 3), request_hash, status)
    book.calls.append(call)
    return call


def _key(url: str, body) -> str:
    return hashlib.sha256(json.dumps({'url': url, 'body': body}, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def _load(key: str) -> dict | None:
    path = CACHE / key[:2] / f'{key}.json'
    if not path.exists():
        return None
    return json.loads(path.read_text())


def _store(key: str, value: dict) -> None:
    folder = CACHE / key[:2]
    write_artifact(folder / f'{key}.json', json.dumps(value))


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
                book = CURRENT.get() or UNATTRIBUTED
                if 'attempt_calls' in hit:
                    replay(hit['attempt_calls'], book)
                else:
                    _record(body or {}, hit['response'], True, hit.get('seconds', 0.0), key,
                            'legacy_unverified', legacy=True, endpoint=urlsplit(target).path)
                attempt_event('cache_hit', request_hash=key, stage=_stage(body or {}),
                              model=(body or {}).get('model', 'unknown'), effort=(body or {}).get('reasoning_effort'),
                              dispatched=False, status='cache_hit')
                return httpx.Response(200, json=hit['response'], request=httpx.Request('POST', target))
            if (body or {}).get('service_tier') not in (None, 'default', 'auto'):
                raise RuntimeError('priority or flex service tiers are not used in these runs')
            started = time.monotonic()
            attempt_id = attempt_event('attempt_started', request_hash=key, stage=_stage(body or {}),
                                       model=(body or {}).get('model', 'unknown'),
                                       effort=(body or {}).get('reasoning_effort'), dispatched=True,
                                       status='dispatching', usd=None, cost_status='unknown')
            response, data, status = None, {}, 'transport_error'
            try:
                response = original(self, url, *args, **kwargs)
                status = 'http_error' if response.status_code != 200 else 'invalid_response_json'
                try:
                    data = response.json()
                except ValueError:
                    if response.status_code == 200:
                        raise
                if response.status_code == 200:
                    status = 'succeeded'
                return response
            finally:
                seconds = time.monotonic() - started
                call = _record(body or {}, data, False, seconds, key, status, endpoint=urlsplit(target).path)
                attempt_event('attempt_finished', attempt_id=attempt_id, request_hash=key, stage=call.stage,
                              model=call.model, effort=call.effort, dispatched=True, status=status,
                              http_status=response.status_code if response is not None else None,
                              seconds=seconds, input_tokens=call.input_tokens, output_tokens=call.output_tokens,
                              usd=call.usd, cost_status='priced' if call.usd is not None else 'unknown')
                if status == 'succeeded':
                    chain = []
                    for prior in reversed((CURRENT.get() or UNATTRIBUTED).calls):
                        if prior.request_hash != key:
                            continue
                        if chain and (prior.from_cache or prior.status == 'succeeded'):
                            break
                        chain.append(asdict(prior))
                    _store(key, {'response': data, 'seconds': round(seconds, 3),
                                 'attempt_calls': list(reversed(chain))})

        httpx.Client.post = post
        _installed = True


def as_dict(ledger: Ledger) -> dict:
    return {'summary': ledger.summary(), 'calls': [asdict(c) for c in ledger.calls]}
