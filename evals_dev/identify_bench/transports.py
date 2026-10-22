"""Provider transports for the benchmark: OpenAI Chat Completions behind the hard-stop ledger, and Jev accounting.

``OpenAIChat`` makes one strict-JSON-schema request. Before it sends, it reserves the worst-case cost in the ledger
(refused past the stop); after the response it settles with the usage the API reported. A response with no usage
(rejected request, rate limit) releases the reservation; a client timeout after the request left is charged at its
worst case. Retries (429, 5xx, timeouts) are counted in ``attempts`` and each attempt is metered on its own.

No ``service_tier`` is sent, so requests run on the standard tier, and the tier the API reports is recorded.
Keys are read from the environment by name and used only as a request header; they never appear in a log, an
exception message or a row (``envfile.redact`` is applied to anything that could echo one).
"""
from __future__ import annotations

import json
import os
import random
import re
import sys
import threading
import time
from collections import deque
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from decimal import Decimal

from evals_dev import envfile

from . import pricing
from .ledger import BudgetExceeded, Ledger

OPENAI_URL = 'https://api.openai.com/v1/chat/completions'
CIRCUIT_WINDOW = 20             # attempts looked at
CIRCUIT_FAILURES = 10           # connection failures among them that open the circuit
CIRCUIT_COOLDOWN = 45.0         # seconds a run waits before it tries again
NOT_SENT = frozenset({'ConnectError', 'ConnectTimeout', 'PoolTimeout', 'gaierror'})   # failed before any request bytes left
_KEY_SHAPE = re.compile(r'sk-[A-Za-z0-9_\-]{10,}')
# (url, headers, json body, timeout seconds) -> (status, response headers, parsed json or None)
Http = Callable[[str, Mapping[str, str], dict, float], tuple[int, Mapping[str, str], dict | None]]


@dataclass
class CallResult:
    payload: dict | None = None
    input_tokens: int = 0
    output_tokens: int = 0              # completion tokens, reasoning included
    reasoning_tokens: int = 0
    cached_tokens: int = 0
    usd: Decimal = Decimal(0)
    latency_ms: float = 0.0             # of the successful (or final) attempt
    returned_model: str | None = None
    service_tier: str | None = None
    request_id: str | None = None
    finish_reason: str | None = None
    attempts: int = 0
    errors: list[dict] = field(default_factory=list)
    refusal: str | None = None

    @property
    def ok(self) -> bool:
        return self.payload is not None and not self.errors_fatal

    @property
    def errors_fatal(self) -> bool:
        return any(e.get('fatal') for e in self.errors)


_CLIENT = None
_CLIENT_LOCK = threading.Lock()


def keepalive_options() -> list[tuple[int, int, int]]:
    """Socket options that make the kernel probe an idle connection. A non-streaming completion leaves the connection silent for the
    whole reasoning time (5 to 60 seconds); some path elements drop a flow that stays silent, which showed up as completions that never
    returned ("read timeout" after 150 s) and "server disconnected without sending a response". With probes every few seconds the same
    load ran 36 of 36 where it had lost 3 of 36."""
    import socket
    opts = [(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)]
    if sys.platform == 'darwin':
        opts += [(socket.IPPROTO_TCP, 0x10, 10), (socket.IPPROTO_TCP, 0x101, 5), (socket.IPPROTO_TCP, 0x102, 6)]   # idle, interval, count
    elif hasattr(socket, 'TCP_KEEPIDLE'):
        opts += [(socket.IPPROTO_TCP, socket.TCP_KEEPIDLE, 10), (socket.IPPROTO_TCP, socket.TCP_KEEPINTVL, 5),
                 (socket.IPPROTO_TCP, socket.TCP_KEEPCNT, 6)]
    return opts


def shared_client():
    """One pooled client for the process, with TCP keepalive. Many simultaneous fresh TLS connections made the server drop some of them,
    so connections are reused up to a bound and kept short-lived."""
    global _CLIENT
    import httpx
    with _CLIENT_LOCK:
        if _CLIENT is None:
            transport = httpx.HTTPTransport(socket_options=keepalive_options(),
                                            limits=httpx.Limits(max_connections=32, max_keepalive_connections=16, keepalive_expiry=10.0))
            _CLIENT = httpx.Client(follow_redirects=False, transport=transport)
        return _CLIENT


