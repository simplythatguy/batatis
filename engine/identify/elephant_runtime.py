"""Pinned, free Elephant Decisions transport. No chat generation or provider fallback.

The Jev R4 transport remains frozen in jev_runtime.py. This independent adapter
keeps the same one-attempt, verified-TLS and total-deadline guarantees, with a
smaller whole-request context bound and a distinct calibration identity.
"""
from __future__ import annotations

import json
import math
import os
import threading
import time
from contextlib import contextmanager
from functools import lru_cache
from typing import TYPE_CHECKING

from engine import llm_gate
from .screen import Ask, ELEPHANT_MODEL, MAX_QUESTIONS, NoRetry

if TYPE_CHECKING:
    from .providers import SpendLog

ENDPOINT = 'https://openrouter.ai/api/alpha/decisions'
RESPONSE_MODEL = 'baseten/elephant-1-20261021'
CONTEXT_TOKENS = 16_384
FRAMING_TOKENS = 2_048
MAX_RESPONSE_BYTES = 1_000_000
MAX_TIMEOUT = 60
# Included only in Elephant configuration hashes; historical configurations keep
# their original hashes. A new response pin or request policy needs a new fit.
IDENTITY = {'protocol': 'elephant-decisions-v1', 'endpoint': ENDPOINT,
            'response_model': RESPONSE_MODEL, 'context': CONTEXT_TOKENS,
            'framing': FRAMING_TOKENS, 'answer_budget': '128+64/criterion'}
ROUTING = {'only': ['baseten'], 'allow_fallbacks': False,
           'max_price': {'prompt': '0', 'completion': '0', 'request': '0'}}
_SLOT = threading.BoundedSemaphore(1)


class ElephantError(NoRetry):
    """Fixed codes only: no provider body, applicant text, key or HTTP exception."""

    def __init__(self, code: str, *, dispatched: bool | None = None):
        self.code, self.dispatched = code, dispatched
        super().__init__(code)


def _deadline(timeout: float) -> float:
    if type(timeout) not in (int, float) or timeout <= 0.05 or timeout > MAX_TIMEOUT or not math.isfinite(timeout):
        raise ElephantError('invalid_timeout', dispatched=False)
    return time.monotonic() + timeout


def _content(value) -> bool:
    return isinstance(value, (str, dict, list)) and bool(value)


def request_bytes(state, questions, model: str = ELEPHANT_MODEL) -> bytes:
    """Bound the ACTUAL serialized state + questions + routing, without truncation.

    One UTF-8 byte per token is a conservative local admission bound, with 2K
    extra framing tokens and an explicit answer allowance. It is intentionally
    stricter than a characters/4 guess; provider tokenization is not measured.
    """
    if model != ELEPHANT_MODEL:
        raise ElephantError('unexpected_request_model', dispatched=False)
    if not isinstance(state, (str, dict, list)) or not isinstance(questions, dict) \
            or not 1 <= len(questions) <= MAX_QUESTIONS:
        raise ElephantError('invalid_request', dispatched=False)
    answer_budget = 0
    for name, question in questions.items():
        if not isinstance(name, str) or not 1 <= len(name) <= 128 or not isinstance(question, dict) \
                or set(question) - {'type', 'instructions', 'criteria'} \
                or not _content(question.get('instructions')):
            raise ElephantError('invalid_question', dispatched=False)
        kind, criteria = question.get('type'), question.get('criteria')
        if kind == 'noul':
            if criteria is not None and (not isinstance(criteria, dict) or set(criteria) != {'true', 'false'}
                                         or not all(_content(v) for v in criteria.values())):
                raise ElephantError('invalid_question', dispatched=False)
        elif kind == 'choice':
            if not isinstance(criteria, dict) or not 2 <= len(criteria) <= 100 \
                    or any(not isinstance(k, str) or not k or not _content(v) for k, v in criteria.items()):
                raise ElephantError('invalid_question', dispatched=False)
        elif kind == 'score':
            if not isinstance(criteria, list) or not 2 <= len(criteria) <= 10 \
                    or not all(_content(v) for v in criteria):
                raise ElephantError('invalid_question', dispatched=False)
        else:
            raise ElephantError('invalid_question', dispatched=False)
        answer_budget += 128 + (64 * len(criteria) if criteria is not None else 0)
    try:
        encoded = json.dumps({'model': model, 'state': state, 'questions': questions, 'provider': ROUTING},
                             ensure_ascii=False, allow_nan=False, separators=(',', ':')).encode('utf-8')
    except (TypeError, ValueError, OverflowError, RecursionError):
        raise ElephantError('invalid_request', dispatched=False) from None
    if len(encoded) + FRAMING_TOKENS + answer_budget > CONTEXT_TOKENS:
        raise ElephantError('request_too_large', dispatched=False)
    return encoded


