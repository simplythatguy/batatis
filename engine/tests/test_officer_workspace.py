"""One server-owned tally, finding dispositions, gates, and safe request drafts."""
from __future__ import annotations

import pytest
import uuid

from engine.completeness import Gap
from engine.models import Case
from engine.models_review import Disposition, Finding, InformationRequest, ReviewSession
from engine.review import information_request as ir
from engine.review import workspace
from engine.review.sessions import Sessions
from engine.tests.case_builder_fixtures import fact
from engine.tests.test_review import scene  # noqa: F401
from engine.tests.test_package_review_api import claimed


def finding(key='owner:presence', **changes):
    return Finding(**(dict(key=key, section='A', field=key.split(':')[0], label='owner name',
                           status='blank', message='Please check the saved information.', severity='blocking') | changes))


def session(findings, **changes):
    return ReviewSession(**(dict(package_id='pkg_test', case_id=None, authority='edmonton', version=1,
        created_at='2099-01-01T00:00:00+00:00', created_by_name='Officer', input_kind='upload',
        findings=findings, information_request=ir.build(findings)) | changes))


def install(scene, findings, **changes):
    store, clients, _ = scene
    case = claimed(scene)
    case = store.get(case.id)
    review = session(findings, package_id=case.id, case_id=case.id, case_version=case.version, **changes)
    Sessions(store).add(review)
    return case, review, clients['reviewer']


def edits(review):
    return [{'id': i.id, 'text': i.text, 'included': i.included} for i in review.information_request.items]


def test_tally_defaults_include_uncertainty_professionals_and_exclude_peer_signal():
    findings = [finding(), finding('unreadable:x', status='not_found'),
        finding('warning:x', severity='warning'), finding('professional:x', routed_to='professional'),
        finding('officer:x', routed_to='officer', severity='warning'),
        finding('peer_review:signal', routed_to='officer')]
    review = session(findings)
    result = workspace.build(review)
    assert result.tally.model_dump() == dict(required=3, to_check=2, verify=3, dismissed=0, asked=2, rulebook=0)
    assert [s.state for s in result.states] == ['ask', 'verify', 'ask', 'verify', 'verify']
    assert not result.gate.can_accept and 'Standalone' in result.gate.reason
    assert all(i.target for i in review.information_request.items)


def test_rulebook_coverage_locked_and_current_gate():
    case = Case(version=3)
    gaps = [Gap(id='required:owner', field='owner', section='A', severity='blocking', message='Need owner', fix_hint='x'),
            Gap(id='required:legal', field='legal', section='B', severity='blocking', message='Need lot', fix_hint='x')]
    review = session([finding()], case_version=3)
    result = workspace.build(review, case, gaps)
    assert result.current and result.states[0].locked
    assert [g.id for g in result.rulebook] == ['required:legal']
    assert result.tally.required == 2 and result.tally.rulebook == 1
    assert not result.gate.can_accept
    assert not workspace.build(review, Case(version=4)).current
    clean = session([], case_version=3)
    assert workspace.build(clean, case).gate.can_accept


def test_not_found_is_unverified_never_resolved():
    prior = finding('owner:presence')
    result = ir.diff(1, [prior], [prior.model_copy(update={'status': 'not_found'})])
    assert result.resolved == [] and result.still_open == []
    assert [entry.key for entry in result.unverified] == ['owner:presence']
    assert result.statement == "0 of 1 gaps resolved, 1 can't tell"
    assert workspace.build(session([prior.model_copy(update={'status': 'not_found'})])).tally.required == 1


def test_dispositions_targets_and_full_index_response(scene):
    case, review, client = install(scene, [finding()])
    path = f'/review/{case.id}/package-review/1/information-request'
    for change in [dict(key='unknown', state='verify'), dict(key='owner:presence', state='dismissed'),
                   dict(key='owner:presence', state='dismissed', reason='checked', note=' a b ')]:
        response = client.put(path, json={'items': edits(review), 'findings': [change]})
        assert response.status_code == 422, response.text
    response = client.put(path, json={'items': edits(review), 'findings': [
        dict(key='owner:presence', state='dismissed', reason='checked', note='Checked saved record')]})
    assert response.status_code == 200, response.text
    index = response.json()
    assert index['workspace']['tally']['required'] == 0
    assert index['sessions'][0]['required'] == 0
    assert index['latest']['dispositions'][0]['by_name'] == 'Reviewer'
    assert index['latest']['dispositions'][0]['at']
    assert not index['latest']['information_request']['items'][0]['included']
    # Correspondence cannot hide an ask. Server inclusion follows the finding state.
    response = client.put(path, json={'items': [dict(edits(review)[0], included=False)], 'findings': [
        dict(key='owner:presence', state='ask')]})
    assert response.json()['latest']['information_request']['items'][0]['included']
    assert response.json()['workspace']['tally']['asked'] == 1



