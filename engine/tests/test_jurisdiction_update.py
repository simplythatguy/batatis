"""Synthetic jurisdiction edits exercise the real router and both storage adapters."""
import os

import pytest
from fastapi.testclient import TestClient

from engine.api import create_app
from engine.models import Case
from engine.privacy import PII_NOTICE
from engine.retention import reset_purge_clock
from engine.store import CaseStore


FIRST = {'id': 'test-ahj-a', 'name': 'TEST jurisdiction A (synthetic)', 'authority': 'TEST authority A'}
SECOND = {'id': 'test-ahj-b', 'name': 'TEST jurisdiction B (synthetic)', 'authority': None}


@pytest.fixture(params=['sqlite', 'postgres'])
def context(request, tmp_path):
    if request.param == 'postgres':
        url = os.environ.get('TEST_DATABASE_URL')
        if not url:
            pytest.skip('TEST_DATABASE_URL is not set; real Postgres required')
        from engine.store_postgres import PostgresCaseStore
        store = PostgresCaseStore(url)
    else:
        store = CaseStore(tmp_path / 'cases.sqlite')
    reset_purge_clock()
    with TestClient(create_app(store=store)) as client:
        yield client, store
    reset_purge_clock()


def assert_private(response, status):
    assert response.status_code == status, response.text
    assert response.json()['meta']['notice'] == PII_NOTICE
    assert response.headers['x-batatis-notice'] == PII_NOTICE
    assert response.headers['x-robots-tag'] == 'noindex, nofollow'


def update(client, case_id, jurisdiction, version, prefix='/api'):
    return client.put(f'{prefix}/cases/{case_id}/jurisdiction', json={
        'jurisdiction': jurisdiction, 'expected_version': version,
    })


def test_create_change_clear_keeps_same_case_and_acknowledges_actual_versions(context):
    client, store = context
    created = client.post('/api/cases', json={'title': 'TEST jurisdiction edits', 'jurisdiction': FIRST})
    assert_private(created, 201)
    original = Case.model_validate(created.json())
    assert original.version == 1
    changed = update(client, original.id, SECOND, original.version)
    assert_private(changed, 200)
    assert changed.json()['id'] == original.id
    assert changed.json()['jurisdiction'] == SECOND
    assert changed.json()['version'] == store.get_version(original.id) == 2
    cleared = update(client, original.id, None, changed.json()['version'], prefix='')
    assert_private(cleared, 200)
    assert cleared.json()['id'] == original.id
    assert cleared.json()['jurisdiction'] is None
    assert cleared.json()['version'] == store.get_version(original.id) == 3
    loaded = client.get(f'/api/cases/{original.id}')
    assert_private(loaded, 200)
    assert loaded.json() == cleared.json()
    assert loaded.json()['created_at'] == original.created_at