def _unit(value) -> float:
    # Range-check before isfinite: a malicious huge Python integer must not
    # overflow conversion to float and escape as a retryable exception.
    if type(value) not in (int, float) or not 0 <= value <= 1 or not math.isfinite(value):
        raise ElephantError('invalid_answer')
    return float(value)


def _distribution(value, keys) -> dict:
    if not isinstance(value, dict) or set(value) != set(keys):
        raise ElephantError('invalid_distribution')
    spread = {key: _unit(value[key]) for key in keys}
    if not math.isclose(sum(spread.values()), 1.0, abs_tol=0.001):
        raise ElephantError('invalid_distribution')
    return spread


def _answer(question: dict, answer) -> dict:
    kind = question['type']
    if not isinstance(answer, dict) or answer.get('type') != kind:
        raise ElephantError('invalid_answer')
    if kind == 'noul':
        return {'type': kind, 'noul': _unit(answer.get('noul'))}
    criteria = question['criteria']
    keys = list(criteria) if kind == 'choice' else [str(i) for i in range(len(criteria))]
    spread = _distribution(answer.get('probabilities'), keys)
    confidence = _unit(answer.get('confidence'))
    if kind == 'choice':
        chosen = answer.get('choice')
        if not isinstance(chosen, str) or chosen not in spread \
                or spread[chosen] < max(spread.values()):
            raise ElephantError('invalid_choice')
        return {'type': kind, 'choice': chosen, 'probabilities': spread, 'confidence': confidence}
    score = answer.get('score')
    if type(score) not in (int, float) or not 0 <= score <= len(criteria) - 1 \
            or not math.isfinite(score) \
            or not math.isclose(score, sum(i * spread[str(i)] for i in range(len(criteria))), abs_tol=0.01):
        raise ElephantError('invalid_score')
    legend = {str(i): text for i, text in enumerate(criteria)}
    if answer.get('legend') != legend:
        raise ElephantError('invalid_legend')
    return {'type': kind, 'score': float(score), 'probabilities': spread,
            'confidence': confidence, 'legend': legend}


def _usage(value) -> dict | None:
    if not isinstance(value, dict):
        return None
    counts = [value.get(k) for k in ('input_tokens', 'output_tokens')]
    if any(type(n) is not int or not 0 <= n <= CONTEXT_TOKENS for n in counts) \
            or sum(counts) > CONTEXT_TOKENS:
        return None
    # Require the free route's observed zero cost, rather than assuming that a
    # successful response with unknown/nonzero billing was free.
    if type(value.get('cost')) not in (int, float) or value['cost'] != 0:
        return None
    if 'total_tokens' in value and (type(value['total_tokens']) is not int or value['total_tokens'] != sum(counts)):
        return None
    return {'input_tokens': counts[0], 'output_tokens': counts[1], 'cost': 0}


def _validate(payload, questions) -> dict:
    if not isinstance(payload, dict):
        raise ElephantError('malformed')
    if payload.get('model') != RESPONSE_MODEL:
        raise ElephantError('unexpected_model')
    usage = _usage(payload.get('usage'))
    if usage is None:
        raise ElephantError('invalid_usage')
    answers = payload.get('answers')
    if not isinstance(answers, dict) or set(answers) != set(questions):
        raise ElephantError('unexpected_answers')
    return {'model': RESPONSE_MODEL, 'usage': usage,
            'answers': {name: _answer(question, answers[name]) for name, question in questions.items()}}


