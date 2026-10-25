"""Jev-only accounting and transport policy; other providers keep their own adapters.

The published pinned model costs USD0.042/M input tokens, with free output and
a 64k request context unless an explicit long-context header is sent. Reserve a
65,536-token ceiling for ONE HTTP attempt, never refund an unknown outcome.
BATATIS_JEV_UNCAPPED=1 explicitly exempts Jev from the shared dollar ledger;
it does not enable live calls, supply a credential, or change any rate limit.
"""
from __future__ import annotations

import json
import math
import os
import threading
import time
from functools import lru_cache
from typing import TYPE_CHECKING

from engine import llm_gate
from .screen import Ask, JEV_MODEL, NoRetry

if TYPE_CHECKING:
    from .providers import SpendLog

MAX_INPUT_TOKENS = 65_536
ENDPOINT = 'https://api.typesafe.ai/v1/systemone'
MAX_RESPONSE_BYTES = 1_000_000
_RUNTIME_LOCK = threading.Lock()
_RUNTIME_ACTIVE = 0
_RUNTIME_FROZEN = False


class JevResponseError(NoRetry):
    """A fixed protocol error; retrying a billed malformed response is unhelpful."""

    def __init__(self, code: str, *, dispatched: bool | None = None):
        self.code = code
        # False proves transport never started. True is an attempted/ambiguous send,
        # not confirmation of provider billing. None gives no dispatch evidence.
        self.dispatched = dispatched
        super().__init__(code)


def _deadline(timeout):
    if isinstance(timeout, bool) or not isinstance(timeout, (int, float)) \
            or not math.isfinite(timeout) or timeout <= 0:
        raise JevResponseError('invalid_timeout', dispatched=False)
    return time.monotonic() + timeout


def _freeze_runtime(*, require_idle: bool = True):
    """Narrow update seam: refuse active Jev work, then block future cached calls."""
    global _RUNTIME_FROZEN
    if not _RUNTIME_LOCK.acquire(blocking=False):
        raise JevResponseError('runtime_busy', dispatched=False)
    try:
        if require_idle and _RUNTIME_ACTIVE:
            raise JevResponseError('runtime_busy', dispatched=False)
        _RUNTIME_FROZEN = True
    finally:
        _RUNTIME_LOCK.release()


def _resume_runtime():
    global _RUNTIME_FROZEN
    if not _RUNTIME_LOCK.acquire(blocking=False):
        raise JevResponseError('runtime_busy', dispatched=False)
    try:
        _RUNTIME_FROZEN = False
    finally:
        _RUNTIME_LOCK.release()


def _tracked(ask):
    def call(state, questions, timeout):
        global _RUNTIME_ACTIVE
        deadline = _deadline(timeout)
        with _RUNTIME_LOCK:
            if _RUNTIME_FROZEN:
                raise JevResponseError('runtime_busy', dispatched=False)
            _RUNTIME_ACTIVE += 1
        try:
            remaining = deadline - time.monotonic()
            if remaining <= 0.05:
                raise JevResponseError('timeout', dispatched=False)
            result = ask(state, questions, remaining)
        finally:
            with _RUNTIME_LOCK:
                _RUNTIME_ACTIVE -= 1
        if time.monotonic() > deadline:
            error = JevResponseError('timeout')
            if isinstance(result, dict) and result.get('model') == JEV_MODEL and _usage(result.get('usage')) is not None:
                error.usage = result['usage']
            raise error
        return result
    call.__dict__.update(ask.__dict__)
    return call


@lru_cache(maxsize=1)
def _tls_context():
    """Verified public roots for this Jev transport alone; ignore shared SSL env vars.

    Built once: `ssl.create_default_context` reads the whole CA bundle, which costs
    about 0.4 s on Windows. Rebuilding it per request both slowed every call and
    spent the caller's deadline on local work before a byte was sent.
    """
    import certifi
    import ssl
    return ssl.create_default_context(cafile=certifi.where())


