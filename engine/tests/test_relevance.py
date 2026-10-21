"""Offline HTTP acceptance checks: real exhaustive pipeline with injectable fake Jev asks."""
import hashlib
import os
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from engine import llm_gate
from engine.api import create_app
from engine.codes import Codes
from engine.identify import Judge, articles
from engine.identify.jevkit import keystore
from engine.models import Case, Fact, Source
from engine.relevance import display_probabilities
from engine.routes_relevance import _save_record
from engine.store import CaseStore


@pytest.fixture(autouse=True)
def reset_gate(monkeypatch):
    llm_gate.reset_for_tests()
    monkeypatch.delenv('BATATIS_LIVE', raising=False)
    monkeypatch.setenv('BATATIS_RELEVANCE_RATE_LIMIT', '100')
    monkeypatch.setenv('BATATIS_RELEVANCE_DAILY_RUNS', '100')
    yield
    llm_gate.reset_for_tests()


@pytest.fixture(scope='module')
def codes():
    return Codes()


class FakeAsk:
    def __init__(self):
        self.calls = []
        self.failure = False
        self.block_proposal = None
        self.started = threading.Event()
        self.release = threading.Event()

    def __call__(self, state, questions, timeout):
        self.calls.append((state['proposal'], len(questions)))
        if state['proposal'] == self.block_proposal and not self.started.is_set():
            self.started.set()
            assert self.release.wait(10), 'test did not release scoring'
        if self.failure:
            raise TimeoutError('do not log provider bodies or secrets')
        rerank = len(questions) == 60
        return {'answers': {q: {'noul': (0 if q == 'q0' else 0.8) if rerank else 0.25} for q in questions},
                'usage': {'input_tokens': 10, 'output_tokens': 1}}


@pytest.fixture
def setup(tmp_path, codes):
    store = CaseStore(tmp_path / 'cases.sqlite')
    ask = FakeAsk()
    factory = lambda: Judge(ask=ask, workers=1, attempts=1)
    client = TestClient(create_app(store=store, codes=codes, relevance_judge_factory=factory))
    return client, store, ask, factory


def description_fact(text):
    return {'id': 'desc-description', 'field': 'project.description', 'value': text, 'kind': 'pointed',
            'status': 'confirmed', 'source': {'type': 'user_text', 'ref': 'Your description', 'quote': text}}


def create_described(client, text='A proposed exterior insulation board.'):
    case_id = client.post('/cases').json()['id']
    assert client.post(f'/cases/{case_id}/facts', json=description_fact(text)).status_code == 200
    return case_id


def test_scores_all_division_b_articles_persists_and_get_never_scores(setup, codes):
    client, store, ask, factory = setup
    text = 'Foil-faced exterior insulation replaces housewrap.'
    case_id = create_described(client, text)
    assert client.get(f'/cases/{case_id}/relevance').json()['detail'] == 'not scored'
    assert not ask.calls
    response = client.post(f'/cases/{case_id}/relevance')
    assert response.status_code == 200 and response.headers['cache-control'] == 'no-store'
    record = response.json()
    assert record['status'] == 'scored' and record['model'] == 'jev-1.13.0' and record['stale'] is False
    assert datetime.fromisoformat(record['scored_at']).tzinfo is not None
    assert record['description_sha256'] == hashlib.sha256(text.encode()).hexdigest()
    assert set(record['scores']) == set(articles(codes.db_path))
    assert len(record['scores']) > 2000 and len(record['rerank']) == 60
    assert sum(count for _, count in ask.calls) == len(record['scores']) + 60
    assert record['display'] == display_probabilities(record['scores'], record['rerank'])
    assert all(record['display'][a] == p for a, p in record['rerank'].items())
    assert 0 in record['rerank'].values() and 0 in record['display'].values()
    assert any(record['display'][a] == p == 0.25 for a, p in record['scores'].items() if a not in record['rerank'])
    assert record['bands'] == {'x': 0.2, 'y': 0.6, 'status': 'placeholder_uncalibrated'}
    assert store.get(case_id).relevance.model_dump() == {k: v for k, v in record.items() if k != 'meta'}
    count = len(ask.calls)
    # A new app/store instance reads the persisted record, not an in-memory cache.
    reopened = TestClient(create_app(store=CaseStore(store.path), codes=codes, relevance_judge_factory=factory))
    assert reopened.get(f'/cases/{case_id}/relevance').json() == record
    assert len(ask.calls) == count


def test_description_changes_recompute_stale_without_changing_scores(setup):
    client, _, ask, _ = setup
    case_id = create_described(client)
    before = client.post(f'/cases/{case_id}/relevance').json()
    count = len(ask.calls)
    assert client.post(f'/cases/{case_id}/facts', json=description_fact('A different project.')).status_code == 200
    after = client.get(f'/cases/{case_id}/relevance').json()
    assert after == {**before, 'stale': True}
    assert len(ask.calls) == count


