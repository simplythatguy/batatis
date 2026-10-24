"""Explicit-live, cached, bounded benchmark transports (never imported by the app).

Offline is the process default, including when credentials exist. CLI callers must opt in with
live_mode(True). A cache hit never reads credentials or quota. OpenAI requests reserve a conservative
maximum charge in a durable ledger before dispatch; unknown failures/crashes retain that charge.
Identical requests and cap claims serialize across threads/processes; at most three independent
OpenAI calls dispatch concurrently per process. Every invocation makes at most one provider attempt.
Elephant keeps the engine's exact free route and response validation.
"""
from __future__ import annotations

import json
import math
import os
import threading
import time
import uuid
from contextlib import contextmanager
from datetime import date, timedelta
from decimal import Decimal, ROUND_CEILING
from pathlib import Path

from .cache import CacheError, Store, request_key

ENV_FILE = Path(os.environ.get('BENCH_ENV_FILE') or Path(__file__).resolve().parents[2] / '.env')
KEY_URL = 'https://openrouter.ai/api/v1/key'
MIN_INTERVAL = 3.2
_live_enabled = False
_mode_lock = threading.RLock()
_openai_slots = threading.BoundedSemaphore(3)
_SAFE_ERRORS = frozenset({
    'internal_error', 'timeout', 'transport_error', 'provider_error', 'invalid_response', 'invalid_request',
    'io_error', 'cache_error', 'live_disabled', 'budget_exhausted', 'quota_unavailable', 'invalid_budget',
    'credential_absent', 'auth_failed', 'quota_exhausted', 'rate_limited', 'provider_unavailable',
    'request_too_large', 'response_too_large', 'unexpected_model', 'invalid_usage', 'invalid_answer',
    'invalid_distribution', 'invalid_choice', 'invalid_score', 'unexpected_answers', 'invalid_question',
    'duplicate_field', 'malformed', 'corpus_changed',
})


class ProviderFailure(RuntimeError):
    def __init__(self, code: str = 'internal_error'):
        self.code = code if code in _SAFE_ERRORS else 'internal_error'
        super().__init__(self.code)


class BudgetExhausted(ProviderFailure):
    def __init__(self, code: str = 'budget_exhausted'):
        super().__init__(code if code in _SAFE_ERRORS else 'budget_exhausted')


def error_tag(error: Exception) -> str:
    """Closed vocabulary only: never expose exception messages, URLs, bodies, paths or class names."""
    if isinstance(error, ProviderFailure):
        return error.code
    if isinstance(error, CacheError):
        return 'cache_error'
    from engine.identify.elephant_runtime import ElephantError
    from engine.identify.providers import UnreadableResponse
    import httpx
    if isinstance(error, ElephantError):
        return error.code if error.code in _SAFE_ERRORS else 'provider_error'
    if isinstance(error, (TimeoutError, httpx.TimeoutException)):
        return 'timeout'
    if isinstance(error, httpx.TransportError):
        return 'transport_error'
    if isinstance(error, httpx.HTTPStatusError):
        return 'rate_limited' if error.response.status_code == 429 else 'provider_error'
    if isinstance(error, (UnreadableResponse, json.JSONDecodeError)):
        return 'invalid_response'
    if isinstance(error, OSError):
        return 'io_error'
    return 'internal_error'


@contextmanager
def live_mode(enabled: bool):
    """Process-wide so ThreadPoolExecutor workers share the CLI's explicit choice."""
    global _live_enabled
    with _mode_lock:
        previous = _live_enabled
        _live_enabled = bool(enabled)
        try:
            yield
        finally:
            _live_enabled = previous


def _require_live(allowed: bool | None = None) -> None:
    if not _live_enabled or allowed is False:
        raise BudgetExhausted('live_disabled')