def _post_once(body: bytes, headers: dict, timeout: float) -> tuple[int, bytes]:
    """One POST under a cancellable total deadline, without redirects or retries.

    Judge and the HTTP routes call this synchronous Ask from worker threads. A
    private event loop bounds DNS, TLS, headers and body together; no shared loop
    or HTTP client is changed.
    """
    import asyncio
    import anyio
    import httpcore
    import httpx
    import ssl
    import time
    attempted = False
    started = time.monotonic()
    if httpcore.__version__ != '1.0.9':
        # The trace ownership events below were verified on this installed contract.
        # Fail locally on a changed dependency instead of guessing about cleanup.
        raise JevResponseError('transport_version_unverified', dispatched=False)
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        pass
    else:
        raise JevResponseError('synchronous_ask_requires_worker_thread', dispatched=False)

    # Reuse the trust store, but keep cold setup inside the caller's time budget.
    try:
        context = _tls_context()
    except Exception:
        raise JevResponseError('transport_not_ready', dispatched=False) from None
    if context.verify_mode != ssl.CERT_REQUIRED or not context.check_hostname or not context.get_ca_certs():
        raise JevResponseError('tls_not_ready', dispatched=False)

    async def post():
        nonlocal attempted
        pending_tls = None

        async def trace(event, info):
            nonlocal pending_tls
            if event == 'connection.connect_tcp.complete':
                pending_tls = info['return_value']
            elif event == 'connection.start_tls.complete':
                pending_tls = None  # HTTPcore now owns the successfully wrapped stream.

        try:
            remaining = timeout - (time.monotonic() - started)
            if remaining <= 0:
                raise JevResponseError('timeout', dispatched=False)
            async with asyncio.timeout(remaining):
                transport = httpx.AsyncHTTPTransport(verify=context, retries=0, trust_env=False)
                async with httpx.AsyncClient(transport=transport, timeout=timeout, follow_redirects=False,
                                             trust_env=False) as http:
                    if time.monotonic() - started >= timeout:
                        raise JevResponseError('timeout', dispatched=False)
                    attempted = True
                    async with http.stream('POST', ENDPOINT, content=body, headers=headers,
                                           extensions={'trace': trace}) as response:
                        chunks, size = [], 0
                        async for chunk in response.aiter_bytes(chunk_size=65_536):
                            size += len(chunk)
                            if size > MAX_RESPONSE_BYTES:
                                raise JevResponseError('response_too_large')
                            chunks.append(chunk)
                        if time.monotonic() - started > timeout:
                            raise TimeoutError
                        return response.status_code, b''.join(chunks)
        finally:
            if pending_tls is not None:
                # HTTPcore1.0.9 catches Exception, so task cancellation before TLS
                # ownership transfer needs this Jev-local cleanup. Never log trace info.
                with anyio.CancelScope(shield=True):
                    await anyio.aclose_forcefully(pending_tls)
    try:
        return asyncio.run(post())
    except JevResponseError:
        raise
    except TimeoutError:
        raise JevResponseError('timeout', dispatched=attempted) from None
    except httpx.HTTPError:
        # Do not retain a request/header-bearing exception in the public error chain.
        raise JevResponseError('network', dispatched=attempted) from None
    except Exception:
        code = 'invalid_response' if attempted else 'transport_not_ready'
        raise JevResponseError(code, dispatched=attempted) from None


def _unique_members(pairs):
    found = {}
    for name, value in pairs:
        if name in found:
            raise JevResponseError('duplicate_field')
        found[name] = value
    return found


def _invalid_json_constant(value):
    raise JevResponseError('malformed')


def raw_ask(model: str = JEV_MODEL) -> Ask:
    """Keep jevkit's strict question/answer validation, replacing only its transport."""
    from .jevkit import client
    from .screen import JEV_PROVIDER
    if model != JEV_MODEL:
        raise ValueError('Jev requires the pinned model')

    def ask(state, questions, timeout):
        reported = None
        dispatched = False
        deadline = 0.0

        def send(body, headers, remaining):
            nonlocal reported, dispatched
            remaining = min(remaining, deadline - time.monotonic())
            if remaining <= 0.05:
                raise JevResponseError('timeout', dispatched=False)
            dispatched = True
            status, raw = _post_once(body, headers, remaining)
            try:
                payload = json.loads(raw, object_pairs_hook=_unique_members,
                                     parse_constant=_invalid_json_constant)
            except (UnicodeDecodeError, ValueError):
                raise JevResponseError('malformed') from None
            if not isinstance(payload, dict):
                raise JevResponseError('malformed')
            # Remember valid billing even when we must refuse the model or answers.
            reported = _usage(payload.get('usage')) if payload.get('model') == model else None
            if status != 200:
                code = {401: 'auth_failed', 403: 'auth_failed', 402: 'credits_exhausted',
                        429: 'rate_limited'}.get(status, f'http_{status}')
                raise JevResponseError(code)
            if payload.get('model') != model:
                # Usage from an unexpected model cannot settle this model's price.
                reported = None
                raise JevResponseError('unexpected_model')
            answers = payload.get('answers')
            if not isinstance(answers, dict) or set(answers) != set(questions):
                raise JevResponseError('unexpected_answers')
            if reported is None:
                raise JevResponseError('invalid_usage')
            return raw

        try:
            deadline = _deadline(timeout)
            result = client.ask(state, questions, timeout=timeout, model=model,
                                provider=JEV_PROVIDER, retries=0, transport=send)
            if time.monotonic() > deadline:
                raise JevResponseError('timeout', dispatched=dispatched)
            return {**result, 'model': model}
        except Exception as error:
            # Fixed codes only: never echo the provider body, questions, or credentials.
            code = (error.code if isinstance(error, (client.JevError, JevResponseError)) else
                    'invalid_response' if dispatched else 'invalid_request')
            if isinstance(error, JevResponseError) and error.dispatched is not None:
                dispatched = error.dispatched
            safe = JevResponseError(code, dispatched=dispatched)
            if reported is not None:
                safe.usage = {'input_tokens': reported[0], 'output_tokens': reported[1]}
            raise safe from None

    return _tracked(ask)


