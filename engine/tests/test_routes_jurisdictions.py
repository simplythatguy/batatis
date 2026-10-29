"""GET /jurisdictions, /jurisdictions/{id} and a case's pack, including the access guard."""
from __future__ import annotations

from contextlib import ExitStack
from io import BytesIO
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from pypdf import PdfReader

from engine.api import create_app
from engine.codes import Codes
from engine.export.sample import sample_case
from engine.jurisdictions import registry
from engine.models import Case, Jurisdiction
from engine.privacy import PRIVACY_NOTICE
from engine.store import CaseStore
from engine.tests.test_accounts import onboard, signup
from engine.tests.case_builder_fixtures import store_with_synthetic_files


@pytest.fixture
def scene(tmp_path, monkeypatch):
    monkeypatch.delenv('VERCEL', raising=False)
    monkeypatch.setenv('BATATIS_REVIEWER_CODES', '{"edmonton":"officer-secret","calgary":"calgary-secret"}')
    monkeypatch.setenv('BATATIS_AUTH_RATE_LIMIT', '100')
    store = CaseStore(tmp_path / 'cases.sqlite')
    app = create_app(store=store)
    with ExitStack() as stack:
        clients = {name: stack.enter_context(TestClient(app, base_url='http://localhost'))
                   for name in ('owner', 'other', 'anonymous')}
        users = {}
        for name in ('owner', 'other'):
            assert signup(clients[name], f'{name}@example.test', name.title()).status_code == 201
            users[name] = onboard(clients[name])
        yield SimpleNamespace(app=app, store=store, clients=clients, users=users)


def test_public_list_has_packs_coverage_and_disclaimer(scene):
    r = scene.clients['anonymous'].get('/jurisdictions')
    assert r.status_code == 200
    body = r.json()
    assert {row['id'] for row in body['jurisdictions']} >= {'calgary', 'edmonton', 'alberta-other'}
    assert {row['id'] for row in body['coverage']} >= {'AB', 'BC', 'NU'}
    assert 'never' in body['disclaimer'] and 'complies' in body['disclaimer']
    fallback = [row for row in body['jurisdictions'] if row['fallback']]
    assert [row['id'] for row in fallback] == ['alberta-other']


def test_detail_merges_province_items_and_404s(scene):
    client = scene.clients['anonymous']
    body = client.get('/jurisdictions/calgary').json()
    assert [f['id'] for f in body['forms']] == ['scc-variance', 'calgary-request-for-specific-variance']
    assert [f['scope'] for f in body['forms']] == ['province', 'local']
    assert {b['id'] for b in body['bulletins']} == {'IB-2026-10-01', 'IB-2025-11-18', 'IB-2026-10-16'}
    assert all(n['sources'] for n in body['process_notes'])
    assert {'province', 'local'} == {n['scope'] for n in body['process_notes']}
    edmonton = client.get('/jurisdictions/edmonton').json()
    b14 = next(p for p in edmonton['standing_packages'] if p['code'] == 'B14-01')
    assert b14['status'] == 'historical' and '2014' in b14['edition']
    r = client.get('/jurisdictions/nowhere')
    assert r.status_code == 404 and r.json()['detail'] == 'jurisdiction not found'


@pytest.mark.parametrize('jurisdiction, authority, expected, how', [
    ({'id': 'calgary', 'name': 'Calgary'}, None, 'calgary', 'id'),
    ({'id': 'edmonton', 'name': 'Edmonton'}, None, 'edmonton', 'id'),
    ({'id': 'x-1', 'name': 'City of Edmonton'}, None, 'edmonton', 'name'),
    ({'id': 'red-deer', 'name': 'City of Red Deer'}, None, 'red-deer', 'id'),
    ({'id': 'x-2', 'name': 'Lacombe County'}, None, 'lacombe-county', 'name'),
    ({'id': 'vancouver', 'name': 'Vancouver'}, None, 'vancouver', 'id'),
    ({'id': 'Example Hamlet', 'name': 'Example Hamlet'}, None, 'alberta-other', 'fallback'),
    (None, 'edmonton', 'edmonton', 'reviewer_code'),
])
def test_a_case_resolves_to_a_pack(scene, jurisdiction, authority, expected, how):
    body = {'title': 'Resolve', **({'jurisdiction': jurisdiction} if jurisdiction else {}),
            **({'authority': authority} if authority else {})}
    case = scene.clients['owner'].post('/cases', json=body).json()
    r = scene.clients['owner'].get(f'/cases/{case["id"]}/jurisdiction/pack')
    assert r.status_code == 200
    assert (r.json()['pack']['id'], r.json()['matched_by']) == (expected, how)


def test_a_case_without_a_jurisdiction_has_no_pack(scene):
    case = scene.clients['owner'].post('/cases', json={'title': 'Open'}).json()
    body = scene.clients['owner'].get(f'/cases/{case["id"]}/jurisdiction/pack').json()
    assert body['pack'] is None and body['matched_by'] is None


