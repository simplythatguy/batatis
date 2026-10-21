"""Acknowledged mutations and elapsed retention survive in-flight backend work."""
import os
import sqlite3
import threading
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from engine.api import create_app
from engine.codes import Codes
from engine.models import Case, EvidenceItem, Fact, Source
from engine.privacy import PII_NOTICE
from engine.retention import reset_purge_clock
from engine.section_d import SectionDPlan
from engine.store import CaseStore, VersionConflict
from engine.store_postgres import PostgresCaseStore


def fact(field):
    return Fact(field=field, value='synthetic', kind='pointed', status='confirmed',
                source=Source(type='user_text', ref='synthetic', quote='synthetic'))


@pytest.fixture(params=['sqlite', 'postgres'])
def store(request, tmp_path):
    reset_purge_clock()
    if request.param == 'sqlite':
        result = CaseStore(tmp_path / 'cases.sqlite')
    else:
        if not os.getenv('TEST_DATABASE_URL'):
            pytest.skip('TEST_DATABASE_URL is not set; real Postgres required')
        result = PostgresCaseStore(os.environ['TEST_DATABASE_URL'])
    yield result
    reset_purge_clock()


def raw_rows(store, case_id):
    """A getter could conceal a resurrected expired row by purging it again."""
    if isinstance(store, CaseStore):
        with sqlite3.connect(store.path) as con:
            row = con.execute('SELECT json, version FROM cases WHERE id=?', (case_id,)).fetchone()
            files = con.execute('SELECT count(*) FROM case_files WHERE case_id=?', (case_id,)).fetchone()[0]
        return (Case.model_validate_json(row[0]), row[1], files) if row else (None, None, files)
    with store._conn() as con:
        row = con.execute('SELECT data, version FROM cases WHERE id=%s', (case_id,)).fetchone()
        files = con.execute('SELECT count(*) FROM case_files WHERE case_id=%s', (case_id,)).fetchone()[0]
    return (Case.model_validate(row[0]), row[1], files) if row else (None, None, files)


@pytest.mark.parametrize('real_builders', [False, True], ids=['isolated-save', 'real-codedb-planner'])
@pytest.mark.parametrize('mutation', ['whole_delete', 'slot_delete', 'new_fact', 'purge', 'elapsed_expiry'])
def test_section_d_cannot_replace_completed_mutation(store, monkeypatch, real_builders, mutation):
    codes = Codes() if real_builders else object()
    case = store.put(Case(provisions=['9.10.13.13.(1)'], facts=[fact('evidence.wall.title')],
                          evidence=[EvidenceItem(id='wall', description='synthetic')]))
    store.put_file(case.id, 'owned.pdf', b'%PDF-1.4 synthetic')
    entered, resume = threading.Event(), threading.Event()
    # Before the repair the route reads get(); afterward it reads an atomic snapshot.
    read_name = 'get_snapshot' if hasattr(store, 'get_snapshot') else 'get'
    original = getattr(store, read_name)
    first = True

    def paused_read(cid):
        nonlocal first
        result = original(cid)
        if first:
            first = False
            entered.set()
            assert resume.wait(15)
        return result

    monkeypatch.setattr(store, read_name, paused_read)
    plans = []
    if real_builders:
        from engine.section_d import section_d_plan

        def checked_real_plan(current, db):
            plan = section_d_plan(current, db)
            assert current.section_c and all(row.citation and row.pairs for row in current.section_c)
            assert plan.items and all(item.citation and item.function and item.objective for item in plan.items)
            plans.append(plan)
            return plan

        monkeypatch.setattr('engine.routes_case.section_d_plan', checked_real_plan)
    else:
        monkeypatch.setattr('engine.routes_case.section_c_rows', lambda *args: [])
        monkeypatch.setattr('engine.routes_case.section_d_plan', lambda *args: SectionDPlan(items=[], notices=[]))
    app = create_app(store=store, codes=codes)
    client = TestClient(app)
    responses, errors = [], []

    def plan_request():
        try:
            responses.append(TestClient(app).post(f'/api/cases/{case.id}/section-d'))
        except BaseException as error:
            errors.append(error)

    thread = threading.Thread(target=plan_request)
    thread.start()
    try:
        assert entered.wait(15)
        base = f'/api/cases/{case.id}'
        if mutation == 'whole_delete':
            assert client.delete(base).status_code == 204
        elif mutation == 'slot_delete':
            assert client.request('DELETE', base + '/evidence/wall',
                                  json={'expected_version': store.get_version(case.id)}).status_code == 200
        elif mutation == 'new_fact':
            assert client.post(base + '/facts', json=fact('project.new_answer').model_dump()).status_code == 200
        else:
            cutoff = (datetime.now(timezone.utc) + timedelta(days=1)).isoformat()
            monkeypatch.setattr('engine.store.retention_cutoff', lambda: cutoff)
            monkeypatch.setattr('engine.store_postgres.retention_cutoff', lambda: cutoff)
            if mutation == 'purge':
                assert store.purge_expired() >= 1
    finally:
        resume.set()
        thread.join(20)
    assert not thread.is_alive() and not errors
    if real_builders:
        assert len(plans) == 1  # Real source-backed generation ran before the guarded save.
    terminal = mutation in ('whole_delete', 'purge', 'elapsed_expiry')
    response = responses[0]
    assert response.status_code == (404 if terminal else 409), response.text
    assert response.json()['detail'] == ('case not found' if terminal else 'case was updated concurrently')
    assert response.json()['meta']['notice'] == PII_NOTICE
    assert response.headers.get_list('x-batatis-notice') == [PII_NOTICE]
    assert response.headers['x-robots-tag'] == 'noindex, nofollow'
    saved, version, files = raw_rows(store, case.id)
    if terminal:
        assert saved is None and files == 0
    else:
        assert version == 2 and files == 1
        if mutation == 'slot_delete':
            assert saved.facts == [] and saved.evidence == []
        else:
            assert any(item.field == 'project.new_answer' for item in saved.facts)


