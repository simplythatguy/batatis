"""Evidence withdrawal uses the same atomic/versioned contract on both case backends."""
from __future__ import annotations

import os
import sqlite3
import threading
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone

import psycopg
import pytest
from fastapi.testclient import TestClient

from engine.api import create_app
from engine.models import Case, EvidenceItem, Fact, Source
from engine.privacy import PII_NOTICE
from engine.retention import reset_purge_clock
from engine.routes_case import create_router
from engine.store import RETENTION_DAYS, CaseBackend, CaseStore, VersionConflict


def _fact(field, value):
    return Fact(field=field, value=value, kind='pointed', status='confirmed',
                source=Source(type='user_text', ref='synthetic applicant', quote=str(value)))


@pytest.fixture(params=['sqlite', 'postgres'])
def evidence_store(request, tmp_path):
    if request.param == 'sqlite':
        store = CaseStore(tmp_path / 'cases.sqlite')
    else:
        url = os.environ.get('TEST_DATABASE_URL')
        if not url:
            pytest.skip('TEST_DATABASE_URL is not set')
        from engine.store_postgres import PostgresCaseStore
        store = PostgresCaseStore(url)
    created = []

    def create(**kwargs):
        case = Case(**kwargs)
        created.append(case.id)
        return store.put(case, expected_version=0)

    reset_purge_clock()
    try:
        yield store, create
    finally:
        for case_id in created:
            store.delete(case_id)
        reset_purge_clock()


def test_protocol_exposes_evidence_removal():
    assert callable(getattr(CaseBackend, 'remove_evidence', None))


def test_removal_is_slot_exact_and_preserves_other_cases_and_files(evidence_store):
    store, create = evidence_store
    removed = [_fact(f'evidence.wall.{field}', f'withdrawn-{field}') for field in (
        'title', 'description', 'file_ref', 'responsible_party', 'issuer', 'date',
        'professional_seal', 'evidence_type', 'covers.synthetic-plan',
    )]
    # All revisions of a withdrawn field must go, including unconfirmed ones.
    removed.append(_fact('evidence.wall.title', 'withdrawn-revision'))
    removed[-1].status = 'unconfirmed'
    kept = [_fact(field, 'kept') for field in (
        'evidence.wall~2.title', 'evidence.wall~20.title', 'evidence.wallpaper.title',
        'evidence.Wall.title', 'evidence.wall', 'project.description',
    )]
    items = [EvidenceItem(id=slot, description='kept')
             for slot in ('wall~2', 'wall~20', 'wallpaper', 'Wall')]
    case = create(title='Synthetic removal', facts=removed + kept,
                  evidence=[EvidenceItem(id='wall', description='withdrawn-item')] + items)
    other = create(facts=removed, evidence=[EvidenceItem(id='wall', description='withdrawn-other-case')])
    other_before = store.get(other.id).model_dump()
    file = store.put_file(case.id, 'retained.pdf', b'%PDF-1.4 synthetic retained attachment')
    result = store.remove_evidence(case.id, 'wall')
    assert result.facts == kept
    assert result.evidence == items
    assert result.title == case.title and result.created_at == case.created_at
    assert store.get(case.id) == result
    assert 'withdrawn-' not in result.model_dump_json()
    assert store.get(other.id).model_dump() == other_before
    assert store.get_file(case.id, file['id'])['data'] == b'%PDF-1.4 synthetic retained attachment'


@pytest.mark.parametrize('representation', ['facts_only', 'item_only'])
def test_removal_does_not_require_both_an_item_and_facts(evidence_store, representation):
    store, create = evidence_store
    case = create(facts=[_fact('evidence.wall.title', 'withdrawn')] if representation == 'facts_only' else [],
                  evidence=[EvidenceItem(id='wall', description='withdrawn')] if representation == 'item_only' else [])
    result = store.remove_evidence(case.id, 'wall')
    assert result.facts == [] and result.evidence == []


