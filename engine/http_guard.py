"""ASGI guard: strip /api, tag robots, attribute NRC text, and log ids, routes, and status."""
from __future__ import annotations

import json
import logging

from starlette.responses import JSONResponse

from .copyright import attach_meta, attribute_code
from .privacy import PII_NOTICE

access_log = logging.getLogger('engine.access')


def _header(headers, name: bytes) -> bytes:
    for key, value in headers:
        if key.lower() == name:
            return value
    return b''


def private_editors(payload, user_id: str | None):
    """Unsubmitted editors stay owner-only, including nested cases in workflow responses.

    Filter the HTTP representation, never the stored model used by officer writes.
    """
    if isinstance(payload, list):
        return [private_editors(item, user_id) for item in payload]
    if isinstance(payload, dict):
        result = {key: private_editors(value, user_id) for key, value in payload.items()}
        if result.get('owner_id') and result['owner_id'] != user_id and 'applicant_draft' in result:
            result['applicant_draft'] = None
        return result
    return payload


class HttpGuard:
    def __init__(self, app, sweep=None):
        self.app = app
        self.sweep = sweep

    async def __call__(self, scope, receive, send):
        if scope.get('type') != 'http':
            await self.app(scope, receive, send)
            return
        # The explicit purge authenticates in its route before touching the store.
        if self.sweep is not None and scope.get('path') not in ('/retention/purge', '/api/retention/purge'):
            try:
                self.sweep()
            except Exception as exc:
                # Database errors may contain credentials. Only log the exception type.
                access_log.warning('case purge failed: %s', type(exc).__name__)
                response = JSONResponse(
                    attach_meta({'detail': 'case purge failed'}), status_code=503,
                    headers={'X-Robots-Tag': 'noindex, nofollow', 'X-Batatis-Notice': PII_NOTICE})
                await response(scope, receive, send)
                return
        path = scope.get('path') or ''
        if path == '/api' or path.startswith('/api/'):
            scope = dict(scope)
            scope['batatis_api_prefix'] = '/api'
            scope['path'] = path[4:] or '/'
            raw_path = scope.get('raw_path') or b''
            if raw_path.startswith(b'/api'):
                scope['raw_path'] = raw_path[4:] or b'/'
            path = scope['path']
        route = path.split('?', 1)[0]
        started: dict = {}
        chunks: list[bytes] = []

        async def send_wrap(message):
            if message['type'] == 'http.response.start':
                headers = list(message.get('headers') or [])
                if b'text/event-stream' in _header(headers, b'content-type'):
                    # Server-sent events pass through unbuffered so each stage arrives as it happens.
                    # The route attributes NRC text in its own payloads; the guard adds the same headers.
                    started['stream'] = True
                    headers = [(key, value) for key, value in headers
                               if key.lower() not in (b'x-robots-tag', b'x-batatis-notice', b'cache-control')]
                    headers += [(b'x-robots-tag', b'noindex, nofollow'), (b'x-batatis-notice', PII_NOTICE.encode()),
                                (b'cache-control', b'no-store')]
                    access_log.info('%s %s %s', scope.get('method', '-'), route, message.get('status', '-'))
                    await send({**message, 'headers': headers})
                    return
                started['message'] = message
                started['headers'] = headers
                return
            if started.get('stream'):
                await send(message)
                return
            if message['type'] != 'http.response.body':
                await send(message)
                return
            chunks.append(message.get('body') or b'')
            if message.get('more_body'):
                return
            raw = b''.join(chunks)
            headers = list(started.get('headers') or [])
            if raw and b'application/json' in _header(headers, b'content-type'):
                try:
                    user = scope.get('state', {}).get('user')
                    payload = attach_meta(attribute_code(private_editors(json.loads(raw), getattr(user, 'id', None))))
                    raw = json.dumps(payload).encode()
                except (ValueError, UnicodeError):
                    pass
                headers = [(key, value) for key, value in headers if key.lower() != b'content-length']
                headers.append((b'content-length', str(len(raw)).encode()))
            notice = next(((key, value) for key, value in headers if key.lower() == b'x-batatis-notice'),
                          (b'x-batatis-notice', PII_NOTICE.encode()))
            headers = [(key, value) for key, value in headers
                       if key.lower() not in (b'x-robots-tag', b'x-batatis-notice')]
            headers.append((b'x-robots-tag', b'noindex, nofollow'))
            headers.append(notice)
            if route.startswith(('/auth/', '/cases', '/me/', '/review/', '/assist')):
                headers = [(key, value) for key, value in headers if key.lower() != b'cache-control']
                headers.append((b'cache-control', b'no-store'))
            start = dict(started['message'])
            start['headers'] = headers
            # Ids, route, and status only. Never the body, a quote, or uploaded bytes.
            access_log.info('%s %s %s', scope.get('method', '-'), route, start.get('status', '-'))
            await send(start)
            await send({'type': 'http.response.body', 'body': raw})

        await self.app(scope, receive, send_wrap)