def _unique_members(pairs):
    value = {}
    for key, item in pairs:
        if key in value:
            raise ElephantError('duplicate_field')
        value[key] = item
    return value


def _invalid_constant(value):
    raise ElephantError('malformed')


@lru_cache(maxsize=1)
def _tls_context():
    """The trust store is fixed local state: parse it once, not on every request.

    `ssl.create_default_context` reads the whole CA bundle. On Windows that costs
    about 0.4 s per call, which slowed every scoring call and spent the caller's
    network deadline before a single byte was sent.
    """
    import certifi
    import ssl
    return ssl.create_default_context(cafile=certifi.where())


def _post_once(body: bytes, headers: dict, timeout: float) -> tuple[int, bytes]:
    """Cancel DNS/TLS/headers/body together; no redirect, proxy or HTTP retry."""
    import asyncio
    import anyio
    import httpcore
    import httpx
    import ssl
    attempted = False
    if httpcore.__version__ != '1.0.9':
        raise ElephantError('transport_version_unverified', dispatched=False)
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        pass
    else:
        raise ElephantError('synchronous_ask_requires_worker_thread', dispatched=False)

    # Building and checking the trust store is local, fixed work, so it happens
    # before the clock starts: the deadline covers the request, not the CA parse.
    try:
        context = _tls_context()
    except Exception:
        raise ElephantError('transport_not_ready', dispatched=False) from None
    if context.verify_mode != ssl.CERT_REQUIRED or not context.check_hostname or not context.get_ca_certs():
        raise ElephantError('tls_not_ready', dispatched=False)
    started = time.monotonic()

    async def post():
        nonlocal attempted
        pending_tls = None

        async def trace(event, info):
            nonlocal pending_tls
            if event == 'connection.connect_tcp.complete':
                pending_tls = info['return_value']
            elif event == 'connection.start_tls.complete':
                pending_tls = None

        try:
            async with asyncio.timeout(timeout):
                if time.monotonic() - started >= timeout:
                    raise ElephantError('timeout', dispatched=False)
                transport = httpx.AsyncHTTPTransport(verify=context, retries=0, trust_env=False)
                async with httpx.AsyncClient(transport=transport, timeout=timeout, follow_redirects=False,
                                             trust_env=False) as http:
                    attempted = True
                    async with http.stream('POST', ENDPOINT, content=body, headers=headers,
                                           extensions={'trace': trace}) as response:
                        chunks, size = [], 0
                        async for chunk in response.aiter_bytes(chunk_size=65_536):
                            size += len(chunk)
                            if size > MAX_RESPONSE_BYTES:
                                raise ElephantError('response_too_large')
                            chunks.append(chunk)
                        return response.status_code, b''.join(chunks)
        finally:
            if pending_tls is not None:
                # HTTPcore 1.0.9 does not catch cancellation before TLS transfers
                # stream ownership. Clean up this request's TCP stream explicitly.
                with anyio.CancelScope(shield=True):
                    await anyio.aclose_forcefully(pending_tls)
    try:
        return asyncio.run(post())
    except ElephantError:
        raise
    except TimeoutError:
        raise ElephantError('timeout', dispatched=attempted) from None
    except httpx.HTTPError:
        raise ElephantError('network', dispatched=attempted) from None
    except Exception:
        raise ElephantError('invalid_response' if attempted else 'transport_not_ready',
                            dispatched=attempted) from None


@contextmanager
def _claim():
    if not _SLOT.acquire(blocking=False):
        raise ElephantError('scoring_busy', dispatched=False)
    try:
        yield
    finally:
        _SLOT.release()


