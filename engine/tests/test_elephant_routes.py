"""Actual adapter + HTTP callers with a synthetic wire peer, never provider calls."""
import json
import os
import re
import socket

import pytest
from fastapi.testclient import TestClient

from engine import llm_gate
from engine.api import create_app
from engine.codes import Codes
from engine.identify import elephant_runtime as runtime, providers
from engine.identify.config import load_config
from engine.identify import identify
from engine.identify.jevkit import keystore
from engine.relevance import live_judge
from engine.store import CaseStore
from engine.tests.test_relevance import create_described, description_fact

PRIVATE = re.compile(r'elephant|baseten|openrouter|jev|typesafe|openai|gpt|luna|API_KEY|BATATIS_', re.I)


@pytest.fixture
def world(tmp_path, monkeypatch):
    for name in list(os.environ):
        if name.startswith(('BATATIS_', 'VERCEL')) or name.endswith('API_KEY'):
            monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv('BATATIS_LIVE', '0')
    monkeypatch.setenv('BATATIS_LIVE_ELEPHANT', '1')
    monkeypatch.setenv('OPENROUTER_API_KEY', 'synthetic-only-key')
    for name in ('BATATIS_RELEVANCE_RATE_LIMIT', 'BATATIS_IDENTIFY_RATE_LIMIT', 'BATATIS_RELEVANCE_DAILY_RUNS'):
        monkeypatch.setenv(name, '100')
    monkeypatch.setattr(socket.socket, 'connect', lambda *_: pytest.fail('unexpected network'))
    monkeypatch.setattr(keystore, 'resolve', lambda *_: pytest.fail('Jev credential resolution'))
    monkeypatch.setattr(providers, 'raw_openai_decisions', lambda *_: pytest.fail('paid scorer fallback'))
    monkeypatch.setattr(providers, 'raw_openai_json', lambda *_, **__: pytest.fail('disabled verifier called'))
    calls = []
    def synthetic(body, headers, timeout):
        data = json.loads(body)
        calls.append(data)
        assert data['model'] == 'baseten/elephant-1:free' and data['provider'] == runtime.ROUTING
        runtime.request_bytes(data['state'], data['questions'])
        return 200, json.dumps({'model': runtime.RESPONSE_MODEL,
            'answers': {name: {'type': 'noul', 'noul': 0.9} for name in data['questions']},
            'usage': {'input_tokens': 20, 'output_tokens': len(data['questions']), 'cost': 0}}).encode()
    monkeypatch.setattr(runtime, '_post_once', synthetic)
    llm_gate.reset_for_tests()
    store = CaseStore(tmp_path / 'cases.sqlite')
    with TestClient(create_app(store=store, codes=Codes())) as client:
        yield client, store, calls
    llm_gate.reset_for_tests()


def assert_record(record):
    assert record['model'] == 'relevance-3'
    assert record['config_hash'] == load_config().config_hash
    assert record['model_ids'] == {'screen': 'relevance-3', 'rerank': 'relevance-3'}
    assert len(record['scores']) == len(record['display']) == 2080 and len(record['rerank']) == 60
    assert record['bands'] == {'x': 0, 'y': 1, 'status': 'uncalibrated; display range only'}
    assert not PRIVATE.search(json.dumps(record))


def test_explicit_relevance_post_covers_all_articles_and_rerank_without_other_providers(world):
    client, store, calls = world
    case_id = create_described(client, 'SYNTHETIC: an insulation board.')
    assert calls == []  # no scoring on create, typing/saving, reads or navigation
    assert client.get(f'/cases/{case_id}/relevance').status_code == 404
    result = client.post(f'/cases/{case_id}/relevance')
    assert result.status_code == 200, result.text
    assert_record(result.json())
    assert sum(len(c['questions']) for c in calls) == 2140
    assert all(c['state']['proposal'] == 'SYNTHETIC: an insulation board.' for c in calls)
    assert store.get(case_id).relevance.model == 'relevance-3'
    n = len(calls)
    assert client.get(f'/cases/{case_id}/relevance').json() == result.json()
    assert len(calls) == n


