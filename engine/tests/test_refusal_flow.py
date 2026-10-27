"""Terminal administrative refusal through real authenticated routes and SQLite."""
from io import BytesIO

import pytest
from pypdf import PdfReader

from engine.store import VersionConflict
from engine.tests.case_builder_fixtures import fact
from engine.tests.test_review import owned, scene  # noqa: F401 - isolated account fixture


REASON = 'SYNTHETIC refusal: the requested administrative record was not provided.'


def in_review(scene, *, complete=True):
    store, clients, _ = scene
    case = owned(scene, 'submitted', complete=complete)
    assert clients['reviewer'].post(f'/review/{case.id}/claim', json={}).status_code == 200
    return store.get(case.id)


def refuse(client, case, **changes):
    return client.post(f'/review/{case.id}/decision', json={
        'outcome': 'refuse', 'message': REASON, 'expected_version': case.version, **changes})


def test_refusal_is_terminal_and_preserves_history_notices_and_pdf(scene):
    store, clients, users = scene
    owner, officer = clients['owner'], clients['reviewer']
    case = owned(scene, complete=True)
    assert owner.post(f'/cases/{case.id}/submit', json={'expected_version': case.version}).status_code == 200
    assert officer.post(f'/review/{case.id}/claim', json={}).status_code == 200
    returned = officer.post(f'/review/{case.id}/decision', json={
        'outcome': 'return', 'message': 'SYNTHETIC request to clarify the attachment revision.'})
    assert returned.status_code == 200
    prior = returned.json()['decision']
    corrected = owner.post(f'/cases/{case.id}/facts', json=fact('request_answer.revision',
        'SYNTHETIC corrected attachment revision.').model_dump())
    assert corrected.status_code == 200
    assert owner.post(f'/cases/{case.id}/submit', json={'expected_version': corrected.json()['version']}).status_code == 200
    assert officer.post(f'/review/{case.id}/claim', json={}).status_code == 200
    case = store.get(case.id)
    before = case.model_dump()
    files = store.list_files(case.id)
    response = refuse(officer, case)
    assert response.status_code == 200, response.text
    final = response.json()
    assert final['status'] == 'refused'
    assert final['version'] == before['version'] + 1
    assert final['decision']['outcome'] == 'refuse'
    assert final['decision']['by_id'] == users['reviewer']['id']
    assert REASON in final['decision']['message']
    assert final['decision_history'] == [prior, final['decision']]
    assert final['status_history'][-1]['from_status'] == 'in_review'
    assert final['status_history'][-1]['to_status'] == 'refused'
    assert final['submission_number'] == 2
    for field in ('facts', 'evidence', 'submissions', 'return_snapshot', 'claim'):
        assert final[field] == before[field]
    assert store.list_files(case.id) == files
    persisted = store.get(case.id)
    reopened = owner.get(f'/cases/{case.id}').json()
    for field in ('status', 'version', 'decision', 'decision_history', 'status_history', 'facts', 'evidence', 'submissions'):
        assert persisted.model_dump()[field] == final[field] == reopened[field]
    summary = next(a for a in owner.get('/me/applications').json()['applications'] if a['id'] == case.id)
    assert summary['status'] == 'refused' and summary['reviewer']['name'] == 'Reviewer'
    queue = officer.get('/review/queue?status=refused').json()
    assert queue['reviewer_id'] == users['reviewer']['id'] and queue['authority'] == 'edmonton'
    row = next(a for a in queue['applications'] if a['id'] == case.id)
    assert row['decision']['outcome'] == 'refuse' and row['submission_number'] == 2
    assert not any(a['id'] == case.id for a in officer.get('/review/queue?status=returned').json()['applications'])
    notice = next(n for n in owner.get('/me/notifications').json()['notifications']
                  if n['case_id'] == case.id and n['status'] == 'refused')
    assert 'refusal' in notice['summary'] and 'accepted' not in notice['summary']
    assert 'safe' not in notice['summary'] and not notice['read']
    assert officer.post(f'/cases/{case.id}/messages', json={'body': 'SYNTHETIC notice after refusal.'}).status_code == 201
    thread = owner.get(f'/cases/{case.id}/messages').json()
    assert thread['decision'] == final['decision']
    assert thread['messages'][-1]['body'] == 'SYNTHETIC notice after refusal.'
    assert owner.post(f'/cases/{case.id}/messages', json={'body': 'SYNTHETIC prohibited applicant reply.'}).status_code == 403
    for draft in (True, False):
        pdf = owner.post(f'/cases/{case.id}/export', json={'draft': draft})
        assert pdf.status_code == 200 and pdf.headers['content-type'] == 'application/pdf', pdf.text[:100]
        text = '\n'.join(page.extract_text() for page in PdfReader(BytesIO(pdf.content)).pages)
        assert case.title in text  # The final saved application, never a generated refusal rationale.
        assert REASON not in text  # The text review record preserves the decision separately.
    stable = store.get(case.id).model_dump()
    for outcome in ('refuse', 'return', 'accept'):
        assert refuse(officer, store.get(case.id), outcome=outcome).status_code == 409
    assert officer.delete(f'/review/{case.id}/claim').status_code == 409
    assert officer.post(f'/review/{case.id}/claim', json={'take_over': True}).status_code == 409
    assert owner.post(f'/cases/{case.id}/submit', json={'expected_version': stable['version']}).status_code == 409
    assert owner.post(f'/cases/{case.id}/facts', json={
        'field': 'owner_name', 'value': 'SYNTHETIC changed owner', 'kind': 'pointed', 'status': 'confirmed',
        'source': {'type': 'user_text', 'ref': 'test', 'quote': 'SYNTHETIC changed owner'}}).status_code == 409
    assert store.get(case.id).model_dump() == stable


