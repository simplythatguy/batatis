"""Applicant edits -> resubmit -> officer queue/claim, without providers or durable fixtures."""
from datetime import datetime, timedelta, timezone

import threading

import pytest

from engine.tests.case_builder_fixtures import acceptance_request, fact
from engine.tests.test_review import scene, owned  # noqa: F401 -- shared authenticated API fixture


def sent_back(scene):
    _, clients, _ = scene
    case = owned(scene, complete=True)
    assert clients['owner'].post(f'/cases/{case.id}/submit', json={}).status_code == 200
    assert clients['reviewer'].post(f'/review/{case.id}/claim', json={}).status_code == 200
    response = clients['reviewer'].post(f'/review/{case.id}/decision', json={
        'outcome': 'return', 'message': 'Please clarify the synthetic legal description.',
        'items': [{'field': 'legal_description', 'note': 'Clarify the lot.'}],
    })
    assert response.status_code == 200, response.text
    return response.json()


def test_resubmit_keeps_identity_history_valid_reviewer_and_real_changes(scene):
    store, clients, users = scene
    returned = sent_back(scene)
    path = '/cases/' + returned['id']
    changed = clients['owner'].post(path + '/facts', json=fact('legal_description', 'Synthetic revised lot B').model_dump())
    assert changed.status_code == 200, changed.text
    changed = clients['owner'].post(path + '/facts', json=fact('evidence.synthetic.title', 'Synthetic revision B report').model_dump())
    assert changed.status_code == 200, changed.text
    response = clients['owner'].post(path + '/submit', json={'expected_version': changed.json()['version']})
    assert response.status_code == 200, response.text
    revised = response.json()
    assert revised['claim'] == returned['claim'], 'resubmission lost the current exclusive reviewer reservation'
    assert revised['status'] == 'submitted' and revised['decision'] is None
    assert revised['decision_history'] == [returned['decision']]
    assert revised['id'] == returned['id'] and revised['created_at'] == returned['created_at']
    assert [s['number'] for s in revised['submissions']] == [1, 2]
    submission = revised['submissions'][-1]
    assert submission['returned_at'] == returned['decision']['at'] and submission['comparison_available']
    changes = {change['field']: change for change in submission['changes']}
    assert changes['legal_description']['before'] == 'Synthetic lot 1 block 2 plan 3'
    assert changes['legal_description']['after'] == 'Synthetic revised lot B'
    assert changes['evidence.synthetic.title']['after'] == 'Synthetic revision B report'
    assert 'owner_name' not in changes
    # History/notes distinguish a re-submission and preserve the first event.
    assert [m['body'] for m in revised['messages'] if m['kind'] == 'status'] == [
        'Submitted for administrative review. Submission 1.',
        'Resubmitted for administrative review. Submission 2.',
    ]
    row = next(a for a in clients['reviewer'].get('/review/queue?mine=true').json()['applications'] if a['id'] == revised['id'])
    assert row['submission_number'] == 2 and row['claim']['reviewer_id'] == users['reviewer']['id']
    assert clients['second'].post(f"/review/{revised['id']}/claim", json={}).status_code == 409
    assert clients['reviewer'].post(f"/review/{revised['id']}/decision", json={'outcome': 'accept', 'expected_version': store.get(revised['id']).version}).status_code == 409
    assert clients['reviewer'].post(f"/review/{revised['id']}/claim", json={}).status_code == 200
    assert store.get(revised['id']).status == 'in_review'
    # A past return is history, so it must not prevent releasing this new round.
    assert clients['reviewer'].delete(f"/review/{revised['id']}/claim").status_code == 204
    assert clients['second'].post(f"/review/{revised['id']}/claim", json={}).status_code == 200
    accepted = clients['second'].post(f"/review/{revised['id']}/decision", json=acceptance_request(clients['second'], revised['id']))
    assert accepted.status_code == 200, accepted.text
    assert [d['outcome'] for d in accepted.json()['decision_history']] == ['return', 'accept']
    assert clients['owner'].post(path + '/submit', json={}).status_code == 409


def test_public_evidence_edits_appear_once_with_legacy_snapshot_representations(scene):
    store, clients, _ = scene
    case = owned(scene, complete=True)
    path = '/cases/' + case.id
    file_ref = next(f.value for f in case.facts if f.field == 'evidence.synthetic.file_ref')

    def edit(description):
        saved = clients['owner'].get(path).json()
        response = clients['owner'].post(path + '/evidence', json={
            'operation': 'update', 'evidence_id': 'synthetic', 'expected_version': saved['version'],
            'title': 'Synthetic evidence report', 'description': description,
            'evidence_type': 'evaluation', 'file_ref': file_ref,
        })
        assert response.status_code == 200, response.text

    edit('Synthetic original document description')
    assert clients['owner'].post(path + '/submit', json={}).status_code == 200
    assert clients['reviewer'].post(f'/review/{case.id}/claim', json={}).status_code == 200
    assert clients['reviewer'].post(f'/review/{case.id}/decision', json={
        'outcome': 'return', 'message': 'Clarify the synthetic document description.',
    }).status_code == 200
    # Old persisted snapshots contain both representations. Normalize only the comparison.
    returned = store.get(case.id)
    returned.return_snapshot.values['evidence.synthetic.listing.description'] = 'Synthetic original document description'
    store.put(returned)
    edit('Synthetic corrected document description')
    response = clients['owner'].post(path + '/submit', json={})
    assert response.status_code == 200, response.text
    revised = response.json()
    changes = revised['submissions'][-1]['changes']
    assert [change for change in changes if 'description' in change['field']] == [{
        'field': 'evidence.synthetic.description',
        'before': 'Synthetic original document description',
        'after': 'Synthetic corrected document description',
    }]
    assert revised['return_snapshot']['values']['evidence.synthetic.listing.description'] == 'Synthetic original document description'


