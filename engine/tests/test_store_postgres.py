"""DELETE /cases/{id} on the Postgres case store. Skips unless DATABASE_URL is postgresql://."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from engine.api import create_app
from engine.models import Case
from engine.spend import database_url
from engine.store import open_store
from engine.store_postgres import PostgresCaseStore


def _url() -> str | None:
    url = database_url()
    if url and url.startswith('postgresql://'):
        return url
    return None


def test_postgres_delete_case_removes_the_row():
    url = _url()
    if url is None:
        pytest.skip('postgres service not configured')
    store = PostgresCaseStore(url)
    with store._conn() as con:
        con.execute('DELETE FROM cases')
    http = TestClient(create_app(store))
    created = http.post('/cases', json={'title': 'soffit trial'})
    assert created.status_code == 201
    case_id = created.json()['id']
    assert store.get(case_id) is not None
    deleted = http.delete(f'/cases/{case_id}')
    assert deleted.status_code == 204
    assert deleted.content == b''
    assert http.get(f'/cases/{case_id}').status_code == 404
    assert store.get(case_id) is None
    assert http.delete(f'/cases/{case_id}').status_code == 404


def test_open_store_uses_postgres_for_a_postgres_url():
    url = _url()
    if url is None:
        pytest.skip('postgres service not configured')
    store = open_store()
    assert isinstance(store, PostgresCaseStore)
    case = store.put(Case(title='postgres round trip'))
    assert store.get(case.id).title == 'postgres round trip'
    assert store.delete(case.id) is True
    assert store.delete(case.id) is False