def load_keys(names=('OPENROUTER_API_KEY', 'OPENAI_API_KEY')) -> dict[str, bool]:
    """Read this worktree's .env only in explicit live mode; report presence only."""
    _require_live()
    env_file = Path(os.environ.get('BENCH_ENV_FILE') or ENV_FILE)
    if env_file.is_file():
        for line in env_file.read_text(encoding='utf-8').splitlines():
            line = line.strip()
            if not line or line.startswith('#') or '=' not in line:
                continue
            name, value = line.split('=', 1)
            name = name.strip().removeprefix('export ').strip()
            if name in names and not os.environ.get(name):
                value = value.strip().strip('"').strip("'")
                if value:
                    os.environ[name] = value
    return {name: bool(os.environ.get(name)) for name in names}


def elephant_quota() -> dict:
    """One bounded quota request, allowed only in explicit live mode. No retries or redirects."""
    _require_live()
    load_keys(('OPENROUTER_API_KEY',))
    import certifi
    import httpx
    key = os.environ.get('OPENROUTER_API_KEY') or ''
    if not key:
        raise ProviderFailure('credential_absent')
    try:
        with httpx.Client(verify=certifi.where(), trust_env=False, follow_redirects=False, timeout=20) as client:
            response = client.get(KEY_URL, headers={'Authorization': 'Bearer ' + key})
            response.raise_for_status()
            if len(response.content) > 100_000:
                raise ProviderFailure('response_too_large')
            quota = (response.json().get('data') or {}).get('free_model_daily_requests') or {}
            return {k: quota.get(k) for k in ('used', 'limit', 'remaining')}
    except Exception as error:
        raise ProviderFailure(error_tag(error)) from None


def _utc_day(stamp: float | None = None) -> str:
    return time.strftime('%Y-%m-%d', time.gmtime(time.time() if stamp is None else stamp))


def _reservation_days(row: dict) -> set[str]:
    """Hold admission/dispatch dates and the following UTC day, including persistence latency.

    Aggregate counters cannot acknowledge an individual attempt. Carrying every hold
    through the next day is deliberately conservative and avoids guessing a save-time bound.
    """
    days = {row['quota_day']} if isinstance(row.get('quota_day'), str) else set()
    stamp = row.get('started_at')
    if type(stamp) in (int, float) and math.isfinite(stamp):
        days.add(_utc_day(stamp))
    if not days:
        return {_utc_day()}
    try:
        return days | {(date.fromisoformat(day) + timedelta(days=1)).isoformat() for day in days}
    except ValueError:
        return {_utc_day()}


class ElephantBudget:
    """Keep every local daily attempt ambiguous against the remote aggregate.

    Even acknowledged work is counted again: deliberate conservative under-use protects
    the reserve when unrelated usage can mask pending local attempts. Only a known older
    UTC day releases a reservation.
    """

    def __init__(self, reserve: int = 3, max_calls: int | None = None):
        if type(reserve) is not int or reserve < 0 or (max_calls is not None and
                (type(max_calls) is not int or max_calls < 0)):
            raise BudgetExhausted('invalid_budget')
        self.reserve = reserve
        self.max_calls = 50 if max_calls is None else max_calls
        self.sent = 0
        self.remaining: int | None = None
        self._last = 0.0
        self._lock = threading.Lock()

    def refresh(self) -> int:
        _require_live()
        remaining = elephant_quota().get('remaining')
        if type(remaining) is not int or remaining < 0:
            raise BudgetExhausted('quota_unavailable')
        self.remaining = remaining
        return remaining

    def take(self, *, spend: Store | None = None) -> dict:
        """Admission under the transport's shared claim; return its durable quota reservation."""
        _require_live()
        with self._lock:
            # Exhausted local budgets never contact the quota endpoint.
            if self.sent >= self.max_calls:
                raise BudgetExhausted()
            wait = MIN_INTERVAL - (time.monotonic() - self._last)
            if wait > 0:
                time.sleep(wait)
            day = _utc_day()
            self.refresh()
            if _utc_day() != day:
                raise BudgetExhausted('quota_unavailable')
            ledger = spend if spend is not None else _stores()[2]
            previous = [r['response'] for r in ledger.rows()
                        if r['response'].get('provider') == 'elephant'
                        and day in _reservation_days(r['response'])]
            self.remaining -= len(previous)
            for index, row in enumerate(previous):
                after = row.get('quota_remaining_after')
                admission_day = row.get('quota_day') or _utc_day(row.get('started_at'))
                if type(after) is int and after >= 0 and admission_day == day:
                    # A prior ceiling also loses every reservation made after it, including
                    # legacy rows. Remote aggregate changes never release a local attempt.
                    later_attempts = len(previous) - index - 1
                    self.remaining = min(self.remaining, after - later_attempts)
            if self.remaining <= self.reserve:
                raise BudgetExhausted('quota_exhausted')
            self._last = time.monotonic()
            self.sent += 1
            self.remaining -= 1
            return {'quota_day': day, 'quota_remaining_after': self.remaining}


