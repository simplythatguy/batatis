"""Reference mutations cross the real HTTP/store seam, without provider calls."""
import os

import pytest
from fastapi.testclient import TestClient

from engine.api import create_app
from engine.codes import Codes
from engine.models import Case, SectionCRow
from engine.store import CaseStore


@pytest.fixture(params=['sqlite', 'postgres'])
def context(request, tmp_path):
    if request.param == 'postgres':
        url = os.environ.get('TEST_DATABASE_URL')
        if not url:
            pytest.skip('TEST_DATABASE_URL is not set')
        from engine.store_postgres import PostgresCaseStore
        store = PostgresCaseStore(url)
    else:
        store = CaseStore(tmp_path / 'cases.sqlite')
    return TestClient(create_app(store, Codes())), store


def selected_case(store):
    return store.put(Case(
        title='Synthetic last-reference withdrawal',
        provisions=['9.25.5.2.(1)(b)'],
        section_c=[SectionCRow(
            provision_id='9.25.5.2.(1)(b)', citation='Synthetic saved lookup',
            attribution_status='no row in the attribution table', pairs=[], intents=[])],
    ))


def test_explicit_empty_withdraws_last_reference_over_http(context):
    client, store = context
    case = selected_case(store)
    version = store.get_version(case.id)
    response = client.post(f'/cases/{case.id}/section-d', json={
        'provisions': [], 'expected_version': version,
    })
    assert response.status_code == 200, response.text
    saved = store.get(case.id)
    assert saved.provisions == [] and saved.section_c == []
    assert response.json()['items'] == []
    assert response.json()['case_version'] == version + 1


def test_public_case_version_is_stored_row_version(context):
    client, store = context
    created = client.post('/cases', json={'title': 'Synthetic version acknowledgment'})
    assert created.status_code == 201
    case = created.json()
    assert case['version'] == store.get_version(case['id']) == 1
    assert client.get(f"/cases/{case['id']}").json()['version'] == 1
