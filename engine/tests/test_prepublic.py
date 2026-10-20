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
from engine.ccmc import CCMCRegistry
from engine.identify_http import (
    CODEDB_DOWNLOADS, IDENTIFY_MAX_INPUT, IDENTIFY_MAX_OUTPUT, IDENTIFY_MODEL, KEYWORD_LABEL, MODEL_LABEL,
)
from engine.llm_gate import reset_for_tests
from engine.privacy import (
    DELETE_LINE, DONT_PASTE, LIVE_SEND_LINE, OPENAI_RETENTION_LINE, OPENAI_RETENTION_URL,
    PRIVACY_HEADER, PRIVACY_SENTENCE, PROCESSOR_LINE, privacy_header,
)
from engine.spend import LEDGER_NOTICE, live_enabled
from engine.spend import token_cost
from engine.tests.test_spend import _prepare

ROOT = Path(__file__).resolve().parents[2]
MARKER = b'SQLite format 3'


def test_privacy_notice_names_openai_us_in_the_api_and_the_sidebar():
    web = (ROOT / 'web/src/privacy.ts').read_text()
    sidebar = (ROOT / 'web/src/App.tsx').read_text()
    assert PRIVACY_SENTENCE in web and PROCESSOR_LINE in web
    assert DONT_PASTE in web and DELETE_LINE in web
    assert 'PRIVACY_SENTENCE' in sidebar and 'PROCESSOR_LINE' in sidebar
    assert 'DONT_PASTE' in sidebar and 'DELETE_LINE' in sidebar
    assert 'OpenAI (US)' in PROCESSOR_LINE and 'processor' in PROCESSOR_LINE
    assert PRIVACY_SENTENCE == 'Do not upload personal information. Demo data may be deleted.'
    assert DONT_PASTE == "Don't paste personal information you don't need."
    assert '7-day' not in (ROOT / 'engine/privacy.py').read_text()
    reset_for_tests()
    response = TestClient(create_app()).get('/status/budget')
    assert response.status_code == 200
    notice = response.headers['x-batatis-notice']
    assert PRIVACY_SENTENCE in notice
    assert PROCESSOR_LINE in notice
    assert DONT_PASTE in notice and DELETE_LINE in notice
    assert LIVE_SEND_LINE not in notice
    assert notice == PRIVACY_HEADER


def test_live_notice_names_openai_processing_and_the_delete_route(tmp_path, monkeypatch):
    """Live header says content is sent to OpenAI (US) and how to delete a case."""
    monkeypatch.setenv('BATATIS_LIVE', '1')
    monkeypatch.setenv('OPENAI_API_KEY', 'test-openai-key')
    assert live_enabled()
    contract = (ROOT / 'docs/api-contract.md').read_text()
    source = (ROOT / 'engine/privacy.py').read_text()
    verbatim = (
        'OpenAI may securely retain API inputs and outputs for up to 30 days to provide '
        'the services and to identify abuse.'
    )
    assert 'Checked 2026-10-20' in source
    assert verbatim in source
    assert OPENAI_RETENTION_URL in contract
    assert verbatim in contract
    assert '7-day' not in contract.split('### Privacy notice', 1)[1].split('### ', 1)[0]
    header = privacy_header(live=True)
    assert LIVE_SEND_LINE in header
    assert 'Pasted text and uploaded content are sent to OpenAI (US) for processing.' in header
    assert DONT_PASTE in header
    assert DELETE_LINE in header
    assert OPENAI_RETENTION_URL in header
    assert 'up to 30 days' in OPENAI_RETENTION_LINE
    reset_for_tests()
    from engine.store import CaseStore
    http = TestClient(create_app(CaseStore(tmp_path / 'cases.sqlite')))
    response = http.get('/status/budget')
    assert response.headers['x-batatis-notice'] == header
    created = http.post('/cases', json={'title': 'soffit trial'})
    assert created.status_code == 201
    case_id = created.json()['id']
    assert http.get(f'/cases/{case_id}').status_code == 200
    deleted = http.delete(f'/cases/{case_id}')
    assert deleted.status_code == 204
    assert deleted.content == b''
    missing = http.get(f'/cases/{case_id}')
    assert missing.status_code == 404
    assert missing.json()['detail'] == 'case not found'
    assert http.delete(f'/cases/{case_id}').status_code == 404


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
    assert first.json()['label'] == MODEL_LABEL
    assert first.json()['label'] == 'model output, not verified'
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


def _bm25(monkeypatch):
    monkeypatch.setattr(
        'engine.identify.corpus.bm25_rank',
        lambda query, path, limit=20: ['9.10.15.4.'],
    )


def test_identify_falls_back_to_bm25_when_the_ledger_is_unavailable(monkeypatch):
    reset_for_tests()
    monkeypatch.setenv('BATATIS_LIVE', '1')
    monkeypatch.setenv('OPENAI_API_KEY', 'test-openai-key')
    monkeypatch.setenv('BATATIS_TOTAL_BUDGET_USD', '20')
    monkeypatch.delenv('DATABASE_URL', raising=False)
    monkeypatch.delenv('POSTGRES_URL', raising=False)
    _bm25(monkeypatch)
    seen = []
    http = TestClient(create_app(identify_client=lambda: seen.append('called')))
    response = http.post('/identify', json={'query': 'soffit limiting distance'})
    assert response.status_code == 200
    body = response.json()
    assert body['label'] == 'keyword search, no AI'
    assert body['notice'] == LEDGER_NOTICE
    assert body['notice']
    assert body['hits'] == ['9.10.15.4.']
    assert seen == []