def test_omitting_a_linked_item_does_not_change_the_finding_state(scene):
    case, review, client = install(scene, [finding()])
    response = client.put(f'/review/{case.id}/package-review/1/information-request', json={'items': []})
    assert response.status_code == 200, response.text
    index = response.json()
    assert index['workspace']['states'][0]['state'] == 'ask'
    assert index['workspace']['tally']['asked'] == 1
    assert index['latest']['information_request']['items'][0]['id'] == review.information_request.items[0].id
    assert index['latest']['information_request']['items'][0]['included']

def test_locked_findings_cannot_be_dismissed(scene):
    store, _, _ = scene
    case, review, client = install(scene, [finding('owner_name:presence')])
    saved = store.get(case.id)
    saved.facts = [f for f in saved.facts if f.field != 'owner_name']
    store.put(saved)
    response = client.put(f'/review/{case.id}/package-review/1/information-request', json={
        'items': edits(review), 'findings': [dict(key='owner_name:presence', state='dismissed',
                                                reason='checked', note='Checked by officer')]})
    assert response.status_code == 422
    assert response.json()['detail'] == 'The completeness rules still require this; ask for it'


def test_officer_only_finding_cannot_ask_without_linked_item(scene):
    case, review, client = install(scene, [finding('officer:check', routed_to='officer')])
    response = client.put(f'/review/{case.id}/package-review/1/information-request', json={
        'items': [], 'findings': [dict(key='officer:check', state='ask')]})
    assert response.status_code == 422


def test_officer_items_need_targets_and_latest_version_only(scene):
    store, _, _ = scene
    case, review, client = install(scene, [])
    path = f'/review/{case.id}/package-review/1/information-request'
    assert client.put(path, json={'items': [{'text': 'Please explain the supplied scope.'}]}).status_code == 422
    response = client.put(path, json={'items': [{'text': 'Please explain the supplied scope.',
        'target': {'section': 'B', 'label': 'Section B · Scope'}}]})
    assert response.status_code == 200, response.text
    assert response.json()['latest']['information_request']['items'][0]['target']['section'] == 'B'
    Sessions(store).add(review.model_copy(update={'version': 2}))
    assert client.put(path, json={'items': []}).status_code == 409


@pytest.mark.parametrize('payload', [
    {'intro': 'x' * 2001, 'items': []},
    {'items': [{'text': 'x' * 2001, 'target': {'section': 'A', 'label': 'Owner'}}]},
    {'items': [{'text': 'x', 'target': {'section': 'A', 'label': 'Owner'}}] * 51},
    {'items': [{'text': 'x' * 2000, 'target': {'section': 'A', 'label': 'Owner'}}] * 6},
])
def test_draft_limits_reject_before_saving(scene, payload):
    store, _, _ = scene
    case, review, client = install(scene, [])
    response = client.put(f'/review/{case.id}/package-review/1/information-request', json=payload)
    assert response.status_code == 422, response.text
    assert Sessions(store).get(case.id, 1)[0] == review


def draft_return(scene):
    case, review, client = install(scene, [finding('legal_description:presence', section='B')])
    response = client.put(f'/review/{case.id}/package-review/1/information-request', json={
        'items': edits(review) + [{'text': 'Please explain the unknown assembly.',
                                  'target': {'section': 'D', 'label': 'Section D · Assembly'}}]})
    assert response.status_code == 200, response.text
    return case, client, response.json()['latest']['information_request']