@pytest.mark.parametrize('message', [None, '', '         ', 'Too short'])
def test_refusal_requires_a_meaningful_reason_without_mutation(scene, message):
    store, clients, _ = scene
    case = in_review(scene)
    before = case.model_dump()
    response = refuse(clients['reviewer'], case, message=message)
    assert response.status_code == 422
    assert store.get(case.id).model_dump() == before


def test_refusal_is_not_a_correction_checklist(scene):
    store, clients, _ = scene
    case = in_review(scene)
    before = case.model_dump()
    assert refuse(clients['reviewer'], case, items=[{'field': 'owner_name', 'note': 'SYNTHETIC correction'}]).status_code == 422
    assert store.get(case.id).model_dump() == before


@pytest.mark.parametrize('version', [None, 0, True, '1'])
def test_new_refusal_requires_an_explicit_valid_version(scene, version):
    store, clients, _ = scene
    case = in_review(scene)
    before = case.model_dump()
    assert refuse(clients['reviewer'], case, expected_version=version).status_code == 422
    assert store.get(case.id).model_dump() == before


def test_refusal_without_a_displayed_version_is_rejected_without_mutation(scene):
    store, clients, _ = scene
    case = in_review(scene)
    before = case.model_dump()
    response = clients['reviewer'].post(f'/review/{case.id}/decision', json={
        'outcome': 'refuse', 'message': REASON})
    assert response.status_code == 422
    assert store.get(case.id).model_dump() == before


@pytest.mark.parametrize('actor,status', [('owner', 404), ('other', 404), ('foreign', 404), ('anonymous', 404), ('second', 409)])
def test_only_claiming_officer_of_authority_can_refuse(scene, actor, status):
    store, clients, _ = scene
    case = in_review(scene)
    before = case.model_dump()
    assert refuse(clients[actor], case).status_code == status
    assert store.get(case.id).model_dump() == before


def test_refusal_with_gaps_is_distinct_from_acceptance_and_return(scene):
    store, clients, _ = scene
    case = in_review(scene, complete=False)
    assert clients['owner'].get(f'/cases/{case.id}/gaps').json()['items']
    assert clients['reviewer'].post(f'/review/{case.id}/decision', json={'outcome': 'accept', 'expected_version': store.get(case.id).version}).status_code == 409
    response = refuse(clients['reviewer'], case)
    assert response.status_code == 200, response.text
    assert response.json()['status'] == 'refused'
    assert clients['owner'].post(f'/cases/{case.id}/export', json={'draft': False}).status_code == 409
    assert clients['owner'].post(f'/cases/{case.id}/export', json={'draft': True}).status_code == 200


def test_stale_refusal_never_decides_an_unseen_application_revision(scene):
    store, clients, _ = scene
    case = in_review(scene)
    newer = case.model_copy(deep=True)
    newer.title = 'SYNTHETIC concurrently updated application'
    store.put(newer, expected_version=case.version)
    before = store.get(case.id).model_dump()
    assert refuse(clients['reviewer'], case).status_code == 409
    assert store.get(case.id).model_dump() == before


def test_refusal_cas_retry_rechecks_version_and_claim(scene, monkeypatch):
    store, clients, users = scene
    case = in_review(scene)
    original_put = store.put
    changed = False

    def competing_claim(record, expected_version=None):
        nonlocal changed
        if record.id == case.id and not changed:
            changed = True
            concurrent = store.get(case.id)
            concurrent.claim.reviewer_id = users['second']['id']
            concurrent.claim.reviewer_name = 'Second'
            saved = original_put(concurrent, expected_version=concurrent.version)
            raise VersionConflict(case.id, expected_version, saved.version)
        return original_put(record, expected_version=expected_version)

    monkeypatch.setattr(store, 'put', competing_claim)
    assert refuse(clients['reviewer'], case).status_code == 409
    saved = store.get(case.id)
    assert changed and saved.claim.reviewer_id == users['second']['id']
    assert saved.status == 'in_review' and saved.decision is None
    assert not any(message.kind == 'decision' for message in saved.messages)


def test_refusal_retry_never_adopts_a_new_version_with_the_same_claim(scene, monkeypatch):
    store, clients, _ = scene
    case = in_review(scene)
    original_put = store.put
    raced = False

    def concurrent_revision(record, *, expected_version=None):
        nonlocal raced
        if record.id == case.id and not raced:
            raced = True
            newer = store.get(case.id)
            newer.title = 'SYNTHETIC revision not displayed to the officer'
            original_put(newer, expected_version=newer.version)
        return original_put(record, expected_version=expected_version)

    monkeypatch.setattr(store, 'put', concurrent_revision)
    response = refuse(clients['reviewer'], case)
    assert raced and response.status_code == 409
    saved = store.get(case.id)
    assert saved.version == case.version + 1 and saved.claim == case.claim
    assert saved.title == 'SYNTHETIC revision not displayed to the officer'
    assert saved.status == 'in_review' and saved.decision is None
    assert saved.status_history == case.status_history and saved.messages == case.messages
