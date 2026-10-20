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
    CODEDB_DOWNLOADS, IDENTIFY_MAX_OUTPUT, IDENTIFY_MODEL, KEYWORD_LABEL, MODEL_LABEL,
    identify_messages, identify_response_format,
)
from engine.llm_gate import SlidingWindow, reset_for_tests
from engine.spend import LEDGER_NOTICE, estimate_input_tokens, openai_chat_json, token_cost
from engine.tests.test_spend import _install, _prepare

ROOT = Path(__file__).resolve().parents[2]
MARKER = b'SQLite format 3'


def test_spend_change_does_not_duplicate_the_shared_privacy_notice():
    """#24 owns the shared notice. Its later integration must be allowed."""
    for banned in ('up to 30 days', 'cases stay until deleted', 'Cases do not expire'):
        assert banned not in (ROOT / 'docs/api-contract.md').read_text()
        assert banned not in (ROOT / 'docs/deploy.md').read_text()
    sidebar = (ROOT / 'web/src/App.tsx').read_text()
    assert 'DELETE /cases' not in sidebar
    assert sidebar.count('privacy-notice') <= 1
    reset_for_tests()
    response = TestClient(create_app()).get('/status/budget')
    assert response.status_code == 200
    # Header text, purge, deletion, and canonical web/engine equality are tested
    # by #24. Never require those headers/files to be absent on this branch.


def test_delete_case_route_removes_the_case(tmp_path):
    """DELETE /cases/{id} removes a stored case.

    Manual check (no web unit runner in web/package.json): open the app, choose
    Delete this case, confirm in the dialog, and see an empty case on Describe.
    Cancel leaves the current case. A failed request shows an error and does not clear.
    """
    from engine.store import CaseStore
    http = TestClient(create_app(CaseStore(tmp_path / 'cases.sqlite')))
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


def test_vercel_json_sets_robots_noindex_on_every_route():
    config = json.loads((ROOT / 'vercel.json').read_text())
    routes = _vercel_routes()
    global_headers = {
        h['key'].lower(): h['value']
        for entry in config.get('headers', []) if entry.get('source') == '/(.*)'
        for h in entry.get('headers', [])
    }
    if global_headers.get('x-robots-tag') != 'noindex, nofollow':
        assert routes
        for route in routes:
            headers = {key.lower(): value for key, value in (route.get('headers') or {}).items()}
            assert headers.get('x-robots-tag') == 'noindex, nofollow', route.get('src')
    index = (ROOT / 'web/index.html').read_text()
    assert 'name="robots"' in index and 'content="noindex, nofollow"' in index


def test_daily_budget_variable_does_not_limit_spend(tmp_path, monkeypatch):
    """#24's $5/day variable is not a cap. The total is BATATIS_TOTAL_BUDGET_USD."""
    _prepare(tmp_path, monkeypatch, cap='20')
    monkeypatch.setenv('BATATIS_DAILY_SPEND_CAP_USD', '0')
    seen = []
    _install(monkeypatch, seen, completion=0)
    result = openai_chat_json(
        [{'role': 'user', 'content': 'soffit'}], model='gpt-4.1-mini', max_completion_tokens=8)
    assert result.offline is False and len(seen) == 1
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
    for path in (*CODEDB_DOWNLOADS, '/reference/text/NBC.jsonl', '/codedb/build/extract.jsonl'):
        response = client.get(path)
        assert response.status_code == 404, path
        assert MARKER not in response.content
        assert 'not-for-download' not in response.text
        assert response.json()['detail'] == 'not found'
    assert '/api/codedb/build/codedb.sqlite' in CODEDB_DOWNLOADS


def _vercel_routes():
    config = json.loads((ROOT / 'vercel.json').read_text())
    return config.get('routes', [])


def _routed_status(path: str, dist: Path) -> tuple[int, bytes]:
    """Apply vercel.json routes, then a file in dist. A 404 route wins over a planted file."""
    for route in _vercel_routes():
        if route.get('src') and re.search(route['src'], path):
            if route.get('status') == 404:
                return 404, b'not found'
    config = json.loads((ROOT / 'vercel.json').read_text())
    for rewrite in config.get('rewrites', []):
        if re.search(rewrite['source'], path):
            destination = rewrite.get('destination')
            if isinstance(destination, dict) and destination.get('service') == 'engine':
                from engine.identify_http import codedb_download
                if codedb_download(path):
                    return 404, b'not found'
            break
    file = dist / path.lstrip('/')
    if file.is_file():
        return 200, file.read_bytes()
    return 404, b'missing'


