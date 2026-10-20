"""Karen's pre-public checks: privacy notice, codedb 404s, identify cap and rate limit."""
from __future__ import annotations

import json
import re
import sqlite3
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread

import pytest
from fastapi.testclient import TestClient

from engine.api import create_app
from engine.identify_http import CODEDB_DOWNLOADS, IDENTIFY_MAX_INPUT, IDENTIFY_MAX_OUTPUT, IDENTIFY_MODEL, KEYWORD_LABEL
from engine.llm_gate import reset_for_tests
from engine.privacy import PRIVACY_HEADER, PRIVACY_SENTENCE, PROCESSOR_LINE
from engine.spend import token_cost
from engine.tests.test_spend import _prepare

ROOT = Path(__file__).resolve().parents[2]
MARKER = b'SQLite format 3'


def test_privacy_notice_names_openai_us_in_the_api_and_the_sidebar():
    web = (ROOT / 'web/src/privacy.ts').read_text()
    sidebar = (ROOT / 'web/src/App.tsx').read_text()
    assert PRIVACY_SENTENCE in web and PROCESSOR_LINE in web
    assert 'PRIVACY_SENTENCE' in sidebar and 'PROCESSOR_LINE' in sidebar
    assert 'OpenAI (US)' in PROCESSOR_LINE and 'processor' in PROCESSOR_LINE
    assert PRIVACY_SENTENCE == 'Do not upload personal information. Demo data may be deleted.'
    reset_for_tests()
    response = TestClient(create_app()).get('/status/budget')
    assert response.status_code == 200
    notice = response.headers['x-batatis-notice']
    assert PRIVACY_SENTENCE in notice
    assert PROCESSOR_LINE in notice
    assert notice == PRIVACY_HEADER


def test_daily_budget_variable_does_not_limit_spend(tmp_path, monkeypatch):
    """#24's $5/day variable is not a cap. The total is BATATIS_TOTAL_BUDGET_USD."""
    path = _prepare(tmp_path, monkeypatch, cap='20')
    monkeypatch.setenv('BATATIS_DAILY_SPEND_CAP_USD', '0')
    seen = []
    from engine.spend import keyed_openai_call
    from engine.spend import ROUTE_IDENTIFY_RERANK
    result = keyed_openai_call(
        route=ROUTE_IDENTIFY_RERANK, model='gpt-4.1-mini',
        max_input_tokens=35000, max_output_tokens=0,
        client=lambda: seen.append(1) or {'usage': {'prompt_tokens': 35000, 'completion_tokens': 0}})
    assert result.offline is False and seen == [1]
    gate = (ROOT / 'engine/llm_gate.py').read_text()
    spend = (ROOT / 'engine/spend.py').read_text()
    assert "os.environ.get('BATATIS_DAILY_SPEND_CAP_USD')" not in gate
    assert "os.environ.get('BATATIS_DAILY_SPEND_CAP_USD')" not in spend


def test_engine_codedb_paths_404_and_do_not_return_the_file(tmp_path, monkeypatch):
    planted = tmp_path / 'codedb' / 'build' / 'codedb.sqlite'
    planted.parent.mkdir(parents=True)
    planted.write_bytes(MARKER + b'\x00not-for-download')
    monkeypatch.setenv('BATATIS_CODEDB', str(planted))
    client = TestClient(create_app())
    for path in ('/codedb.sqlite', '/codedb/build/codedb.sqlite', '/api/codedb/build/codedb.sqlite'):
        response = client.get(path)
        assert response.status_code == 404, path
        assert MARKER not in response.content
        assert 'not-for-download' not in response.text
        assert response.json()['detail'] == 'not found'
    assert '/api/codedb/build/codedb.sqlite' in CODEDB_DOWNLOADS


def _vercel_routes():
    config = json.loads((ROOT / 'vercel.json').read_text())
    return config['routes']


