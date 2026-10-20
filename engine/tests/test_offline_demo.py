"""Offline identify serves the demo cache and does not invent a citation."""
import json
import os
import re
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


def _brief(case_id: str) -> str:
    return (ROOT / 'evals' / 'demo-cases' / case_id / 'input' / 'project-brief.md').read_text()


def _client(tmp_path):
    return TestClient(create_app(store=CaseStore(tmp_path / 'cases.sqlite'), codes=Codes()))


def _post(client, prose: str):
    case_id = client.post('/cases').json()['id']
    return client.post(f'/cases/{case_id}/identify', json={'prose': prose})


def test_no_key_serves_cached_demo_cases(tmp_path, monkeypatch):
    monkeypatch.delenv('OPENAI_API_KEY', raising=False)
    monkeypatch.delenv('BATATIS_OFFLINE', raising=False)
    client = _client(tmp_path)
    for case_id in DEMO_CASE_IDS:
        body = _post(client, _brief(case_id)).json()
        assert body['source'] == 'cache' and body['mode'] == 'cached_demo' and body['cached'] is True
        assert body['articles']
        assert all(article['suggested'] is False for article in body['articles'])
        assert all(
            article['snippet'] and len(article['snippet'].split(' … [clipped, see NBC')[0].split()) <= 25
            for article in body['articles'])
        assert 'compli' not in json.dumps(body).lower()


def test_unknown_case_is_an_offline_miss_without_a_citation(tmp_path, monkeypatch):
    monkeypatch.delenv('OPENAI_API_KEY', raising=False)
    monkeypatch.delenv('BATATIS_OFFLINE', raising=False)
    response = _post(_client(tmp_path), 'a proposal that is not one of the demo descriptions')
    assert response.status_code == 200
    body = response.json()
    assert body['mode'] == 'bm25_fallback' and body['source'] == 'bm25'
    assert body['section_c'] == []
    assert body['cached'] is False
    assert all(article['suggested'] is False for article in body['articles'])
    assert not any('committed' in article for article in body['articles'])
    assert all(article['decision'] is None and article['verifier_status'] == 'unknown' for article in body['articles'])
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
    hit = _post(_client(tmp_path), DEMO_CASE_IDS[0])
    assert hit.status_code == 200
    assert hit.json()['source'] == 'cache' and hit.json()['mode'] == 'cached_demo'
    assert hit.json()['cached'] is True
    assert all(article['suggested'] is False for article in hit.json()['articles'])
    miss = _post(_client(tmp_path), 'something the cache has never seen')
    assert miss.status_code == 200 and miss.json()['mode'] == 'bm25_fallback'
    assert miss.json()['section_c'] == []
    assert not any('committed' in article for article in miss.json()['articles'])


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
    hit = _post(client, DEMO_CASE_IDS[1])
    miss = _post(client, 'not a cached description')
    assert hit.json()['source'] == 'cache' and hit.json()['mode'] == 'cached_demo'
    assert miss.json()['mode'] == 'bm25_fallback'


def test_build_script_records_the_offline_run_without_a_key(tmp_path):
    env = os.environ.copy()
    env.pop('OPENAI_API_KEY', None)
    env.pop('ANTHROPIC_API_KEY', None)
    env.pop('BATATIS_LIVE', None)
    env.pop('BATATIS_OFFLINE', None)
    before = CACHE.read_bytes()
    done = subprocess.run([sys.executable, str(ROOT / 'scripts' / 'build_demo_cache.py')],
                          cwd=ROOT, env=env, capture_output=True, text=True)
    assert 'sk-' not in done.stderr and 'sk-' not in done.stdout
    if not default_db().exists():
        assert done.returncode == 2
        assert 'code database not found' in done.stderr
        assert CACHE.read_bytes() == before
        return
    assert done.returncode == 0, done.stderr
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
        assert match_demo(row['id'])['mode'] == 'cached_demo'
    assert seen


def test_cached_snippets_are_verbatim_codedb_prefixes():
    if not default_db().exists():
        pytest.skip('codedb is not built')
    codes = Codes()
    raw = CACHE.read_text()
    rows = json.loads(raw)
    for row in rows:
        for article in row['payload']['articles']:
            record = codes.provision(article['provision'], 'B')
            flat = re.sub(r'\s+', ' ', record['text'] or '').strip()
            snippet = article['snippet']
            assert 1 <= len(snippet.split()) <= 25
            sentence_hit = False
            for child in record.get('children') or []:
                if child.get('level') != 'sentence':
                    continue
                sentence = codes.provision(child['id'], 'B') or {}
                text = re.sub(r'\s+', ' ', sentence.get('text') or '').strip()
                sentence_hit = sentence_hit or text.startswith(snippet)
            assert flat.startswith(snippet) or sentence_hit
            if len(flat.split()) > 25:
                assert flat not in raw and record['text'] not in raw
