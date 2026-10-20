"""7-day purge: an 8-day case goes, a 6-day case stays, files go with the case, a second purge is a no-op."""
from __future__ import annotations

import os
import sqlite3
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from fastapi.testclient import TestClient

from engine.api import create_app
from engine.models import Case, EvidenceItem
from engine.retention import maybe_purge, purge_now, reset_purge_clock
from engine.store import CaseStore, open_store


def _stamp(days: int) -> str:
    return (datetime.now(timezone.utc) - timedelta(days=days)).isoformat(timespec='seconds')


def _age(store, case_id: str, days: int) -> None:
    stamp = _stamp(days)
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
    assert store.get(second.id).title == 'second'
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