def raw_ask(model: str = ELEPHANT_MODEL, *, post=None, credential=None) -> Ask:
    """The injection seam is for offline fakes/tests; production uses the fixed URL."""
    if model != ELEPHANT_MODEL:
        raise ValueError('Elephant requires the pinned free model')

    def ask(state, questions, timeout):
        deadline = _deadline(timeout)
        reported, dispatched = None, False
        try:
            body = request_bytes(state, questions, model)
            key = (credential() if credential is not None else os.environ.get('OPENROUTER_API_KEY') or '').strip()
            if not key:
                raise ElephantError('credential_absent', dispatched=False)
            with _claim():
                remaining = deadline - time.monotonic()
                if remaining <= 0.05:
                    raise ElephantError('timeout', dispatched=False)
                dispatched = True
                status, raw = (post or _post_once)(body, {'Authorization': 'Bearer ' + key,
                                                        'Content-Type': 'application/json'}, remaining)
                if len(raw) > MAX_RESPONSE_BYTES:
                    raise ElephantError('response_too_large')
                payload = json.loads(raw, object_pairs_hook=_unique_members, parse_constant=_invalid_constant)
                if isinstance(payload, dict) and payload.get('model') == RESPONSE_MODEL:
                    reported = _usage(payload.get('usage'))
                if status != 200:
                    code = {401: 'auth_failed', 403: 'auth_failed', 402: 'quota_exhausted',
                            429: 'rate_limited'}.get(status, 'provider_unavailable')
                    raise ElephantError(code)
                result = _validate(payload, questions)
                if time.monotonic() > deadline:
                    raise ElephantError('timeout')
                return result
        except Exception as error:
            code = error.code if isinstance(error, ElephantError) else 'invalid_response' if dispatched else 'invalid_request'
            if isinstance(error, ElephantError) and error.dispatched is not None:
                dispatched = error.dispatched
            safe = ElephantError(code, dispatched=dispatched)
            if reported is not None:
                safe.usage = reported
            raise safe from None
    ask.model, ask.method = model, 'elephant'
    return ask


def metered_ask(raw: Ask, *, model: str = ELEPHANT_MODEL, client_ip: str | None = None,
                log: SpendLog | None = None) -> Ask:
    if model != ELEPHANT_MODEL:
        raise ValueError('Elephant requires the pinned free model')

    def ask(state, questions, timeout):
        from .providers import GateClosed
        deadline = _deadline(timeout)
        request_bytes(state, questions, model)  # reject oversized input before admission
        decision = llm_gate.reserve(provider='elephant', model=model, max_input_tokens=CONTEXT_TOKENS,
                                    max_output_tokens=0, client_ip=client_ip)
        if not decision.allowed:
            raise GateClosed('elephant', decision.source)
        accounted = False

        def settle(usage):
            nonlocal accounted
            try:
                usd = llm_gate.settle(decision, model=model, input_tokens=usage['input_tokens'],
                                      output_tokens=usage['output_tokens'])
            except Exception:
                raise ElephantError('accounting_unavailable') from None
            accounted = True
            if log is not None:
                log.add(provider='elephant', model=model, response_model=RESPONSE_MODEL,
                        input_tokens=usage['input_tokens'], output_tokens=usage['output_tokens'],
                        usd=float(usd), accounting='settled')
        try:
            try:
                remaining = deadline - time.monotonic()
                if remaining <= 0.05:
                    raise ElephantError('timeout', dispatched=False)
                reply = raw(state, questions, remaining)
                usage = _usage(reply.get('usage')) if isinstance(reply, dict) and reply.get('model') == RESPONSE_MODEL else None
                if usage is not None:
                    settle(usage)
                result = _validate(reply, questions)
                if time.monotonic() > deadline:
                    raise ElephantError('timeout')
                return result
            except Exception as error:
                reported = _usage(getattr(error, 'usage', None))
                if reported is not None and not accounted:
                    settle(reported)
                if isinstance(error, ElephantError):
                    raise
                raise ElephantError('scoring_failed') from None
        finally:
            if not accounted and log is not None:
                # The route is pinned free, but unknown usage is still UNKNOWN.
                # Keep its admission (zero dollars), and never fabricate counts.
                log.add(provider='elephant', model=model, input_tokens=0, output_tokens=0,
                        usd=float(decision.reserved_usd), accounting='unknown')
    ask.model, ask.method = model, 'elephant'
    return ask