def test_removal_advances_version_and_rejects_stale_put_without_changing_its_contract(evidence_store):
    store, create = evidence_store
    stale = create(facts=[_fact('evidence.wall.title', 'withdrawn')])
    version = store.get_version(stale.id)
    result = store.remove_evidence(stale.id, 'wall')
    assert store.get_version(stale.id) == version + 1
    with pytest.raises(VersionConflict) as error:
        store.put(stale, expected_version=version)
    assert error.value.expected == version and error.value.actual == version + 1
    assert store.get(stale.id) == result
    # Retrying an already absent slot still returns the existing case, as #16 does.
    assert store.remove_evidence(stale.id, 'wall').facts == []
    assert store.get_version(stale.id) == version + 2
    result.title = 'Current optimistic write'
    store.put(result, expected_version=version + 2)
    assert store.get_version(stale.id) == version + 3


def test_failed_removal_rolls_back_case_and_version_together(evidence_store, monkeypatch):
    store, create = evidence_store
    case = create(facts=[_fact('evidence.wall.title', 'withdrawn')],
                  evidence=[EvidenceItem(id='wall', description='withdrawn')])
    serializer = 'model_dump_json' if isinstance(store, CaseStore) else 'model_dump'

    def fail(*_args, **_kwargs):
        raise RuntimeError('synthetic serialization failure')

    with monkeypatch.context() as patch:
        patch.setattr(Case, serializer, fail)
        with pytest.raises(RuntimeError, match='synthetic serialization failure'):
            store.remove_evidence(case.id, 'wall')
    assert store.get(case.id) == case
    assert store.get_version(case.id) == 1


def _private_response(response, status):
    assert response.status_code == status, response.text
    assert response.json()['meta']['notice'] == PII_NOTICE
    assert response.headers['x-batatis-notice'] == PII_NOTICE
    assert response.headers['x-robots-tag'] == 'noindex, nofollow'


def test_actual_delete_route_works_without_codedb_and_is_mounted_once(evidence_store, monkeypatch):
    store, create = evidence_store
    monkeypatch.setattr('engine.api.Codes', lambda: pytest.fail('Deletion must not open CodeDB'))
    case = create(facts=[_fact('evidence.wall.title', 'withdrawn'), _fact('evidence.wall~2.title', 'kept')],
                  evidence=[EvidenceItem(id='wall', description='withdrawn'),
                            EvidenceItem(id='wall~2', description='kept')])
    app = create_app(store=store)
    # Inspect the router before inclusion: FastAPI may include it lazily in app.routes.
    router = create_router(lambda: store, lambda: pytest.fail('Deletion must not open CodeDB'))
    routes = [route for route in router.routes
              if getattr(route, 'path', '') == '/cases/{case_id}/evidence/{evidence_id}'
              and 'DELETE' in getattr(route, 'methods', set())]
    assert len(routes) == 1
    client = TestClient(app)
    response = client.delete(f'/cases/{case.id}/evidence/wall')
    _private_response(response, 200)
    result = Case.model_validate(response.json())
    assert [fact.field for fact in result.facts] == ['evidence.wall~2.title']
    assert [item.id for item in result.evidence] == ['wall~2']
    assert store.get(case.id) == result
    # The hosted /api prefix uses that same handler and absent slots return the case.
    response = client.delete(f'/api/cases/{case.id}/evidence/absent')
    _private_response(response, 200)
    assert Case.model_validate(response.json()).facts == result.facts
    response = client.delete('/cases/case_synthetic_missing/evidence/wall')
    _private_response(response, 404)
    assert response.json()['detail'] == 'case not found'


@pytest.mark.parametrize('failure,status,detail', [
    (VersionConflict('synthetic'), 409, 'case was updated concurrently'),
    (psycopg.OperationalError('private-host private-credential'), 503, 'case store unavailable'),
])
def test_delete_route_preserves_safe_error_and_privacy_contract(evidence_store, monkeypatch, failure, status, detail):
    store, _ = evidence_store

    def fail(*_args):
        raise failure

    monkeypatch.setattr(store, 'remove_evidence', fail)
    response = TestClient(create_app(store=store)).delete('/cases/synthetic/evidence/wall')
    _private_response(response, status)
    assert response.json()['detail'] == detail
    assert 'private-' not in response.text


