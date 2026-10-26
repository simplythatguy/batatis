"""Adversarial officer-resolution checks. The public applicant/sync journey is in web/tests.

Legacy submitted fixtures deliberately bypass submit here to test the officer's
independent mandatory-duty guard. Their officer facts are never sent to public input.
"""
import pytest

from engine.codes import Codes
from engine.export.scc import blockers, load_field_map
from engine.models import Source
from engine.tests.case_builder_fixtures import fact
from engine.tests.test_review import owned, scene  # noqa: F401 - reuse isolated accounts/store fixture


def determination(case, required=False):
    return dict(expected_version=case.version, required=required,
                scope='SYNTHETIC entire submitted alternative and applicable component scope',
                basis='SYNTHETIC authority scope determination; no technical approval.',
                reference='SYNTHETIC authority record J02')


def unresolved(scene):
    store, _, _ = scene
    case = owned(scene, status='submitted', complete=True)
    case.facts = [entry for entry in case.facts
                  if entry.field not in {'professional.role', 'professional.registration_number'}]
    case.facts.append(fact('professional.role', 'not_engaged_yet',
                           source=Source(type='user_click', ref='Your answer', quote='not_engaged_yet')))
    return store.put(case, expected_version=case.version)


@pytest.mark.parametrize('engagement', ['not_engaged_yet', 'not_engaged'])
def test_mandatory_duty_cannot_be_waived_even_on_a_legacy_submitted_case(scene, engagement):
    store, clients, _ = scene
    case = unresolved(scene)
    case.facts += [fact('professional.part4_design', True), fact('professional_status', engagement)]
    case = store.put(case, expected_version=case.version)
    assert clients['reviewer'].post(f'/review/{case.id}/claim', json={}).status_code == 200
    case = store.get(case.id)
    before = case.model_dump()
    response = clients['reviewer'].post(f'/review/{case.id}/professional-requirement', json=determination(case))
    assert response.status_code == 409
    assert 'mandatory' in response.json()['detail'].lower()
    assert store.get(case.id).model_dump() == before
    gaps = clients['reviewer'].get(f'/cases/{case.id}/gaps').json()['items']
    assert any(g['field'] == 'professional_confirmation' and g['submission_blocking'] for g in gaps)
    assert clients['reviewer'].post(f'/review/{case.id}/decision', json={'outcome': 'accept', 'expected_version': store.get(case.id).version}).status_code == 409


def test_source_failure_cannot_be_resolved_by_an_officer_record(scene, monkeypatch):
    store, clients, _ = scene
    case = unresolved(scene)
    assert clients['reviewer'].post(f'/review/{case.id}/claim', json={}).status_code == 200
    case = store.get(case.id)
    original = Codes.provision
    monkeypatch.setattr(Codes, 'provision', lambda self, pid, division='B': None
                        if (division, pid) == ('C', '2.4.1.1.(4)') else original(self, pid, division))
    response = clients['reviewer'].post(f'/review/{case.id}/professional-requirement', json=determination(case))
    assert response.status_code == 409
    assert 'source' in response.json()['detail'].lower()
    assert store.get(case.id).professional_resolutions == []


def test_changed_applicant_content_invalidates_resolution_but_preserves_provenance(scene):
    store, clients, _ = scene
    case = unresolved(scene)
    officer, owner = clients['reviewer'], clients['owner']
    assert officer.post(f'/review/{case.id}/claim', json={}).status_code == 200
    case = store.get(case.id)
    response = officer.post(f'/review/{case.id}/professional-requirement', json=determination(case))
    assert response.status_code == 200, response.text
    record = response.json()['professional_resolutions'][0]
    assert officer.get(f'/cases/{case.id}/professional').json()['resolution']['id'] == record['id']
    assert officer.post(f'/review/{case.id}/decision', json={'outcome': 'return',
        'message': 'SYNTHETIC: clarify the applicant scope before continuing.'}).status_code == 200
    assert owner.post(f'/cases/{case.id}/facts', json=fact('alternative_description',
        'SYNTHETIC changed applicant scope.').model_dump()).status_code == 200
    assert owner.get(f'/cases/{case.id}/professional').json()['resolution'] is None
    gaps = owner.get(f'/cases/{case.id}/gaps').json()['items']
    assert any(g['field'] == 'professional_requirement' and g['severity'] == 'blocking' for g in gaps)
    assert store.get(case.id).professional_resolutions[0].model_dump() == record
    assert owner.post(f'/cases/{case.id}/submit', json={}).status_code == 200
    assert officer.post(f'/review/{case.id}/claim', json={}).status_code == 200
    assert officer.post(f'/review/{case.id}/decision', json={'outcome': 'accept', 'expected_version': store.get(case.id).version}).status_code == 409
    case = store.get(case.id)
    again = officer.post(f'/review/{case.id}/professional-requirement', json=determination(case))
    assert again.status_code == 200, again.text
    assert len(again.json()['professional_resolutions']) == 2