@pytest.mark.parametrize('text', [None, '', ' \n\t '])
def test_empty_description_is_409_without_judge_or_database(tmp_path, text):
    def forbidden():
        pytest.fail('an empty description must not construct a judge')
    client = TestClient(create_app(store=CaseStore(tmp_path / 'cases.sqlite'), codes=object(),
                                   relevance_judge_factory=forbidden))
    case_id = client.post('/cases').json()['id']
    if text is not None:
        client.post(f'/cases/{case_id}/facts', json=description_fact(text))
    response = client.post(f'/cases/{case_id}/relevance')
    assert response.status_code == 409 and response.json()['detail'] == 'Describe your project first'


def test_latest_empty_description_wins(setup):
    client, _, ask, _ = setup
    case_id = create_described(client)
    payload = {**description_fact(''), 'id': 'later-description'}
    client.post(f'/cases/{case_id}/facts', json=payload)
    assert client.post(f'/cases/{case_id}/relevance').status_code == 409
    assert not ask.calls


def test_no_key_is_safe_503_and_does_not_start_scoring(tmp_path, codes, monkeypatch, caplog):
    monkeypatch.setenv('BATATIS_LIVE', '1')
    resolved = []
    monkeypatch.setattr(keystore, 'resolve', lambda provider: resolved.append(provider))
    client = TestClient(create_app(store=CaseStore(tmp_path / 'cases.sqlite'), codes=codes))
    case_id = create_described(client)
    response = client.post(f'/cases/{case_id}/relevance')
    assert response.status_code == 503 and response.json()['detail'] == 'Relevance scoring unavailable'
    assert resolved == ['typesafe']
    assert 'TypeSafe credential is absent' in caplog.text and 'credential' not in response.text
    assert client.get(f'/cases/{case_id}/relevance').status_code == 404


def test_live_switch_refuses_before_resolving_key(tmp_path, codes, monkeypatch, caplog):
    monkeypatch.setattr(keystore, 'resolve', lambda *args: pytest.fail('offline must not read credentials'))
    client = TestClient(create_app(store=CaseStore(tmp_path / 'cases.sqlite'), codes=codes))
    case_id = create_described(client)
    response = client.post(f'/cases/{case_id}/relevance')
    assert response.status_code == 503 and response.json()['detail'] == 'Relevance scoring unavailable'
    assert 'BATATIS_LIVE is disabled' in caplog.text


def test_network_failure_keeps_previous_record_and_unlocks_case(setup, caplog):
    client, _, ask, _ = setup
    case_id = create_described(client)
    previous = client.post(f'/cases/{case_id}/relevance').json()
    ask.failure = True
    failed = client.post(f'/cases/{case_id}/relevance')
    assert failed.status_code == 503 and failed.json()['detail'] == 'Relevance scoring unavailable'
    assert 'TimeoutError' in caplog.text and 'do not log' not in caplog.text
    assert 'TimeoutError' not in failed.text
    assert client.get(f'/cases/{case_id}/relevance').json() == previous
    ask.failure = False
    assert client.post(f'/cases/{case_id}/relevance').status_code == 200


def test_per_ip_rate_limit_has_retry_after_and_never_calls_judge_again(setup, monkeypatch):
    client, _, ask, _ = setup
    monkeypatch.setenv('BATATIS_RELEVANCE_RATE_LIMIT', '1')
    monkeypatch.setenv('BATATIS_RELEVANCE_RATE_WINDOW_SECONDS', '60')
    case_id = create_described(client)
    path = f'/cases/{case_id}/relevance'
    assert client.post(path, headers={'x-vercel-forwarded-for': '203.0.113.1'}).status_code == 200
    count = len(ask.calls)
    limited = client.post(path, headers={'x-vercel-forwarded-for': '203.0.113.1'})
    assert limited.status_code == 429 and 1 <= int(limited.headers['retry-after']) <= 60
    assert len(ask.calls) == count
    assert client.post(path, headers={'x-vercel-forwarded-for': '203.0.113.2'}).status_code == 200


def test_daily_cap_is_shared_across_ips_and_failed_runs_count(setup, monkeypatch):
    client, _, ask, _ = setup
    monkeypatch.setenv('BATATIS_RELEVANCE_DAILY_RUNS', '1')
    case_id = create_described(client)
    ask.failure = True
    path = f'/cases/{case_id}/relevance'
    assert client.post(path, headers={'x-forwarded-for': '203.0.113.1'}).status_code == 503
    count = len(ask.calls)
    limited = client.post(path, headers={'x-forwarded-for': '203.0.113.2'})
    assert limited.status_code == 429 and 1 <= int(limited.headers['retry-after']) <= 86400
    assert len(ask.calls) == count


