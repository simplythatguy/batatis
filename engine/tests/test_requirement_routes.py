"""Real-corpus HTTP regressions, not an expert applicability benchmark."""
import pytest
from fastapi.testclient import TestClient

from engine.api import create_app
from engine.codes import Codes
from engine.models import Case, Fact, Source
from engine.store import CaseStore


def input_fact(field, value):
    return Fact(field=field, value=value, kind='pointed', status='confirmed',
                source=Source(type='user_text', ref='applicant'))


@pytest.fixture
def scene(tmp_path, monkeypatch):
    for name in ('BATATIS_IDENTIFY_CONFIG', 'BATATIS_IDENTIFY_SCREEN', 'BATATIS_IDENTIFY_RERANK',
                 'BATATIS_IDENTIFY_VERIFIER', 'BATATIS_PROVIDER', 'BATATIS_LIVE', 'VERCEL'):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv('BATATIS_IDENTIFY_RATE_LIMIT', '10000')
    from engine import llm_gate
    from engine.identify import pipeline
    llm_gate.reset_for_tests()
    monkeypatch.setattr(pipeline, 'default_transports', lambda *a, **k: pytest.fail('provider construction'))
    store = CaseStore(tmp_path / 'cases.sqlite')
    with TestClient(create_app(store=store, codes=Codes()), base_url='http://localhost') as client:
        yield client, store
    llm_gate.reset_for_tests()


def test_exact_reference_identification_is_local_and_has_no_hidden_top_ten(scene):
    client, store = scene
    case = store.put(Case(facts=[input_fact('project.description', '9.10.15.5.')]))
    response = client.post(f'/cases/{case.id}/identify', json={})
    assert response.status_code == 200, response.text
    result = response.json()
    assert any(item['provision'] == '9.10.15.5.' for item in result['articles'])
    assert result['articles'][0]['provision'] == '9.10.15.5.'
    assert result['input_sha256'] and not result['stale']
    assert sum(stage['requests'] for stage in result['trace']['stages']) == 0
    assert result['trace']['usd'] == 0
    assert store.get(case.id).provisions == []


def test_fact_update_invalidates_even_when_description_is_identical(scene):
    client, store = scene
    case = store.put(Case(facts=[input_fact('project.description', 'Exterior wall near a property line.'),
                               input_fact('storeys', 2)]))
    first = client.post(f'/cases/{case.id}/identify', json={}).json()
    store.add_fact(case.id, input_fact('storeys', 8))
    stored = client.get(f'/cases/{case.id}/identify').json()
    assert stored['stale']
    rerun = client.post(f'/cases/{case.id}/identify', json={}).json()
    assert rerun['input_sha256'] != first['input_sha256'] and not rerun['stale']


def test_readable_plans_alone_run_identification_during_intake(scene):
    client, store = scene
    case = store.put(Case())
    file = store.put_file(case.id, 'plans.txt', b'Exterior wall: see article 9.10.15.5.', 'text/plain')
    response = client.post(f'/cases/{case.id}/intake', json={'file_ids': [file['id']], 'model': False})
    assert response.status_code == 200, response.text
    result = client.get(f'/cases/{case.id}/identify').json()
    assert result['input_sha256'] and not result['stale']
    assert any(item['provision'] == '9.10.15.5.' for item in result['articles'])


def test_new_attachment_marks_previous_result_stale_without_a_fact_write(scene):
    client, store = scene
    case = store.put(Case(facts=[input_fact('project.description', '9.10.15.5.')]))
    first = client.post(f'/cases/{case.id}/identify', json={}).json()
    store.put_file(case.id, 'new-plan.txt', b'Building height: eight storeys.', 'text/plain')
    result = client.get(f'/cases/{case.id}/identify').json()
    assert result['stale'] and result['input_sha256'] == first['input_sha256']


def test_identify_accepts_long_prose_without_a_provider(scene):
    client, store = scene
    case = store.put(Case())
    response = client.post(f'/cases/{case.id}/identify', json={'prose': ('description ' * 2500) + '9.10.15.5.'})
    assert response.status_code == 200, response.text
    assert any(item['provision'] == '9.10.15.5.' for item in response.json()['articles'])


