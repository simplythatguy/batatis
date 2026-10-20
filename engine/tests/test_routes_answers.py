"""Applicant routes for evidence, building facts and description facts."""
import json
import re

import pytest
from fastapi.testclient import TestClient

from engine.api import create_app
from engine.models import Case, Jurisdiction, SectionCRow, Source
from engine.professional import ProfessionalResult
from engine.section_d import EvidencePlanItem, SectionDPlan
from engine.store import CaseStore
from engine.tests.case_builder_fixtures import fact


class FakeCodes:
    db_path = 'synthetic'

    def provision(self, pid, division='B'):
        return {'id': pid, 'division': division, 'citation': f'synthetic Div {division} {pid}',
                'level': 'sentence', 'attributions': [], 'intents': [], 'intent_comparison': [],
                'attribution_status': None, 'children': [], 'text': 'synthetic', 'pdf_page': 1,
                'pdf_page_end': 1, 'article_title': 'synthetic'}

    def citation(self, pid, division='B'):
        return self.provision(pid, division)['citation']


def plan_item(function, objective, provision='9.99.1.1.(1)'):
    return EvidencePlanItem(
        id=f'{provision}-{function}-{objective}', provision_id=provision, citation='synthetic citation',
        attribution_status='direct', objective=objective, function=function, performance_issue='synthetic issue',
        recommended_types=("manufacturer's literature", 'CCMC evaluation'))


@pytest.fixture
def client(tmp_path, monkeypatch):
    items = [plan_item(f'P{index}', f'Q{index}') for index in range(19)]

    def fake_plan(case, codes, documents=None):
        return SectionDPlan(items=list(items), notices=[])

    def fake_section_c(provision_ids, codes):
        # A non-empty Section C result is what lets completeness emit evidence gaps.
        return [SectionCRow(provision_id=pid, citation=f'synthetic Div B {pid}',
                            attribution_status='no row in the attribution table', pairs=[], intents=[])
                for pid in provision_ids]

    monkeypatch.setattr('engine.routes_answers.section_d_plan', fake_plan)
    monkeypatch.setattr('engine.completeness.section_d_plan', fake_plan)
    monkeypatch.setattr('engine.completeness.section_c_rows', fake_section_c)
    monkeypatch.setattr('engine.completeness.process_fields', lambda case, codes: [])
    monkeypatch.setattr(
        'engine.completeness.professional_involvement',
        lambda case, codes: ProfessionalResult(required='no', general_required='no', reasons=[], questions=[]))
    store = CaseStore(tmp_path / 'cases.sqlite')
    return TestClient(create_app(store, FakeCodes())), store


def _case(store):
    return store.put(Case(
        provisions=['9.99.1.1.(1)'],
        jurisdiction=Jurisdiction(id='alberta-other', name='Synthetic AHJ'),
        facts=[fact(name, 'synthetic') for name in (
            'owner_name', 'application_date', 'civic_address', 'legal_description',
            'representative', 'mailing_address', 'alternative_description', 'scope')]))


def _gap_rows(payload):
    if isinstance(payload, dict) and 'gaps' in payload:
        return payload['gaps']
    return payload


def _evidence_gaps(payload):
    return [gap for gap in _gap_rows(payload) if str(gap.get('id', '')).startswith('evidence')
            or str(gap.get('field', '')).startswith('evidence')]


_SIGN_OFF = re.compile(r'\b(?:addressed|satisfied|compliant)\b', re.I)


def _assert_not_a_sign_off(*payloads):
    text = json.dumps(payloads)
    assert _SIGN_OFF.search(text) is None, text


def test_evidence_post_groups_and_closes_then_delete_reopens(client):
    http, store = client
    case = _case(store)
    before = http.get(f'/cases/{case.id}/gaps')
    assert before.status_code == 200
    evidence = _evidence_gaps(before.json())
    assert len(evidence) == 1
    assert evidence[0]['provision_id'] == '9.99.1.1.(1)'
    assert len(evidence[0]['pairs']) == 19

    created = http.post(f'/cases/{case.id}/evidence', json={
        'provision_id': '9.99.1.1.(1)', 'evidence_type': "manufacturer's literature",
        'description': 'Applicant product sheet for the hempcrete mix'})
    assert created.status_code == 201
    body = created.json()
    assert body['gaps'] == []
    assert body['evidence']['status'] == 'evidence_listed'
    assert body['closed'][0]['reason'] == 'evidence listed (not reviewed)'
    assert len(body['closed'][0]['pairs']) == 19
    assert body['evidence']['professional_required'] is None
    assert body['evidence']['file_id'] is None
    after = http.get(f'/cases/{case.id}/gaps').json()
    assert _evidence_gaps(after) == []
    _assert_not_a_sign_off(evidence, body['gaps'], body['closed'], after)

    evidence_id = body['evidence']['id']
    assert http.delete(f'/cases/{case.id}/evidence/{evidence_id}').status_code == 204
    reopened = _evidence_gaps(http.get(f'/cases/{case.id}/gaps').json())
    assert len(reopened) == 1 and len(reopened[0]['pairs']) == 19
    assert http.delete(f'/cases/{case.id}/evidence/{evidence_id}').status_code == 404


