"""7-day purge: an 8-day case goes, a 6-day case stays, files go with the case, a second purge is a no-op."""
from __future__ import annotations

import logging
import os
import sqlite3
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from engine.api import create_app
from engine.models import Case, EvidenceItem, Fact, Source
from engine.retention import maybe_purge, purge_now, reset_purge_clock
from engine.store import RETENTION_DAYS, CaseStore, open_store


@pytest.fixture(params=['sqlite', 'postgres'])
def retention_store(request, tmp_path):
    if request.param == 'sqlite':
        store = CaseStore(tmp_path / 'cases.sqlite')
    else:
        url = os.environ.get('TEST_DATABASE_URL')
        if not url:
            pytest.skip('TEST_DATABASE_URL is not set')
        from engine.store_postgres import PostgresCaseStore
        store = PostgresCaseStore(url)
    created = []
    reset_purge_clock()
    try:
        yield store, created
    finally:
        for case_id in created:
            store.delete(case_id)
        reset_purge_clock()


def test_expired_case_and_file_cannot_be_accessed_between_sweeps(retention_store):
    store, created = retention_store
    case = store.put(Case(title='expires between sweeps'))
    created.append(case.id)
    file_id = store.put_file(case.id, 'old.pdf', b'%PDF-1.4 expired')['id']
    client = TestClient(create_app(store=store))
    assert client.get(f'/cases/{case.id}').status_code == 200
    _age(store, case.id, RETENTION_DAYS + 1)
    # The previous request just consumed the sweep window. Access must still expire it.
    response = client.get(f'/cases/{case.id}')
    assert response.status_code == 404
    assert response.json()['detail'] == 'case not found'
    assert store.get_file(case.id, file_id) is None
    assert store.get_version(case.id) is None
    assert store.purge_expired() == 0  # Access already physically removed the case and file.


@pytest.mark.parametrize('access', ['get_file', 'get_version', 'add_fact', 'put_file'])
def test_direct_store_access_cannot_read_or_extend_an_expired_case(retention_store, access):
    store, created = retention_store
    case = store.put(Case(title='expired'))
    created.append(case.id)
    file_id = store.put_file(case.id, 'old.pdf', b'%PDF-1.4 expired')['id']
    _age(store, case.id, RETENTION_DAYS + 1)
    if access == 'get_file':
        result = store.get_file(case.id, file_id)
    elif access == 'get_version':
        result = store.get_version(case.id)
    elif access == 'add_fact':
        result = store.add_fact(case.id, Fact(field='storeys', value=2, kind='pointed',
                                            source=Source(type='user_text', ref='message')))
    else:
        result = store.put_file(case.id, 'new.pdf', b'%PDF-1.4 new')
    assert result is None
    assert store.purge_expired() == 0


def test_delete_is_empty_204_then_404_and_removes_files(retention_store):
    store, created = retention_store
    client = TestClient(create_app(store=store))
    case_id = client.post('/cases', json={'title': 'delete'}).json()['id']
    created.append(case_id)
    uploaded = client.post(f'/cases/{case_id}/files', content=b'%PDF-1.4 delete',
                           headers={'content-type': 'application/pdf'})
    assert uploaded.status_code == 201
    file_id = uploaded.json()['id']
    response = client.delete(f'/cases/{case_id}')
    assert response.status_code == 204
    assert response.content == b''
    assert store.get_file(case_id, file_id) is None
    assert store.get(case_id) is None
    assert client.delete(f'/cases/{case_id}').status_code == 404


@pytest.mark.parametrize('trigger', ['cold_create', 'explicit_purge'])
def test_purge_failure_in_a_route_is_a_safe_503(tmp_path, monkeypatch, caplog, trigger):
    class FailingStore(CaseStore):
        fail = False

        def purge_expired(self):
            if self.fail:
                raise RuntimeError('connection failed: private-host, private-credential')
            return super().purge_expired()

    reset_purge_clock()
    store = FailingStore(tmp_path / 'cases.sqlite')
    monkeypatch.setattr('engine.api.open_store', lambda: store)
    client = TestClient(create_app(), raise_server_exceptions=False)
    if trigger == 'explicit_purge':
        assert client.post('/cases').status_code == 201
    store.fail = True
    with caplog.at_level(logging.WARNING):
        response = client.post('/cases') if trigger == 'cold_create' else client.get('/retention/purge')
    assert response.status_code == 503
    assert response.json()['detail'] == 'case purge failed'
    assert 'private-' not in response.text + caplog.text
    reset_purge_clock()


