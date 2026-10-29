"""Synthetic HTTP acceptance for explicitly selected legacy Decisions; no live requests."""
import json
import re
import threading

import httpx
import pytest
from fastapi.testclient import TestClient

from engine import llm_gate
from engine.api import create_app
from engine.codes import Codes
from engine.identify import identify
from engine.identify.config import load_config
from engine.identify.jevkit import keystore
from engine.identify import providers
from engine.store import CaseStore
from engine.tests.test_relevance import create_described
from engine.tests.test_decisions import reply


@pytest.fixture
def world(tmp_path, monkeypatch):
    llm_gate.reset_for_tests()
    for name in ('BATATIS_PROVIDER', 'BATATIS_STORE', 'VERCEL', 'BATATIS_IDENTIFY_CONFIG'):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv('BATATIS_LIVE', '1')
    monkeypatch.setenv('BATATIS_IDENTIFY_SCREEN', 'decisions')
    monkeypatch.setenv('BATATIS_IDENTIFY_RERANK', 'decisions')
    monkeypatch.setenv('OPENAI_API_KEY', 'synthetic-key')
    monkeypatch.setenv('TYPESAFE_API_KEY', 'stale-synthetic-key')
    for limit in ('BATATIS_RELEVANCE_RATE_LIMIT', 'BATATIS_IDENTIFY_RATE_LIMIT', 'BATATIS_RELEVANCE_DAILY_RUNS'):
        monkeypatch.setenv(limit, '100')
    monkeypatch.setattr(keystore, 'resolve', lambda *_: pytest.fail('Decisions must not resolve Jev credentials'))
    monkeypatch.setattr(providers, 'raw_openai_json', lambda *_, **__: ({'picks': []}, {
        'input_tokens': 5, 'output_tokens': 0, 'returned_model': 'gpt-6-luna'}))
    calls = []
    lock = threading.Lock()

    def raw(body, timeout):
        with lock:
            calls.append(body)
        return {**reply(), 'answers': [{'type': 'predicate', 'name': q['name'], 'probability': 0.9}
                                       for q in body['questions']]}
    monkeypatch.setattr(providers, 'raw_openai_decisions', raw)
    store = CaseStore(tmp_path / 'cases.sqlite')
    with TestClient(create_app(store=store, codes=Codes())) as client:
        yield client, store, calls
    llm_gate.reset_for_tests()


def assert_provenance(record):
    assert record['model'] == 'relevance-2'
    assert record['config_hash'] == load_config().config_hash
    assert record['model_ids'] == {'screen': 'relevance-2', 'rerank': 'relevance-2'}
    assert record['bands'] == {'x': 0.0, 'y': 1.0, 'status': 'uncalibrated; display range only'}
    assert len(record['scores']) == 2080 and len(record['rerank']) == 60
    assert not re.search(r'jev|typesafe|openai|gpt|luna|decisions', json.dumps(record), re.I)


def test_explicit_decisions_and_jev_are_exhaustive_and_hash_distinct():
    current = load_config(env={'BATATIS_IDENTIFY_SCREEN': 'decisions', 'BATATIS_IDENTIFY_RERANK': 'decisions'})
    assert (current.screen, current.rerank, current.screen_model, current.rerank_model) == (
        'decisions', 'decisions', 'gpt-6-luna', 'gpt-6-luna')
    previous = load_config(env={'BATATIS_IDENTIFY_SCREEN': 'jev', 'BATATIS_IDENTIFY_RERANK': 'jev'})
    assert previous.screen_model == previous.rerank_model == 'jev-1.13.0'
    assert previous.exhaustive and current.exhaustive
    assert previous.config_hash != current.config_hash