def default_http(url: str, headers: Mapping[str, str], body: dict, timeout: float):
    r = shared_client().post(url, headers=dict(headers), json=body, timeout=timeout)
    try:
        data = r.json()
    except ValueError:
        data = None
    return r.status_code, dict(r.headers), data


class OpenAIChat:
    def __init__(self, ledger: Ledger, *, key_env: str = 'OPENAI_API_KEY', http: Http | None = None,
                 timeout: float = 90.0, max_attempts: int = 3, sleep: Callable[[float], None] = time.sleep,
                 environ: Mapping[str, str] | None = None, url: str = OPENAI_URL):
        self.ledger, self.key_env, self.timeout, self.max_attempts = ledger, key_env, timeout, max_attempts
        self.http, self.sleep, self.url = http or default_http, sleep, url
        self._environ = environ if environ is not None else os.environ
        self._recent: deque[bool] = deque(maxlen=CIRCUIT_WINDOW)          # True = the attempt failed at the connection
        self._recent_lock = threading.Lock()
        self._open_until = 0.0

    def _key(self) -> str:
        key = (self._environ.get(self.key_env) or '').strip()
        if not key:
            raise RuntimeError(f'{self.key_env} is not set')
        return key

    def _redact(self, text: str) -> str:
        """Anything copied out of a response (an error message can echo the key) is scrubbed before it is stored."""
        key = (self._environ.get(self.key_env) or '').strip()
        if key:
            text = text.replace(key, f'<{self.key_env}>')
        return _KEY_SHAPE.sub(f'<{self.key_env}>', envfile.redact(text))

    def __call__(self, *, name: str, schema: dict, system: str, user: str, model: str, effort: str | None,
                 max_completion_tokens: int, arm: str = '', case: str = '') -> CallResult:
        if 'haiku' in model.lower():
            raise ValueError('Haiku models are not used')
        pricing.price_for(model)                                   # unpriced models are refused before any call
        body = {
            'model': model, 'max_completion_tokens': max_completion_tokens,
            'messages': [{'role': 'system', 'content': system}, {'role': 'user', 'content': user}],
            'response_format': {'type': 'json_schema', 'json_schema': {'name': name, 'strict': True, 'schema': schema}},
        }
        if effort:
            body['reasoning_effort'] = effort
        headers = {'Authorization': 'Bearer ' + self._key(), 'Content-Type': 'application/json'}
        worst = pricing.worst_case_usd(model, pricing.input_token_upper_bound(system + user + json.dumps(schema)),
                                       max_completion_tokens)
        result = CallResult()
        for attempt in range(1, self.max_attempts + 1):
            result.attempts = attempt
            if self._circuit_is_open():
                result.errors.append({'category': 'circuit_open', 'detail': f'{CIRCUIT_FAILURES} of the last {CIRCUIT_WINDOW} attempts '
                                      'failed at the connection; the run stops rather than charge more failed calls', 'fatal': True})
                return result
            try:
                res = self.ledger.reserve(model=model, worst_case_usd=worst, arm=arm, case=case)
            except BudgetExceeded as e:
                result.errors.append({'category': 'budget_stop', 'detail': str(e), 'fatal': True})
                return result
            started = time.monotonic()
            try:
                status, resp_headers, data = self.http(self.url, headers, body, self.timeout)
            except Exception as e:                                  # noqa: BLE001 - timeout, reset, TLS
                self._note(failed=True)
                if type(e).__name__ in NOT_SENT:                    # the connection was never made: nothing was billed
                    self.ledger.release(res)
                else:                                               # the request left; the provider may have billed it
                    typical = self.ledger.typical_usd(model)
                    self.ledger.unknown(res, f'{type(e).__name__} after the request was sent', usd=typical,
                                        basis='worst case' if typical is None else '99th percentile of settled calls',
                                        arm=arm, case=case)
                result.errors.append({'category': 'timeout' if 'Timeout' in type(e).__name__ else 'connection',
                                      'detail': self._redact(type(e).__name__), 'fatal': attempt == self.max_attempts})
                self._backoff(attempt, None)
                continue
            result.latency_ms = (time.monotonic() - started) * 1000.0
            self._note(failed=False)
            usage = (data or {}).get('usage') or {}
            if status == 200 and data and usage:
                return self._finish(res, result, data, usage, model, resp_headers, arm, case)
            self.ledger.release(res)                                # no usage came back: nothing to charge
            category = ('rate_limited' if status == 429 else 'server_error' if status >= 500 else
                        'auth' if status in (401, 403) else 'bad_request')
            detail = self._redact(str(((data or {}).get('error') or {}).get('message', ''))[:300])
            retryable = status == 429 or status >= 500
            result.errors.append({'category': category, 'status': status, 'detail': detail,
                                  'fatal': (not retryable) or attempt == self.max_attempts})
            if not retryable:
                return result
            self._backoff(attempt, resp_headers.get('retry-after'))
        return result

    def _note(self, failed: bool) -> None:
        with self._recent_lock:
            self._recent.append(failed)
            if sum(self._recent) >= CIRCUIT_FAILURES and len(self._recent) >= CIRCUIT_WINDOW // 2:
                self._open_until = time.monotonic() + CIRCUIT_COOLDOWN
                self._recent.clear()

    def _circuit_is_open(self) -> bool:
        with self._recent_lock:
            return time.monotonic() < self._open_until

    def _backoff(self, attempt: int, retry_after) -> None:
        try:
            delay = float(retry_after) if retry_after else min(30.0, 2.0 ** attempt)
        except ValueError:
            delay = min(30.0, 2.0 ** attempt)
        if attempt < self.max_attempts:
            self.sleep(delay + random.uniform(0, 0.5))

    def _finish(self, res, result: CallResult, data: dict, usage: dict, model: str, resp_headers, arm, case) -> CallResult:
        details_out = usage.get('completion_tokens_details') or {}
        details_in = usage.get('prompt_tokens_details') or {}
        result.input_tokens = int(usage.get('prompt_tokens') or 0)
        result.output_tokens = int(usage.get('completion_tokens') or 0)
        result.reasoning_tokens = int(details_out.get('reasoning_tokens') or 0)
        result.cached_tokens = int(details_in.get('cached_tokens') or 0)
        result.usd = pricing.cost_usd(model, result.input_tokens, result.output_tokens, result.cached_tokens)
        result.returned_model = data.get('model')
        result.service_tier = data.get('service_tier')
        result.request_id = resp_headers.get('x-request-id') or data.get('id')
        self.ledger.settle(res, usd=result.usd, input_tokens=result.input_tokens, output_tokens=result.output_tokens,
                           cached_tokens=result.cached_tokens, reasoning_tokens=result.reasoning_tokens,
                           request_id=result.request_id, returned_model=result.returned_model, arm=arm, case=case)
        choice = (data.get('choices') or [{}])[0]
        result.finish_reason = choice.get('finish_reason')
        message = choice.get('message') or {}
        if message.get('refusal'):
            result.refusal = self._redact(str(message['refusal']))[:200]
            result.errors.append({'category': 'refusal', 'detail': result.refusal, 'fatal': True})
            return result
        if result.finish_reason == 'length':
            result.errors.append({'category': 'truncated', 'detail': 'finish_reason=length (reasoning plus answer hit '
                                  'max_completion_tokens)', 'fatal': True})
            return result
        try:
            payload = json.loads(message.get('content') or '')
        except ValueError:
            result.errors.append({'category': 'schema', 'detail': 'response content was not JSON', 'fatal': True})
            return result
        if not isinstance(payload, dict):
            result.errors.append({'category': 'schema', 'detail': 'response JSON was not an object', 'fatal': True})
            return result
        result.payload = payload
        return result