def _usage(value) -> tuple[int, int] | None:
    if not isinstance(value, dict):
        return None
    counts = (value.get('input_tokens'), value.get('output_tokens'))
    if any(isinstance(count, bool) or not isinstance(count, int) or count < 0 for count in counts):
        return None
    if counts[0] > MAX_INPUT_TOKENS:
        return None
    return counts


def metered_ask(raw: Ask, *, model: str = JEV_MODEL, client_ip: str | None = None,
                log: SpendLog | None = None) -> Ask:
    if model != JEV_MODEL:
        raise ValueError('Jev requires the pinned model')

    def ask(state, questions, timeout):
        from .providers import GateClosed
        deadline = _deadline(timeout)
        uncapped = os.environ.get('BATATIS_JEV_UNCAPPED') == '1'
        if uncapped:
            if not llm_gate.provider_enabled('jev'):
                raise GateClosed('jev', 'offline')
            decision = None
        else:
            decision = llm_gate.reserve(provider='jev', model=model, max_input_tokens=MAX_INPUT_TOKENS,
                                        max_output_tokens=0, client_ip=client_ip)
            if not decision.allowed:
                raise GateClosed('jev', decision.source)
        accounted = False

        def settle(usage: tuple[int, int]) -> None:
            nonlocal accounted
            # Output is free for this pinned model. Keep its reported count in the log.
            if decision is not None:
                try:
                    usd = llm_gate.settle(decision, model=model, input_tokens=usage[0], output_tokens=0)
                except Exception:
                    # The provider replied; an uncertain ledger acknowledgement is never a retry signal.
                    raise JevResponseError('accounting_unavailable') from None
            else:
                usd = llm_gate.estimate_usd(model, usage[0], 0)
            if log is not None:
                log.add(provider='jev', model=model, input_tokens=usage[0], output_tokens=usage[1],
                        usd=float(usd), accounting='uncapped' if uncapped else 'settled')
            accounted = True

        try:
            try:
                remaining = deadline - time.monotonic()
                if remaining <= 0.05:
                    raise JevResponseError('timeout', dispatched=False)
                reply = raw(state, questions, remaining)
            except Exception as error:
                if isinstance(error, JevResponseError) and error.dispatched is False:
                    # This factory proved that validation/setup stopped before transport.
                    # This is unrelated to the historical, inconclusive network attempt.
                    if decision is not None:
                        try:
                            llm_gate.release(decision)
                        except Exception:
                            raise JevResponseError('accounting_unavailable') from None
                    if log is not None:
                        log.add(provider='jev', model=model, input_tokens=0, output_tokens=0,
                                usd=0.0, accounting='not_dispatched')
                    accounted = True
                    raise
                # A transport may have received valid usage before rejecting the answers.
                reported = _usage(getattr(error, 'usage', None))
                if reported is not None:
                    settle(reported)
                raise
            reported = _usage(reply.get('usage') if isinstance(reply, dict) else None)
            if reported is None:
                raise JevResponseError('invalid_usage')
            settle(reported)
            if time.monotonic() > deadline:
                raise JevResponseError('timeout')
            return reply
        finally:
            if not accounted and log is not None:
                estimate = (decision.reserved_usd if decision is not None else
                            llm_gate.estimate_usd(model, MAX_INPUT_TOKENS, 0))
                log.add(provider='jev', model=model, input_tokens=0, output_tokens=0,
                        usd=float(estimate), accounting='uncapped_unknown' if uncapped else 'held')
            # Unknown dispatch or failed/missing/invalid usage never establishes zero billing.

    ask.model, ask.method = model, 'jev'
    return _tracked(ask)