def test_changed_jev_configuration_cannot_borrow_historical_relevance_cutoffs(world, monkeypatch):
    monkeypatch.setenv('BATATIS_PROVIDER', 'fake')
    monkeypatch.setenv('BATATIS_IDENTIFY_SCREEN', 'jev')
    monkeypatch.setenv('BATATIS_IDENTIFY_RERANK', 'jev')
    monkeypatch.setenv('BATATIS_IDENTIFY_CARD_CHARS', '1')
    client, _, _ = world
    case_id = create_described(client, 'SYNTHETIC: insulation')
    response = client.post(f'/cases/{case_id}/relevance')
    assert response.status_code == 200
    assert response.json()['bands'] == {'x': 0.0, 'y': 1.0, 'status': 'uncalibrated; display range only'}


def test_public_relevance_explicitly_selects_decisions_without_touching_stale_jev_key(world):
    client, store, calls = world
    case_id = create_described(client, 'SYNTHETIC: exterior insulation replaces housewrap.')
    result = client.post(f'/cases/{case_id}/relevance')
    assert result.status_code == 200, result.text
    record = result.json()
    assert_provenance(record)
    assert sum(len(c['questions']) for c in calls) == 2140
    assert all(1 <= len(c['questions']) <= 400 for c in calls)
    assert store.get(case_id).relevance.model == 'relevance-2'
    count = len(calls)
    assert client.get(f'/cases/{case_id}/relevance').json() == record
    assert len(calls) == count


def test_identify_json_and_stream_use_decisions_keep_choices_and_never_auto_commit(world):
    client, store, calls = world
    case_id = create_described(client, 'SYNTHETIC: insulation board.')
    response = client.post(f'/cases/{case_id}/identify')
    assert response.status_code == 200, response.text
    result = response.json()
    assert result['mode'] == 'live' and result['trace']['exhaustive']
    assert result['committed'] == [] and result['commit_policy']['status'] == 'uncalibrated'
    assert result['choices'] and result['model_ids'] == {
        'screen': 'relevance-2', 'rerank': 'relevance-2', 'verifier': 'verifier-1'}
    assert result['trace']['config']['screen_model'] == 'relevance-2'
    assert result['trace']['stages'][0]['model'] == 'relevance-2'
    assert 'scoring' in result['trace']['spend'] and 'verification' in result['trace']['spend']
    assert_provenance(client.get(f'/cases/{case_id}/relevance').json())
    stream = client.post(f'/cases/{case_id}/identify', headers={'accept': 'text/event-stream'})
    assert stream.status_code == 200 and 'event: done' in stream.text
    assert '"method": "model"' in stream.text
    assert not re.search(r'jev|typesafe|openai|gpt|luna', stream.text, re.I)
    assert '"method": "decisions"' not in stream.text
    assert store.get(case_id).provisions == []


def test_library_identify_uses_same_default_and_records_its_configuration(world):
    _, _, calls = world
    result = identify('SYNTHETIC: insulation', Codes().db_path)
    assert result.model == 'gpt-6-luna'
    assert result.config_hash == load_config().config_hash
    assert result.model_ids == {'screen': 'gpt-6-luna', 'rerank': 'gpt-6-luna'}
    assert len(result.screen) == 2080 and len(result.ranked) == 60
    assert sum(len(c['questions']) for c in calls) == 2140


def test_injected_metered_decisions_judge_carries_its_actual_scoring_provenance(world):
    from engine.identify import Judge
    ask = providers.metered_decisions_ask(providers.raw_openai_decisions)
    result = identify('SYNTHETIC: insulation', Codes().db_path, judge=Judge(ask, workers=1))
    assert result.model == 'gpt-6-luna'
    assert result.methods == {'screen': 'decisions', 'rerank': 'decisions'}
    assert result.config_hash == load_config().config_hash