@pytest.mark.parametrize('url', ['/retention/purge', '/api/retention/purge'])
@pytest.mark.parametrize('configured,authorization,status', [
    (False, None, 503),
    (True, None, 401),
    (True, 'Bearer wrong', 401),
    (True, 'Bearer retention-test-token', 200),
])
def test_hosted_cron_requires_auth_before_any_bulk_purge(
        tmp_path, monkeypatch, caplog, url, configured, authorization, status):
    class CountingStore(CaseStore):
        purges = 0

        def purge_expired(self):
            self.purges += 1
            return super().purge_expired()

    reset_purge_clock()
    monkeypatch.setenv('VERCEL', '1')
    if configured:
        monkeypatch.setenv('CRON_SECRET', 'retention-test-token')
    else:
        monkeypatch.delenv('CRON_SECRET', raising=False)
    store = CountingStore(tmp_path / 'cases.sqlite')
    client = TestClient(create_app(store=store))
    headers = {'authorization': authorization} if authorization else {}
    with caplog.at_level(logging.INFO):
        response = client.get(url, headers=headers)
    assert response.status_code == status
    assert store.purges == (1 if status == 200 else 0)
    assert response.headers['cache-control'] == 'no-store'
    assert 'retention-test-token' not in response.text + caplog.text
    reset_purge_clock()


def test_retention_boundary_uses_elapsed_days_including_timezone_offsets(retention_store, monkeypatch):
    store, created = retention_store
    current = datetime.now(timezone.utc).replace(microsecond=0)

    class FrozenDatetime(datetime):
        @classmethod
        def now(cls, tz=None):
            return current.astimezone(tz) if tz else current.replace(tzinfo=None)

    monkeypatch.setattr('engine.store.datetime', FrozenDatetime)
    cutoff = current - timedelta(days=RETENTION_DAYS)
    cases = []
    for stamp in [cutoff - timedelta(seconds=1),
                  (cutoff - timedelta(seconds=1)).astimezone(timezone(timedelta(hours=3))),
                  cutoff, cutoff + timedelta(seconds=1)]:
        case = store.put(Case())
        created.append(case.id)
        file_id = store.put_file(case.id, 'boundary.pdf', b'%PDF-1.4 boundary')['id']
        _set_created_at(store, case.id, stamp.isoformat(timespec='seconds'))
        cases.append((case.id, file_id))
    assert store.purge_expired() == 2
    for index, (case_id, file_id) in enumerate(cases):
        assert (store.get(case_id) is None) == (index < 2)
        assert (store.get_file(case_id, file_id) is None) == (index < 2)
    assert store.purge_expired() == 0


def _stamp(days: int) -> str:
    return (datetime.now(timezone.utc) - timedelta(days=days)).isoformat(timespec='seconds')


def _age(store, case_id: str, days: int) -> None:
    _set_created_at(store, case_id, _stamp(days))


def _set_created_at(store, case_id: str, stamp: str) -> None:
    if isinstance(store, CaseStore):
        with sqlite3.connect(store.path) as con:
            con.execute("UPDATE cases SET json = json_set(json, '$.created_at', ?) WHERE id=?", (stamp, case_id))
        return
    with store._conn() as con:
        con.execute("UPDATE cases SET data = jsonb_set(data, '{created_at}', to_jsonb(%s::text)) WHERE id=%s",
                    (stamp, case_id))


def assert_retention(store, created: list | None = None) -> None:
    old = store.put(Case(title='old', evidence=[EvidenceItem(description='old evidence')]))
    kept = store.put(Case(title='kept', evidence=[EvidenceItem(description='kept evidence')]))
    if created is not None:
        created.extend((old.id, kept.id))
    old_file = store.put_file(old.id, 'old.pdf', b'%PDF-1.4 old')
    kept_file = store.put_file(kept.id, 'kept.pdf', b'%PDF-1.4 kept')
    _age(store, old.id, 8)
    _age(store, kept.id, 6)
    assert store.purge_expired() == 1
    assert store.get(old.id) is None
    assert store.get_file(old.id, old_file['id']) is None
    staying = store.get(kept.id)
    assert staying.title == 'kept'
    assert staying.evidence[0].description == 'kept evidence'
    assert store.get_file(kept.id, kept_file['id'])['data'] == b'%PDF-1.4 kept'
    assert store.delete(kept.id) is True
    assert store.get(kept.id) is None
    assert store.get_file(kept.id, kept_file['id']) is None
    assert store.purge_expired() == 0


