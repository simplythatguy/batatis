import pytest
from fastapi.testclient import TestClient

from engine.api import create_app
from engine.codes import Codes
from engine.store import CaseStore
from engine.tests.json_body import listed


@pytest.fixture(scope='module')
def client(tmp_path_factory):
    store = CaseStore(tmp_path_factory.mktemp('cases') / 'cases.sqlite')
    return TestClient(create_app(store=store, codes=Codes()))


def test_case_lifecycle(client):
    r = client.post('/cases', json={'title': 'Garage suite', 'jurisdiction': {'id': 'calgary', 'name': 'Calgary'}})
    assert r.status_code == 201
    cid = r.json()['id']
    fact = {'field': 'storeys', 'value': 2, 'kind': 'pointed',
            'source': {'type': 'user_text', 'ref': 'msg_1', 'quote': 'two storey'}}
    r = client.post(f'/cases/{cid}/facts', json=fact)
    assert r.status_code == 200 and r.json()['facts'][0]['field'] == 'storeys'
    assert client.get(f'/cases/{cid}').json()['jurisdiction']['id'] == 'calgary'
    assert client.get('/cases/case_nope').status_code == 404


def test_proposed_confirmed_fact_is_rejected(client):
    cid = client.post('/cases').json()['id']
    bad = {'field': 'x', 'value': 1, 'kind': 'proposed', 'status': 'confirmed',
           'source': {'type': 'user_text', 'ref': 'm'}}
    assert client.post(f'/cases/{cid}/facts', json=bad).status_code == 422


def test_code_lookup_and_search(client):
    r = client.get('/code/9.10.15.5.(8)', params={'division': 'B'})
    assert r.status_code == 200 and r.json()['citation'].startswith('NBC(AE) 2023 p2, Div B, Sentence 9.10.15.5.(8)')
    assert client.get('/code/9.99.99.99.', params={'division': 'B'}).status_code == 404
    hits = listed(client.get('/code/search', params={'q': 'limiting distance unprotected openings'}).json())
    assert hits and all(h['division'] == 'B' and h['citation'] for h in hits)


def test_section_c_endpoint(client):
    r = client.post('/section-c', json={'provisions': ['9.10.13.13.(1)', '9.10.14.2.']})
    assert r.status_code == 200
    rows = listed(r.json())
    assert rows[0]['attribution_status'] == 'direct'
    assert {x['attribution_status'] for x in rows[1:]} == {'no row in the attribution table'}
    assert client.post('/section-c', json={'provisions': ['9.99.99.99.(1)']}).status_code == 404


def test_cors_allows_localhost(client):
    r = client.options('/cases', headers={'Origin': 'http://localhost:5173', 'Access-Control-Request-Method': 'POST'})
    assert r.headers.get('access-control-allow-origin') == 'http://localhost:5173'