def test_pair_evidence_closes_only_that_pair_and_rejects_unknown_pairs(client):
    http, store = client
    case = _case(store)
    rejected = http.post(f'/cases/{case.id}/evidence', json={
        'provision_id': '9.99.1.1.(1)', 'objective': 'Q1', 'function': 'P1',
        'evidence_type': 'CCMC evaluation', 'description': 'Applicant named a CCMC report they will attach',
        'file_id': 'file_applicant_1'})
    assert rejected.status_code == 400
    assert rejected.json()['detail'] == 'file_id does not match a stored file'
    case.facts.append(fact(
        'file', 'file_applicant_1',
        source=Source(type='file', ref='file_applicant_1', quote='Applicant file metadata.')))
    store.put(case)
    created = http.post(f'/cases/{case.id}/evidence', json={
        'provision_id': '9.99.1.1.(1)', 'objective': 'Q1', 'function': 'P1',
        'evidence_type': 'CCMC evaluation', 'description': 'Applicant named a CCMC report they will attach',
        'file_id': 'file_applicant_1'})
    assert created.status_code == 201
    assert created.json()['evidence']['file_id'] == 'file_applicant_1'
    assert created.json()['evidence']['status'] == 'evidence_listed'
    assert created.json()['closed'][0]['reason'] == 'evidence listed (not reviewed)'
    assert [(pair['function'], pair['objective']) for pair in created.json()['closed'][0]['pairs']] == [('P1', 'Q1')]
    _assert_not_a_sign_off(created.json()['gaps'], created.json()['closed'])
    left = created.json()['gaps']
    assert len(left) == 1 and len(left[0]['pairs']) == 18
    assert all(pair['function'] != 'P1' for pair in left[0]['pairs'])
    assert http.post(f'/cases/{case.id}/evidence', json={
        'provision_id': '9.99.1.1.(1)', 'objective': 'NOPE', 'function': 'P1',
        'evidence_type': 'evaluation', 'description': 'not on the table'}).status_code == 400
    assert http.post(f'/cases/{case.id}/evidence', json={
        'provision_id': '9.99.1.1.(1)', 'objective': 'Q1',
        'evidence_type': 'evaluation', 'description': 'half a pair'}).status_code == 422
    assert http.post(f'/cases/{case.id}/evidence', json={
        'provision_id': '9.99.1.1.(1)', 'evidence_type': 'not a ladder rung',
        'description': 'no'}).status_code == 422
    assert http.post(f'/cases/{case.id}/evidence', json={
        'provision_id': '9.88.1.1.(1)', 'evidence_type': 'evaluation',
        'description': 'wrong benchmark'}).status_code == 400
    assert http.post('/cases/missing/evidence', json={
        'provision_id': '9.99.1.1.(1)', 'evidence_type': 'evaluation',
        'description': 'no case'}).status_code == 404


def test_put_facts_is_partial_and_reevaluates_the_professional_screen(client):
    http, store = client
    case = store.put(Case())
    first = http.put(f'/cases/{case.id}/facts', json={'occupancy': 'single_family', 'storeys': 2})
    assert first.status_code == 200
    assert first.json()['updated'] == ['occupancy', 'storeys']
    assert first.json()['professional']['required'] == 'depends'
    assert http.put(f'/cases/{case.id}/facts', json={'span_m': 18}).json()['professional']['required'] == 'yes'
    stored = store.get(case.id)
    assert [item.field for item in stored.facts] == ['occupancy', 'storeys', 'span_m']
    assert all(item.status == 'confirmed' and item.kind == 'pointed' for item in stored.facts)
    assert not any(item.field == 'part4_design' for item in stored.facts)
    settled = http.put(f'/cases/{case.id}/facts', json={
        'part4_design': False, 'preserved_wood_foundation_part4': False, 'roof_trusses': False,
        'prescriptive_route_confirmed': True, 'ahj_requires_professional': False,
        'special_safety_concerns': False, 'professional_judgement_required': False,
        'professional_scope_resolved': True, 'fire_suppression': False, 'fire_alarm': False,
        'span_m': 4})
    assert settled.status_code == 200
    assert settled.json()['professional']['required'] == 'no'
    assert http.put(f'/cases/{case.id}/facts', json={}).status_code == 422
    assert http.put(f'/cases/{case.id}/facts', json={'occupancy': 'castle'}).status_code == 422
    assert http.put('/cases/missing/facts', json={'storeys': 1}).status_code == 404


def test_description_extracts_storeys_and_drops_the_question(client):
    http, store = client
    case = store.put(Case())
    text = 'Hempcrete garden suite, 2-storey, about 45 m2. What do I need?'
    response = http.post(f'/cases/{case.id}/description', json={'text': text})
    assert response.status_code == 200
    body = response.json()
    assert body['alternative_description'] == 'Hempcrete garden suite, 2-storey, about 45 m2.'
    facts = {item['field']: item for item in body['facts']}
    assert facts['storeys']['value'] == 2
    assert facts['storeys']['source'] == 'description'
    assert facts['storeys']['status'] == 'unconfirmed'
    assert facts['building_area_m2']['value'] == 45
    assert facts['occupancy']['value'] == 'single_family'
    assert facts['alternative_description']['source'] == 'description'
    stored = store.get(case.id)
    assert all(item.source.type == 'description' and item.status == 'unconfirmed' for item in stored.facts)
    assert http.post('/cases/missing/description', json={'text': '2-storey'}).status_code == 404
