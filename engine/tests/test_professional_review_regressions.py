"""Synthetic administrative regressions, not evidence of licences or code applicability.

The small corpus isolates shared decisions. Source-backed execution is verified separately;
the imported package fixture explicitly stubs citation validation, not professional decisions.
"""
import pytest
from fastapi.testclient import TestClient

from engine.api import create_app
from engine.codes import Codes
from engine.export.scc import blockers, load_field_map
from engine.models import Case, Source
from engine.professional import ProfessionalFacts, professional_confirmed, professional_involvement
from engine.section_d_issues import render_practice
from engine.store import CaseStore
from engine.tests.case_builder_fixtures import fact
from engine.tests.test_professional_export_gate import package  # noqa: F401 - shared pytest fixture


def _items(response):
    assert response.status_code == 200, response.text
    return response.json()['items']


def _without(case, *fields):
    case.facts = [item for item in case.facts if item.field not in fields]


def _cleared(case):
    values = dict(
        occupancy='single_family', storeys=2, building_area_m2=210.0, part4_design=False,
        preserved_wood_foundation_part4=False, roof_trusses=False, prescriptive_route_confirmed=True,
        ahj_requires_professional=False, special_safety_concerns=False,
        professional_judgement_required=False, professional_scope_resolved=True,
        fire_suppression=False, fire_alarm=False, pathway='acceptable',
    )
    _without(case, *values, 'professional_name', 'professional_seal', 'professional.role')
    authority = Source(type='officer', ref='SYNTHETIC internal record')
    case.facts.extend(fact(key, value, source=authority) for key, value in values.items())
    return case


@pytest.mark.parametrize('field,value', [
    ('span_m', 18.0), ('supported_joist_span_m', 5.2),
    ('hourly_wind_pressure_1in50_kPa', 1.25), ('reinforced_concrete', True),
])
def test_mandatory_requirement_is_shared_by_professional_issues_gaps_and_export(package, tmp_path, field, value):
    case, codes = package
    _cleared(case)
    assert professional_involvement(case, codes).required == 'no'
    assert blockers(case, load_field_map(), codes) == []
    case.facts.append(fact(field, value))
    store = CaseStore(tmp_path / 'cases.sqlite')
    store.put(case)
    client = TestClient(create_app(store, codes))
    professional = client.get(f'/cases/{case.id}/professional').json()
    issues = _items(client.get(f'/cases/{case.id}/section-d/issues'))
    gaps = _items(client.get(f'/cases/{case.id}/gaps'))
    exported = client.post(f'/cases/{case.id}/export', json={'draft': False})
    assert professional['required'] == 'yes'
    assert any(row['practice_of_engineering']['value'] is True and row['status'] == 'needs_professional'
               for row in issues)
    assert any(row['id'] == 'D12:professional_confirmation' for row in gaps)
    assert exported.status_code == 409


@pytest.mark.parametrize('role', [
    'student engineer', 'engineer in training', 'Engineer-in-Training', 'intern architect',
    'engineer technologist', 'engineer technician', 'engineer EIT', 'trainee architect',
    'engineer E.I.T.', 'sales engineer',
])
def test_trainee_or_commercial_role_does_not_close_professional_confirmation(package, role):
    case, codes = package
    case.facts.append(fact('professional.role', role))
    assert professional_confirmed(case) is False
    assert any('professional_confirmation' in reason for reason in blockers(case, load_field_map(), codes))


@pytest.mark.parametrize('role', ['structural engineer', 'P.Eng.', 'Architect, AAA'])
def test_supported_role_wording_still_confirms_identity(package, role):
    case, codes = package
    case.facts.append(fact('professional.role', role))
    assert professional_confirmed(case) is True
    assert blockers(case, load_field_map(), codes) == []


@pytest.mark.parametrize('number,expected', [(12345, True), ('12345', True), (True, False)])
def test_registration_normalizes_integer_ids_but_not_booleans(package, number, expected):
    case, _ = package
    _without(case, 'professional_seal')
    case.facts += [fact('professional.role', 'engineer'), fact('professional.registration_number', number)]
    assert professional_confirmed(case) is expected


def test_later_discipline_and_name_do_not_withdraw_the_role_but_role_withdrawal_does(package):
    case, codes = package
    case.facts += [fact('professional.role', 'engineer'), fact('professional.discipline', 'structural'),
                   fact('professional.name', 'SYNTHETIC person')]
    assert professional_confirmed(case) is True
    assert blockers(case, load_field_map(), codes) == []
    case.facts.append(fact('professional.role', '', status='unconfirmed'))
    assert professional_confirmed(case) is False
    assert any('professional_confirmation' in reason for reason in blockers(case, load_field_map(), codes))


@pytest.mark.parametrize('seal_source,quote', [
    ('file', 'Unsigned vendor sales email'),
    ('user_text', 'Copied from an unsigned note; the work has not been authenticated'),
])
def test_unsigned_seal_metadata_does_not_authenticate_work(package, seal_source, quote):
    case, codes = package
    _without(case, 'professional_seal')
    case.facts += [fact('professional.role', 'engineer'), fact('professional.registration_number', 'TEST-123'),
                   fact('professional_seal', 'stamp copied from unsigned note',
                        source=Source(type=seal_source, ref='SYNTHETIC note', quote=quote))]
    # Registration identifies the stated professional; it does not authenticate the work.
    assert professional_confirmed(case) is True
    assert any('professional_authentication' in reason for reason in blockers(case, load_field_map(), codes))