def test_cli_uses_default_pipeline_provenance_and_never_uses_unfitted_threshold(world):
    from engine import cli_sut
    out = cli_sut.run('SYNTHETIC: insulation', Codes().db_path)
    assert out['articles'] and not any(a['committed'] for a in out['articles'])
    assert out['section_c'] == []
    assert out['trace']['config_hash'] == load_config().config_hash
    assert out['trace']['config']['screen_model'] == 'relevance-2'
    assert 'commit_threshold' not in out['trace']
    assert out['trace']['commit_policy']['status'] == 'uncalibrated'
    assert not re.search(r'jev|typesafe|openai|gpt|luna', json.dumps(out), re.I)


@pytest.mark.parametrize('failure', ['refusal', 'missing_answer', 'timeout', 'http', 'budget'])
def test_failures_keep_previous_scores_and_identify_falls_back_without_commits(world, monkeypatch, failure):
    from engine.identify import screen
    monkeypatch.setattr(screen.time, 'sleep', lambda _: None)
    client, store, _ = world
    case_id = create_described(client, 'SYNTHETIC: insulation')
    path = f'/cases/{case_id}/relevance'
    previous = client.post(path).json()
    version = store.get(case_id).version

    def broken(body, timeout):
        if failure == 'timeout':
            raise httpx.ReadTimeout('secret provider body must never escape')
        if failure == 'http':
            response = httpx.Response(401, request=httpx.Request('POST', providers.DECISIONS_URL))
            raise httpx.HTTPStatusError('secret provider body must never escape', request=response.request,
                                        response=response)
        data = {**reply(), 'answers': [{'type': 'predicate', 'name': q['name'], 'probability': 0.9}
                                      for q in body['questions']]}
        if failure == 'refusal':
            data['answers'][0] = {'type': 'refusal', 'name': body['questions'][0]['name']}
        else:
            data['answers'].pop()
        return data
    monkeypatch.setattr(providers, 'raw_openai_decisions', broken)
    if failure == 'budget':
        monkeypatch.setenv('BATATIS_DAILY_SPEND_CAP_USD', '0')
    failed = client.post(path)
    assert failed.status_code == 503 and failed.json()['detail'] == 'Relevance scoring unavailable'
    assert client.get(path).json() == previous and store.get(case_id).version == version
    result = client.post(f'/cases/{case_id}/identify').json()
    assert result['mode'] == 'bm25_fallback' and result['committed'] == []
    assert result['model_ids'] == {'screen': None, 'rerank': None, 'verifier': None}
    # The identify run saved the case; only the returned case version moves.
    assert store.get(case_id).provisions == [] and client.get(path).json() == {**previous, 'case_version': previous['case_version'] + 1}
    assert 'secret provider' not in json.dumps(result)
    assert 'DecisionsProtocolError' not in json.dumps(result)


def test_decisions_relevance_needs_no_jev_key(world, monkeypatch):
    monkeypatch.delenv('TYPESAFE_API_KEY')
    monkeypatch.delenv('JEV_API_KEY', raising=False)
    client, _, _ = world
    case_id = create_described(client, 'SYNTHETIC: insulation')
    result = client.post(f'/cases/{case_id}/relevance')
    assert result.status_code == 200
    assert_provenance(result.json())


@pytest.mark.parametrize('endpoint', ['identify', 'relevance'])
def test_decisions_receives_redacted_description_and_hash_keeps_original(world, endpoint):
    from engine.relevance import description_hash
    client, _, calls = world
    text = 'SYNTHETIC: insulation. Call Priya Natarajan at 780-555-0199 or priya@example.com.'
    case_id = create_described(client, text)
    response = client.post(f'/cases/{case_id}/{endpoint}')
    assert response.status_code == 200
    assert response.json()['description_sha256'] == description_hash(text)
    sent = [json.loads(c['input'])['proposal'] for c in calls]
    assert sent and all('Natarajan' not in p and '780-555-0199' not in p and 'priya@example.com' not in p
                        for p in sent)