def _routed_status(path: str, dist: Path) -> tuple[int, bytes]:
    """Apply vercel.json routes, then a file in dist. A 404 route wins over a planted file."""
    for route in _vercel_routes():
        if route.get('src') and re.search(route['src'], path):
            if route.get('status') == 404:
                return 404, b'not found'
    file = dist / path.lstrip('/')
    if file.is_file():
        return 200, file.read_bytes()
    return 404, b'missing'


def test_vercel_routes_404_a_planted_codedb_sqlite(tmp_path):
    dist = tmp_path / 'dist'
    for path in ('/codedb.sqlite', '/codedb/build/codedb.sqlite', '/api/codedb/build/codedb.sqlite'):
        file = dist / path.lstrip('/')
        file.parent.mkdir(parents=True, exist_ok=True)
        file.write_bytes(MARKER + b'\x00planted')
        status, body = _routed_status(path, dist)
        assert status == 404, path
        assert MARKER not in body

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            status, body = _routed_status(self.path.split('?', 1)[0], dist)
            self.send_response(status)
            self.send_header('content-type', 'text/plain')
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *_args):
            return

    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    Thread(target=server.serve_forever, daemon=True).start()
    try:
        for path in ('/codedb.sqlite', '/codedb/build/codedb.sqlite', '/api/codedb/build/codedb.sqlite'):
            with pytest.raises(urllib.error.HTTPError) as caught:
                urllib.request.urlopen(f'http://127.0.0.1:{server.server_address[1]}{path}')
            assert caught.value.code == 404
            assert MARKER not in caught.value.read()
    finally:
        server.shutdown()


def test_identify_falls_back_to_keyword_search_when_the_cap_is_exhausted(tmp_path, monkeypatch):
    reset_for_tests()
    estimate = token_cost(IDENTIFY_MODEL, IDENTIFY_MAX_INPUT, IDENTIFY_MAX_OUTPUT)
    path = _prepare(tmp_path, monkeypatch, cap=format(estimate, 'f'))
    monkeypatch.setenv('BATATIS_LLM_RATE_LIMIT', '20')
    seen = []

    def client():
        seen.append('called')
        return {'usage': {'prompt_tokens': IDENTIFY_MAX_INPUT, 'completion_tokens': IDENTIFY_MAX_OUTPUT}}

    http = TestClient(create_app(identify_client=client))
    first = http.post('/identify', json={'query': 'soffit limiting distance'})
    assert first.status_code == 200
    assert seen == ['called']
    assert first.json()['label'] == 'model'
    second = http.post('/identify', json={'query': 'soffit limiting distance'})
    assert second.status_code == 200
    body = second.json()
    assert body['label'] == KEYWORD_LABEL
    assert body['label'] == 'keyword search, no AI'
    assert "demo's spending limit has been reached" in body['notice']
    assert seen == ['called']
    with sqlite3.connect(path) as con:
        statuses = [row[0] for row in con.execute('SELECT status FROM spend_ledger ORDER BY id')]
    assert statuses == ['settled']


def test_identify_returns_429_at_the_per_ip_limit(monkeypatch):
    reset_for_tests()
    monkeypatch.delenv('BATATIS_LIVE', raising=False)
    monkeypatch.setenv('BATATIS_LLM_RATE_LIMIT', '1')
    monkeypatch.setenv('BATATIS_LLM_RATE_WINDOW_SECONDS', '600')
    seen = []
    http = TestClient(create_app(identify_client=lambda: seen.append('called')))
    first = http.post('/identify', json={'query': 'egress window'})
    assert first.status_code == 200
    assert first.json()['label'] == KEYWORD_LABEL
    assert seen == []
    blocked = http.post('/identify', json={'query': 'egress window'})
    assert blocked.status_code == 429
    assert blocked.headers['retry-after']
    assert 'limit' in blocked.json()['detail'].lower()
    assert seen == []
    other = http.post('/identify', json={'query': 'egress window'}, headers={'X-Forwarded-For': '203.0.113.5'})
    assert other.status_code == 200
