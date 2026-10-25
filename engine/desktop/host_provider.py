"""The engine's side of the desktop host provider (desktop/src/main/providers.ts).

Outside the desktop bridge there is no host and `host_transport` returns None. Inside it, a model task
asks the host, which owns the provider connection; the engine never sees a key, token or account.
The workflow names the exact model and effort; the host never substitutes either.
"""
from __future__ import annotations

import base64
import json
from types import EllipsisType

from ..intake.model import GateClosed, Transport
from . import bridge

CALL_SECONDS = 180.0


def private_call(op: str, args: dict, *, context: bridge.RequestContext | None, timeout: float = CALL_SECONDS) -> dict:
    """Keep document payloads within the frozen bridge framing limit, without changing their content."""
    import time
    if context is None or bridge.ACTIVE is not context.bridge:
        raise bridge.HostUnavailable('request is not bound to this host')
    active = context.bridge
    deadline = time.monotonic() + timeout

    def send(operation, value):
        remaining = deadline - time.monotonic()
        if remaining <= 0 or bridge.ACTIVE is not active:
            raise bridge.HostUnavailable('host changed or deadline reached')
        reply = active.call_host(operation, value, timeout=remaining, request_id=context.request_id)
        if not isinstance(reply, dict):
            raise bridge.HostUnavailable('invalid host reply')
        return reply

    encoded = base64.b64encode(json.dumps(args, ensure_ascii=False).encode()).decode('ascii')
    if len(encoded) > 4_000_000:
        raise bridge.HostUnavailable('request too large')
    if len(encoded) > 24_000:
        started = send('provider.transfer.begin', {'lease': args.get('lease'), 'operation': op})
        value = started.get('value') if started.get('ok') else None
        if not isinstance(value, dict) or not isinstance(value.get('id'), str):
            return started
        transfer = {'id': value['id'], 'lease': args.get('lease')}
        for offset in range(0, len(encoded), 24_000):
            sent = send('provider.transfer.chunk', {**transfer, 'chunk': encoded[offset:offset + 24_000]})
            if not sent.get('ok'):
                return sent
        reply = send('provider.transfer.finish', transfer)
    else:
        reply = send(op, args)
    value = reply.get('value') if reply.get('ok') else None
    if isinstance(value, dict) and isinstance(value.get('transfer'), str):
        parts, offset = [], 0
        while offset <= 4_000_000:
            chunk = send('provider.transfer.read', {'lease': args.get('lease'), 'id': value['transfer'], 'offset': offset})
            data = chunk.get('value') if chunk.get('ok') else None
            if not isinstance(data, dict) or not isinstance(data.get('chunk'), str) or type(data.get('more')) is not bool:
                raise bridge.HostUnavailable('incomplete host transfer')
            parts.append(data['chunk'])
            offset += len(data['chunk'])
            if not data['more']:
                decoded = json.loads(base64.b64decode(''.join(parts), validate=True))
                if not isinstance(decoded, dict):
                    raise bridge.HostUnavailable('invalid host transfer')
                return decoded
            if not data['chunk']:
                break
        raise bridge.HostUnavailable('host transfer too large')
    return reply


def host_transport(task: str, *, model: str, effort: str, max_output_tokens: int | None = None,
                   lease: str | None = None, context: bridge.RequestContext | None | EllipsisType = ...) -> Transport | None:
    """An intake-style Transport, (system, user, schema) -> (payload, usage), answered by the host.

    Usage the runtime did not report comes back as None values, never as zero tokens.
    """
    if bridge.ACTIVE is None:
        return None
    context = bridge.REQUEST_CONTEXT.get() if context is ... else context

    def call(system: str, user: str, schema: dict) -> tuple[dict, dict]:
        try:
            reply = private_call('provider.completeJson', {
                'task': task, 'system': system, 'user': user, 'schema': schema, 'model': model,
                'effort': effort, 'maxOutputTokens': max_output_tokens, **({'lease': lease} if lease is not None else {})},
                context=context, timeout=CALL_SECONDS)
        except bridge.HostUnavailable:
            raise GateClosed('host-provider') from None
        value = reply.get('value') if reply.get('ok') else None
        if (not isinstance(value, dict) or not isinstance(value.get('json'), dict)
                or value.get('model') != model or value.get('effort') != effort):
            raise GateClosed('host-provider')
        usage = value.get('usage')
        if usage is None:
            return value['json'], {'input_tokens': None, 'output_tokens': None}
        if (not isinstance(usage, dict) or any(type(usage.get(k)) is not int or usage[k] < 0
                                              for k in ('inputTokens', 'outputTokens'))):
            raise GateClosed('host-provider-usage')
        return value['json'], {'input_tokens': usage['inputTokens'], 'output_tokens': usage['outputTokens']}
    return call
