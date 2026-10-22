"""Package review over HTTP: #48 reviewer roles, claim, information request, re-upload diff, access matrix."""
from __future__ import annotations

from contextlib import ExitStack

import pytest
from fastapi.testclient import TestClient

from engine.api import create_app
from engine.codes import Codes
from engine.models import Case
from engine.store import CaseStore
from engine.tests.case_builder_fixtures import complete_case, store_with_synthetic_files
from engine.tests.package_review_fixtures import CLEAN_FORM, package
from engine.tests.test_accounts import onboard, signup

NAMES = ['owner', 'other', 'reviewer', 'second', 'foreign', 'anonymous']


@pytest.fixture(scope='module')
def scene(tmp_path_factory):
    with pytest.MonkeyPatch.context() as patch, ExitStack() as stack:
        patch.delenv('VERCEL', raising=False)
        patch.setenv('BATATIS_REVIEWER_CODES', '{"edmonton":"officer-secret","calgary":"calgary-secret"}')
        patch.setenv('BATATIS_AUTH_RATE_LIMIT', '100')
        store = CaseStore(tmp_path_factory.mktemp('package-review') / 'cases.sqlite')
        app = create_app(store=store, codes=Codes())
        clients, users = {}, {}
        for name, role, authority in [('owner', 'applicant', 'edmonton'), ('other', 'applicant', 'edmonton'),
                                     ('reviewer', 'reviewer', 'edmonton'), ('second', 'reviewer', 'edmonton'),
                                     ('foreign', 'reviewer', 'calgary'), ('anonymous', None, None)]:
            clients[name] = stack.enter_context(TestClient(app, base_url='http://localhost'))
            if role:
                assert signup(clients[name], name + '@example.test', name.title()).status_code == 201
                users[name] = onboard(clients[name], role, authority)
        yield store, clients, users


def owned(scene, status='draft', complete=False):
    store, _, users = scene
    case = complete_case() if complete else Case(title='Package review matrix')
    case.owner_id, case.authority, case.status = users['owner']['id'], 'edmonton', status
    return store_with_synthetic_files(store, case) if complete else store.put(case)


def claimed(scene):
    store, clients, _ = scene
    case = owned(scene, 'submitted', complete=True)
    assert clients['reviewer'].post(f'/review/{case.id}/claim', json={}).status_code == 200
    return case


def multipart(files):
    return {'files': None} if not files else [('files', (name, data, 'application/pdf')) for name, data in files]


@pytest.mark.parametrize('status', ['draft', 'submitted', 'in_review', 'returned', 'accepted', 'refused'])
def test_read_access_matrix(scene, status):
    store, clients, _ = scene
    case = owned(scene, status)
    for name in NAMES:
        allowed = name in {'reviewer', 'second'} and status != 'draft'
        for suffix in ('', '/1'):
            response = clients[name].get(f'/review/{case.id}/package-review{suffix}')
            expected = (200 if not suffix else 404) if allowed else 404
            assert response.status_code == expected, (name, status, suffix, response.text)
        # Sent requests are readable by the owner and the authority's reviewers, never by others.
        response = clients[name].get(f'/cases/{case.id}/information-request')
        reader = name == 'owner' or allowed
        assert response.status_code == (200 if reader else 404), (name, status, response.text)
    store.delete(case.id)


def test_only_the_claimer_runs_edits_and_sends(scene):
    store, clients, _ = scene
    case = owned(scene, 'submitted', complete=True)
    for name in NAMES:
        response = clients[name].post(f'/review/{case.id}/package-review')
        assert response.status_code == (409 if name in {'reviewer', 'second'} else 404), (name, response.text)
    assert clients['reviewer'].post(f'/review/{case.id}/claim', json={}).status_code == 200
    for name in NAMES:
        if name == 'reviewer':
            continue
        response = clients[name].post(f'/review/{case.id}/package-review')
        assert response.status_code == (409 if name == 'second' else 404), (name, response.text)
    run = clients['reviewer'].post(f'/review/{case.id}/package-review')
    assert run.status_code == 201, run.text
    body = {'items': [{'text': 'Please confirm the owner name.', 'included': True}]}
    for name in NAMES:
        if name == 'reviewer':
            continue
        assert clients[name].put(f'/review/{case.id}/package-review/1/information-request',
                                 json=body).status_code in (404, 409), name
        assert clients[name].post(f'/review/{case.id}/package-review/1/information-request/send').status_code in (404, 409)
    store.delete(case.id)