def test_daily_cap_resets_at_utc_midnight(monkeypatch):
    class Clock(datetime):
        stamp = datetime(2026, 10, 20, 23, 59, 59, tzinfo=timezone.utc)

        @classmethod
        def now(cls, tz=None):
            return cls.stamp

    monkeypatch.setattr(llm_gate, 'datetime', Clock)
    monkeypatch.setenv('BATATIS_RELEVANCE_DAILY_RUNS', '1')
    assert llm_gate.relevance_retry_after('one') is None
    assert llm_gate.relevance_retry_after('two') == 1
    Clock.stamp = datetime(2026, 10, 21, tzinfo=timezone.utc)
    assert llm_gate.relevance_retry_after('two') is None


def test_daily_cap_defaults_to_twenty_runs(monkeypatch):
    monkeypatch.delenv('BATATIS_RELEVANCE_DAILY_RUNS')
    assert all(llm_gate.relevance_retry_after(str(ip)) is None for ip in range(20))
    assert llm_gate.relevance_retry_after('next') is not None


def test_same_case_lock_rejects_duplicate_while_other_cases_can_score(setup):
    client, _, ask, _ = setup
    text = 'Blocked first proposal.'
    case_id = create_described(client, text)
    other = create_described(client, 'Independent second proposal.')
    ask.block_proposal = text
    path = f'/cases/{case_id}/relevance'
    with ThreadPoolExecutor(max_workers=1) as pool:
        pending = pool.submit(client.post, path)
        try:
            assert ask.started.wait(5)
            duplicate = client.post(path)
            assert duplicate.status_code == 409 and duplicate.json()['detail'] == 'Relevance scoring already in progress'
            assert client.post(f'/cases/{other}/relevance').status_code == 200
        finally:
            ask.release.set()
        assert pending.result(timeout=10).status_code == 200
    assert sum(count for proposal, count in ask.calls if proposal == text) == len(pending.result().json()['scores']) + 60
    assert client.post(path).status_code == 200


@pytest.mark.parametrize('action', ['edit', 'delete', 'expire'])
def test_finishing_scoring_preserves_concurrent_edits_or_deletion(setup, action):
    client, store, ask, _ = setup
    text = 'Proposal before the concurrent edit.'
    case_id = create_described(client, text)
    ask.block_proposal = text
    with ThreadPoolExecutor(max_workers=1) as pool:
        pending = pool.submit(client.post, f'/cases/{case_id}/relevance')
        try:
            assert ask.started.wait(5)
            if action == 'edit':
                client.post(f'/cases/{case_id}/facts', json=description_fact('Changed during scoring.'))
            elif action == 'delete':
                assert client.delete(f'/cases/{case_id}').status_code == 204
            else:
                case = store.get(case_id)
                case.created_at = '2000-01-01T00:00:00+00:00'
                store.put(case, expected_version=case.version)
        finally:
            ask.release.set()
        response = pending.result(timeout=10)
    if action == 'edit':
        assert response.status_code == 200 and response.json()['stale'] is True
        assert store.get(case_id).facts[-1].value == 'Changed during scoring.'
        assert client.get(f'/cases/{case_id}/relevance').json()['stale'] is True
    else:
        assert response.status_code == 404 and store.get(case_id) is None


@pytest.mark.parametrize('method', ['get', 'post'])
def test_missing_case_is_404_without_scoring(setup, method):
    client, _, ask, _ = setup
    response = getattr(client, method)('/cases/case_missing/relevance')
    assert response.status_code == 404 and response.json()['detail'] == 'case not found'
    assert not ask.calls


@pytest.mark.parametrize('backend', ['sqlite', 'postgres'])
def test_versioned_persistence_retries_without_losing_a_concurrent_fact(setup, monkeypatch, backend):
    client, local_store, _, _ = setup
    case_id = create_described(client)
    assert client.post(f'/cases/{case_id}/relevance').status_code == 200
    record = local_store.get(case_id).relevance
    if backend == 'postgres':
        url = os.environ.get('TEST_DATABASE_URL')
        if not url:
            pytest.skip('TEST_DATABASE_URL is not set')
        from engine.store_postgres import PostgresCaseStore
        store = PostgresCaseStore(url)
    else:
        store = local_store
    case = store.put(Case(facts=[Fact.model_validate(description_fact('Original.'))]))
    original_put = store.put
    raced = []

    def put_with_one_conflict(value, *, expected_version=None):
        if not raced:
            raced.append(True)
            store.add_fact(case.id, Fact(field='building.storeys', value=2, kind='pointed',
                                        source=Source(type='user_text', ref='Your answer')))
        return original_put(value, expected_version=expected_version)

    monkeypatch.setattr(store, 'put', put_with_one_conflict)
    try:
        saved = _save_record(store, case.id, record)
        assert saved.stale is True
        reopened = store.get(case.id)
        assert reopened.relevance == saved
        assert {fact.field for fact in reopened.facts} == {'project.description', 'building.storeys'}
        assert reopened.version == 3
    finally:
        store.delete(case.id)