def test_return_commits_one_targeted_decision_and_freezes_the_request(scene):
    store, clients, _ = scene
    case, client, request = draft_return(scene)
    path = f'/review/{case.id}/package-review/1/return'
    response = client.post(path, json={'expected_version': case.version, 'text': request['text']})
    assert response.status_code == 200, response.text
    saved = response.json()
    assert saved['status'] == 'returned'
    assert saved['decision']['outcome'] == 'return'
    assert saved['decision']['message'] == 'Returned for administrative information.\n\n' + request['text']
    assert saved['return_snapshot']['returned_at'] == saved['decision']['at']
    assert len(saved['decision_history']) == 1
    messages = [message for message in saved['messages'] if message['kind'] == 'decision']
    assert len(messages) == 1 and messages[0]['body'] == saved['decision']['message']
    items = saved['decision']['items']
    assert items[0] == dict(gap_id=None, field='legal_description', section='B', label='Section B · Owner name',
        note=request['items'][0]['text'], request_item_id=request['items'][0]['id'],
        finding_key='legal_description:presence')
    assert items[-1]['field'] == 'request_answer.' + request['items'][-1]['id']
    assert items[-1]['section'] == 'D' and items[-1]['label'] == 'Section D · Assembly'
    assert client.post(path, json={'expected_version': case.version, 'text': request['text']}).status_code == 409
    assert client.put(path.removesuffix('/return') + '/information-request', json={'items': []}).status_code == 409
    applicant = clients['owner'].get(f'/cases/{case.id}/information-request').json()['requests']
    assert len(applicant) == 1 and applicant[0]['text'] == request['text']
    assert applicant[0]['items'] == [i['text'] for i in request['items'] if i['included']]
    assert len([m for m in store.get(case.id).messages if m.kind == 'decision']) == 1


@pytest.mark.parametrize('failure', ['before', 'inside'])
def test_return_recovers_from_session_failure_after_the_case_commit(scene, monkeypatch, failure):
    store, clients, _ = scene
    case, client, request = draft_return(scene)
    original = Sessions.replace

    def fail_finalization(self, review, expected):
        if self.store.get(case.id).status == 'returned':
            if failure == 'inside':
                original(self, review, expected)
            raise OSError('session storage failed after case commit')
        return original(self, review, expected)

    monkeypatch.setattr(Sessions, 'replace', fail_finalization)
    path = f'/review/{case.id}/package-review/1'
    response = client.post(path + '/return', json={'expected_version': case.version, 'text': request['text']})
    assert response.status_code == 200, response.text
    assert store.get(case.id).status == 'returned'
    # Both reviewer and applicant reads recover sent state, even while finalization remains unavailable.
    result = client.get(f'/review/{case.id}/package-review').json()['latest']['information_request']
    assert result['sent_at'] and result['sent_by_name'] == 'Reviewer' and result['message_id']
    assert result['text'] == request['text']
    assert len(clients['owner'].get(f'/cases/{case.id}/information-request').json()['requests']) == 1
    assert client.post(path + '/return', json={'expected_version': case.version, 'text': request['text']}).status_code == 409
    assert client.put(path + '/information-request', json={'items': []}).status_code == 409
    assert len([m for m in store.get(case.id).messages if m.kind == 'decision']) == 1


def test_case_write_failure_leaves_no_send_and_can_retry(scene, monkeypatch):
    store, clients, _ = scene
    case, client, request = draft_return(scene)
    original = store.put

    def unavailable(*args, **kwargs):
        raise OSError('case write failed')

    monkeypatch.setattr(store, 'put', unavailable)
    path = f'/review/{case.id}/package-review/1/return'
    with pytest.raises(OSError, match='case write failed'):
        client.post(path, json={'expected_version': case.version, 'text': request['text']})
    assert store.get(case.id).status == 'in_review'
    assert Sessions(store).get(case.id, 1)[0].information_request.sent_at is None
    assert clients['owner'].get(f'/cases/{case.id}/information-request').json()['requests'] == []
    monkeypatch.setattr(store, 'put', original)
    assert client.post(path, json={'expected_version': case.version, 'text': request['text']}).status_code == 200


def test_return_rejects_changed_text_and_stale_case_before_sending(scene):
    store, clients, _ = scene
    case, client, request = draft_return(scene)
    path = f'/review/{case.id}/package-review/1/return'
    response = client.post(path, json={'expected_version': case.version, 'text': request['text'] + ' changed'})
    assert response.status_code == 409 and response.json()['detail'] == 'The request changed. Review it again.'
    assert client.post(path, json={'expected_version': case.version + 1, 'text': request['text']}).status_code == 409
    assert not Sessions(store).get(case.id, 1)[0].information_request.sent_at
    assert clients['owner'].get(f'/cases/{case.id}/information-request').json()['requests'] == []