def test_conflicting_legacy_evidence_representations_remain_visible_in_comparison():
    from engine.review_lifecycle import comparison_values
    values = {'evidence.doc.description': 'Fact description', 'evidence.doc.listing.description': 'Different legacy description'}
    assert comparison_values(values) == values


@pytest.mark.parametrize('changes', [{'authority': 'calgary'}, {'role': 'applicant'}])
def test_resubmit_does_not_restore_a_stale_claim_or_authority_permission(scene, changes):
    store, clients, users = scene
    returned = sent_back(scene)
    assert clients['owner'].post(f"/cases/{returned['id']}/facts", json=fact('request_answer.scope', 'Revised scope.').model_dump()).status_code == 200
    # A reviewer that changed role is history, not a current authority permission.
    person = store.get_user(users['reviewer']['id'])
    try:
        store.update_user(person.model_copy(update=changes), revoke_sessions=False)
        revised = clients['owner'].post(f"/cases/{returned['id']}/submit", json={}).json()
        assert revised['claim'] is None
        assert revised['submissions'][-1]['number'] == 2
        assert revised['decision_history'][0] == returned['decision']
        assert clients['reviewer'].get('/cases/' + returned['id']).status_code == 404
        assert clients['second'].post(f"/review/{returned['id']}/claim", json={}).status_code == 200
    finally:
        store.update_user(person, revoke_sessions=False)


def test_legacy_return_has_honest_unavailable_comparison_and_no_claim_resurrection(scene):
    store, clients, _ = scene
    returned = sent_back(scene)
    legacy = store.get(returned['id'])
    legacy.submissions = []
    legacy.return_snapshot = None
    legacy.decision_history = []
    legacy.claim = None
    store.put(legacy)
    revised = clients['owner'].post(f"/cases/{legacy.id}/submit", json={}).json()
    assert revised['claim'] is None, 'a historical decision must not create an exclusive claim'
    assert revised['submissions'][-1]['number'] == 2  # historic applicant submissions, not claim releases
    assert not revised['submissions'][-1]['comparison_available']
    assert revised['submissions'][-1]['changes'] == []
    assert revised['decision_history'] == [returned['decision']]


def test_resubmission_notifications_agree_with_actual_submitted_state(scene):
    _, clients, _ = scene
    returned = sent_back(scene)
    assert clients['owner'].post(f"/cases/{returned['id']}/facts", json=fact('request_answer.scope', 'Clarified scope.').model_dump()).status_code == 200
    response = clients['owner'].post(f"/cases/{returned['id']}/submit", json={})
    assert response.status_code == 200
    notes = clients['reviewer'].get('/me/notifications').json()['notifications']
    note = next(n for n in notes if n['case_id'] == returned['id'] and n['kind'] == 'status')
    assert note['status'] == 'submitted' and note['submission_number'] == 2
    assert 'resubmitted' in note['summary']
    # Releasing a round is not a new applicant submission/notification.
    assert clients['reviewer'].post(f"/review/{returned['id']}/claim", json={}).status_code == 200
    assert clients['reviewer'].delete(f"/review/{returned['id']}/claim").status_code == 204
    later = clients['reviewer'].get('/me/notifications').json()['notifications']
    assert [n for n in later if n['case_id'] == returned['id'] and n['kind'] == 'status'] == [note]


def test_active_review_is_retained_regardless_of_creation_or_inactivity(scene):
    store, clients, _ = scene
    case = owned(scene, complete=True)
    case.created_at = (datetime.now(timezone.utc) - timedelta(days=6)).isoformat()
    store.put(case)
    path = '/cases/' + case.id
    read = clients['owner'].get(path).json()
    expected = (datetime.fromisoformat(read['updated_at']) + timedelta(days=180)).isoformat()
    assert read['expires_at'] == expected
    assert clients['owner'].post(path + '/submit', json={}).json()['expires_at'] is None
    assert clients['reviewer'].post(path + '/messages', json={'body': 'Keep a synthetic local record.'}).status_code == 201
    app = next(a for a in clients['owner'].get('/me/applications').json()['applications'] if a['id'] == case.id)
    assert app['expires_at'] is None
    row = next(a for a in clients['reviewer'].get('/review/queue').json()['applications'] if a['id'] == case.id)
    assert row['expires_at'] is None
    from engine.tests.test_retention import _set_last_activity
    _set_last_activity(store, case.id, (datetime.now(timezone.utc) - timedelta(days=2000)).isoformat())
    assert clients['owner'].get(path).status_code == 200
    assert any(a['id'] == case.id for a in clients['reviewer'].get('/review/queue').json()['applications'])


