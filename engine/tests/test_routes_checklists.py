"""GET /jurisdictions/{id}/checklists, GET /cases/{id}/checklists and the versioned answer route."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from engine.api import create_app
from engine.jurisdictions.checklists import NONE_IN_PACK, NONE_NO_JURISDICTION, NOTICE
from engine.models import Case, Fact, Jurisdiction, Source
from engine.store import CaseStore

CALGARY = {'id': 'calgary', 'name': 'City of Calgary'}


@pytest.fixture
def scene(tmp_path, monkeypatch):
    monkeypatch.delenv('VERCEL', raising=False)
    store = CaseStore(tmp_path / 'cases.sqlite')
    return store, TestClient(create_app(store=store), base_url='http://localhost')


def _case(client, jurisdiction=CALGARY) -> dict:
    r = client.post('/cases', json={'title': 'SYNTHETIC checklist fixture', 'jurisdiction': jurisdiction})
    assert r.status_code == 201
    return r.json()


def _answer(client, case_id, version, condition, state, reason=None, checklist='calgary-spv-001'):
    body = {'condition_id': condition, 'state': state, 'expected_version': version}
    if reason is not None:
        body['reason'] = reason
    return client.post(f'/cases/{case_id}/checklists/{checklist}/answers', json=body)


def test_jurisdiction_checklists_and_historical_packages(scene):
    _, client = scene
    calgary = client.get('/jurisdictions/calgary/checklists').json()
    assert [c['code'] for c in calgary['checklists']] == ['SPV-001', 'SPV-006']
    assert calgary['historical'] == [] and calgary['notice'] == NOTICE
    first = calgary['checklists'][0]['conditions'][0]
    assert {'plain', 'source', 'may_not_apply'} <= set(first) and 'answer' not in first
    edmonton = client.get('/jurisdictions/edmonton/checklists').json()
    assert [c['code'] for c in edmonton['checklists']] == ['B23-01']
    assert [(h['code'], h['status']) for h in edmonton['historical']] == [('B14-01', 'historical')]
    assert 'superseded' in edmonton['historical'][0]['historical_reason']
    assert client.get('/jurisdictions/alberta-other/checklists').json()['checklists'] == []
    assert client.get('/jurisdictions/nowhere/checklists').status_code == 404


def test_case_checklists_follow_the_case_jurisdiction(scene):
    _, client = scene
    case = _case(client)
    body = client.get(f'/cases/{case["id"]}/checklists').json()
    assert body['jurisdiction'] == 'calgary' and body['matched_by'] == 'id' and body['none_reason'] is None
    assert [c['code'] for c in body['checklists']] == ['SPV-001', 'SPV-006']
    spv = body['checklists'][0]
    assert spv['counts']['unanswered'] == spv['counts']['total'] == len(spv['conditions'])
    assert all(c['answer'] is None for c in spv['conditions']) and spv['reviewed'] is False
    edmonton = client.get(f'/cases/{_case(client, {"id": "edmonton", "name": "City of Edmonton"})["id"]}/checklists').json()
    assert [c['code'] for c in edmonton['checklists']] == ['B23-01']
    assert [h['code'] for h in edmonton['historical']] == ['B14-01']
    other = client.get(f'/cases/{_case(client, {"id": "red-deer", "name": "Red Deer"})["id"]}/checklists').json()
    assert other['matched_by'] == 'fallback' and other['checklists'] == [] and other['none_reason'] == NONE_IN_PACK
    none = client.get(f'/cases/{_case(client, None)["id"]}/checklists').json()
    assert none['jurisdiction'] is None and none['none_reason'] == NONE_NO_JURISDICTION
    assert client.get('/cases/missing/checklists').status_code == 404


def test_a_package_for_one_of_the_case_provisions_comes_first(scene):
    store, client = scene
    case = store.put(Case(title='SYNTHETIC', jurisdiction=Jurisdiction(**CALGARY), provisions=['9.10.11.2.(2)']))
    rows = client.get(f'/cases/{case.id}/checklists').json()['checklists']
    assert [(r['code'], r['matches_case_provisions']) for r in rows] == [('SPV-006', True), ('SPV-001', False)]


def test_answers_are_versioned_declarations(scene):
    _, client = scene
    case = _case(client)
    r = _answer(client, case['id'], case['version'], 'scope-houses', 'confirmed')
    assert r.status_code == 200, r.text
    version = r.json()['case_version']
    assert version == case['version'] + 1
    row = next(c for c in r.json()['checklist']['conditions'] if c['id'] == 'scope-houses')
    assert row['answer']['state'] == 'confirmed' and row['answer']['reason'] is None
    assert r.json()['checklist']['counts']['confirmed'] == 1

    stale = _answer(client, case['id'], case['version'], 'scope-storeys', 'confirmed')
    assert stale.status_code == 409 and stale.json()['detail'] == 'case was updated concurrently'

    r = _answer(client, case['id'], version, 'b-i-balcony-no-openings', 'does_not_apply', 'No balconies.')
    assert r.status_code == 200
    version = r.json()['case_version']
    r = _answer(client, case['id'], version, 'b-i-balcony-no-openings', 'not_yet')
    version = r.json()['case_version']
    row = next(c for c in r.json()['checklist']['conditions'] if c['id'] == 'b-i-balcony-no-openings')
    assert row['answer'] == {'state': 'not_yet', 'reason': None, 'fact_id': row['answer']['fact_id']}

    fetched = client.get(f'/cases/{case["id"]}/checklists').json()
    assert fetched['case_version'] == version
    counts = fetched['checklists'][0]['counts']
    assert (counts['confirmed'], counts['not_yet'], counts['does_not_apply']) == (1, 1, 0)
    assert counts['unanswered'] == counts['total'] - 2


def test_answer_validation(scene):
    _, client = scene
    case = _case(client)
    v = case['version']
    assert _answer(client, case['id'], v, 'b-i-balcony-no-openings', 'does_not_apply').status_code == 422
    assert _answer(client, case['id'], v, 'b-i-balcony-no-openings', 'does_not_apply', '  ').status_code == 422
    always = _answer(client, case['id'], v, 'marw-both-titles', 'does_not_apply', 'No neighbour.')
    assert always.status_code == 422 and 'always applies' in always.json()['detail']
    assert _answer(client, case['id'], v, 'nope', 'confirmed').status_code == 422
    assert _answer(client, case['id'], v, 'scope-houses', 'complies').status_code == 422
    assert _answer(client, case['id'], v, 'scope-houses', 'confirmed', checklist='edmonton-b23-01').status_code == 404
    body = {'condition_id': 'scope-houses', 'state': 'confirmed', 'expected_version': '1'}
    assert client.post(f'/cases/{case["id"]}/checklists/calgary-spv-001/answers', json=body).status_code == 422
    assert _answer(client, 'missing', 1, 'scope-houses', 'confirmed').status_code == 404
    assert client.get(f'/cases/{case["id"]}').json()['version'] == v     # nothing was written


def test_only_applicant_facts_count_as_answers(scene):
    store, client = scene
    case = _case(client)
    field = 'checklist.calgary-spv-001.scope-houses'
    proposed = Fact(field=field, value='confirmed', kind='proposed', source=Source(type='user_text', ref='model'))
    store.add_fact(case['id'], proposed)
    always = Fact(field='checklist.calgary-spv-001.marw-both-titles', value='does_not_apply', kind='exact',
                  status='confirmed', source=Source(type='user_click', ref='raw'))
    store.add_fact(case['id'], always)
    rows = {c['id']: c for c in client.get(f'/cases/{case["id"]}/checklists').json()['checklists'][0]['conditions']}
    assert rows['scope-houses']['answer'] is None and rows['marw-both-titles']['answer'] is None
    clicked = {'field': field, 'value': 'confirmed', 'kind': 'exact', 'status': 'confirmed',
               'source': {'type': 'user_click', 'ref': 'checklist card'}}
    assert client.post(f'/cases/{case["id"]}/facts', json=clicked).status_code == 200
    rows = {c['id']: c for c in client.get(f'/cases/{case["id"]}/checklists').json()['checklists'][0]['conditions']}
    assert rows['scope-houses']['answer']['state'] == 'confirmed'