def test_case_review_request_send_and_applicant_view(scene):
    store, clients, _ = scene
    case = claimed(scene)
    first = clients['reviewer'].post(f'/review/{case.id}/package-review')
    assert first.status_code == 201, first.text
    session = first.json()
    assert session['input_kind'] == 'case' and session['version'] == 1 and session['diff'] is None
    assert session['administrative_only'] is True and session['not_a_compliance_determination'] is True
    assert session['citations'] and all(check['exists'] for check in session['citations'])
    assert session['documents'], 'the documents panel lists the case attachments'
    # Drafts stay private until sent.
    assert clients['owner'].get(f'/cases/{case.id}/information-request').json()['requests'] == []
    items = [{'id': item['id'], 'text': item['text'], 'included': item['included']}
             for item in session['information_request']['items']]
    items.append({'text': 'Please send the stamped drawing set referenced in Section D.', 'included': True})
    edited = clients['reviewer'].put(f'/review/{case.id}/package-review/1/information-request',
                                     json={'items': items, 'intro': 'Officer intro.'})
    assert edited.status_code == 200, edited.text
    request = edited.json()['information_request']
    assert request['edited'] and request['intro'] == 'Officer intro.'
    assert request['items'][-1]['authored_by'] == 'officer'
    assert 'stamped drawing set' in request['text']
    bad = clients['reviewer'].put(f'/review/{case.id}/package-review/1/information-request',
                                  json={'items': [{'id': 'ir_nope', 'text': 'x'}]})
    assert bad.status_code == 422
    sent = clients['reviewer'].post(f'/review/{case.id}/package-review/1/information-request/send')
    assert sent.status_code == 200, sent.text
    assert sent.json()['information_request']['sent_at']
    assert clients['reviewer'].post(f'/review/{case.id}/package-review/1/information-request/send').status_code == 409
    assert clients['reviewer'].put(f'/review/{case.id}/package-review/1/information-request',
                                   json={'items': items}).status_code == 409
    view = clients['owner'].get(f'/cases/{case.id}/information-request').json()['requests']
    assert len(view) == 1 and 'stamped drawing set' in view[0]['text']
    thread = clients['owner'].get(f'/cases/{case.id}/messages').json()['messages']
    assert any('stamped drawing set' in message['body'] for message in thread)
    notifications = clients['owner'].get('/me/notifications').json()
    assert notifications['unread'] >= 1
    # The review never records a decision or moves the status.
    saved = store.get(case.id)
    assert saved.decision is None and saved.status == 'in_review'
    second = clients['reviewer'].post(f'/review/{case.id}/package-review').json()
    assert second['version'] == 2 and second['diff']['previous_version'] == 1
    assert second['diff']['statement'].startswith(f"0 of {second['diff']['previous_gaps']} gaps resolved")
    index = clients['second'].get(f'/review/{case.id}/package-review').json()
    assert [s['version'] for s in index['sessions']] == [1, 2] and index['latest']['version'] == 2
    store.delete(case.id)
    assert store.get(case.id) is None


def test_upload_on_queue_case_and_reupload_diff(scene):
    store, clients, _ = scene
    case = claimed(scene)
    planted = dict(CLEAN_FORM, Owner='', **{'Date of Reqeuest': '', 'Name Responsible': ''})
    first = clients['reviewer'].post(f'/review/{case.id}/package-review', files=multipart(package(planted)))
    assert first.status_code == 201, first.text
    keys = {f['key'] for f in first.json()['findings'] if f['status'] != 'not_found'}
    assert {'owner_name:presence', 'application_date:presence', 'supporting_doc:no_responsible'} <= keys
    fixed = dict(CLEAN_FORM, **{'Date of Reqeuest': '', 'Lot': 'TBD'})
    second = clients['reviewer'].post(f'/review/{case.id}/package-review', files=multipart(package(fixed, flat=True)))
    assert second.status_code == 201, second.text
    diff = second.json()['diff']
    assert diff['previous_gaps'] == 3
    assert {e['key'] for e in diff['resolved']} == {'owner_name:presence', 'supporting_doc:no_responsible'}
    assert {e['key'] for e in diff['still_open']} == {'application_date:presence'}
    assert {e['key'] for e in diff['new']} == {'legal_description:presence'}
    assert diff['statement'] == '2 of 3 gaps resolved, 1 still open, 1 new'
    store.delete(case.id)


