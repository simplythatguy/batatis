"""End-to-end case flow through the HTTP API.

Create a case, add a fact, then read administrative gaps and export. Gaps and
export open the code database. When that file is not built, those steps are
skipped through ``engine.tests._db_skip.require_repo_db``.

An empty case export is 409. A draft export is 200 when the blank SCC form is
present; without that form the 409 result still stands. Neither response is a
finding that a design complies or is safe.

File upload is the deploy branch's route. This flow does not post one.
"""
from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from engine.api import create_app
from engine.export import form_path
from engine.store import CaseStore
from engine.tests._db_skip import require_repo_db

FACT = {
    'field': 'municipal_address',
    'value': '100 Example Avenue, Edmonton',
    'kind': 'exact',
    'status': 'confirmed',
    'source': {'type': 'user_text', 'ref': 'e2e-synthetic'},
}


def _client(tmp_path: Path) -> TestClient:
    store = CaseStore(tmp_path / 'cases.sqlite')
    return TestClient(create_app(store))


def _create_with_fact(client: TestClient) -> str:
    created = client.post('/cases', json={'title': 'Synthetic e2e case'})
    assert created.status_code == 201
    case_id = created.json()['id']
    added = client.post(f'/cases/{case_id}/facts', json=FACT)
    assert added.status_code == 200
    assert added.json()['facts'][0]['field'] == 'municipal_address'
    return case_id


def test_e2e_create_and_store_a_fact(tmp_path):
    """A confirmed fact is stored on the case. This branch has no file route."""
    client = _client(tmp_path)
    case_id = _create_with_fact(client)
    case = client.get(f'/cases/{case_id}').json()
    assert case['facts'][0]['value'] == '100 Example Avenue, Edmonton'
    assert '/cases/{case_id}/files' not in client.get('/openapi.json').json()['paths']


def test_e2e_gaps_then_export_409_and_draft_200(tmp_path):
    """Administrative gaps, then a blocked export and a draft PDF when the form exists."""
    require_repo_db()
    client = _client(tmp_path)
    case_id = _create_with_fact(client)

    gaps = client.get(f'/cases/{case_id}/gaps')
    assert gaps.status_code == 200
    assert isinstance(gaps.json(), list)
    assert 'complies' not in gaps.text.lower()

    blocked = client.post(f'/cases/{case_id}/export')
    assert blocked.status_code == 409
    body = blocked.json()
    assert isinstance(body['detail'], list) and body['detail']
    assert body['reasons']
    assert 'complies' not in blocked.text.lower()

    if not form_path().exists():
        return
    draft = client.post(f'/cases/{case_id}/export', json={'draft': True})
    assert draft.status_code == 200
    assert draft.headers['content-type'] == 'application/pdf'
    assert draft.content.startswith(b'%PDF')
    assert 'DRAFT' in draft.headers['content-disposition']
    assert 'complies' not in draft.headers.get('content-disposition', '').lower()