def test_snapshot_version_cannot_acknowledge_a_newer_case(store):
    case = store.put(Case(facts=[fact('project.original')]), expected_version=0)
    snapshot, version = store.get_snapshot(case.id)
    assert version == 1 and snapshot.id == case.id
    store.add_fact(case.id, fact('project.new_answer'))
    with pytest.raises(VersionConflict):
        store.put(snapshot, expected_version=version)
    assert {item.field for item in store.get(case.id).facts} == {'project.original', 'project.new_answer'}
    store.delete(case.id)
    with pytest.raises(VersionConflict):
        store.put(snapshot, expected_version=version)
    assert raw_rows(store, case.id) == (None, None, 0)


@pytest.mark.parametrize('operation', ['remove_evidence', 'add_fact', 'put_file', 'versioned_put'])
def test_current_expiry_is_checked_after_a_real_write_lock(store, monkeypatch, operation):
    cutoff = [datetime(2026, 10, 13, 18, tzinfo=timezone.utc)]
    monkeypatch.setattr('engine.store.retention_cutoff', lambda: cutoff[0].isoformat())
    monkeypatch.setattr('engine.store_postgres.retention_cutoff', lambda: cutoff[0].isoformat())
    case = store.put(Case(created_at=(cutoff[0] + timedelta(seconds=1)).isoformat(),
                          facts=[fact('evidence.wall.title')]))
    store.put_file(case.id, 'old.pdf', b'%PDF-1.4 old')
    attempted, done = threading.Event(), threading.Event()
    results, errors = [], []

    def write():
        try:
            if operation == 'remove_evidence':
                result = store.remove_evidence(case.id, 'wall')
            elif operation == 'add_fact':
                result = store.add_fact(case.id, fact('project.late'))
            elif operation == 'put_file':
                result = store.put_file(case.id, 'new.pdf', b'%PDF-1.4 late')
            else:
                try:
                    result = store.put(case, expected_version=1)
                except VersionConflict:
                    result = None
            results.append(result)
        except BaseException as error:
            errors.append(error)
        finally:
            done.set()

    thread = threading.Thread(target=write)

    class Observed:
        def __init__(self, con):
            self.con = con

        def execute(self, query, *args):
            if threading.current_thread() is thread:
                text = str(query)
                if ('BEGIN IMMEDIATE' in text or text.startswith('DELETE FROM case_files') or
                        text.startswith('UPDATE cases') or text.startswith('SELECT data, version') or
                        ('SELECT id FROM cases' in text and 'FOR ' in text)):
                    attempted.set()
            return self.con.execute(query, *args)

        def __enter__(self):
            self.con.__enter__()
            return self

        def __exit__(self, *args):
            return self.con.__exit__(*args)

        def __getattr__(self, key):
            return getattr(self.con, key)

    if isinstance(store, CaseStore):
        connect = sqlite3.connect
        monkeypatch.setattr(sqlite3, 'connect', lambda *args, **kwargs: Observed(connect(*args, **kwargs)))
        holder = connect(store.path, isolation_level=None)
        holder.execute('BEGIN IMMEDIATE')
    else:
        connect = store._conn

        @contextmanager
        def observed_connection():
            with connect() as con:
                yield Observed(con)

        monkeypatch.setattr(store, '_conn', observed_connection)
        context = connect()
        holder = context.__enter__()
        holder.execute('SELECT id FROM cases WHERE id=%s FOR UPDATE', (case.id,))
    try:
        thread.start()
        assert attempted.wait(10) and not done.wait(.2)
        cutoff[0] += timedelta(seconds=2)
    finally:
        if isinstance(store, CaseStore):
            holder.commit()
            holder.close()
        else:
            context.__exit__(None, None, None)
        thread.join(20)
    assert not thread.is_alive() and not errors
    assert results == [None]
    assert raw_rows(store, case.id) == (None, None, 0)
