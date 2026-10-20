"""HTTP description and fact routes. They run without a code database."""
import pytest
from fastapi.testclient import TestClient

from engine.api import create_app
from engine.store import CaseStore

MIRA = (
    'We manufacture NailBase CI-50, a 50 mm rigid foam panel with a 6 mm fibre-cement facer that replaces '
    '11 mm OSB sheathing on 2x6 walls at 400 mm o.c. Vinyl siding is nailed directly into the facer with no furring. '
    'We want approval to sell it across Alberta and to build a pilot house in Edmonton: 2-storey single-family, '
    'about 190 m2, unsprinklered, builder Birchfield Example Homes, address 0000 Example Way NW. We have our '
    'product data sheet, a US lab permeance test summary, and an unsigned draft engineer letter about nail pull-out. '
    'We have no CCMC evaluation yet, no air-leakage test, and no bracing design. Do we need an engineer to stamp anything?'
)


@pytest.fixture
def client(tmp_path):
    store = CaseStore(tmp_path / 'cases.sqlite')
    return TestClient(create_app(store=store, codes=None))


def _case(client):
    return client.post('/cases', json={'title': 'intake'}).json()['id']


def test_description_returns_facts_and_not_the_whole_paste(client):
    cid = _case(client)
    response = client.post(f'/cases/{cid}/description', json={'text': MIRA})
    assert response.status_code == 200
    body = response.json()
    assert set(body) == {'facts', 'alternative_description', 'proposed_alternative'}
    assert body['alternative_description'] == body['proposed_alternative']
    assert body['proposed_alternative']
    assert 'Birchfield' not in body['proposed_alternative']
    assert '0000 Example Way' not in body['proposed_alternative']
    facts = body['facts']
    assert facts['applicant_role']['value'] == 'manufacturer'
    assert facts['applicant_role']['status'] == 'extracted'
    assert facts['sprinklered']['value'] == 'no'
    assert facts['storeys']['value'] == 2
    assert facts['evidence_items'][2]['professional_confirmed'] is False
    stored = client.get(f'/cases/{cid}/facts')
    assert stored.status_code == 200
    assert stored.json()['owner_name']['value'] is None
    got = client.get(f'/cases/{cid}').json()
    assert got['intake_text'] == MIRA
    assert all(fact['source']['quote'] in MIRA for fact in got['facts'] if fact['source'].get('quote'))


def test_get_facts_before_a_description_is_a_blank_object(client):
    cid = _case(client)
    response = client.get(f'/cases/{cid}/facts')
    assert response.status_code == 200
    assert response.json()['permit_number']['status'] == 'missing'
    assert client.get('/cases/missing/facts').status_code == 404


def test_patch_confirms_and_survives_reextraction(client):
    cid = _case(client)
    client.post(f'/cases/{cid}/description', json={'text': 'The owner is Pat Example. Permit number BP-1 is issued.'})
    patched = client.patch(f'/cases/{cid}/facts', json={'owner_name': 'Kept Name', 'occupancy': 'single_family'})
    assert patched.status_code == 200
    body = patched.json()
    assert body['facts']['owner_name']['status'] == 'corrected'
    assert body['facts']['owner_name']['method'] == 'user'
    assert body['facts']['occupancy']['status'] == 'confirmed'
    summary = body['gaps_summary']
    assert summary['unavailable'] is True
    assert summary['detail'] == 'code database not found'
    assert summary['blocking'] is None
    again = client.post(f'/cases/{cid}/description', json={'text': 'The owner is Pat Example. Permit number BP-1 is issued.'})
    assert again.json()['facts']['owner_name']['value'] == 'Kept Name'
    assert again.json()['facts']['permit_number']['value'] == 'BP-1'


def test_patch_rejects_a_bad_enum_and_an_empty_body(client):
    cid = _case(client)
    client.post(f'/cases/{cid}/description', json={'text': 'A house.'})
    assert client.patch(f'/cases/{cid}/facts', json={}).status_code == 422
    assert client.patch(f'/cases/{cid}/facts', json={'occupancy': 'Group C'}).status_code == 422
    assert client.patch(f'/cases/{cid}/facts', json={'sprinklered': 'exempt'}).status_code == 422
    assert client.patch(f'/cases/{cid}/facts', json={'owner_name': None}).status_code == 422
    assert client.patch(f'/cases/{cid}/facts', json={'claimed_exemptions': []}).status_code == 422


def test_exemption_patch_summary_includes_the_officer_gap_without_the_database(client):
    cid = _case(client)
    client.post(f'/cases/{cid}/description', json={'text': 'The sub says sprinklers are "exempt".'})
    response = client.patch(f'/cases/{cid}/facts', json={'project_name': 'Example Commons'})
    assert response.status_code == 200
    gaps = response.json()['gaps_summary']['gaps']
    assert any(gap['message'] == 'applicant claim not supported by a citation' for gap in gaps)
    assert client.get(f'/cases/{cid}/gaps').status_code == 503


def test_description_rejects_an_empty_paste(client):
    cid = _case(client)
    assert client.post(f'/cases/{cid}/description', json={'text': ''}).status_code == 422
    assert client.post(f'/cases/{cid}/description', json={}).status_code == 422
