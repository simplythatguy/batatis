"""ASGI guard: strip /api, tag robots, and clip provision text in JSON bodies."""
from __future__ import annotations

import json

from .copyright import clip_tree


def _header(headers, name: bytes) -> bytes:
    for key, value in headers:
        if key.lower() == name:
            return value
    return b''


class HttpGuard:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope.get('type') != 'http':
            await self.app(scope, receive, send)
            return
        path = scope.get('path') or ''
        if path == '/api' or path.startswith('/api/'):
            scope = dict(scope)
            scope['path'] = path[4:] or '/'
            raw = scope.get('raw_path') or b''
            if raw.startswith(b'/api'):
                scope['raw_path'] = raw[4:] or b'/'
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
            if b'application/json' in _header(headers, b'content-type'):
                try:
                    raw = json.dumps(clip_tree(json.loads(raw))).encode()
                except (ValueError, UnicodeError):
                    pass
                headers = [(key, value) for key, value in headers if key.lower() != b'content-length']
                headers.append((b'content-length', str(len(raw)).encode()))
            headers = [(key, value) for key, value in headers if key.lower() != b'x-robots-tag']
            headers.append((b'x-robots-tag', b'noindex, nofollow'))
            start = dict(started['message'])
            start['headers'] = headers
            await send(start)
            await send({'type': 'http.response.body', 'body': raw})

        await self.app(scope, receive, send_wrap)