def test_vercel_routes_404_a_planted_codedb_sqlite(tmp_path):
    dist = tmp_path / 'dist'
    for path in (*CODEDB_DOWNLOADS, '/reference/text/NBC.jsonl', '/codedb/build/extract.jsonl'):
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
        for path in (*CODEDB_DOWNLOADS, '/reference/text/NBC.jsonl', '/codedb/build/extract.jsonl'):
            with pytest.raises(urllib.error.HTTPError) as caught:
                urllib.request.urlopen(f'http://127.0.0.1:{server.server_address[1]}{path}')
            assert caught.value.code == 404
            assert MARKER not in caught.value.read()
    finally:
        server.shutdown()


_ARTICLE_ID = '9.10.15.4.'
_CANDIDATES = {_ARTICLE_ID: {'title': 'Fixture', 'text': 'Fixture text'}}


def _identify_estimate(query: str):
    return token_cost(
        IDENTIFY_MODEL, estimate_input_tokens(identify_messages(query, _CANDIDATES),
            identify_response_format(list(_CANDIDATES)), max_completion_tokens=IDENTIFY_MAX_OUTPUT),
        IDENTIFY_MAX_OUTPUT)


def _install_identify(monkeypatch, seen, query: str):
    _bm25(monkeypatch)
    reserved = estimate_input_tokens(identify_messages(query, _CANDIDATES),
        identify_response_format(list(_CANDIDATES)), max_completion_tokens=IDENTIFY_MAX_OUTPUT)

    def post(payload, key):
        seen.append(payload)
        return {
            'model': payload['model'],
            'service_tier': 'default',
            'usage': {'prompt_tokens': reserved, 'completion_tokens': IDENTIFY_MAX_OUTPUT},
            'choices': [{'finish_reason': 'stop', 'message': {'content': json.dumps({'hits': [_ARTICLE_ID]})}}],
        }

    monkeypatch.setattr('engine.spend._post_chat', post)


def test_identify_falls_back_to_keyword_search_when_the_cap_is_exhausted(tmp_path, monkeypatch):
    reset_for_tests()
    query = 'soffit limiting distance'
    estimate = _identify_estimate(query)
    path = _prepare(tmp_path, monkeypatch, cap=format(estimate, 'f'))
    monkeypatch.setenv('BATATIS_LLM_RATE_LIMIT', '20')
    seen = []
    _install_identify(monkeypatch, seen, query)
    http = TestClient(create_app())
    first = http.post('/identify', json={'query': query})
    assert first.status_code == 200
    assert len(seen) == 1
    assert seen[0]['max_completion_tokens'] == IDENTIFY_MAX_OUTPUT
    assert first.json()['label'] == MODEL_LABEL
    assert first.json()['label'] == 'model output, not verified'
    second = http.post('/identify', json={'query': query})
    assert second.status_code == 200
    body = second.json()
    assert body['label'] == KEYWORD_LABEL
    assert body['label'] == 'keyword search, no AI'
    assert "demo's spending limit has been reached" in body['notice']
    assert len(seen) == 1
    with sqlite3.connect(path) as con:
        statuses = [row[0] for row in con.execute('SELECT status FROM spend_ledger ORDER BY id')]
    assert statuses == ['settled']


def test_identify_returns_429_at_the_per_ip_limit(monkeypatch):
    reset_for_tests()
    monkeypatch.delenv('BATATIS_LIVE', raising=False)
    monkeypatch.setenv('BATATIS_LLM_RATE_LIMIT', '1')
    monkeypatch.setenv('BATATIS_LLM_RATE_WINDOW_SECONDS', '600')
    seen = []
    _install(monkeypatch, seen)
    http = TestClient(create_app())
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
    monkeypatch.setattr('engine.identify.corpus.articles', lambda *args: _CANDIDATES)


