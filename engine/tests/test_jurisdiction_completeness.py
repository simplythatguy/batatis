"""Synthetic jurisdiction omissions remain visible through the public case routes."""
import pytest
from fastapi.testclient import TestClient

from engine.api import create_app
from engine.codes import Codes
from engine.models import Case
from engine.store import CaseStore


VALID = {'id': 'test-jurisdiction', 'name': 'TEST reviewing jurisdiction'}
INCOMPLETE = [
    {'id': '', 'name': VALID['name']},
    {'id': ' \t\n', 'name': VALID['name']},
    {'id': VALID['id'], 'name': ''},
    {'id': VALID['id'], 'name': ' \t\n'},
    {'id': '', 'name': ''},
]


@pytest.fixture
def context(tmp_path):
    store = CaseStore(tmp_path / 'cases.sqlite')
    with TestClient(create_app(store=store, codes=Codes())) as client:
        yield client, store


def jurisdiction_gaps(client, case_id):
    response = client.get(f'/api/cases/{case_id}/gaps')
    assert response.status_code == 200, response.text
    return [gap for gap in response.json()['items'] if gap['field'] == 'jurisdiction']


@pytest.mark.parametrize('jurisdiction', INCOMPLETE)
@pytest.mark.parametrize('write', ['create', 'update'])
def test_blank_jurisdiction_fields_cannot_clear_the_required_gap(context, jurisdiction, write):
    client, store = context
    response = client.post('/api/cases', json={
        'title': 'TEST incomplete reviewing jurisdiction',
        'jurisdiction': jurisdiction if write == 'create' else VALID,
    })
    assert response.status_code == 201, response.text
    case = response.json()
    if write == 'update':
        response = client.put(f"/api/cases/{case['id']}/jurisdiction", json={
            'jurisdiction': jurisdiction, 'expected_version': case['version'],
        })
        assert response.status_code == 200, response.text
        case = response.json()

    gaps = jurisdiction_gaps(client, case['id'])
    assert len(gaps) == 1
    assert gaps[0]['severity'] == 'blocking'
    assert gaps[0]['id'] == 'admin:jurisdiction'
    # Checking an incomplete draft must not invent or silently change its authority.
    loaded = client.get(f"/api/cases/{case['id']}")
    assert loaded.status_code == 200
    assert loaded.json()['jurisdiction'] == case['jurisdiction']
    assert loaded.json()['version'] == case['version'] == store.get_version(case['id'])


@pytest.mark.parametrize('jurisdiction', [VALID, {**VALID, 'authority': None}])
def test_supplied_jurisdiction_does_not_add_a_missing_jurisdiction_gap(context, jurisdiction):
    client, _ = context
    created = client.post('/api/cases', json={'jurisdiction': jurisdiction})
    assert created.status_code == 201
    assert jurisdiction_gaps(client, created.json()['id']) == []


def test_legacy_blank_jurisdiction_remains_readable_and_repairable(context):
    client, store = context
    saved = store.put(Case(title='TEST legacy blank authority', jurisdiction=INCOMPLETE[-1]))
    loaded = client.get(f'/api/cases/{saved.id}')
    assert loaded.status_code == 200
    assert len(jurisdiction_gaps(client, saved.id)) == 1
    repaired = client.put(f'/api/cases/{saved.id}/jurisdiction', json={
        'jurisdiction': VALID, 'expected_version': loaded.json()['version'],
    })
    assert repaired.status_code == 200, repaired.text
    assert repaired.json()['id'] == saved.id
    assert jurisdiction_gaps(client, saved.id) == []