_elephant_store: Store | None = None
_openai_store: Store | None = None
_spend: Store | None = None
_stores_lock = threading.Lock()


def _stores():
    global _elephant_store, _openai_store, _spend
    with _stores_lock:
        if _elephant_store is None:
            _elephant_store, _openai_store, _spend = Store('elephant'), Store('openai'), Store('spend')
    return _elephant_store, _openai_store, _spend


def _price(model: str, input_tokens: int, output_tokens: int) -> float:
    from engine.llm_gate import CONSERVATIVE, PRICES
    inn, out = PRICES.get(model, CONSERVATIVE)
    return float((Decimal(input_tokens) * inn + Decimal(output_tokens) * out) / Decimal(1_000_000))


def _money(value) -> Decimal:
    amount = Decimal(str(value))
    if not amount.is_finite() or amount < 0:
        raise BudgetExhausted('invalid_budget')
    return amount.quantize(Decimal('0.000001'), rounding=ROUND_CEILING)


def openai_spent() -> float:
    _, _, spend = _stores()
    return float(sum((_money(row['response']['usd']) for row in spend.rows()), Decimal(0)))


def _usage(value) -> dict | None:
    # The engine's raw transport defaults absent counts to zero. A nonempty JSON request
    # needs input and generated tokens; either zero is untrusted, never a free settlement.
    if not isinstance(value, dict) or any(type(value.get(k)) is not int or value[k] <= 0
                                         for k in ('input_tokens', 'output_tokens')):
        return None
    return {k: value[k] for k in ('input_tokens', 'output_tokens')}