def test_identify_falls_back_to_bm25_when_the_ledger_is_unavailable(monkeypatch):
    reset_for_tests()
    monkeypatch.setenv('BATATIS_LIVE', '1')
    monkeypatch.setenv('OPENAI_API_KEY', 'test-openai-key')
    monkeypatch.setenv('BATATIS_TOTAL_BUDGET_USD', '20')
    monkeypatch.delenv('DATABASE_URL', raising=False)
    monkeypatch.delenv('POSTGRES_URL', raising=False)
    _bm25(monkeypatch)
    seen = []
    _install(monkeypatch, seen)
    http = TestClient(create_app())
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
    query = 'soffit limiting distance'
    estimate = _identify_estimate(query)
    _prepare(tmp_path, monkeypatch, cap=format(estimate, 'f'))
    _bm25(monkeypatch)
    seen = []
    _install_identify(monkeypatch, seen, query)
    http = TestClient(create_app())
    http.post('/identify', json={'query': query})
    response = http.post('/identify', json={'query': query})
    body = response.json()
    assert response.status_code == 200
    assert body['label'] == KEYWORD_LABEL
    assert body['notice']
    assert 'keyword search, no AI' in response.text
    assert body['hits'] == ['9.10.15.4.']
    assert len(seen) == 1


def test_identify_llm_error_falls_back_with_hits(tmp_path, monkeypatch):
    """A provider failure keeps its reservation and returns labelled BM25 hits."""
    reset_for_tests()
    path = _prepare(tmp_path, monkeypatch, cap='20')
    _bm25(monkeypatch)

    def boom(payload, key):
        raise RuntimeError('provider down')

    monkeypatch.setattr('engine.spend._post_chat', boom)
    http = TestClient(create_app())
    response = http.post('/identify', json={'query': 'soffit limiting distance'})
    assert response.status_code == 200
    body = response.json()
    assert body['label'] == KEYWORD_LABEL
    assert body['notice']
    assert body['hits'] == ['9.10.15.4.']
    assert body['hits'] != []
    with sqlite3.connect(path) as con:
        statuses = [row[0] for row in con.execute('SELECT status FROM spend_ledger ORDER BY id')]
    assert statuses == ['reserved']

    def refuse(payload, key):
        return {
            'model': payload['model'],
            'service_tier': 'default',
            'usage': {'prompt_tokens': 1, 'completion_tokens': 1},
            'choices': [{'message': {'refusal': 'no'}, 'finish_reason': 'refusal'}],
        }

    monkeypatch.setattr('engine.spend._post_chat', refuse)
    again = http.post('/identify', json={'query': 'soffit limiting distance'})
    assert again.status_code == 200
    assert again.json()['label'] == KEYWORD_LABEL
    assert again.json()['notice']
    assert again.json()['hits'] == ['9.10.15.4.']
    with sqlite3.connect(path) as con:
        statuses = [row[0] for row in con.execute('SELECT status FROM spend_ledger ORDER BY id')]
    assert statuses == ['reserved', 'reserved']


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


def test_sliding_window_evicts_expired_ips():
    import time
    window = SlidingWindow()
    window.events['old'] = [time.monotonic() - 10_000]
    window.events['fresh'] = [time.monotonic()]
    assert window.allow('new', limit=5, window_s=60) is True
    assert 'old' not in window.events
    assert 'fresh' in window.events
    assert 'new' in window.events


def test_live_model_result_is_labelled_and_has_no_accuracy_field(tmp_path, monkeypatch):
    reset_for_tests()
    _prepare(tmp_path, monkeypatch, cap='20')
    _bm25(monkeypatch)

    def post(payload, key):
        return {
            'model': payload['model'],
            'service_tier': 'default',
            'usage': {'prompt_tokens': 10, 'completion_tokens': 2},
            'accuracy': '9/11',
            'score': '50/60',
            'text': 'held-out accuracy 9/11 and 50/60',
            'choices': [{'finish_reason': 'stop', 'message': {'content': json.dumps({'hits': [_ARTICLE_ID]})}}],
        }

    monkeypatch.setattr('engine.spend._post_chat', post)
    http = TestClient(create_app())
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
