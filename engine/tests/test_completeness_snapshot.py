"""Controlled real-SQLite report/save/delete/expiry interleavings, through HTTP."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from threading import Event

import pytest
from fastapi.testclient import TestClient

from engine.api import create_app
from engine.codes import Codes
from engine.models import Case
from engine.store import CaseStore
from engine.tests.test_completeness_saved_case import fact


@pytest.mark.parametrize('change,status', [('save', 409), ('delete', 404), ('expire', 404)])
def test_controlled_change_while_report_runs_never_returns_old_report_as_current(tmp_path, monkeypatch, change, status):
    store = CaseStore(tmp_path / 'racing.sqlite')
    saved = store.put(Case(title='SYNTHETIC snapshot race', facts=[fact('owner_name', 'SYNTHETIC before')]))
    file = store.put_file(saved.id, 'synthetic.pdf', b'%PDF SYNTHETIC race bytes')
    entered, release = Event(), Event()
    codes = Codes()
    original = codes.provision
    paused = False

    def provision(*args, **kwargs):
        nonlocal paused
        if not paused:
            paused = True
            entered.set()
            assert release.wait(5), 'controlled report was never released'
        return original(*args, **kwargs)

    monkeypatch.setattr(codes, 'provision', provision)
    with TestClient(create_app(store, codes)) as client, ThreadPoolExecutor(max_workers=1) as pool:
        pending = pool.submit(client.post, f'/api/cases/{saved.id}/completeness', json={})
        try:
            assert entered.wait(5), 'report never reached source lookup after its snapshot'
            writer = CaseStore(store.path)  # independent actual current adapter/connection
            if change == 'save':
                updated = writer.add_fact(saved.id, fact('owner_name', 'SYNTHETIC concurrent owner'))
                assert updated.version == saved.version + 1
            elif change == 'delete':
                assert writer.delete(saved.id)
            else:
                future_cutoff = (datetime.now(timezone.utc) + timedelta(days=1)).isoformat()
                monkeypatch.setattr('engine.store.retention_cutoff', lambda: future_cutoff)
        finally:
            release.set()
        response = pending.result(timeout=10)
        assert response.status_code == status, response.text
        assert response.json()['detail'] == ('case was updated concurrently' if status == 409 else 'case not found')
        assert 'reviews' not in response.json()
        assert response.headers['cache-control'] == 'no-store'
        if change == 'save':
            current = writer.get(saved.id)
            assert current.facts[-1].value == 'SYNTHETIC concurrent owner'
            assert current.version == saved.version + 1
            assert writer.get_file(saved.id, file['id'])['data'] == b'%PDF SYNTHETIC race bytes'
        else:
            assert writer.get(saved.id) is None
            assert writer.get_file(saved.id, file['id']) is None
            with writer._connect() as con:
                assert con.execute('SELECT count(*) FROM cases WHERE id=?', (saved.id,)).fetchone()[0] == 0
                assert con.execute('SELECT count(*) FROM case_files WHERE case_id=?', (saved.id,)).fetchone()[0] == 0


@pytest.mark.parametrize('state', ['deleted', 'expired'])
def test_gone_case_cannot_return_prior_success_or_touch_corpus(tmp_path, state):
    store = CaseStore(tmp_path / 'gone.sqlite')
    case = store.put(Case())
    with TestClient(create_app(store, Codes())) as client:
        initial = client.post(f'/cases/{case.id}/completeness', json={})
        assert initial.status_code == 200, initial.text
    if state == 'deleted':
        store.delete(case.id)
    else:
        case.created_at = (datetime.now(timezone.utc) - timedelta(days=8)).isoformat()
        store.put(case, expected_version=case.version)

    class Forbidden:
        def __getattribute__(self, name):
            raise AssertionError(f'Gone-case report touched corpus: {name}')

    with TestClient(create_app(store, Forbidden())) as client:
        response = client.post(f'/cases/{case.id}/completeness', json={})
        assert response.status_code == 404, response.text
        assert response.json()['detail'] == 'case not found'
        assert 'reviews' not in response.json()
    assert CaseStore(store.path).get(case.id) is None