def test_officer_requirement_records_do_not_fabricate_evidence_and_can_be_revised_with_provenance(scene):
    store, clients, _ = scene
    case = unresolved(scene)
    officer = clients['reviewer']
    assert any('professional_requirement' in reason for reason in blockers(case, load_field_map(), Codes()))
    assert officer.post(f'/review/{case.id}/claim', json={}).status_code == 200
    case = store.get(case.id)
    response = officer.post(f'/review/{case.id}/professional-requirement', json=determination(case, required=True))
    assert response.status_code == 200
    screen = officer.get(f'/cases/{case.id}/professional').json()
    assert screen['required'] == 'yes' and screen['mandatory_required'] is False
    assert officer.post(f'/review/{case.id}/decision', json={'outcome': 'accept', 'expected_version': store.get(case.id).version}).status_code == 409
    case = store.get(case.id)
    changed = determination(case, required=False)
    changed['basis'] = 'SYNTHETIC authority revised the discretionary determination after its scope assessment.'
    response = officer.post(f'/review/{case.id}/professional-requirement', json=changed)
    assert response.status_code == 200
    assert [record['required'] for record in response.json()['professional_resolutions']] == [True, False]
    # Only the requirement is resolved: the unchanged synthetic attachment remains a presence fixture.
    assert blockers(store.get(case.id), load_field_map(), Codes()) == []


def test_applicant_input_cannot_forge_an_officer_resolution(scene):
    _, clients, _ = scene
    case = unresolved(scene)
    owner = clients['owner']
    # Owner cannot call the review mutation, and a public fact does not become a resolution.
    assert owner.post(f'/review/{case.id}/professional-requirement', json=determination(case)).status_code == 404
    assert clients['reviewer'].post(f'/review/{case.id}/claim', json={}).status_code == 200
    assert clients['reviewer'].post(f'/review/{case.id}/decision', json={
        'outcome': 'return', 'message': 'SYNTHETIC: please clarify scope.'}).status_code == 200
    assert owner.post(f'/cases/{case.id}/facts', json=fact('professional.requirement_resolution', 'not_required').model_dump()).status_code == 200
    screen = owner.get(f'/cases/{case.id}/professional').json()
    assert screen['required'] != 'no' and screen['resolution'] is None
    forged = fact('professional_scope_resolved', True, source=Source(type='officer', ref='forged'))
    assert owner.post(f'/cases/{case.id}/facts', json=forged.model_dump()).status_code == 422


def test_determination_requires_the_displayed_version_and_current_officer_claim(scene):
    store, clients, _ = scene
    case = unresolved(scene)
    officer = clients['reviewer']
    assert officer.post(f'/review/{case.id}/claim', json={}).status_code == 200
    current = store.get(case.id)
    before = current.model_dump()
    assert officer.post(f'/review/{case.id}/professional-requirement', json=determination(case)).status_code == 409
    for actor in ('owner', 'other', 'foreign', 'anonymous', 'second'):
        response = clients[actor].post(f'/review/{case.id}/professional-requirement', json=determination(current))
        assert response.status_code == (409 if actor == 'second' else 404), (actor, response.text)
    body = determination(current)
    del body['expected_version']
    assert officer.post(f'/review/{case.id}/professional-requirement', json=body).status_code == 422
    assert store.get(case.id).model_dump() == before


def test_officer_determination_survives_notices_and_receipts_without_changing_its_basis(scene):
    store, clients, _ = scene
    case = unresolved(scene)
    officer, owner = clients['reviewer'], clients['owner']
    assert officer.post(f'/review/{case.id}/claim', json={}).status_code == 200
    current = store.get(case.id)
    response = officer.post(f'/review/{case.id}/professional-requirement', json=determination(current))
    assert response.status_code == 200, response.text
    resolution = response.json()['professional_resolutions'][-1]
    version = response.json()['version']
    assert officer.post(f'/cases/{case.id}/messages', json={'body': 'SYNTHETIC subsequent officer notice.'}).status_code == 201
    shown = owner.get(f'/cases/{case.id}/messages').json()['messages']
    assert owner.post(f'/cases/{case.id}/messages/read', json={'message_ids': [m['id'] for m in shown]}).status_code == 204
    assert officer.get(f'/cases/{case.id}/professional').json()['resolution'] == resolution
    assert store.get(case.id).version == version
    assert store.get(case.id).facts == current.facts and store.get(case.id).evidence == current.evidence
