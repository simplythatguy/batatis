"""The pinned desktop identification profile over main-owned generation and optional screening."""
from __future__ import annotations

import json
import time

from . import bridge, composition
from .host_provider import host_transport, private_call


def transports(*, scoring, jev_model, anthropic):
    from ..identify.providers import Transports, SpendLog, GateClosed
    selected = composition.profile()
    log = SpendLog()
    out = Transports(kind='live', log=log, unavailable={
        'jev': 'Optional screening is off or its key is missing; keyword fallback is used.',
        'openai': 'The selected desktop generation connection is off.',
        'anthropic': 'Not part of the pinned desktop workflow.',
        'elephant': 'Not part of the pinned desktop workflow.',
        'decisions': 'Not part of the pinned desktop workflow.'})
    if selected.generation == 'off':
        return out
    context = bridge.REQUEST_CONTEXT.get()

    def complete(name, schema, system, user, *, model, max_output_tokens=4096, effort=None, timeout=60):
        if name != 'picks' or (model, effort) != (composition.MODEL, composition.EFFORT):
            raise GateClosed('desktop', 'desktop-profile')
        transport = host_transport('identify-picks', model=model, effort=effort,
                                   max_output_tokens=max_output_tokens, lease=selected.lease, context=context)
        usage = {'input_tokens': None, 'output_tokens': None}
        try:
            payload, usage = transport(system, user, schema)
            return payload, usage
        finally:
            log.add(provider='openai', model=model, input_tokens=usage['input_tokens'],
                    output_tokens=usage['output_tokens'], usd=None, billing=selected.billing)

    out.openai = complete
    if selected.screening and 'jev' in scoring and jev_model == 'jev-1.13.0':
        out.jev = screening(selected.lease, log, 'included' if selected.billing == 'included' else 'api')
    return out


def screening(lease, log, billing: str = 'api'):
    from ..identify.jevkit import client
    from ..identify import jev_runtime as runtime
    from ..identify.screen import JEV_MODEL, JEV_PROVIDER
    context = bridge.REQUEST_CONTEXT.get()

    def ask(state, questions, timeout):
        reported = None
        deadline = runtime._deadline(timeout)

        def send(body, _nonsecret_headers, remaining):
            nonlocal reported
            remaining = min(remaining, deadline - time.monotonic())
            if remaining <= 0.05:
                raise runtime.JevResponseError('timeout', dispatched=False)
            # client.ask receives an explicit non-credential sentinel solely to avoid ambient key resolution.
            # Its headers are discarded here. Only main decrypts and adds the actual Authorization header.
            reply = private_call('provider.jev', {'lease': lease, 'body': body.decode('utf-8'), 'timeout': remaining},
                                 context=context, timeout=remaining)
            value = reply.get('value') if reply.get('ok') else None
            if not isinstance(value, dict) or type(value.get('status')) is not int or not isinstance(value.get('body'), str):
                raise runtime.JevResponseError('desktop_unavailable', dispatched=False)
            raw = value['body'].encode('utf-8')
            if len(raw) > runtime.MAX_RESPONSE_BYTES:
                raise runtime.JevResponseError('response_too_large')
            payload = json.loads(raw, object_pairs_hook=runtime._unique_members,
                                 parse_constant=runtime._invalid_json_constant)
            if not isinstance(payload, dict):
                raise runtime.JevResponseError('malformed')
            reported = runtime._usage(payload.get('usage')) if payload.get('model') == JEV_MODEL else None
            if value['status'] != 200:
                raise runtime.JevResponseError({401: 'auth_failed', 403: 'auth_failed', 402: 'credits_exhausted',
                                               429: 'rate_limited'}.get(value['status'], 'http_error'))
            if payload.get('model') != JEV_MODEL:
                raise runtime.JevResponseError('unexpected_model')
            if not isinstance(payload.get('answers'), dict) or set(payload['answers']) != set(questions):
                raise runtime.JevResponseError('unexpected_answers')
            if reported is None:
                raise runtime.JevResponseError('invalid_usage')
            return raw

        try:
            result = client.ask(state, questions, timeout=timeout, model=JEV_MODEL, provider=JEV_PROVIDER,
                                api_key='desktop-host-transport', retries=0, transport=send)
            if time.monotonic() > deadline:
                raise runtime.JevResponseError('timeout')
            return {**result, 'model': JEV_MODEL}
        except Exception:
            # Judge does not retry a desktop failure, even when its underlying code was transient.
            raise runtime.JevResponseError('desktop_screening_failed') from None
        finally:
            log.add(provider='jev', model=JEV_MODEL, input_tokens=reported[0] if reported else None,
                    output_tokens=reported[1] if reported else None, usd=None, billing=billing)
    ask.model, ask.method = JEV_MODEL, 'jev'
    return runtime._tracked(ask)