def test_supporting_application_scope_survives_no_departure_and_a_rerun(scene):
    client, store = scene
    case = store.put(Case(facts=[input_fact('project.description', '9.10.15.5.')]))
    first = client.post(f'/cases/{case.id}/identify', json={}).json()
    requirement = next(r for r in first['requirements'] if r['division'] == 'B' and r['provision_id'] == '9.10.15.5.')
    url = f'/cases/{case.id}/identify/requirements/{requirement["id"]}/decision'
    chosen = client.post(url, json={'disposition': 'include', 'role': 'supporting',
        'reason': 'Retain the exterior-wall requirement for the application analysis.',
        'expected_version': first['case_version']})
    assert chosen.status_code == 200, chosen.text
    no = client.post(f'/cases/{case.id}/identify/9.10.15.5./decision',
                     json={'decision': 'no', 'expected_version': chosen.json()['case_version']})
    assert no.status_code == 200, no.text
    rerun = client.post(f'/cases/{case.id}/identify', json={}).json()
    kept = next(r for r in rerun['requirements'] if r['id'] == requirement['id'])
    assert kept['role'] == 'supporting' and kept['disposition'] == 'include'
    assert kept['confirmation_reason'] == 'Retain the exterior-wall requirement for the application analysis.'
    assert store.get(case.id).provisions == []


def test_stale_applicability_decision_rejected_then_confirmation_retained_for_review(scene):
    client, store = scene
    case = store.put(Case(facts=[input_fact('project.description', '9.10.15.5.'), input_fact('storeys', 2)]))
    first = client.post(f'/cases/{case.id}/identify', json={}).json()
    requirement = next(r for r in first['requirements'] if r['division'] == 'B' and r['provision_id'] == '9.10.15.5.')
    url = f'/cases/{case.id}/identify/requirements/{requirement["id"]}/decision'
    body = {'disposition': 'include', 'role': 'supporting', 'reason': 'Exterior wall for the described project.',
            'expected_version': first['case_version']}
    chosen = client.post(url, json=body)
    assert chosen.status_code == 200, chosen.text
    changed = store.add_fact(case.id, input_fact('storeys', 8))
    body['expected_version'] = changed.version
    assert client.post(url, json=body).status_code == 409
    rerun = client.post(f'/cases/{case.id}/identify', json={}).json()
    kept = next(r for r in rerun['requirements'] if r['id'] == requirement['id'])
    assert kept['human_confirmed'] and kept['needs_review'] and kept['disposition'] == 'review'
    assert kept['confirmation_reason'] == 'Exterior wall for the described project.'


def test_legacy_confirmation_cannot_bypass_second_printing_provenance(tmp_path):
    import shutil
    import sqlite3
    db = tmp_path / 'wrong-edition.sqlite'
    shutil.copyfile(Codes().db_path, db)
    with sqlite3.connect(db) as con:
        con.execute("UPDATE docs SET label='NBC(AE) 2023 p1' WHERE doc='NBC-AE'")
    store = CaseStore(tmp_path / 'cases.sqlite')
    case = store.put(Case())
    with TestClient(create_app(store=store, codes=Codes(db)), base_url='http://localhost') as client:
        response = client.post(f'/cases/{case.id}/identify/confirm', json={'provisions': ['9.10.15.5.']})
    assert response.status_code == 503
    assert store.get(case.id).provisions == [] and store.get(case.id).section_c == []


def test_stored_identification_becomes_stale_when_the_code_source_changes(tmp_path):
    import shutil
    import sqlite3
    db = tmp_path / 'source.sqlite'
    shutil.copyfile(Codes().db_path, db)
    store = CaseStore(tmp_path / 'cases.sqlite')
    case = store.put(Case(facts=[input_fact('project.description', '9.10.15.5.')]))
    with TestClient(create_app(store=store, codes=Codes(db)), base_url='http://localhost') as client:
        first = client.post(f'/cases/{case.id}/identify', json={})
        assert first.status_code == 200 and not first.json()['stale']
        with sqlite3.connect(db) as con:
            con.execute("UPDATE docs SET label='NBC(AE) 2023 p1' WHERE doc='NBC-AE'")
        current = client.get(f'/cases/{case.id}/identify')
        assert current.status_code == 200 and current.json()['stale']