def test_identify_cap_fallback_keeps_the_bm25_label_and_the_notice(tmp_path, monkeypatch):
    reset_for_tests()
    estimate = token_cost(IDENTIFY_MODEL, IDENTIFY_MAX_INPUT, IDENTIFY_MAX_OUTPUT)
    _prepare(tmp_path, monkeypatch, cap=format(estimate, 'f'))
    _bm25(monkeypatch)
    seen = []

    def client():
        seen.append('called')
        return {'usage': {'prompt_tokens': IDENTIFY_MAX_INPUT, 'completion_tokens': IDENTIFY_MAX_OUTPUT}}

    http = TestClient(create_app(identify_client=client))
    http.post('/identify', json={'query': 'soffit limiting distance'})
    response = http.post('/identify', json={'query': 'soffit limiting distance'})
    body = response.json()
    assert response.status_code == 200
    assert body['label'] == KEYWORD_LABEL
    assert body['notice']
    assert 'keyword search, no AI' in response.text
    assert body['hits'] == ['9.10.15.4.']
    assert seen == ['called']


def _offline_registry(tmp_path):
    snapshot = tmp_path / 'registry.json'
    snapshot.write_text('{"items": [], "hasMore": false}')
    return CCMCRegistry(snapshot, '2026-10-18', offline=True)


def test_ccmc_search_returns_429_at_the_per_ip_limit(tmp_path, monkeypatch):
    reset_for_tests()
    monkeypatch.setenv('BATATIS_SEARCH_RATE_LIMIT', '1')
    monkeypatch.setenv('BATATIS_SEARCH_RATE_WINDOW_SECONDS', '600')
    http = TestClient(create_app(registry=_offline_registry(tmp_path)))
    first = http.get('/ccmc/search', params={'q': 'board'})
    assert first.status_code == 200
    blocked = http.get('/ccmc/search', params={'q': 'board'})
    assert blocked.status_code == 429
    assert blocked.headers['retry-after']
    assert blocked.json()['detail'].startswith('Search limit reached; try again in ')
    other = http.get('/ccmc/search', params={'q': 'board'}, headers={'x-vercel-forwarded-for': '198.51.100.20'})
    assert other.status_code == 200


def test_client_ip_is_taken_from_x_vercel_forwarded_for_first(tmp_path, monkeypatch):
    reset_for_tests()
    monkeypatch.delenv('BATATIS_LIVE', raising=False)
    monkeypatch.setenv('BATATIS_LLM_RATE_LIMIT', '1')
    monkeypatch.setenv('BATATIS_SEARCH_RATE_LIMIT', '1')
    http = TestClient(create_app(registry=_offline_registry(tmp_path)))
    both = {'x-vercel-forwarded-for': '198.51.100.8, 10.0.0.1', 'x-forwarded-for': '203.0.113.9'}
    assert http.post('/identify', json={'query': 'egress window'}, headers=both).status_code == 200
    forwarded_only = http.post(
        '/identify', json={'query': 'egress window'}, headers={'x-forwarded-for': '203.0.113.9'})
    assert forwarded_only.status_code == 200
    again = http.post('/identify', json={'query': 'egress window'}, headers=both)
    assert again.status_code == 429
    assert 'Live model limit reached' in again.json()['detail']
    assert http.get('/ccmc/search', params={'q': 'board'}, headers=both).status_code == 200
    assert http.get(
        '/ccmc/search', params={'q': 'board'}, headers={'x-forwarded-for': '203.0.113.9'}).status_code == 200
    blocked = http.get('/ccmc/search', params={'q': 'board'}, headers=both)
    assert blocked.status_code == 429
    assert blocked.json()['detail'].startswith('Search limit reached; try again in ')


def _reject_accuracy(payload: object) -> None:
    banned = ('9/11', '50/60')
    raw = json.dumps(payload)
    for item in banned:
        assert item not in raw

    def walk(value: object) -> None:
        if isinstance(value, dict):
            for key, item in value.items():
                assert key.lower() not in {'accuracy', 'score', 'scores'}
                walk(item)
        elif isinstance(value, list):
            for item in value:
                walk(item)

    walk(payload)


def test_live_model_result_is_labelled_and_has_no_accuracy_field(tmp_path, monkeypatch):
    reset_for_tests()
    _prepare(tmp_path, monkeypatch, cap='20')

    def client():
        return {
            'usage': {'prompt_tokens': 10, 'completion_tokens': 2},
            'accuracy': '9/11',
            'score': '50/60',
            'text': 'held-out accuracy 9/11 and 50/60',
        }

    http = TestClient(create_app(identify_client=client))
    identified = http.post('/identify', json={'query': 'soffit limiting distance'})
    assert identified.status_code == 200
    body = identified.json()
    assert body['label'] == 'model output, not verified'
    assert set(body) == {'label', 'notice', 'hits'}
    _reject_accuracy(body)
    assert '9/11' not in identified.text and '50/60' not in identified.text
    status = http.get('/status/budget')
    assert status.status_code == 200
    _reject_accuracy(status.json())
    created = http.post('/cases', json={'title': 'trial'})
    assert created.status_code == 201
    _reject_accuracy(created.json())