def test_registered_seal_alias_has_the_same_authentication_behavior(package):
    case, codes = package
    _without(case, 'professional_seal')
    case.facts += [fact('professional.role', 'engineer'),
                   fact('registered_professional.seal', 'SYNTHETIC applicant-confirmed authentication metadata')]
    assert professional_confirmed(case) is True
    assert blockers(case, load_field_map(), codes) == []


def _attachment(reference, **changes):
    return fact('evidence.synthetic.file_ref', reference,
                source=Source(type='file', ref=reference, quote='SYNTHETIC uploaded document'), **changes)


def test_public_attachment_presence_requires_a_file_owned_by_the_current_case(tmp_path):
    store = CaseStore(tmp_path / 'cases.sqlite')
    client = TestClient(create_app(store, Codes()))
    case = client.post('/cases', json={'title': 'SYNTHETIC upload binding'}).json()
    other = client.post('/cases', json={'title': 'SYNTHETIC different owner'}).json()
    path = f"/cases/{case['id']}/facts"
    forged = _attachment('SYNTHETIC-not-uploaded.pdf')
    assert client.post(path, json=forged.model_dump()).status_code == 422
    assert store.get(case['id']).facts == []
    uploaded = client.post(f"/cases/{case['id']}/files", content=b'%PDF-1.4\nSYNTHETIC storage bytes',
                           headers={'Content-Type': 'application/pdf', 'x-filename': 'test.pdf'})
    assert uploaded.status_code == 201
    reference = uploaded.json()['id']
    attached = _attachment(reference)
    assert client.post(path, json=attached.model_dump()).status_code == 200
    assert client.post(f"/cases/{other['id']}/facts", json=attached.model_dump()).status_code == 422
    mismatch = attached.model_copy(update={'value': 'SYNTHETIC mismatched file'})
    assert client.post(path, json=mismatch.model_dump()).status_code == 422
    # Extraction provenance is a distinct contract, and withdrawal must remain possible.
    extraction = fact('storeys', 2, source=Source(type='drawing', ref=reference))
    assert client.post(path, json=extraction.model_dump()).status_code == 200
    withdrawn = _attachment('', status='unconfirmed')
    assert client.post(path, json=withdrawn.model_dump()).status_code == 200
    assert client.delete(f"/cases/{case['id']}").status_code == 204
    assert client.post(path, json=attached.model_dump()).status_code == 404
    assert store.get(case['id']) is None


def test_legacy_stored_file_claim_without_bytes_is_unconfirmed_and_cannot_export(package, tmp_path):
    case, codes = package
    case.facts += [fact('professional.role', 'engineer'), _attachment('SYNTHETIC-legacy-missing.pdf')]
    store = CaseStore(tmp_path / 'cases.sqlite')
    store.put(case)  # Models an old internal record predating the public input repair.
    client = TestClient(create_app(store, codes))
    saved = client.get(f'/cases/{case.id}').json()
    legacy = next(row for row in saved['facts'] if row['field'] == 'evidence.synthetic.file_ref')
    assert legacy['value'] == 'SYNTHETIC-legacy-missing.pdf'  # Preserve the applicant's listing.
    assert legacy['status'] == 'unconfirmed'
    assert client.post(f'/cases/{case.id}/export', json={'draft': False}).status_code == 409


def test_missing_citation_keeps_the_known_rule_identity(package):
    case, codes = package
    result = professional_involvement(case, codes)
    result.reasons = [row.model_copy(update={'citation': ''}) if row.code == 'part4' else row
                      for row in result.reasons]
    flag = render_practice(result, codes)
    assert flag.value == 'unknown' and flag.citation is None
    assert flag.rule == '2.4.1.2.(1)' and flag.division == 'C'
    assert '2.4.1.2.(1)' in flag.question


def test_unsettled_suite_count_routes_to_officer_without_an_authentication_count_rule(package):
    _, codes = package
    result = professional_involvement(ProfessionalFacts(
        occupancy='multi_family', principal_dwelling_units=4, total_unit_count=5,
        storeys=2, building_area_m2=200.0, part4_design=False,
        preserved_wood_foundation_part4=False, roof_trusses=False,
        prescriptive_route_confirmed=True, ahj_requires_professional=False,
        special_safety_concerns=False, professional_judgement_required=False,
        professional_scope_resolved=True, fire_suppression=False, fire_alarm=False,
    ), codes)
    assert result.general_required == 'no'
    assert result.required == 'depends' and result.routed_to == 'officer'
    assert not any(row.code == 'acts_units' and row.required == 'yes' for row in result.reasons)
    assert any('suite' in question.lower() for question in result.questions)


def test_gross_area_question_reports_the_specific_missing_fact(package):
    case, codes = package
    _cleared(case)
    case.facts.append(fact('gross_area_unsettled', True))
    result = professional_involvement(case, codes)
    assert 'gross_area_per_floor_m2' in result.missing_facts
