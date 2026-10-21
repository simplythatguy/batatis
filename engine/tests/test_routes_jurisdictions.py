"""GET /jurisdictions, /jurisdictions/{id} and a case's pack, including the access guard."""
from __future__ import annotations

from contextlib import ExitStack
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from engine.api import create_app
from engine.jurisdictions import registry
from engine.models import Case
from engine.store import CaseStore
from engine.tests.test_accounts import onboard, signup


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
    ({'id': 'x-1', 'name': 'City of Edmonton'}, None, 'edmonton', 'name'),
    ({'id': 'red-deer', 'name': 'City of Red Deer'}, None, 'alberta-other', 'fallback'),
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
        assert r.status_code == 200 and r.headers['x-batatis-notice'] == message
    other = client.post(f'/cases/{edmonton["id"]}/export')
    assert other.status_code == 200 and other.headers['x-batatis-notice'] != message


def test_submit_message_names_the_reviewing_offices(scene):
    names = [p.name for p in registry().reviewing_packs()]
    from engine.jurisdictions import reviewing_authority_names
    assert reviewing_authority_names() == ' or '.join(names)