def test_sqlite_purges_eight_days_keeps_six_and_a_second_purge_is_a_noop(tmp_path):
    assert_retention(CaseStore(tmp_path / 'cases.sqlite'))


def test_maybe_purge_runs_once_per_interval(tmp_path):
    reset_purge_clock()
    store = CaseStore(tmp_path / 'cases.sqlite')
    first = store.put(Case(title='first'))
    _age(store, first.id, 8)
    assert maybe_purge(store, interval=600) == 1
    assert store.get(first.id) is None
    second = store.put(Case(title='second'))
    _age(store, second.id, 8)
    assert maybe_purge(store, interval=600) == 0
    # Inspect storage directly: accessing an expired case must itself remove it.
    with sqlite3.connect(store.path) as con:
        assert con.execute('SELECT id FROM cases WHERE id=?', (second.id,)).fetchone()
    reset_purge_clock()
    assert maybe_purge(store, interval=600) == 1
    assert store.get(second.id) is None
    reset_purge_clock()


def test_cli_purges_once_and_the_second_run_deletes_nothing(tmp_path, monkeypatch):
    path = tmp_path / 'cases.sqlite'
    monkeypatch.delenv('BATATIS_STORE', raising=False)
    monkeypatch.delenv('VERCEL', raising=False)
    monkeypatch.setenv('BATATIS_CASES', str(path))
    store = open_store(path)
    old = store.put(Case(title='cli'))
    _age(store, old.id, 8)
    root = str(Path(__file__).resolve().parents[2])
    env = os.environ.copy()
    env['PYTHONPATH'] = root + os.pathsep + env.get('PYTHONPATH', '')
    first = subprocess.run([sys.executable, '-m', 'engine.retention'], cwd=root, env=env,
                           capture_output=True, text=True, check=False)
    assert first.returncode == 0, first.stderr
    assert first.stdout.strip() == '1'
    assert store.get(old.id) is None
    second = subprocess.run([sys.executable, '-m', 'engine.retention'], cwd=root, env=env,
                            capture_output=True, text=True, check=False)
    assert second.returncode == 0, second.stderr
    assert second.stdout.strip() == '0'


def test_delete_and_cron_purge(tmp_path):
    reset_purge_clock()
    store = CaseStore(tmp_path / 'cases.sqlite')
    client = TestClient(create_app(store=store, codes=None))
    missing = client.delete('/cases/case_missing')
    assert missing.status_code == 404
    assert missing.json()['detail'] == 'case not found'
    created = client.post('/cases', json={'title': 'soon gone'})
    assert created.status_code == 201
    case_id = created.json()['id']
    uploaded = client.post(f'/cases/{case_id}/files', content=b'%PDF-1.4 cron',
                           headers={'content-type': 'application/pdf'})
    file_id = uploaded.json()['id']
    _age(store, case_id, 8)
    purged = client.get('/retention/purge')
    assert purged.status_code == 200
    assert purged.json()['deleted'] == 1
    assert store.get(case_id) is None
    assert store.get_file(case_id, file_id) is None
    again = client.get('/retention/purge')
    assert again.json()['deleted'] == 0
    assert client.delete(f'/cases/{case_id}').status_code == 404
    reset_purge_clock()


def test_purge_now_matches_the_store(tmp_path, monkeypatch):
    path = tmp_path / 'cases.sqlite'
    monkeypatch.delenv('BATATIS_STORE', raising=False)
    monkeypatch.delenv('VERCEL', raising=False)
    monkeypatch.setenv('BATATIS_CASES', str(path))
    store = open_store(path)
    case = store.put(Case(title='direct'))
    _age(store, case.id, 8)
    assert purge_now() == 1
    assert purge_now() == 0