def test_standalone_upload_review_is_reviewer_and_authority_scoped(scene):
    _, clients, _ = scene
    files = package(dict(CLEAN_FORM, Owner=''))
    assert clients['anonymous'].post('/package-review', files=multipart(files)).status_code == 401
    assert clients['owner'].post('/package-review', files=multipart(files)).status_code == 403
    created = clients['reviewer'].post('/package-review', files=multipart(files))
    assert created.status_code == 201, created.text
    package_id = created.json()['package_id']
    assert created.json()['case_id'] is None
    assert clients['second'].get(f'/package-review/{package_id}').status_code == 200
    assert clients['foreign'].get(f'/package-review/{package_id}').status_code == 404
    assert clients['foreign'].post(f'/package-review/{package_id}', files=multipart(files)).status_code == 404
    assert clients['owner'].get(f'/package-review/{package_id}').status_code == 403
    again = clients['second'].post(f'/package-review/{package_id}', files=multipart(package()))
    assert again.status_code == 201
    assert again.json()['diff']['statement'].startswith('1 of 1 gaps resolved')
    assert clients['reviewer'].get(f'/package-review/{package_id}/2').json()['version'] == 2


def test_upload_input_errors(scene):
    _, clients, _ = scene
    assert clients['reviewer'].post('/package-review', content=b'%PDF-1.4',
                                    headers={'content-type': 'application/pdf'}).status_code == 415
    response = clients['reviewer'].post('/package-review', files=[('files', ('notes.txt', b'hello', 'text/plain'))])
    assert response.status_code == 201
    session = response.json()
    assert session['files'][0]['role'] == 'unreadable'
    assert {f['key'] for f in session['findings']} >= {'form:presence', 'file:notes.txt:unreadable'}
    big = [('files', ('big.pdf', b'%PDF' + b'0' * (4 * 1024 * 1024), 'application/pdf'))]
    assert clients['reviewer'].post('/package-review', files=big).status_code == 413


@pytest.mark.parametrize('outcome', ['accept', 'refuse'])
def test_close_out_after_decision_with_record_package(scene, outcome):
    store, clients, _ = scene
    case = claimed(scene)
    reviewed = clients['reviewer'].post(f'/review/{case.id}/package-review')
    assert reviewed.status_code == 201
    source_version = reviewed.json()['case_version']
    assert clients['reviewer'].get(f'/review/{case.id}/close-out').status_code == 404   # no decision yet
    decided = clients['reviewer'].post(f'/review/{case.id}/decision',
                                      json={'outcome': outcome, 'message': 'Officer recorded the written reason.'})
    assert decided.status_code == 200, decided.text
    close = clients['second'].get(f'/review/{case.id}/close-out')
    assert close.status_code == 200, close.text
    body = close.json()
    assert body['outcome'] == outcome
    assert body['decided_at'] == decided.json()['decision']['at']
    decided_case = store.get(case.id).model_dump()
    # Decision/close-out writes never rewrite the review's saved source version or applicant evidence.
    for path, payload in [('/package-review', None),
                          ('/package-review/1/information-request', {'items': []}),
                          ('/package-review/1/information-request/send', None)]:
        method = 'put' if payload is not None else 'post'
        assert clients['reviewer'].request(method, f'/review/{case.id}' + path, json=payload).status_code == 409
    from datetime import datetime, timedelta, timezone
    decided_at = datetime.fromisoformat(body['decided_at']).date()
    assert body['due_date'] == (decided_at + timedelta(days=10)).isoformat()
    assert body['days_remaining'] == (decided_at + timedelta(days=10) - datetime.now(timezone.utc).date()).days
    assert body['sent'] is False and body['overdue'] is False
    package_ = body['record_package']
    assert package_['send_to_council'][0]['label'] == 'Copy of the variance as decided'
    assert {item['label'] for item in package_['retain_on_file']} >= {'Supporting documents',
                                                                      'Section C code references and attributions'}
    assert 'IB-2025-11-18' in package_['basis'][0]
    assert 'never' not in body['notice'] or 'does not send' in body['notice']
    index = clients['reviewer'].get(f'/review/{case.id}/package-review').json()
    assert index['close_out']['due_date'] == body['due_date']
    assert index['close_out']['outcome'] == outcome
    assert index['latest']['case_version'] == source_version
    for name in ['owner', 'other', 'foreign', 'anonymous']:
        assert clients[name].post(f'/review/{case.id}/close-out/sent').status_code == 404, name
    assert clients['second'].post(f'/review/{case.id}/close-out/sent').status_code == 409
    sent = clients['reviewer'].post(f'/review/{case.id}/close-out/sent')
    assert sent.status_code == 200 and sent.json()['sent'] and sent.json()['sent_by_name'] == 'Reviewer'
    assert clients['reviewer'].post(f'/review/{case.id}/close-out/sent').status_code == 409
    assert clients['second'].get(f'/review/{case.id}/close-out').json()['sent']
    assert store.get(case.id).model_dump() == decided_case
    store.delete(case.id)