def test_not_sure_is_persisted_without_fabricating_a_jurisdiction(scene):
    client = scene.clients['owner']
    case = client.post('/cases', json={'title': 'Office not known yet'}).json()
    response = client.post(f'/cases/{case["id"]}/facts', json={
        'field': 'office.choice', 'value': 'not_sure', 'kind': 'pointed', 'status': 'confirmed',
        'source': {'type': 'user_click', 'ref': 'rules:office', 'quote': 'Not sure'},
    })
    assert response.status_code == 200
    saved = client.get(f'/cases/{case["id"]}').json()
    assert saved['authority'] is None and saved['jurisdiction'] is None
    assert any(fact['field'] == 'office.choice' and fact['value'] == 'not_sure' for fact in saved['facts'])
    assert client.get(f'/cases/{case["id"]}/jurisdiction/pack').json()['pack'] is None


@pytest.mark.parametrize('place, pack_id, office, source', [
    ('Red Deer', 'red-deer', 'City of Red Deer', 'councilconnect.safetycodes.ab.ca'),          # a named place
    ('Example Hamlet', 'alberta-other', None, '/where-to-get-a-permit/'),                    # an unknown one
])
def test_other_offices_keep_their_place_and_pdf_path_without_reviewer_submission(scene, monkeypatch, place, pack_id,
                                                                                  office, source):
    client = scene.clients['owner']
    case = client.post('/cases', json={'jurisdiction': {'id': place, 'name': place}}).json()
    assert case['authority'] is None
    assert client.get(f'/cases/{case["id"]}').json()['jurisdiction']['name'] == place
    pack = client.get(f'/cases/{case["id"]}/jurisdiction/pack').json()['pack']
    assert pack['id'] == pack_id and pack['authority']['reviewer_code'] is None
    assert office is None or pack['authority']['name'] == office
    assert any(source in s['url'] for s in pack['authority']['sources'])
    # Isolate routing from the independent completeness gate and PDF renderer.
    monkeypatch.setattr('engine.routes_review.check_completeness', lambda *_args, **_kw: [])
    monkeypatch.setattr('engine.api.export_case', lambda *_args, **_kw: SimpleNamespace(pdf=b'%PDF-1.4 synthetic route fixture'))
    response = client.post(f'/cases/{case["id"]}/submit', json={'expected_version': case['version']})
    assert response.status_code == 409
    assert client.post(f'/cases/{case["id"]}/export', json={'draft': True}).status_code == 200


def test_other_office_exports_the_real_pdf_with_existing_completeness_gates(scene):
    case = sample_case(Codes(), provisions=['9.25.2.2.(1)'])
    case.owner_id = scene.users['owner']['id']
    case.authority = None
    case.jurisdiction = Jurisdiction(id='red-deer', name='Red Deer')
    case = store_with_synthetic_files(scene.store, case)
    for draft in (True, False):
        response = scene.clients['owner'].post(f'/cases/{case.id}/export', json={'draft': draft})
        assert response.status_code == 200, response.text
        assert response.content.startswith(b'%PDF')
        assert len(PdfReader(BytesIO(response.content)).pages) >= 1


def test_a_case_pack_follows_the_case_access_policy(scene):
    case = Case(title='Private', owner_id=scene.users['owner']['id'])
    case.jurisdiction = None
    case = scene.store.put(case)
    url = f'/cases/{case.id}/jurisdiction/pack'
    assert scene.clients['owner'].get(url).status_code == 200
    assert scene.clients['other'].get(url).status_code == 404
    assert scene.clients['anonymous'].get(url).status_code == 404
    assert scene.clients['anonymous'].get('/cases/case_nope/jurisdiction/pack').status_code == 404


def test_export_header_and_gap_carry_the_pack_notice(scene, monkeypatch):
    monkeypatch.setattr('engine.api.export_case', lambda case, **kw: SimpleNamespace(pdf=b'%PDF-1.4 stub'))
    # The export is stubbed, so a stand-in code database is enough; the header comes from the pack.
    client = TestClient(create_app(store=scene.store, codes=SimpleNamespace()), base_url='http://localhost')
    message = registry().get('calgary').notices[0].message
    calgary = client.post('/cases', json={'jurisdiction': {'id': 'calgary', 'name': 'City of Calgary'}}).json()
    edmonton = client.post('/cases', json={'jurisdiction': {'id': 'edmonton', 'name': 'City of Edmonton'}}).json()
    for draft in (False, True):
        r = client.post(f'/cases/{calgary["id"]}/export', json={'draft': draft})
        assert r.status_code == 200 and r.headers['x-batatis-jurisdiction-notice'] == message
        assert r.headers['x-batatis-notice'] == PRIVACY_NOTICE   # the standard notice is not replaced
    other = client.post(f'/cases/{edmonton["id"]}/export')
    assert other.status_code == 200 and 'x-batatis-jurisdiction-notice' not in other.headers


def test_submit_message_names_the_reviewing_offices(scene):
    names = [p.name for p in registry().reviewing_packs()]
    from engine.jurisdictions import reviewing_authority_names
    assert reviewing_authority_names() == ' or '.join(names)
