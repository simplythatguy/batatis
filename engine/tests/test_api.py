import pytest
from fastapi.testclient import TestClient

from engine.api import create_app
from engine.codes import Codes
from engine.store import CaseStore


@pytest.fixture(scope='module')
def client(tmp_path_factory):
    store = CaseStore(tmp_path_factory.mktemp('cases') / 'cases.sqlite')
    return TestClient(create_app(store=store, codes=Codes()))


def test_missing_code_database_is_not_turned_into_a_503(tmp_path, monkeypatch):
    """A missing codedb must not be rewritten into a 503 that echoes the filesystem path.

    The narrow CodeDbMissing 503 lives on the backend/case-api branch, not here.
    The response is a fixed 500 so the body does not include the path.
    """
    monkeypatch.setenv('BATATIS_CODEDB', str(tmp_path / 'no-such.sqlite'))
    client = TestClient(create_app(store=CaseStore(tmp_path / 'cases.sqlite')), raise_server_exceptions=False)
    r = client.get('/code/search', params={'q': 'wall'})
    assert r.status_code == 500
    assert 'no-such.sqlite' not in r.text
    assert 'BATATIS_CODEDB' not in r.text
    assert 'code database not found' not in r.text


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
    hits = client.get('/code/search', params={'q': 'limiting distance unprotected openings'}).json()
    assert hits and all(h['division'] == 'B' and h['citation'] for h in hits)


def test_section_c_endpoint(client):
    r = client.post('/section-c', json={'provisions': ['9.10.13.13.(1)', '9.10.14.2.']})
    assert r.status_code == 200
    rows = r.json()
    assert rows[0]['attribution_status'] == 'direct'
    assert {x['attribution_status'] for x in rows[1:]} == {'no row in the attribution table'}
    assert client.post('/section-c', json={'provisions': ['9.99.99.99.(1)']}).status_code == 404


def test_cors_allows_localhost(client):
    r = client.options('/cases', headers={'Origin': 'http://localhost:5173', 'Access-Control-Request-Method': 'POST'})
    assert r.headers.get('access-control-allow-origin') == 'http://localhost:5173'


def test_missing_scc_form_response_does_not_expose_path(tmp_path, monkeypatch):
    from engine import api
    from engine.export.scc import load_form

    missing_form = tmp_path / 'private-scc-form.pdf'
    monkeypatch.setenv('BATATIS_SCC_FORM', str(missing_form))
    monkeypatch.setattr(api, 'export_case', lambda *args, **kwargs: load_form(None, {}))
    client = TestClient(create_app(store=CaseStore(tmp_path / 'cases.sqlite'), codes=object()))
    case_id = client.post('/cases').json()['id']

    response = client.post(f'/cases/{case_id}/export')

    assert response.status_code == 503
    assert response.json() == {'detail': 'SCC variance form not found'}
    assert str(tmp_path) not in response.text
    assert 'BATATIS_SCC_FORM' not in response.text


def test_export_error_response_does_not_expose_path(tmp_path, monkeypatch):
    from engine import api
    from engine.export import FormMismatch

    def mismatched_form(*args, **kwargs):
        raise FormMismatch(f'{tmp_path}/private-scc-form.pdf has an unexpected SHA-256')

    monkeypatch.setattr(api, 'export_case', mismatched_form)
    client = TestClient(create_app(store=CaseStore(tmp_path / 'cases.sqlite'), codes=object()))
    case_id = client.post('/cases').json()['id']

    response = client.post(f'/cases/{case_id}/export')

    assert response.status_code == 500
    assert response.json() == {'detail': 'The SCC variance form could not be exported.'}
    assert str(tmp_path) not in response.text
