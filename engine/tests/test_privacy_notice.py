"""The web notice and the engine notice are one sentence, and no other notice remains."""
from __future__ import annotations

import re
from pathlib import Path

from fastapi.testclient import TestClient

from engine.copyright import PII_NOTICE as BODY_NOTICE
from engine.http_guard import HttpGuard
from engine.http_guard import PII_NOTICE as HEADER_NOTICE
from engine.privacy import PII_NOTICE, PRIVACY_NOTICE

ROOT = Path(__file__).resolve().parents[2]
ENGINE = ROOT / 'engine'
SKIP = {'.git', 'node_modules', 'dist', '__pycache__', '.venv', 'reference'}
OLD = 'Demo data ' + 'may be deleted.'


def _web_notice() -> str:
    text = (ROOT / 'web/src/privacy.ts').read_text()
    match = re.search(r'export const PRIVACY_NOTICE =\s*"([^"]*)"', text)
    assert match, 'web/src/privacy.ts does not export PRIVACY_NOTICE as one string'
    return match.group(1)


def _text_files():
    for path in ROOT.rglob('*'):
        if not path.is_file():
            continue
        if SKIP.intersection(path.parts):
            continue
        if path.suffix.lower() not in {'.py', '.ts', '.tsx', '.md', '.json', '.yml', '.css', '.mjs'}:
            continue
        yield path


def _header_values(response, name: bytes) -> list[str]:
    return [value.decode() for key, value in response.headers.raw if key.lower() == name]


def test_web_and_engine_notices_match_and_no_other_notice_remains():
    web = _web_notice()
    assert HEADER_NOTICE is BODY_NOTICE is PII_NOTICE is PRIVACY_NOTICE == web
    assert web.endswith('after 7 days or on request.')
    needle = PRIVACY_NOTICE.split('.', 1)[0]
    for path in ENGINE.rglob('*.py'):
        if '__pycache__' in path.parts:
            continue
        text = path.read_text(encoding='utf-8')
        assert OLD not in text, path.relative_to(ROOT)
        if path.resolve() == (ENGINE / 'privacy.py').resolve():
            assert text.count(PRIVACY_NOTICE) == 1
            assert needle not in text.replace(PRIVACY_NOTICE, '', 1)
            continue
        assert needle not in text, path.relative_to(ROOT)
        assert PRIVACY_NOTICE not in text, path.relative_to(ROOT)
    for path in _text_files():
        if ENGINE in path.parents or path == ENGINE:
            continue
        text = path.read_text(encoding='utf-8')
        assert OLD not in text, path.relative_to(ROOT)
        start = 0
        while True:
            found = text.find(needle, start)
            if found < 0:
                break
            assert text.startswith(PRIVACY_NOTICE, found), path.relative_to(ROOT)
            start = found + len(PRIVACY_NOTICE)


def test_each_response_has_one_notice_header_and_noindex():
    """A route that tries to set its own notice still leaves exactly one header."""

    async def inner(scope, receive, send):
        if scope['type'] != 'http':
            return
        body = b'' if scope.get('path') == '/empty' else b'{"ok": true}'
        headers = [
            [b'x-batatis-notice', b'replace-me'],
            [b'X-Batatis-Notice', b'also-replace-me'],
            [b'x-robots-tag', b'index, follow'],
        ]
        if body:
            headers.insert(0, [b'content-type', b'application/json'])
        await send({'type': 'http.response.start', 'status': 204 if not body else 200, 'headers': headers})
        await send({'type': 'http.response.body', 'body': body})

    client = TestClient(HttpGuard(inner))
    for path in ('/json', '/empty'):
        response = client.get(path)
        assert _header_values(response, b'x-batatis-notice') == [PRIVACY_NOTICE]
        assert _header_values(response, b'x-robots-tag') == ['noindex, nofollow']
        if path == '/json':
            assert response.json()['meta']['notice'] == PRIVACY_NOTICE