def test_explicit_jev_switch_back_remains_metered_and_historically_distinct(world, monkeypatch):
    from engine.identify.fakes import fake_jev_ask
    monkeypatch.setenv('BATATIS_IDENTIFY_SCREEN', 'jev')
    monkeypatch.setenv('BATATIS_IDENTIFY_RERANK', 'jev')
    monkeypatch.delenv('OPENAI_API_KEY')
    resolved = []
    monkeypatch.setattr(keystore, 'resolve', lambda name: resolved.append(name) or 'synthetic-key')
    from engine.identify import screen
    monkeypatch.setattr(screen, 'raw_jev_ask', lambda model: fake_jev_ask())
    monkeypatch.setattr(providers, 'raw_openai_decisions', lambda *_: pytest.fail('Decisions selected by stale default'))
    client, store, calls = world
    case_id = create_described(client, 'SYNTHETIC: insulation')
    result = client.post(f'/cases/{case_id}/relevance')
    assert result.status_code == 200, result.text
    record = result.json()
    assert record['model'] == 'relevance-1' and record['model_ids'] == {
        'screen': 'relevance-1', 'rerank': 'relevance-1'}
    assert record['bands']['status'] == 'benchmark-derived, not field-calibrated'
    assert record['config_hash'] == load_config().config_hash
    assert resolved and not calls and llm_gate._memory.today() > 0


def test_decisions_identify_cas_conflict_preserves_concurrent_edit(world, monkeypatch):
    client, store, _ = world
    case_id = create_described(client, 'SYNTHETIC: insulation')
    original = providers.raw_openai_decisions
    lock, changed = threading.Lock(), []

    def edit_during_request(body, timeout):
        with lock:
            if not changed:
                case = store.get(case_id)
                case.title = 'Concurrent user edit'
                store.put(case, expected_version=case.version)
                changed.append(True)
        return original(body, timeout)
    monkeypatch.setattr(providers, 'raw_openai_decisions', edit_during_request)
    response = client.post(f'/cases/{case_id}/identify')
    assert response.status_code == 409
    case = store.get(case_id)
    assert case.title == 'Concurrent user edit' and case.identify is None and case.relevance is None


def test_optional_structured_rerank_is_not_relabelled_as_decisions(world, monkeypatch):
    from engine.identify.fakes import fake_openai_json
    monkeypatch.setenv('BATATIS_IDENTIFY_RERANK', 'openai')
    monkeypatch.setattr(providers, 'raw_openai_json', fake_openai_json)
    client, _, _ = world
    case_id = create_described(client, 'SYNTHETIC: insulation')
    record = client.post(f'/cases/{case_id}/relevance').json()
    assert record['model_ids'] == {'screen': 'relevance-2', 'rerank': 'verifier-1'}


def test_injected_old_config_calibration_cannot_commit_new_config(world, monkeypatch):
    from pathlib import Path
    from engine.identify import articles
    from engine.identify.commit import CommitPolicy
    from engine.identify.pipeline import run
    from engine.identify.verify import Pick, Verification
    from engine.identify.providers import transports
    from engine.identify.corpus import card
    monkeypatch.setenv('BATATIS_PROVIDER', 'fake')
    codes = Codes()
    arts = articles(Path(codes.db_path))

    class Verifier:
        def verify(self, prose, candidates):
            selected = next(a for a in candidates if arts[a]['part'] == 9)
            quote = ' '.join(card(arts[selected], None).split()[:15])
            return Verification([Pick(article=selected, quote=quote, reason='Governs the proposal.', confidence=1)], [],
                                stop_reason='end_turn')
    previous = load_config(env={'BATATIS_IDENTIFY_SCREEN': 'jev', 'BATATIS_IDENTIFY_RERANK': 'jev'})
    old = CommitPolicy('calibrated', 'old configuration test fit', {9: 0.0001}, 3, previous.config_hash)
    result = run('SYNTHETIC: insulation board', codes=codes, transports=transports(), verifier=Verifier(),
                 policy=old).result
    assert result.trace.picks and result.committed == []
    assert result.commit_policy['status'] == 'uncalibrated'