def openai_json(name: str, schema: dict, system: str, user: str, *, model: str = 'gpt-6-luna',
                effort: str | None = 'medium', max_output_tokens: int = 16000, timeout: float = 900,
                tag: str = '', live: bool | None = None) -> tuple[dict, dict]:
    """Cache replay or one reserved, bounded attempt. live=False always narrows to cache-only.

    Keys keep the original full request identity so previously saved answers remain replayable.
    The complete TOC/full article text is in system/user; changed corpus projections change this key.
    """
    _, store, spend = _stores()
    request = {'name': name, 'schema': schema, 'system': system, 'user': user, 'model': model,
               'effort': effort, 'max_output_tokens': max_output_tokens}
    key = request_key('openai', request)
    hit = store.get(key)
    if hit is not None:
        return hit['payload'], hit['usage']
    _require_live(live)
    if type(max_output_tokens) is not int or max_output_tokens < 1 or type(timeout) not in (int, float) \
            or not math.isfinite(timeout) or not 0 < timeout <= 900:
        raise ProviderFailure('invalid_request')
    with store.claim(key), _openai_slots:
        hit = store.get(key)
        if hit is not None:
            return hit['payload'], hit['usage']
        with spend.claim('openai-budget'):
            _require_live(live)
            try:
                cap = Decimal(os.environ.get('BENCH_OPENAI_CAP_USD', '6'))
                if not cap.is_finite() or cap < 0:
                    raise BudgetExhausted('invalid_budget')
            except (ValueError, ArithmeticError):
                raise BudgetExhausted('invalid_budget') from None
            # One token per escaped UTF-8 byte + framing conservatively bounds the wire request.
            input_bound = len(json.dumps(request, ensure_ascii=True).encode('utf-8')) + 4096
            reservation = _money(_price(model, input_bound, max_output_tokens))
            if _money(openai_spent()) + reservation > cap:
                raise BudgetExhausted()
            load_keys(('OPENAI_API_KEY',))
            from engine.identify.providers import raw_openai_json
            attempt = uuid.uuid4().hex
            entry = {'usd': float(reservation), 'reserved_usd': float(reservation), 'provider': 'openai',
                     'model': model, 'tag': tag, 'effort': effort, 'state': 'reserved', 'unknown_usage': True}
            spend.put(attempt, entry)
        # The durable reservation is already visible to every other worker/process. Dispatch outside
        # the budget claim, then reacquire it only to replace the reservation with its final charge.
        t0, usage = time.monotonic(), None
        try:
            payload, usage = raw_openai_json(name, schema, system, user, model=model,
                                             max_output_tokens=max_output_tokens, effort=effort, timeout=timeout)
            counts = _usage(usage)
            if not isinstance(payload, dict) or counts is None:
                raise ProviderFailure('invalid_response')
            usd = _money(_price(model, counts['input_tokens'], counts['output_tokens']))
            public_usage = {**counts, 'returned_model': usage.get('returned_model'), 'usd': float(usd),
                            'seconds': round(time.monotonic() - t0, 2)}
            with spend.claim('openai-budget'):
                spend.put(attempt, {**entry, **counts, 'usd': float(usd), 'unknown_usage': False,
                                    'state': 'completed', 'failed': False})
            store.put(key, {'payload': payload, 'usage': public_usage}, tag=tag)
            return payload, public_usage
        except Exception as error:
            counts = _usage(getattr(error, 'usage', None)) or _usage(usage)
            usd = (_money(_price(model, counts['input_tokens'], counts['output_tokens']))
                   if counts is not None else reservation)
            code = error_tag(error)
            with spend.claim('openai-budget'):
                spend.put(attempt, {**entry, **(counts or {}), 'usd': float(usd), 'state': 'failed',
                                    'failed': True, 'unknown_usage': counts is None, 'error': code})
            failure = ProviderFailure(code)
            failure.usage = {**(counts or {}), 'usd': float(usd), 'unknown_usage': counts is None,
                             'seconds': round(time.monotonic() - t0, 2)}
            raise failure from None


def elephant_cached(state, questions) -> dict | None:
    store, _, _ = _stores()
    from engine.identify import elephant_runtime as er
    body = er.request_bytes(state, questions)
    hit = store.get(request_key('elephant', body.decode('utf-8')))
    return None if hit is None else er._validate(hit, questions)