def test_expired_case_is_purged_on_removal_between_sweeps(evidence_store):
    from engine.tests.test_retention import _age
    store, create = evidence_store
    case = create(facts=[_fact('evidence.wall.title', 'withdrawn')],
                  evidence=[EvidenceItem(id='wall', description='withdrawn')])
    file_id = store.put_file(case.id, 'expired.pdf', b'%PDF-1.4 synthetic')['id']
    client = TestClient(create_app(store=store))
    assert client.get(f'/cases/{case.id}').status_code == 200  # Consume the sweep window.
    _age(store, case.id, 8)
    response = client.delete(f'/cases/{case.id}/evidence/wall')
    _private_response(response, 404)
    assert response.json()['detail'] == 'case not found'
    assert store.purge_expired() == 0  # Removal itself physically purged it.
    assert store.get_version(case.id) is None
    assert store.get_file(case.id, file_id) is None
    assert store.remove_evidence(case.id, 'wall') is None


def test_removal_uses_the_elapsed_seven_day_boundary_without_extending_it(evidence_store, monkeypatch):
    store, create = evidence_store
    current = datetime.now(timezone.utc).replace(microsecond=0)

    class FrozenDatetime(datetime):
        @classmethod
        def now(cls, tz=None):
            return current.astimezone(tz) if tz else current.replace(tzinfo=None)

    monkeypatch.setattr('engine.store.datetime', FrozenDatetime)
    cutoff = current - timedelta(days=RETENTION_DAYS)
    for index, stamp in enumerate([
        cutoff - timedelta(seconds=1),
        (cutoff - timedelta(seconds=1)).astimezone(timezone(timedelta(hours=3))),
        cutoff, cutoff + timedelta(seconds=1),
    ]):
        case = create(created_at=stamp.isoformat(timespec='seconds'),
                      facts=[_fact('evidence.wall.title', 'withdrawn')])
        result = store.remove_evidence(case.id, 'wall')
        if index < 2:
            assert result is None and store.get_version(case.id) is None
        else:
            assert result.facts == [] and result.created_at == case.created_at
            assert store.get_version(case.id) == 2


@pytest.mark.parametrize('writer', ['fact', 'delete'])
def test_removal_serializes_with_unrelated_fact_save_or_case_deletion(evidence_store, monkeypatch, writer):
    store, create = evidence_store
    case = create(facts=[_fact('evidence.wall.title', 'withdrawn'), _fact('project.description', 'kept')],
                  evidence=[EvidenceItem(id='wall', description='withdrawn')])
    paused, resume, started, done = (threading.Event() for _ in range(4))
    errors, results = [], {}
    # Pause at serialization, after reading the case and before its UPDATE. A get/put
    # implementation would leave this window unlocked and lose the save or resurrect the case.
    serializer = 'model_dump_json' if isinstance(store, CaseStore) else 'model_dump'
    original = getattr(Case, serializer)

    def serialize(current, *args, **kwargs):
        payload = original(current, *args, **kwargs)
        if threading.current_thread() is removal:
            paused.set()
            assert resume.wait(15), 'Timed out releasing removal'
        return payload

    monkeypatch.setattr(Case, serializer, serialize)

    def remove():
        try:
            results['removal'] = store.remove_evidence(case.id, 'wall')
        except BaseException as exc:
            errors.append(exc)

    def write():
        started.set()
        try:
            results['write'] = (store.add_fact(case.id, _fact('project.permit_number', 'SYNTHETIC-42'))
                                if writer == 'fact' else store.delete(case.id))
        except BaseException as exc:
            errors.append(exc)
        finally:
            done.set()

    removal = threading.Thread(target=remove)
    concurrent = threading.Thread(target=write)
    removal.start()
    try:
        assert paused.wait(15), 'Removal did not reach its write seam'
        concurrent.start()
        assert started.wait(5)
        assert not done.wait(0.25), 'Concurrent writer bypassed the removal lock'
    finally:
        resume.set()
        removal.join(20)
        if concurrent.ident is not None:
            concurrent.join(20)
    assert not removal.is_alive() and not concurrent.is_alive()
    assert not errors
    assert results['removal'] is not None
    if writer == 'fact':
        assert {fact.field for fact in store.get(case.id).facts} == {'project.description', 'project.permit_number'}
        assert store.get(case.id).evidence == []
        assert store.get_version(case.id) == 3
    else:
        assert results['write'] is True
        assert store.get(case.id) is None and store.get_version(case.id) is None