def test_send_claims_the_session_before_posting_and_releases_it_on_failure(scene, monkeypatch):
    """Nothing reaches the applicant unless the send is claimed; a failed post leaves the request unsent."""
    import engine.routes_package_review as routes
    from engine.review.sessions import Sessions
    store, clients, _ = scene
    case = claimed(scene)
    assert clients['reviewer'].post(f'/review/{case.id}/package-review').status_code == 201
    real = routes.mutate
    seen = []

    def failing(*args, **kwargs):
        seen.append(Sessions(store).get(case.id, 1)[0].information_request.sent_at)
        raise RuntimeError('thread write failed')

    monkeypatch.setattr(routes, 'mutate', failing)
    with pytest.raises(RuntimeError):
        clients['reviewer'].post(f'/review/{case.id}/package-review/1/information-request/send')
    assert seen and seen[0], 'the claim is stored before the message is posted'
    assert Sessions(store).get(case.id, 1)[0].information_request.sent_at is None
    monkeypatch.setattr(routes, 'mutate', real)
    sent = clients['reviewer'].post(f'/review/{case.id}/package-review/1/information-request/send')
    assert sent.status_code == 200, sent.text
    assert sent.json()['information_request']['message_id']
    assert len(clients['owner'].get(f'/cases/{case.id}/information-request').json()['requests']) == 1


def test_send_rechecks_the_claim_on_the_written_case(scene, monkeypatch):
    """A take-over between the route check and the post stops the send; the claim is released."""
    import engine.routes_package_review as routes
    from engine.review.sessions import Sessions
    store, clients, _ = scene
    case = claimed(scene)
    assert clients['reviewer'].post(f'/review/{case.id}/package-review').status_code == 201
    real = routes.mutate

    def taken_over(backend, case_id, user, change):
        current = store.get(case_id)
        current.claim = current.claim.model_copy(update={'reviewer_id': 'someone-else'})
        return change(current)

    monkeypatch.setattr(routes, 'mutate', taken_over)
    refused = clients['reviewer'].post(f'/review/{case.id}/package-review/1/information-request/send')
    assert refused.status_code == 409
    request = Sessions(store).get(case.id, 1)[0].information_request
    assert request.sent_at is None and request.message_id is None
    assert clients['owner'].get(f'/cases/{case.id}/information-request').json()['requests'] == []
    monkeypatch.setattr(routes, 'mutate', real)


def test_a_stuck_claim_keeps_the_original_error_is_hidden_and_expires(scene, monkeypatch):
    import engine.routes_package_review as routes
    from engine.review.sessions import Sessions
    store, clients, _ = scene
    case = claimed(scene)
    assert clients['reviewer'].post(f'/review/{case.id}/package-review').status_code == 201
    real_mutate, real_replace = routes.mutate, Sessions.replace
    calls = []

    def replace_then_fail(self, session, expected):
        calls.append(session.information_request.sent_at)
        if len(calls) > 1:
            raise OSError('store unavailable')
        return real_replace(self, session, expected)

    def outage(*_args, **_kwargs):
        raise RuntimeError('thread write failed')

    monkeypatch.setattr(routes, 'mutate', outage)
    monkeypatch.setattr(Sessions, 'replace', replace_then_fail)
    with pytest.raises(RuntimeError, match='thread write failed'):   # not the release's OSError
        clients['reviewer'].post(f'/review/{case.id}/package-review/1/information-request/send')
    monkeypatch.setattr(Sessions, 'replace', real_replace)
    stuck = Sessions(store).get(case.id, 1)[0].information_request
    assert stuck.sent_at and stuck.message_id is None
    assert clients['owner'].get(f'/cases/{case.id}/information-request').json()['requests'] == []
    busy = clients['reviewer'].post(f'/review/{case.id}/package-review/1/information-request/send')
    assert busy.status_code == 409 and busy.headers['retry-after']
    monkeypatch.setattr(routes, 'SEND_CLAIM_TTL', routes.timedelta(0))   # the claim has expired
    monkeypatch.setattr(routes, 'mutate', real_mutate)
    sent = clients['reviewer'].post(f'/review/{case.id}/package-review/1/information-request/send')
    assert sent.status_code == 200, sent.text
    assert len(clients['owner'].get(f'/cases/{case.id}/information-request').json()['requests']) == 1