def test_accept_gate_rechecks_review_and_saved_case(scene):
    store, _, _ = scene
    case, review, client = install(scene, [finding()])
    path = f'/review/{case.id}/decision'
    payload = dict(outcome='accept', expected_version=case.version, review_version=1)
    assert client.post(path, json={'outcome': 'accept'}).status_code == 422
    for revision in [None, 2]:
        assert client.post(path, json=payload | {'review_version': revision}).status_code == 409
    response = client.post(path, json=payload)
    assert response.status_code == 409 and 'required' in response.json()['detail']
    edit = client.put(f'/review/{case.id}/package-review/1/information-request', json={
        'items': edits(review), 'findings': [dict(key='owner:presence', state='dismissed',
                                               reason='checked', note='Checked source')]})
    assert edit.status_code == 200, edit.text
    assert client.post(path, json=payload).status_code == 200


def test_accept_refuses_stale_review_and_uncovered_canonical_gap(scene):
    store, _, _ = scene
    case, _, client = install(scene, [])
    saved = store.get(case.id)
    saved.facts = [f for f in saved.facts if f.field != 'owner_name']
    saved = store.put(saved)
    path = f'/review/{case.id}/decision'
    payload = dict(outcome='accept', expected_version=saved.version, review_version=1)
    response = client.post(path, json=payload)
    assert response.status_code == 409 and 'changed' in response.json()['detail']
    latest = session([], package_id=case.id, case_id=case.id, version=2, case_version=saved.version)
    Sessions(store).add(latest)
    index = client.get(f'/review/{case.id}/package-review').json()
    assert any(g['field'] == 'owner_name' for g in index['workspace']['rulebook'])
    assert index['workspace']['tally']['rulebook'] >= 1
    assert not index['workspace']['gate']['can_accept']
    response = client.post(path, json=payload | {'review_version': 2})
    assert response.status_code == 409 and 'completeness rules' in response.json()['detail']


def test_accept_requires_a_review_when_codedb_exists(scene):
    store, clients, _ = scene
    case = claimed(scene)
    response = clients['reviewer'].post(f'/review/{case.id}/decision', json={
        'outcome': 'accept', 'expected_version': store.get(case.id).version})
    assert response.status_code == 409 and response.json()['detail'] == 'Run the package review before accepting'


def test_standalone_edits_return_index_and_new_reviews_start_fresh(scene):
    from engine.tests.test_package_review_api import multipart
    from engine.tests.package_review_fixtures import text_pdf
    store, clients, _ = scene
    review = session([finding()], package_id='pkg_' + uuid.uuid4().hex)
    Sessions(store).add(review)
    path = '/package-review/' + review.package_id
    response = clients['reviewer'].put(path + '/1/information-request', json={
        'items': edits(review), 'findings': [dict(key='owner:presence', state='dismissed',
                                               reason='checked', note='Checked saved record')]})
    assert response.status_code == 200, response.text
    assert response.json()['workspace']['tally']['dismissed'] == 1
    assert response.json()['latest']['dispositions']
    new = clients['reviewer'].post(path, files=multipart([('form.pdf', text_pdf(['SYNTHETIC readable page.']))]))
    assert new.status_code == 201, new.text
    assert new.json()['dispositions'] == []
    assert clients['reviewer'].put(path + '/1/information-request', json={'items': []}).status_code == 409


def test_no_session_acceptance_falls_back_only_when_codedb_is_absent(scene, monkeypatch):
    from fastapi.testclient import TestClient
    import engine.api as api
    from engine.codes import CodeDbMissing
    store, clients, _ = scene
    case = claimed(scene)
    version = store.get(case.id).version

    def missing():
        raise CodeDbMissing()

    monkeypatch.setattr(api, 'Codes', missing)
    with TestClient(api.create_app(store=store), base_url='http://localhost') as offline:
        offline.cookies.update(clients['reviewer'].cookies)
        result = offline.post(f'/review/{case.id}/decision', json={'outcome': 'accept', 'expected_version': version})
    assert result.status_code == 200, result.text