def test_repeated_return_rounds_keep_decisions_and_compare_against_the_latest_return(scene):
    store, clients, _ = scene
    returned = sent_back(scene)
    path = '/cases/' + returned['id']
    for value in ['Synthetic lot B', 'Synthetic lot C']:
        assert clients['owner'].post(path + '/facts', json=fact('legalDescription', value).model_dump()).status_code == 200
        revised = clients['owner'].post(path + '/submit', json={}).json()
        change = next(c for c in revised['submissions'][-1]['changes'] if c['field'] == 'legal_description')
        assert change['after'] == value
        assert clients['reviewer'].post(f"/review/{returned['id']}/claim", json={}).status_code == 200
        response = clients['reviewer'].post(f"/review/{returned['id']}/decision", json={
            'outcome': 'return', 'message': 'Please clarify the synthetic legal description.',
            'items': [{'field': 'legal_description', 'note': 'Clarify the lot.'}],
        })
        assert response.status_code == 200, response.text
        if value.endswith('B'):
            assert change['before'] == 'Synthetic lot 1 block 2 plan 3'
        else:
            assert change['before'] == 'Synthetic lot B'
    saved = store.get(returned['id'])
    assert len(saved.decision_history) == 3  # identical return text in successive rounds still counts
    assert [s.number for s in saved.submissions] == [1, 2, 3]
    assert saved.decision == saved.decision_history[-1]


def test_simultaneous_resubmission_resume_and_takeover_never_create_two_claim_owners(scene):
    store, clients, users = scene
    returned = sent_back(scene)
    assert clients['owner'].post(f"/cases/{returned['id']}/facts", json=fact('request_answer.scope', 'Changed before resubmission.').model_dump()).status_code == 200
    assert clients['owner'].post(f"/cases/{returned['id']}/submit", json={}).status_code == 200
    barrier, responses = threading.Barrier(2), []

    def claim(name, body):
        barrier.wait()
        responses.append((name, clients[name].post(f"/review/{returned['id']}/claim", json=body).status_code))

    threads = [threading.Thread(target=claim, args=('reviewer', {})),
               threading.Thread(target=claim, args=('second', {'take_over': True}))]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    current = store.get(returned['id'])
    assert dict(responses)['second'] == 200
    assert current.status == 'in_review' and current.claim.reviewer_id == users['second']['id']
    assert clients['reviewer'].post(f"/review/{current.id}/decision", json={'outcome': 'accept', 'expected_version': current.version}).status_code == 409
    assert clients['second'].post(f"/review/{current.id}/decision", json=acceptance_request(clients['second'], current.id)).status_code == 200


def test_returned_application_cannot_be_resubmitted_unchanged(scene):
    store, clients, _ = scene
    returned = sent_back(scene)
    path = '/cases/' + returned['id']
    before = store.get(returned['id']).model_dump()
    response = clients['owner'].post(path + '/submit', json={})
    assert response.status_code == 409, response.text
    assert response.json()['detail'] == 'Nothing changed since it was returned. Fix the requested items, then send it again.'
    assert store.get(returned['id']).model_dump() == before
    # A changed quote/source alone still does not constitute a changed answer.
    assert clients['owner'].post(path + '/facts', json=fact('legal_description',
        'Synthetic lot 1 block 2 plan 3').model_dump()).status_code == 200
    assert clients['owner'].post(path + '/submit', json={}).status_code == 409
    assert clients['owner'].post(path + '/facts', json=fact('request_answer.ir_custom',
        'SYNTHETIC clarified assembly information.').model_dump()).status_code == 200
    revised = clients['owner'].post(path + '/submit', json={})
    assert revised.status_code == 200, revised.text
    assert revised.json()['submissions'][-1]['changes'] == [{
        'field': 'request_answer.ir_custom', 'before': None, 'after': 'SYNTHETIC clarified assembly information.'}]


def test_new_file_is_a_real_resubmission_change(scene):
    store, clients, _ = scene
    returned = sent_back(scene)
    kept = store.put_file(returned['id'], 'revised-source.pdf', b'%PDF-1.4\nSYNTHETIC new file bytes.\n')
    revised = clients['owner'].post(f"/cases/{returned['id']}/submit", json={})
    assert revised.status_code == 200, revised.text
    changes = revised.json()['submissions'][-1]['changes']
    assert len(changes) == 1 and changes[0]['field'] == 'file.' + kept['id']


def test_new_draft_without_authority_keeps_the_administrative_submit_gate(scene):
    store, clients, _ = scene
    case = owned(scene)
    case.authority = None
    saved = store.put(case)
    before = saved.model_dump()
    response = clients['owner'].post(f'/cases/{case.id}/submit', json={})
    assert response.status_code == 409, response.text
    assert response.json()['detail']['message'] == 'Resolve blocking administrative gaps before submitting'
    assert response.json()['detail']['gaps']
    assert store.get(case.id).model_dump() == before
