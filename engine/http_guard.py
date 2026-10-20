"""ASGI guard: strip /api, tag robots, attribute NRC text, and log ids, routes, and status."""
from __future__ import annotations

import json
import logging

from starlette.responses import JSONResponse

from .copyright import PII_NOTICE, attach_meta, attribute_code

access_log = logging.getLogger('engine.access')


def _header(headers, name: bytes) -> bytes:
    for key, value in headers:
        if key.lower() == name:
            return value
    return b''


class HttpGuard:
    def __init__(self, app, sweep=None):
        self.app = app
        self.sweep = sweep

    async def __call__(self, scope, receive, send):
        if scope.get('type') != 'http':
            await self.app(scope, receive, send)
            return
        if self.sweep is not None:
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
                started['message'] = message
                started['headers'] = list(message.get('headers') or [])
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
                    payload = attach_meta(attribute_code(json.loads(raw)))
                    raw = json.dumps(payload).encode()
                except (ValueError, UnicodeError):
                    pass
                headers = [(key, value) for key, value in headers if key.lower() != b'content-length']
                headers.append((b'content-length', str(len(raw)).encode()))
            headers = [(key, value) for key, value in headers if key.lower() != b'x-robots-tag']
            headers.append((b'x-robots-tag', b'noindex, nofollow'))
            if not any(key.lower() == b'x-batatis-notice' for key, _ in headers):
                headers.append((b'x-batatis-notice', PII_NOTICE.encode()))
            start = dict(started['message'])
            start['headers'] = headers
            # Ids, route, and status only. Never the body, a quote, or uploaded bytes.
            access_log.info('%s %s %s', scope.get('method', '-'), route, start.get('status', '-'))
            await send(start)
            await send({'type': 'http.response.body', 'body': raw})

        await self.app(scope, receive, send_wrap)