def test_close_out_requires_issuance_and_records_the_date_once(scene):
    from datetime import datetime, timedelta
    from zoneinfo import ZoneInfo
    store, clients, _ = scene
    case, _, client = install(scene, [])
    assert client.post(f'/review/{case.id}/decision', json={
        'outcome': 'accept', 'expected_version': case.version, 'review_version': 1}).status_code == 200
    path = f'/review/{case.id}/close-out'
    before = store.get(case.id).model_dump()
    close = client.get(path).json()
    assert close['issued_on'] is None and close['due_date'] is None and close['days_remaining'] is None
    assert not close['overdue'] and not close['sent']
    assert client.post(path + '/sent').status_code == 409
    today = datetime.now(ZoneInfo('America/Edmonton')).date()
    assert clients['second'].post(path + '/issued', json={'issued_on': today.isoformat()}).status_code == 409
    for invalid in ['2026-02-30', (today + timedelta(days=1)).isoformat(), (today - timedelta(days=1)).isoformat()]:
        assert client.post(path + '/issued', json={'issued_on': invalid}).status_code == 422
    issued = client.post(path + '/issued', json={'issued_on': today.isoformat()})
    assert issued.status_code == 200, issued.text
    assert issued.json()['issued_by_name'] == 'Reviewer'
    assert issued.json()['due_date'] == (today + timedelta(days=10)).isoformat()
    assert client.post(path + '/issued', json={'issued_on': today.isoformat()}).status_code == 409
    assert client.post(path + '/sent').json()['sent']
    assert client.post(path + '/sent').status_code == 409
    assert store.get(case.id).model_dump() == before


@pytest.mark.parametrize('standalone', [False, True])
def test_upload_files_are_kept_only_for_case_linked_reviews(scene, standalone):
    from engine.tests.package_review_fixtures import text_pdf
    from engine.tests.test_package_review_api import multipart
    store, clients, _ = scene
    case = None if standalone else claimed(scene)
    before = store.get(case.id) if case else None
    files = [('same.pdf', text_pdf(['SYNTHETIC first page.'])), ('same.pdf', text_pdf(['SYNTHETIC second page.']))]
    path = '/package-review' if standalone else f'/review/{case.id}/package-review'
    response = clients['reviewer'].post(path, files=multipart(files))
    assert response.status_code == 201, response.text
    result = response.json()
    if standalone:
        assert all(item['file_id'] is None for item in result['files'])
    else:
        assert result['case_version'] == before.version
        for item, (_, data) in zip(result['files'], files):
            assert item['file_id']
            kept = clients['owner'].get(f'/cases/{case.id}/files/' + item['file_id'])
            assert kept.status_code == 200 and kept.content == data
        assert store.get(case.id).version == before.version
        assert clients['reviewer'].get(path).json()['workspace']['current']
        # Files retained for the reviewer never change the applicant's facts or evidence.
        assert store.get(case.id).facts == before.facts and store.get(case.id).evidence == before.evidence


def test_upload_storage_failure_keeps_review_available(scene, monkeypatch):
    from engine.tests.package_review_fixtures import text_pdf
    from engine.tests.test_package_review_api import multipart
    store, clients, _ = scene
    case = claimed(scene)

    def unavailable(*args, **kwargs):
        raise OSError('file storage temporarily unavailable')

    monkeypatch.setattr(store, 'put_file', unavailable)
    result = clients['reviewer'].post(f'/review/{case.id}/package-review',
        files=multipart([('page.pdf', text_pdf(['SYNTHETIC readable page.']))]))
    assert result.status_code == 201, result.text
    assert result.json()['files'][0]['file_id'] is None


def test_accept_cas_rechecks_a_concurrent_finding_change(scene, monkeypatch):
    store, _, _ = scene
    case, review, client = install(scene, [finding()], dispositions=[Disposition(
        key='owner:presence', state='dismissed', reason='checked', note='Checked source')])
    original = store.put
    changed = False

    def reopen_before_commit(candidate, **options):
        nonlocal changed
        if candidate.id == case.id and candidate.status == 'accepted' and not changed:
            changed = True
            current, raw = Sessions(store).get(case.id, 1)
            Sessions(store).replace(workspace.sync_request(current.model_copy(update={
                'dispositions': [Disposition(key='owner:presence', state='ask')]})), raw)
        return original(candidate, **options)

    monkeypatch.setattr(store, 'put', reopen_before_commit)
    response = client.post(f'/review/{case.id}/decision', json={
        'outcome': 'accept', 'expected_version': case.version, 'review_version': 1})
    assert response.status_code == 409, response.text
    assert 'required' in response.json()['detail']
    assert store.get(case.id).status == 'in_review' and store.get(case.id).decision is None