@contextmanager
def _terminal_write(store, case_id, terminal):
    """Hold an actual deletion/expiry transaction open while removal is queued."""
    stamp = (datetime.now(timezone.utc) - timedelta(days=8)).isoformat(timespec='seconds')
    if isinstance(store, CaseStore):
        con = sqlite3.connect(store.path, timeout=5, isolation_level=None)
        try:
            con.execute('BEGIN IMMEDIATE')
            if terminal == 'delete':
                con.execute('DELETE FROM case_files WHERE case_id=?', (case_id,))
                con.execute('DELETE FROM cases WHERE id=?', (case_id,))
            else:
                con.execute("UPDATE cases SET json=json_set(json, '$.created_at', ?) WHERE id=?", (stamp, case_id))
            yield
            con.execute('COMMIT')
        finally:
            con.close()
    else:
        with store._conn() as con:
            con.execute('SELECT id FROM cases WHERE id=%s FOR UPDATE', (case_id,))
            if terminal == 'delete':
                con.execute('DELETE FROM case_files WHERE case_id=%s', (case_id,))
                con.execute('DELETE FROM cases WHERE id=%s', (case_id,))
            else:
                con.execute("UPDATE cases SET data=jsonb_set(data, '{created_at}', to_jsonb(%s::text)) WHERE id=%s",
                            (stamp, case_id))
            yield


@pytest.mark.parametrize('terminal', ['delete', 'expire'])
def test_queued_removal_cannot_restore_a_case_after_terminal_write(evidence_store, monkeypatch, terminal):
    store, create = evidence_store
    case = create(facts=[_fact('evidence.wall.title', 'withdrawn')])
    file_id = store.put_file(case.id, 'terminal.pdf', b'%PDF-1.4 synthetic')['id']
    attempted, done = threading.Event(), threading.Event()
    results, errors = [], []

    def remove():
        try:
            results.append(store.remove_evidence(case.id, 'wall'))
        except BaseException as exc:
            errors.append(exc)
        finally:
            done.set()

    thread = threading.Thread(target=remove)
    # Observe the actual lock attempt, rather than assuming a thread has connected.
    # In Postgres this pins expiry between the first purge and a waiting row read.
    class ObservedConnection:
        def __init__(self, con):
            self.con = con

        def execute(self, statement, *args):
            lock = 'BEGIN IMMEDIATE' if isinstance(store, CaseStore) else 'SELECT data, version'
            if threading.current_thread() is thread and statement.startswith(lock):
                attempted.set()
            return self.con.execute(statement, *args)

        def __getattr__(self, name):
            return getattr(self.con, name)

    if isinstance(store, CaseStore):
        connect = store._connect
        monkeypatch.setattr(store, '_connect', lambda: ObservedConnection(connect()))
    else:
        connect = store._conn

        @contextmanager
        def observed_connection():
            with connect() as con:
                yield ObservedConnection(con)

        monkeypatch.setattr(store, '_conn', observed_connection)
    try:
        with _terminal_write(store, case.id, terminal):
            thread.start()
            assert attempted.wait(15), 'Removal did not reach the database lock'
            assert not done.wait(0.25), 'Removal did not wait for the terminal transaction'
    finally:
        if thread.ident is not None:
            thread.join(20)
        monkeypatch.undo()
    assert not thread.is_alive()
    assert not errors and results == [None]
    assert store.get(case.id) is None and store.get_version(case.id) is None
    assert store.get_file(case.id, file_id) is None
    assert store.purge_expired() == 0
    with pytest.raises(VersionConflict):
        store.put(case, expected_version=1)
    assert store.get(case.id) is None