def test_identify_json_and_stream_use_elephant_without_auto_commit_or_verifier_activation(world):
    client, store, calls = world
    case_id = create_described(client, 'SYNTHETIC: insulation board.')
    result = client.post(f'/cases/{case_id}/identify')
    assert result.status_code == 200, result.text
    body = result.json()
    assert body['mode'] == 'live' and body['trace']['exhaustive']
    assert body['committed'] == [] and body['commit_policy']['status'] == 'uncalibrated'
    assert body['choices'] and body['model_ids'] == {
        'screen': 'relevance-3', 'rerank': 'relevance-3', 'verifier': 'verifier-1'}
    assert body['trace']['spend'].keys() == {'scoring'}
    assert 'read in full' not in body['label'] and 'verification was unavailable' in body['label']
    assert sum(len(c['questions']) for c in calls) == 2140
    assert_record(client.get(f'/cases/{case_id}/relevance').json())
    stream = client.post(f'/cases/{case_id}/identify', headers={'accept': 'text/event-stream'})
    assert stream.status_code == 200 and 'event: done' in stream.text
    assert not PRIVATE.search(stream.text)
    assert store.get(case_id).provisions == []


@pytest.mark.parametrize('failure', ['rate_limited', 'timeout', 'malformed', 'stale_model', 'missing_key', 'disabled'])
def test_failures_preserve_saved_scores_and_label_identify_fallback(world, monkeypatch, failure):
    client, store, calls = world
    case_id = create_described(client, 'SYNTHETIC: insulation board.')
    path = f'/cases/{case_id}/relevance'
    previous = client.post(path).json()
    version = store.get(case_id).version
    attempted = []
    def fail_once(body, headers, timeout):
        attempted.append(1)
        if failure == 'rate_limited':
            return 429, b'{}'
        if failure == 'timeout':
            raise TimeoutError('synthetic-only-key provider body')
        if failure == 'malformed':
            return 200, b'not json'
        return 200, b'{"model":"baseten/elephant-1:free","answers":{}}'
    monkeypatch.setattr(runtime, '_post_once', fail_once)
    if failure == 'missing_key':
        monkeypatch.delenv('OPENROUTER_API_KEY')
    if failure == 'disabled':
        monkeypatch.setenv('BATATIS_LIVE_ELEPHANT', '0')
    result = client.post(path)
    assert result.status_code == 503 and result.json()['detail'] == 'Relevance scoring unavailable'
    assert store.get(case_id).version == version and client.get(path).json() == previous
    assert len(attempted) == (0 if failure in ('missing_key', 'disabled') else 1)
    fallback = client.post(f'/cases/{case_id}/identify').json()
    assert fallback['mode'] == 'bm25_fallback' and fallback['committed'] == []
    assert not fallback['trace']['exhaustive']
    assert fallback['trace']['fallback_reason'] == 'scoring unavailable'
    assert not PRIVATE.search(json.dumps(fallback))
    assert client.get(path).json() == previous


def test_library_judge_and_offline_fake_have_same_distinct_identity(world, monkeypatch):
    _, _, calls = world
    judge = live_judge()
    assert judge.method == 'elephant' and judge.model == 'baseten/elephant-1:free'
    result = identify('SYNTHETIC: insulation board.', Codes().db_path, judge=judge)
    assert result.methods == {'screen': 'elephant', 'rerank': 'elephant'}
    assert result.model == 'baseten/elephant-1:free' and len(result.screen) == 2080
    n = len(calls)
    monkeypatch.setenv('BATATIS_PROVIDER', 'fake')
    monkeypatch.delenv('OPENROUTER_API_KEY')
    fake = identify('SYNTHETIC: insulation board.', Codes().db_path)
    assert fake.model == result.model and fake.config_hash == result.config_hash
    assert len(fake.screen) == 2080 and len(fake.ranked) == 60 and len(calls) == n


def test_changed_description_marks_previous_record_stale_without_scoring(world):
    client, _, calls = world
    case_id = create_described(client, 'SYNTHETIC: insulation.')
    record = client.post(f'/cases/{case_id}/relevance').json()
    count = len(calls)
    client.post(f'/cases/{case_id}/facts', json={**description_fact('SYNTHETIC: different project.'), 'id': 'later'})
    assert client.get(f'/cases/{case_id}/relevance').json() == {**record, 'stale': True}
    assert len(calls) == count


def test_cli_keeps_injected_elephant_adapter_and_its_actual_provenance(world):
    from engine import cli_sut
    from engine.identify import Judge
    _, _, wire_calls = world
    batches = []
    def synthetic(state, questions, timeout):
        batches.append(len(questions))
        return {'answers': {name: {'noul': 0.5} for name in questions}, 'usage': {}}
    synthetic.method, synthetic.model = 'elephant', 'baseten/elephant-1:free'
    out = cli_sut.run('SYNTHETIC: insulation.', Codes().db_path, Judge(synthetic))
    assert sum(batches) == 2140 and wire_calls == []
    assert out['trace']['config']['screen_model'] == 'relevance-3'
    assert out['trace']['config_hash'] == load_config().config_hash
    assert out['section_c'] == [] and not any(a['committed'] for a in out['articles'])