def _elephant_call(key, state, questions, *, budget, timeout, tag, send, size, unbounded=False):
    from engine.identify import elephant_runtime as er
    store, _, spend = _stores()
    hit = store.get(key)
    if hit is not None:
        return er._validate(hit, questions)
    if budget is None:
        raise BudgetExhausted('live_disabled')
    _require_live()
    with store.claim(key):
        hit = store.get(key)
        if hit is not None:
            return er._validate(hit, questions)
        # Cross-process serialization also keeps the engine's one-active-call invariant.
        with spend.claim('elephant-budget'):
            _require_live()
            previous = [r['response'] for r in spend.rows() if r['response'].get('provider') == 'elephant']
            if previous:
                wait = MIN_INTERVAL - (time.time() - max(r.get('started_at', 0) for r in previous))
                if wait > 0:
                    time.sleep(wait)
            quota = budget.take(spend=spend)
            load_keys(('OPENROUTER_API_KEY',))
            attempt, t0 = uuid.uuid4().hex, time.monotonic()
            entry = {'usd': 0, 'provider': 'elephant', 'model': er.ELEPHANT_MODEL, 'tag': tag,
                     'started_at': time.time(), 'state': 'reserved', 'unknown_usage': True, **quota}
            spend.put(attempt, entry)
            if _utc_day() != entry['quota_day']:
                spend.put(attempt, {**entry, 'state': 'cancelled_before_dispatch', 'unknown_usage': False,
                                    'error': 'quota_unavailable'})
                raise BudgetExhausted('quota_unavailable')
            try:
                result = send()
                result = er._validate(result, questions)
                spend.put(attempt, {**entry, **result['usage'], 'unknown_usage': False,
                                    'state': 'completed', 'failed': False})
                store.put(key, result, tag=tag, seconds=round(time.monotonic() - t0, 2), bytes=size,
                          questions=len(questions), unbounded=unbounded)
                return result
            except Exception as error:
                usage = er._usage(getattr(error, 'usage', None))
                code = error_tag(error)
                spend.put(attempt, {**entry, **(usage or {}), 'unknown_usage': usage is None,
                                    'state': 'failed', 'failed': True, 'error': code})
                failure = ProviderFailure(code)
                failure.usage = {**(usage or {}), 'usd': 0, 'unknown_usage': usage is None,
                                 'seconds': round(time.monotonic() - t0, 2)}
                raise failure from None


def elephant_ask(state, questions, *, budget: ElephantBudget | None, timeout: float = 60, tag: str = '') -> dict:
    from engine.identify import elephant_runtime as er
    body = er.request_bytes(state, questions)
    er._deadline(timeout)
    return _elephant_call(request_key('elephant', body.decode('utf-8')), state, questions, budget=budget,
                          timeout=timeout, tag=tag, send=lambda: er.raw_ask()(state, questions, timeout), size=len(body))


def unbounded_key(state, questions) -> str:
    from engine.identify import elephant_runtime as er
    body = json.dumps({'model': er.ELEPHANT_MODEL, 'state': state, 'questions': questions, 'provider': er.ROUTING},
                      ensure_ascii=False, allow_nan=False, separators=(',', ':'))
    return request_key('elephant-unbounded', body)


def elephant_ask_unbounded(state, questions, *, budget: ElephantBudget | None, timeout: float = 60,
                           tag: str = '') -> dict:
    """Explicit-live context probe only; budget=None remains cache-only. No retries or fallback."""
    from engine.identify import elephant_runtime as er
    er._deadline(timeout)
    body = json.dumps({'model': er.ELEPHANT_MODEL, 'state': state, 'questions': questions, 'provider': er.ROUTING},
                      ensure_ascii=False, allow_nan=False, separators=(',', ':')).encode('utf-8')

    def send():
        deadline = time.monotonic() + timeout
        status, raw = er._post_once(body, {'Authorization': 'Bearer ' + os.environ.get('OPENROUTER_API_KEY', ''),
                                         'Content-Type': 'application/json'}, timeout)
        if len(raw) > er.MAX_RESPONSE_BYTES:
            raise ProviderFailure('response_too_large')
        payload = json.loads(raw, object_pairs_hook=er._unique_members, parse_constant=er._invalid_constant)
        reported = er._usage(payload.get('usage')) if isinstance(payload, dict) \
            and payload.get('model') == er.RESPONSE_MODEL else None
        try:
            if status != 200:
                raise ProviderFailure('rate_limited' if status == 429 else 'provider_error')
            result = er._validate(payload, questions)
        except Exception as error:
            failure = ProviderFailure(error_tag(error))
            if reported is not None:
                failure.usage = reported
            raise failure from None
        if time.monotonic() > deadline:
            raise ProviderFailure('timeout')
        return result

    return _elephant_call(request_key('elephant-unbounded', body.decode('utf-8')), state, questions,
                          budget=budget, timeout=timeout, tag=tag, send=send, size=len(body), unbounded=True)