@pytest.mark.parametrize('route', ['return', 'information-request/send'])
def test_oversized_saved_drafts_cannot_partly_send(scene, route):
    from engine.models_review import InformationRequestItem, RequestTarget
    store, clients, _ = scene
    case, review, client = install(scene, [], information_request=InformationRequest(intro='Officer request', items=[
        InformationRequestItem(id=f'item_{i}', text='Please provide the requested synthetic information.',
            target=RequestTarget(section='D', label='Section D · Information')) for i in range(51)]))
    # Legacy data is checked at send too, before any reservation/message/status change.
    before = store.get(case.id).model_dump()
    payload = {'expected_version': case.version, 'text': ir.render(review.information_request)} if route == 'return' else None
    response = client.post(f'/review/{case.id}/package-review/1/{route}', json=payload)
    assert response.status_code == 422, response.text
    assert store.get(case.id).model_dump() == before
    assert not Sessions(store).get(case.id, 1)[0].information_request.sent_at
    assert clients['owner'].get(f'/cases/{case.id}/information-request').json()['requests'] == []


def test_legacy_send_preserves_more_than_4000_characters(scene):
    from engine.models_review import InformationRequestItem, RequestTarget
    store, clients, _ = scene
    request = InformationRequest(intro='Synthetic full request', items=[InformationRequestItem(
        id=f'item_{i}', text=chr(65 + i) * 1900, target=RequestTarget(section='D', label='Section D · Source'))
        for i in range(3)])
    case, _, client = install(scene, [], information_request=request)
    sent = client.post(f'/review/{case.id}/package-review/1/information-request/send')
    assert sent.status_code == 200, sent.text
    assert sent.json()['information_request']['text'] == ir.render(request)
    assert len(sent.json()['information_request']['text']) > 4000
    messages = clients['owner'].get(f'/cases/{case.id}/messages').json()['messages']
    assert messages[-1]['body'] == ir.render(request)


def test_historical_summaries_keep_the_rulebook_for_that_version(scene):
    store, clients, _ = scene
    case = claimed(scene)
    saved = store.get(case.id)
    saved.facts = [f for f in saved.facts if f.field != 'owner_name']
    store.put(saved)
    path = f'/review/{case.id}/package-review'
    assert clients['reviewer'].post(path).status_code == 201
    first = clients['reviewer'].get(path).json()['workspace']['tally']['required']
    saved = store.get(case.id)
    saved.facts = [f for f in saved.facts if f.field != 'civic_address'] + [fact('owner_name', 'Restored synthetic owner')]
    store.put(saved)
    assert clients['reviewer'].post(path).status_code == 201
    index = clients['reviewer'].get(path).json()
    assert index['sessions'][0]['required'] == first
    assert index['sessions'][1]['required'] == index['workspace']['tally']['required']


@pytest.mark.parametrize('with_session', [False, True])
def test_missing_codedb_keeps_known_canonical_blockers_and_refuses_session_acceptance(scene, monkeypatch, with_session):
    from fastapi.testclient import TestClient
    import engine.api as api
    from engine.codes import CodeDbMissing
    store, clients, _ = scene
    if with_session:
        case, _, _ = install(scene, [])
    else:
        case = claimed(scene)
        case = store.get(case.id)
        case.gaps = [Gap(id='synthetic:owner', severity='blocking', section='A', field='owner_name',
                         message='Known canonical owner gap', fix_hint='Provide the owner name')]
        case = store.put(case)

    def missing():
        raise CodeDbMissing()

    monkeypatch.setattr(api, 'Codes', missing)
    with TestClient(api.create_app(store=store), base_url='http://localhost') as offline:
        offline.cookies.update(clients['reviewer'].cookies)
        result = offline.post(f'/review/{case.id}/decision', json={
            'outcome': 'accept', 'expected_version': case.version, 'review_version': 1 if with_session else None})
    assert result.status_code == 409, result.text
    assert store.get(case.id).status == 'in_review' and store.get(case.id).decision is None


def test_return_requires_an_item_latest_session_and_current_claim(scene):
    store, clients, _ = scene
    case, review, client = install(scene, [])
    path = f'/review/{case.id}/package-review/1/return'
    body = {'expected_version': case.version, 'text': ir.render(review.information_request)}
    assert client.post(path, json=body).status_code == 409
    assert clients['second'].post(path, json=body).status_code == 409
    assert clients['owner'].post(path, json=body).status_code == 404
    Sessions(store).add(review.model_copy(update={'version': 2}))
    assert client.post(path, json=body).status_code == 409
    assert store.get(case.id).status == 'in_review' and store.get(case.id).decision is None
