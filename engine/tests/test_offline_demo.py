"""Offline identify serves the demo cache and does not invent a citation."""
import json
import os
import socket
import subprocess
import sys
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient

from engine.api import create_app
from engine.codes import Codes, default_db
from engine.identify.demo_cache import DEMO_CASE_IDS, cache_key, match_demo
from engine.identify.offline import ProviderOutage
from engine.identify.pipeline import run
from engine.store import CaseStore

ROOT = Path(__file__).resolve().parents[2]
CACHE = ROOT / 'engine' / 'identify' / 'demo_cache.json'


def _description(case_id: str) -> str:
    return json.loads((ROOT / 'evals_dev' / 'cases' / f'{case_id}.json').read_text())['description']


def _client(tmp_path):
    return TestClient(create_app(store=CaseStore(tmp_path / 'cases.sqlite'), codes=Codes()))


def _post(client, prose: str):
    case_id = client.post('/cases').json()['id']
    return client.post(f'/cases/{case_id}/identify', json={'prose': prose})


def test_no_key_serves_cached_demo_cases(tmp_path, monkeypatch):
    monkeypatch.delenv('OPENAI_API_KEY', raising=False)
    monkeypatch.delenv('BATATIS_OFFLINE', raising=False)
    client = _client(tmp_path)
    expected = {'dev-001': '9.10.15.5.', 'dev-003': '9.10.13.13.', 'dev-013': '3.4.2.1.'}
    for case_id, provision in expected.items():
        body = _post(client, _description(case_id)).json()
        assert body['source'] == 'cache' and body['mode'] == 'cached_demo'
        assert body['benchmark']['provision'] == provision
        assert body['articles']
        assert 'compli' not in json.dumps(body).lower()


def test_unknown_case_is_an_offline_miss_without_a_citation(tmp_path, monkeypatch):
    monkeypatch.delenv('OPENAI_API_KEY', raising=False)
    monkeypatch.delenv('BATATIS_OFFLINE', raising=False)
    response = _post(_client(tmp_path), 'a proposal that is not one of the demo descriptions')
    assert response.status_code == 200
    body = response.json()
    assert body['mode'] == 'bm25_fallback' and body['source'] == 'bm25'
    assert body['section_c'] == []
    assert not any(article.get('committed') for article in body['articles'])
    assert all(article['verifier_status'] == 'unknown' for article in body['articles'])
    assert 'hidden' not in response.text


def test_network_error_falls_back_to_the_cache(tmp_path, monkeypatch):
    monkeypatch.setenv('OPENAI_API_KEY', 'test-not-a-real-key')
    monkeypatch.setenv('BATATIS_LIVE', '1')
    monkeypatch.delenv('BATATIS_OFFLINE', raising=False)

    def boom(*args, **kwargs):
        if kwargs.get('ranker') == 'bm25':
            from engine.identify.pipeline import run as real_run
            return real_run(*args, **kwargs)
        raise httpx.ConnectError('simulated network failure')

    monkeypatch.setattr('engine.routes_case.identify_run', boom)
    hit = _post(_client(tmp_path), _description('dev-001'))
    assert hit.status_code == 200
    assert hit.json()['source'] == 'cache' and hit.json()['mode'] == 'cached_demo'
    assert hit.json()['benchmark']['provision'] == '9.10.15.5.'
    miss = _post(_client(tmp_path), 'something the cache has never seen')
    assert miss.status_code == 200 and miss.json()['mode'] == 'bm25_fallback'
    assert miss.json()['section_c'] == []
    assert not any(article.get('committed') for article in miss.json()['articles'])


def test_verifier_timeout_is_a_provider_outage(monkeypatch):
    monkeypatch.setenv('OPENAI_API_KEY', 'test-not-a-real-key')
    monkeypatch.setattr('engine.identify.llm.score_candidates', lambda *args, **kwargs: [('9.10.15.5.', 0.9)])

    def boom(*args, **kwargs):
        raise httpx.TimeoutException('simulated timeout')

    monkeypatch.setattr('engine.identify.llm.verify_candidates', boom)
    arts = {'9.10.15.5.': {
        'id': '9.10.15.5.', 'part': 9, 'title': 'Soffit', 'section': 's', 'subsection': 'ss',
        'text': 'The soffit shall be noncombustible.',
    }}
    with pytest.raises(ProviderOutage):
        run('soffit', arts=arts)


def test_offline_mode_makes_no_socket_connection(tmp_path, monkeypatch):
    monkeypatch.setenv('OPENAI_API_KEY', 'test-not-a-real-key')
    monkeypatch.setenv('BATATIS_OFFLINE', '1')

    def blocked(*args, **kwargs):
        raise AssertionError('offline mode opened a network connection')

    monkeypatch.setattr(socket.socket, 'connect', blocked)
    monkeypatch.setattr(socket, 'create_connection', blocked)
    client = _client(tmp_path)
    hit = _post(client, _description('dev-003'))
    miss = _post(client, 'not a cached description')
    assert hit.json()['source'] == 'cache' and hit.json()['mode'] == 'cached_demo'
    assert miss.json()['mode'] == 'bm25_fallback'


def test_build_script_refuses_to_write_without_a_key(tmp_path):
    env = os.environ.copy()
    env.pop('OPENAI_API_KEY', None)
    env.pop('BATATIS_OFFLINE', None)
    before = CACHE.read_bytes()
    done = subprocess.run([sys.executable, str(ROOT / 'scripts' / 'build_demo_cache.py')],
                          cwd=ROOT, env=env, capture_output=True, text=True)
    assert done.returncode == 2
    assert 'OPENAI_API_KEY is not set' in done.stderr
    assert 'sk-' not in done.stderr and 'sk-' not in done.stdout
    assert CACHE.read_bytes() == before


def test_cached_citations_resolve_in_codedb():
    if not default_db().exists():
        pytest.skip('codedb is not built')
    codes = Codes()
    rows = json.loads(CACHE.read_text())
    assert [row['id'] for row in rows] == list(DEMO_CASE_IDS)
    seen = []
    for row in rows:
        assert row['description_sha256'] == cache_key(row['description'])
        payload = row['payload']
        ids = [article['provision'] for article in payload['articles']]
        benchmark = payload.get('benchmark') or {}
        if benchmark.get('provision'):
            ids.append(benchmark['provision'])
        for item in list(benchmark.get('section_c') or []) + list(payload.get('section_c') or []):
            ids.append(item['provision_id'])
            assert codes.citation(item['provision_id'], 'B') == item['citation']
        assert ids
        for provision_id in ids:
            assert codes.provision(provision_id, 'B') is not None
            seen.append(provision_id)
        assert match_demo(row['description'])['source'] == 'cache'
    assert seen
