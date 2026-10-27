"""Route-level authorization matrix and administrative workflow (no live models)."""
from __future__ import annotations

from contextlib import ExitStack
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
import os
import threading
import uuid

from fastapi.testclient import TestClient
import pytest

from engine.account_models import MessageAuthor, StoredMessage
from engine.api import create_app
from engine.codes import Codes
from engine.models import Case
from engine.store import CaseStore
from engine.tests.case_builder_fixtures import complete_case, fact, store_with_synthetic_files
from engine.tests.test_accounts import signup, onboard


@pytest.fixture(scope='module', params=['sqlite', 'postgres'])
def scene(request, tmp_path_factory):
    if request.param == 'postgres' and not os.environ.get('TEST_DATABASE_URL'):
        pytest.skip('TEST_DATABASE_URL is not set; real Postgres required')
    with pytest.MonkeyPatch.context() as patch, ExitStack() as stack:
        patch.delenv('VERCEL', raising=False)
        patch.setenv('BATATIS_REVIEWER_CODES', '{"edmonton":"officer-secret","calgary":"calgary-secret"}')
        patch.setenv('BATATIS_AUTH_RATE_LIMIT', '100')
        if request.param == 'postgres':
            from engine.store_postgres import PostgresCaseStore
            store = PostgresCaseStore(os.environ['TEST_DATABASE_URL'])
        else:
            store = CaseStore(tmp_path_factory.mktemp('review') / 'cases.sqlite')
        app = create_app(store=store, codes=Codes())
        clients, users = {}, {}
        suffix = uuid.uuid4().hex
        for name, role, authority in [('owner', 'applicant', 'edmonton'), ('other', 'applicant', 'edmonton'),
                                     ('reviewer', 'reviewer', 'edmonton'), ('second', 'reviewer', 'edmonton'),
                                     ('foreign', 'reviewer', 'calgary'), ('anonymous', None, None)]:
            clients[name] = stack.enter_context(TestClient(app, base_url='http://localhost'))
            if role:
                assert signup(clients[name], name + suffix + '@example.test', name.title()).status_code == 201
                users[name] = onboard(clients[name], role, authority)
        yield store, clients, users


def owned(scene, status='draft', complete=False):
    store, _, users = scene
    case = complete_case() if complete else Case(title='Access matrix')
    case.owner_id, case.authority, case.status = users['owner']['id'], 'edmonton', status
    return store_with_synthetic_files(store, case) if complete else store.put(case)


@pytest.mark.parametrize('status', ['draft', 'submitted', 'in_review', 'returned', 'accepted', 'refused', 'withdrawn'])
def test_owner_cannot_send_new_messages_without_mutation(scene, status):
    store, clients, _ = scene
    owner = clients['owner']
    case = owned(scene, status)
    before = owner.get(f'/cases/{case.id}').json()
    messages = owner.get(f'/cases/{case.id}/messages').json()
    notifications = {name: clients[name].get('/me/notifications').json()
                     for name in ('owner', 'reviewer', 'second')}

    response = owner.post(f'/cases/{case.id}/messages', json={'body': 'Please review my correction.'})

    assert response.status_code == 403, response.text
    assert response.json()['detail'] == 'Only reviewing officers can send notices'
    assert owner.get(f'/cases/{case.id}').json() == before
    assert owner.get(f'/cases/{case.id}/messages').json() == messages
    for name, previous in notifications.items():
        assert clients[name].get('/me/notifications').json() == previous
    store.delete(case.id)


@pytest.mark.parametrize('status', ['draft', 'submitted', 'in_review', 'returned', 'accepted', 'refused', 'withdrawn'])
def test_officer_notice_send_access_matrix(scene, status):
    store, clients, users = scene
    case = owned(scene, status)
    owner = clients['owner']
    for name, client in clients.items():
        before = owner.get(f'/cases/{case.id}').json()
        allowed = name in {'reviewer', 'second'} and status in {'submitted', 'in_review', 'returned', 'accepted', 'refused'}
        body = f'SYNTHETIC notice from {name}.'
        response = client.post(f'/cases/{case.id}/messages', json={'body': body})
        assert response.status_code == (201 if allowed else 403 if name == 'owner' else 404), (name, status, response.text)
        after = owner.get(f'/cases/{case.id}').json()
        if not allowed:
            assert after == before
            continue
        notice = response.json()
        assert notice['body'] == body and notice['author']['id'] == users[name]['id']
        assert notice['author']['role'] == 'reviewer' and notice['kind'] == 'message'
        assert after['messages'][:-1] == before['messages']
        assert after['messages'][-1]['id'] == notice['id']
        assert after['version'] == before['version']
        assert {key: value for key, value in after.items() if key not in {'messages', 'version', 'updated_at', 'expires_at'}} == {
            key: value for key, value in before.items() if key not in {'messages', 'version', 'updated_at', 'expires_at'}}
        notes = owner.get('/me/notifications').json()['notifications']
        assert any(note['id'] == f'{case.id}:message:{notice["id"]}' and not note['read'] for note in notes)
    store.delete(case.id)


@pytest.mark.parametrize('status', ['draft', 'submitted', 'in_review', 'returned', 'accepted', 'refused', 'withdrawn'])
def test_historic_correspondence_and_read_receipts_remain_available(scene, status):
    store, clients, users = scene
    case = owned(scene, status)
    case.messages = [StoredMessage(
        author=MessageAuthor(id=users[name]['id'], name=name.title(), role=users[name]['role']),
        body=body, read_by=[users[name]['id']]) for name, body in (
            ('owner', 'SYNTHETIC historic applicant reply; keep verbatim.'),
            ('reviewer', 'SYNTHETIC officer follow-up; keep verbatim.'))]
    store.put(case, expected_version=case.version)
    owner = clients['owner']
    original = owner.get(f'/cases/{case.id}').json()
    for name, client in clients.items():
        allowed = name == 'owner' or (name in {'reviewer', 'second'} and status in {'submitted', 'in_review', 'returned', 'accepted', 'refused'})
        before = owner.get(f'/cases/{case.id}').json()
        view = client.get(f'/cases/{case.id}/messages')
        assert view.status_code == (200 if allowed else 404), (name, status, view.text)
        receipt = client.post(f'/cases/{case.id}/messages/read', json={})
        assert receipt.status_code == (204 if allowed else 404), (name, status, receipt.text)
        after = owner.get(f'/cases/{case.id}').json()
        if not allowed:
            assert after == before
            continue
        assert after['version'] == before['version']
        read = client.get(f'/cases/{case.id}/messages').json()['messages']
        assert all(message['read_by_me'] for message in read)
        assert [(message['id'], message['body'], message['author']) for message in read] == [
            (message['id'], message['body'], message['author']) for message in original['messages']]
        assert client.post(f'/cases/{case.id}/messages/read', json={}).status_code == 204
        assert owner.get(f'/cases/{case.id}').json() == after  # repeated receipts do not write
    final = owner.get(f'/cases/{case.id}').json()
    assert {key: value for key, value in final.items() if key not in {'messages', 'version', 'updated_at', 'expires_at'}} == {
        key: value for key, value in original.items() if key not in {'messages', 'version', 'updated_at', 'expires_at'}}
    notices = owner.get('/me/notifications').json()['notifications']
    assert any(note['id'] == f'{case.id}:message:{case.messages[1].id}' and note['read'] for note in notices)
    store.delete(case.id)


def test_multiple_applications_and_anonymous_legacy_creation(scene):
    store, clients, users = scene
    first = clients['owner'].post('/cases', json={'title': 'First', 'authority': 'edmonton'}).json()
    second = clients['owner'].post('/cases', json={'title': 'Second', 'authority': 'calgary'}).json()
    assert first['owner_id'] == second['owner_id'] == users['owner']['id']
    items = clients['owner'].get('/me/applications').json()['applications']
    assert {first['id'], second['id']} <= {item['id'] for item in items}
    assert items[0]['id'] == second['id']  # timestamp ties use the stable persisted ordering below
    assert all(item['completeness'] is None for item in items)
    assert clients['other'].get('/me/applications').json()['applications'] == []
    legacy = clients['anonymous'].post('/cases').json()
    assert legacy['owner_id'] is None
    assert clients['anonymous'].get('/cases/' + legacy['id']).status_code == 200
    assert clients['anonymous'].post('/cases/' + legacy['id'] + '/facts', json=fact('scope', 'site').model_dump()).status_code == 200
    assert clients['anonymous'].delete('/cases/' + legacy['id']).status_code == 204


READ_ROUTES = ['', '/gaps', '/process-fields', '/professional', '/section-d/issues', '/messages']


@pytest.mark.parametrize('status', ['draft', 'submitted', 'in_review', 'returned', 'accepted', 'refused', 'withdrawn'])
def test_notices_are_one_way_and_preserve_historical_applicant_messages(scene, status):
    from engine.account_models import MessageAuthor, StoredMessage
    store, clients, users = scene
    case = owned(scene, status)
    historical = StoredMessage(author=MessageAuthor(id=users['owner']['id'], name='Owner', role='applicant'),
                               body='SYNTHETIC historical applicant message.')
    case.messages.append(historical)
    store.put(case, expected_version=case.version)
    for name in clients:
        before = store.get(case.id).model_dump()
        response = clients[name].post(f'/cases/{case.id}/messages', json={'body': f'SYNTHETIC notice from {name}.'})
        allowed = name in {'reviewer', 'second'} and status in {'submitted', 'in_review', 'returned', 'accepted', 'refused'}
        assert response.status_code == (201 if allowed else 403 if name == 'owner' else 404), (name, status, response.text)
        after = store.get(case.id).model_dump()
        if allowed:
            assert after['version'] == before['version']
            assert {k: v for k, v in after.items() if k not in {'messages', 'updated_at', 'expires_at'}} == {
                k: v for k, v in before.items() if k not in {'messages', 'updated_at', 'expires_at'}}
        else:
            assert after == before
    thread = clients['owner'].get(f'/cases/{case.id}/messages').json()['messages']
    assert any(message['id'] == historical.id and message['body'] == historical.body for message in thread)
    store.delete(case.id)


@pytest.mark.parametrize('status', ['draft', 'submitted', 'in_review', 'returned', 'accepted', 'refused', 'withdrawn'])
def test_read_access_matrix_on_all_existing_routes(scene, status):
    store, clients, users = scene
    case = owned(scene, status)
    for name, client in clients.items():
        allowed = name == 'owner' or (name in {'reviewer', 'second'} and status in {'submitted', 'in_review', 'returned', 'accepted', 'refused'})
        for suffix in READ_ROUTES:
            response = client.get(f'/cases/{case.id}' + suffix)
            assert response.status_code == (200 if allowed else 404), (name, status, suffix, response.text)
        response = client.post(f'/cases/{case.id}/export', json={'draft': True})
        if not allowed:
            assert response.status_code == 404, (name, status, response.text)
        else:
            assert response.status_code != 404
    store.delete(case.id)


WRITE_ROUTES = [
    ('post', '/facts', {'field': 'scope', 'value': 'site', 'kind': 'pointed', 'status': 'confirmed',
                       'source': {'type': 'user_text', 'ref': 'matrix', 'quote': 'site'}}),
    ('put', '/jurisdiction', {'expected_version': 1, 'jurisdiction': {'id': 'edmonton', 'name': 'Edmonton'}}),
    ('post', '/section-d', {}),
    ('post', '/evidence', {'operation': 'create', 'evidence_id': 'report', 'expected_version': 1,
                         'title': 'Title', 'description': 'Listing', 'evidence_type': 'manufacturer lit'}),
    ('delete', '/evidence/report', {'expected_version': 1}),
]


@pytest.mark.parametrize('status', ['draft', 'submitted', 'in_review', 'returned', 'accepted', 'refused', 'withdrawn'])
def test_write_access_matrix_facts_evidence_files_and_selection(scene, status):
    store, clients, _ = scene
    case = owned(scene, status)
    for name, client in clients.items():
        for method, suffix, body in WRITE_ROUTES:
            expected = 404 if name != 'owner' else 409 if status not in {'draft', 'returned'} else None
            r = client.request(method, f'/cases/{case.id}' + suffix, json=body)
            if expected:
                assert r.status_code == expected, (name, status, suffix, r.text)
                if expected == 409:
                    assert r.json()['detail'] == 'Submitted applications are read-only until returned'
            else:
                assert r.status_code in {200, 409, 404}, (suffix, r.text)
        r = client.post(f'/cases/{case.id}/files', content=b'%PDF-1.4 test', headers={'Content-Type': 'application/pdf'})
        assert r.status_code == (201 if name == 'owner' and status in {'draft', 'returned'}
                                 else 409 if name == 'owner' else 404), (name, r.text)
    store.delete(case.id)


def test_owner_delete_and_other_review_routes_do_not_leak_ids(scene):
    store, clients, _ = scene
    case = owned(scene, 'submitted')
    for name in ['other', 'foreign', 'anonymous']:
        for method, path, body in [('post', f'/review/{case.id}/claim', {}),
                                   ('post', f'/review/{case.id}/decision', {'outcome': 'accept'}),
                                   ('delete', f'/review/{case.id}/claim', None),
                                   ('post', f'/cases/{case.id}/messages', {'body': 'Can you clarify?'}),
                                   ('post', f'/cases/{case.id}/messages/read', {}),
                                   ('delete', f'/cases/{case.id}', None)]:
            assert clients[name].request(method, path, json=body).status_code == 404
    assert clients['reviewer'].delete('/cases/' + case.id).status_code == 404
    assert clients['owner'].delete('/cases/' + case.id).status_code == 204


def test_submit_uses_the_same_blocking_gaps_and_changes_nothing_when_blocked(scene):
    store, clients, _ = scene
    case = owned(scene)
    before = store.get(case.id).model_dump()
    gaps = clients['owner'].get(f'/cases/{case.id}/gaps').json()['items']
    r = clients['owner'].post(f'/cases/{case.id}/submit', json={})
    assert r.status_code == 409
    assert r.json()['detail']['gaps'] == [g for g in gaps if g['severity'] == 'blocking' and g['submission_blocking']]
    assert store.get(case.id).model_dump() == before
    assert clients['other'].post(f'/cases/{case.id}/submit', json={}).status_code == 404


def test_complete_submit_claim_return_messages_resubmit_and_accept(scene):
    store, clients, users = scene
    owner, first, second = (clients[n] for n in ('owner', 'reviewer', 'second'))
    case = owned(scene, complete=True)
    assert owner.get(f'/cases/{case.id}/gaps').json()['items'] == []
    r = owner.post(f'/cases/{case.id}/submit', json={})
    assert r.status_code == 200 and r.json()['status'] == 'submitted', r.text
    assert r.json()['submitted_at']
    queue = first.get('/review/queue?status=submitted').json()['applications']
    assert any(item['id'] == case.id and item['applicant']['applicant_type'] == 'contractor' for item in queue)
    assert not any(item['id'] == case.id for item in clients['foreign'].get('/review/queue').json()['applications'])
    claim = first.post(f'/review/{case.id}/claim', json={})
    assert claim.status_code == 200
    assert first.post(f'/review/{case.id}/claim', json={}).json()['claim'] == claim.json()['claim']
    conflict = second.post(f'/review/{case.id}/claim', json={})
    assert conflict.status_code == 409 and conflict.json()['detail'] == 'Already being reviewed'
    assert conflict.json()['claim'] == claim.json()['claim']
    assert second.post(f'/review/{case.id}/decision', json={'outcome': 'accept'}).status_code == 409
    assert first.post(f'/review/{case.id}/decision', json={'outcome': 'return', 'message': 'Too short'}).status_code == 422
    items = [{'field': 'risk_assessment', 'note': 'Please identify the scope.'}]
    r = first.post(f'/review/{case.id}/decision', json={'outcome': 'return',
                      'message': 'Please clarify the stated scope and attachment revision.', 'items': items})
    assert r.status_code == 200 and r.json()['status'] == 'returned'
    original_decision = r.json()['decision']
    assert first.post(f'/cases/{case.id}/messages', json={'body': 'SYNTHETIC follow-up: retain the owner details.'}).status_code == 201
    assert owner.get(f'/cases/{case.id}/messages').json()['decision'] == original_decision
    applications = owner.get('/me/applications').json()['applications']
    entry = next(a for a in applications if a['id'] == case.id)
    assert entry['unread_messages'] == 2 and entry['reviewer']['name'] == 'Reviewer'
    messages = owner.get(f'/cases/{case.id}/messages').json()['messages']
    decision_message = next(message for message in messages if message['kind'] == 'decision')
    assert decision_message['items'] == [dict(items[0], gap_id=None)]
    assert not decision_message['read_by_me']
    assert owner.post(f'/cases/{case.id}/messages/read', json={}).status_code == 204
    assert owner.get(f'/cases/{case.id}/messages').json()['messages'][-1]['read_by_me']
    reply = owner.post(f'/cases/{case.id}/messages', json={'body': '<script>plain text</script> Revision clarified.'})
    assert reply.status_code == 403
    notice = first.post(f'/cases/{case.id}/messages', json={'body': '<script>plain text</script> Please confirm the revision.'})
    assert notice.status_code == 201 and notice.json()['body'].startswith('<script>')
    correction = fact('scope', 'site').model_dump()
    correction['source']['quote'] = 'SYNTHETIC applicant confirmation after the officer notice.'
    assert owner.post(f'/cases/{case.id}/facts', json=correction).status_code == 200
    assert first.get('/review/queue?mine=true').json()['applications']
    assert owner.post(f'/cases/{case.id}/submit', json={}).json()['status'] == 'submitted'
    assert first.post(f'/review/{case.id}/claim', json={}).status_code == 200
    assert first.post(f'/cases/{case.id}/messages', json={'body': 'SYNTHETIC final note before acceptance.'}).status_code == 201
    r = first.post(f'/review/{case.id}/decision', json={'outcome': 'accept', 'message': 'SYNTHETIC acceptance record note.'})
    assert r.status_code == 200 and r.json()['status'] == 'accepted'
    assert 'administratively complete' in r.json()['decision']['message']
    assert not any(word in r.json()['decision']['message'].lower() for word in ['approved', 'compliant', 'complies', 'safe'])
    assert [x['to_status'] for x in r.json()['status_history']] == ['submitted', 'in_review', 'returned', 'submitted', 'in_review', 'accepted']
    assert first.delete(f'/review/{case.id}/claim').status_code == 409
    assert owner.post(f'/cases/{case.id}/submit', json={}).status_code == 409
    final_decision = r.json()['decision']
    assert first.post(f'/cases/{case.id}/messages', json={'body': 'SYNTHETIC notice after acceptance.'}).status_code == 201
    reopened = owner.get(f'/cases/{case.id}/messages').json()
    assert reopened['decision'] == final_decision
    assert {message['body'] for message in reopened['messages']} >= {
        original_decision['message'], final_decision['message'], 'SYNTHETIC final note before acceptance.',
        'SYNTHETIC notice after acceptance.'}


def test_takeover_history_release_and_message_limits(scene):
    store, clients, users = scene
    case = owned(scene, 'submitted')
    first, second = clients['reviewer'], clients['second']
    assert first.post(f'/review/{case.id}/claim', json={}).status_code == 200
    assert second.delete(f'/review/{case.id}/claim').status_code == 409
    assert second.post(f'/review/{case.id}/claim', json={'take_over': True}).status_code == 200
    changed = first.get(f'/cases/{case.id}').json()
    assert 'Reviewer' in changed['status_history'][-1]['note'] and 'Second' in changed['status_history'][-1]['note']
    assert first.post(f'/review/{case.id}/decision', json={'outcome': 'accept'}).status_code == 409
    assert second.delete(f'/review/{case.id}/claim').status_code == 204
    assert store.get(case.id).status == 'submitted' and store.get(case.id).claim is None
    for body in ['', '   ', 'x' * 4001]:
        assert first.post(f'/cases/{case.id}/messages', json={'body': body}).status_code == 422
    assert first.post(f'/cases/{case.id}/messages', json={'body': 'x' * 4000}).status_code == 201


def test_simultaneous_officer_notices_preserve_both_messages(scene, monkeypatch):
    store, clients, _ = scene
    case = owned(scene, 'returned')
    before = clients['owner'].get(f'/cases/{case.id}').json()
    barrier, real_mutation = threading.Barrier(2), store.mutate_messages

    def synchronized_messages(case_id, user, operation):
        if case_id == case.id:
            barrier.wait(timeout=5)
        return real_mutation(case_id, user, operation)

    monkeypatch.setattr(store, 'mutate_messages', synchronized_messages)
    with ThreadPoolExecutor(max_workers=2) as pool:
        pending = [pool.submit(clients[name].post, f'/cases/{case.id}/messages',
                               json={'body': f'SYNTHETIC notice from {name}.'})
                   for name in ('reviewer', 'second')]
        responses = [result.result(timeout=10) for result in pending]
    assert [response.status_code for response in responses] == [201, 201], [r.text for r in responses]
    after = clients['owner'].get(f'/cases/{case.id}').json()
    assert after['version'] == before['version']
    assert {message['id'] for message in after['messages']} == {response.json()['id'] for response in responses}
    assert {key: value for key, value in after.items() if key not in {'messages', 'version', 'updated_at', 'expires_at'}} == {
        key: value for key, value in before.items() if key not in {'messages', 'version', 'updated_at', 'expires_at'}}
    store.delete(case.id)


def test_officer_notice_rechecks_self_review_after_a_concurrent_ownership_change(scene, monkeypatch):
    store, clients, users = scene
    case = owned(scene, 'submitted')
    before = clients['owner'].get(f'/cases/{case.id}').json()
    real_mutation, concurrent = store.mutate_messages, None

    def ownership_change_before_message(case_id, user, operation):
        nonlocal concurrent
        if case_id == case.id and concurrent is None:
            changed = store.get(case.id)
            changed.owner_id = users['reviewer']['id']
            concurrent = store.put(changed, expected_version=changed.version)
        return real_mutation(case_id, user, operation)

    monkeypatch.setattr(store, 'mutate_messages', ownership_change_before_message)
    response = clients['reviewer'].post(f'/cases/{case.id}/messages', json={'body': 'This notice must not be saved.'})

    assert response.status_code == 404 and concurrent is not None, response.text
    after = clients['reviewer'].get(f'/cases/{case.id}').json()
    assert after['owner_id'] == users['reviewer']['id'] and after['version'] == before['version'] + 1
    assert {key: value for key, value in after.items() if key not in {'owner_id', 'version', 'updated_at'}} == {
        key: value for key, value in before.items() if key not in {'owner_id', 'version', 'updated_at'}}
    store.delete(case.id)


def test_simultaneous_claims_have_exactly_one_winner(scene):
    store, clients, _ = scene
    case = owned(scene, 'submitted')
    barrier, responses = threading.Barrier(2), []

    def run(name):
        barrier.wait()
        responses.append(clients[name].post(f'/review/{case.id}/claim', json={}).status_code)

    threads = [threading.Thread(target=run, args=(name,)) for name in ['reviewer', 'second']]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert sorted(responses) == [200, 409]


def test_messages_and_review_history_are_purged_with_case(scene):
    store, clients, _ = scene
    case = owned(scene, 'submitted')
    clients['reviewer'].post(f'/review/{case.id}/claim', json={})
    clients['reviewer'].post(f'/cases/{case.id}/messages', json={'body': 'A private thread passage.'})
    expired = store.get(case.id)
    expired.status = 'refused'
    store.put(expired)
    from engine.tests.test_retention import _set_last_activity
    _set_last_activity(store, case.id, (datetime.now(timezone.utc) - timedelta(days=731)).isoformat())
    assert store.purge_expired() >= 1
    assert store.get(case.id) is None
    assert clients['owner'].get(f'/cases/{case.id}/messages').status_code == 404
    assert not any(a['id'] == case.id for a in clients['reviewer'].get('/review/queue').json()['applications'])


def test_new_merged_case_routes_inherit_the_central_guard(scene):
    from fastapi import APIRouter
    store, clients, _ = scene
    # An unmodified router, shaped like the concurrent library branch's new route.
    router = APIRouter()
    @router.get('/cases/{case_id}/future-guard-test')
    def future(case_id: str):
        return {'id': case_id}
    clients['owner'].app.include_router(router)
    case = owned(scene)
    assert clients['owner'].get(f'/cases/{case.id}/future-guard-test').status_code == 200
    assert clients['other'].get(f'/cases/{case.id}/future-guard-test').status_code == 404


def test_only_reviewable_authorities_can_be_targeted_or_submitted(scene):
    store, clients, users = scene
    assert clients['owner'].post('/cases', json={'title': 'Nowhere', 'authority': 'alberta-other'}).status_code == 422
    case = owned(scene, complete=True)
    case.authority = 'alberta-other'  # e.g. derived from an older jurisdiction choice
    case = store.put(case, expected_version=case.version)
    blocked = clients['owner'].post(f'/cases/{case.id}/submit', json={})
    assert blocked.status_code == 409
    assert store.get(case.id).status == 'draft'


def test_an_owner_who_becomes_a_reviewer_cannot_review_their_own_application(scene):
    store, clients, users = scene
    case = owned(scene, status='submitted', complete=True)
    # The owner onboards as an Edmonton reviewer with the shared code.
    became = onboard(clients['owner'], 'reviewer', 'edmonton')
    assert became['role'] == 'reviewer'
    assert clients['owner'].get('/auth/me').json()['user']['role'] == 'reviewer'  # still signed in
    try:
        assert clients['owner'].post(f'/review/{case.id}/claim', json={}).status_code == 404
        queue = clients['owner'].get('/review/queue').json()['applications']
        assert case.id not in {item['id'] for item in queue}
        assert clients['owner'].post(f'/review/{case.id}/decision', json={'outcome': 'accept'}).status_code == 404
        before = clients['owner'].get(f'/cases/{case.id}').json()
        assert clients['owner'].post(f'/cases/{case.id}/messages', json={'body': 'I am also a reviewer now.'}).status_code == 404
        assert clients['owner'].get(f'/cases/{case.id}').json() == before
        assert clients['owner'].get(f'/cases/{case.id}/messages').status_code == 200
        assert clients['owner'].post(f'/cases/{case.id}/messages/read', json={}).status_code == 204
        draft = owned(scene)
        assert clients['owner'].post(f'/cases/{draft.id}/submit', json={}).status_code == 403
    finally:
        # Leaving the reviewer role needs the same authority code.
        back = clients['owner'].post('/auth/onboarding', json={'role': 'applicant', 'applicant_type': 'contractor',
                                                               'access_code': 'officer-secret'})
        assert back.status_code == 200, back.text


def test_unowned_cases_have_no_message_thread(scene):
    store, clients, users = scene
    legacy = store.put(Case(title='Legacy anonymous'))
    for name in ('owner', 'reviewer'):
        assert clients[name].get(f'/cases/{legacy.id}/messages').status_code == 404
        assert clients[name].post(f'/cases/{legacy.id}/messages', json={'body': 'Hello there, anyone?'}).status_code == 404
        assert clients[name].post(f'/cases/{legacy.id}/messages/read', json={}).status_code == 404
    assert store.get(legacy.id).messages == []


def test_notifications_follow_the_other_partys_actions_and_mark_read(scene):
    store, clients, users = scene
    case = owned(scene, status='draft', complete=True)
    assert clients['owner'].post(f'/cases/{case.id}/submit', json={}).status_code == 200
    reviewer_view = clients['reviewer'].get('/me/notifications').json()
    assert any(n['case_id'] == case.id and n['status'] == 'submitted' and not n['read']
               for n in reviewer_view['notifications'])
    assert clients['reviewer'].post(f'/review/{case.id}/claim', json={}).status_code == 200
    returned = clients['reviewer'].post(f'/review/{case.id}/decision',
                                        json={'outcome': 'return', 'message': 'Please add the legal description.'})
    assert returned.status_code == 200
    assert clients['reviewer'].post(f'/cases/{case.id}/messages', json={'body': 'Happy to help with this one.'}).status_code == 201
    mine = clients['owner'].get('/me/notifications').json()
    kinds = {(n['kind'], n['status']) for n in mine['notifications'] if n['case_id'] == case.id}
    assert {('status', 'in_review'), ('status', 'returned'), ('message', None)} <= kinds
    assert all('approved' not in n['summary'] and 'url' not in n for n in mine['notifications'])
    assert mine['unread'] >= 3
    assert clients['owner'].post('/me/notifications/read', json={}).status_code == 204
    after = clients['owner'].get('/me/notifications').json()
    assert after['unread'] == 0
    assert not any(n['case_id'] == case.id and not n['read'] for n in after['notifications'])
    assert clients['owner'].get('/auth/me').status_code == 200  # marking read keeps the session
    assert clients['anonymous'].get('/me/notifications').status_code == 401


def test_a_released_claim_is_not_a_submission_and_repeats_collapse(scene):
    store, clients, users = scene
    case = owned(scene, status='draft', complete=True)
    assert clients['owner'].post(f'/cases/{case.id}/submit', json={}).status_code == 200
    for _ in range(2):  # claim, release, claim again
        assert clients['reviewer'].post(f'/review/{case.id}/claim', json={}).status_code == 200
        assert clients['reviewer'].delete(f'/review/{case.id}/claim').status_code == 204
    second = [n for n in clients['second'].get('/me/notifications').json()['notifications'] if n['case_id'] == case.id]
    assert [n['status'] for n in second] == ['submitted']  # only the applicant's submission
    mine = [n for n in clients['owner'].get('/me/notifications').json()['notifications'] if n['case_id'] == case.id]
    assert [n['status'] for n in mine].count('in_review') == 1
    assert len({n['id'] for n in mine}) == len(mine)


def test_accept_is_refused_while_blocking_gaps_remain(scene):
    store, clients, users = scene
    case = owned(scene, status='submitted')  # an incomplete application, e.g. edited outside the submit gate
    assert clients['reviewer'].post(f'/review/{case.id}/claim', json={}).status_code == 200
    refused = clients['reviewer'].post(f'/review/{case.id}/decision', json={'outcome': 'accept'})
    assert refused.status_code == 409
    assert refused.json()['detail']['gaps']
    assert store.get(case.id).status == 'in_review'
    returned = clients['reviewer'].post(f'/review/{case.id}/decision',
                                        json={'outcome': 'return', 'message': 'Please complete the application.'})
    assert returned.status_code == 200  # returning is always possible


def test_refuse_records_a_distinct_terminal_decision(scene):
    store, clients, users = scene
    owner = store.get_user(users['owner']['id'])
    owner.notifications_seen_at = None  # isolate unread assertions from this module's earlier mark-all-read test
    store.update_user(owner, revoke_sessions=False)
    case = owned(scene, status='submitted')
    reviewer = clients['reviewer']
    assert reviewer.post(f'/review/{case.id}/claim', json={}).status_code == 200
    before = store.get(case.id)
    reason = 'The requested administrative record has not been provided.'
    response = reviewer.post(f'/review/{case.id}/decision',
                             json={'outcome': 'refuse', 'message': reason, 'expected_version': before.version})
    assert response.status_code == 200, response.text
    assert response.json()['status'] == 'refused'
    saved = store.get(case.id)
    assert saved.status == 'refused'
    assert saved.decision.outcome == 'refuse'
    assert saved.decision.message.endswith(reason)
    assert saved.decision.message.startswith('Administrative refusal recorded by the reviewing officer.')
    assert 'Returned' not in saved.decision.message
    assert saved.decision.by_id == users['reviewer']['id']
    assert saved.version == before.version + 1
    assert saved.claim == before.claim
    assert saved.status_history[-1].from_status == 'in_review'
    assert saved.status_history[-1].to_status == 'refused'
    assert 'This is not a finding about design compliance or safety.' in saved.status_history[-1].note
    administrative_label = saved.status_history[-1].note.split(' This is not a finding')[0]
    assert not any(word in administrative_label.lower()
                   for word in ['compliant', 'non-compliance', 'safe', 'unsafe'])
    application = next(a for a in clients['owner'].get('/me/applications').json()['applications'] if a['id'] == case.id)
    assert application['status'] == 'refused' and application['unread_messages'] == 1
    assert application['reviewer']['name'] == 'Reviewer'
    for name in ['reviewer', 'second']:
        assert clients[name].get(f'/cases/{case.id}').json()['decision']['outcome'] == 'refuse'
        queue = clients[name].get('/review/queue?status=refused').json()['applications']
        entry = next(a for a in queue if a['id'] == case.id)
        assert entry['status'] == 'refused' and entry['decision']['outcome'] == 'refuse'
        assert entry['decision']['by_name'] == 'Reviewer'
    assert case.id in {a['id'] for a in reviewer.get('/review/queue?mine=true').json()['applications']}
    assert case.id not in {a['id'] for a in clients['foreign'].get('/review/queue?status=refused').json()['applications']}
    assert case.id not in {a['id'] for a in reviewer.get('/review/queue?status=returned').json()['applications']}
    message = clients['owner'].get(f'/cases/{case.id}/messages').json()['messages'][-1]
    assert message['kind'] == 'decision' and message['body'] == saved.decision.message
    assert message['items'] == [] and saved.decision.items == [] and not message['read_by_me']
    notes = [n for n in clients['owner'].get('/me/notifications').json()['notifications']
             if n['case_id'] == case.id and n['status'] == 'refused']
    assert len(notes) == 1 and not notes[0]['read']
    assert notes[0]['summary'] == f'Reviewer recorded an administrative refusal for {case.title}'
    assert not any(n['case_id'] == case.id and n['status'] == 'refused'
                   for n in clients['second'].get('/me/notifications').json()['notifications'])
    assert clients['owner'].post(f'/cases/{case.id}/messages/read', json={}).status_code == 204
    assert clients['owner'].get(f'/cases/{case.id}/messages').json()['messages'][-1]['read_by_me']
    assert clients['owner'].post('/me/notifications/read', json={}).status_code == 204
    assert all(n['read'] for n in clients['owner'].get('/me/notifications').json()['notifications']
               if n['case_id'] == case.id)
    # A final refusal keeps officer notices available without reopening applicant content or the review.
    before_notice = clients['owner'].get(f'/cases/{case.id}').json()
    assert clients['owner'].post(f'/cases/{case.id}/messages', json={'body': 'Acknowledged the recorded reason.'}).status_code == 403
    assert clients['owner'].get(f'/cases/{case.id}').json() == before_notice
    assert reviewer.post(f'/cases/{case.id}/messages', json={'body': 'Please retain this decision for your records.'}).status_code == 201
    assert clients['owner'].get(f'/cases/{case.id}').json()['decision'] == before_notice['decision']
    terminal = store.get(case.id).model_dump()
    assert clients['owner'].post(f'/cases/{case.id}/submit', json={}).status_code == 409
    for name in ['reviewer', 'second']:
        assert clients[name].post(f'/review/{case.id}/claim', json={'take_over': True}).status_code == 409
        assert clients[name].delete(f'/review/{case.id}/claim').status_code == 409
        for outcome in ['accept', 'return', 'refuse']:
            assert clients[name].post(f'/review/{case.id}/decision',
                                     json={'outcome': outcome, 'message': reason,
                                           'expected_version': terminal['version']}).status_code == 409
    assert store.get(case.id).model_dump() == terminal
    store.delete(case.id)


@pytest.mark.parametrize('reason', [None, '', '   ', 'Too short', ' ' * 10 + '123456789', 'x' * 4001])
def test_refusal_requires_a_written_reason_without_mutation(scene, reason):
    store, clients, _ = scene
    case = owned(scene, status='submitted')
    assert clients['reviewer'].post(f'/review/{case.id}/claim', json={}).status_code == 200
    before = store.get(case.id).model_dump()
    response = clients['reviewer'].post(f'/review/{case.id}/decision', json={
        'outcome': 'refuse', 'message': reason, 'expected_version': before['version']})
    assert response.status_code == 422, response.text
    assert store.get(case.id).model_dump() == before
    store.delete(case.id)


def test_refusal_requires_authority_and_current_claim(scene):
    store, clients, _ = scene
    case = owned(scene, status='submitted')
    body = {'outcome': 'refuse', 'message': 'Administrative record not provided.',
            'expected_version': case.version}
    before = store.get(case.id).model_dump()
    for name in ['reviewer', 'second', 'owner', 'other', 'foreign', 'anonymous']:
        response = clients[name].post(f'/review/{case.id}/decision', json=body)
        assert response.status_code == (409 if name in {'reviewer', 'second'} else 404), (name, response.text)
    assert store.get(case.id).model_dump() == before
    assert clients['reviewer'].post(f'/review/{case.id}/claim', json={}).status_code == 200
    before = store.get(case.id).model_dump()
    body['expected_version'] = before['version']
    assert clients['second'].post(f'/review/{case.id}/decision', json=body).status_code == 409
    assert store.get(case.id).model_dump() == before
    store.delete(case.id)


@pytest.mark.parametrize('competing_outcome', ['accept', 'return', 'refuse'])
def test_simultaneous_refusal_and_decision_have_exactly_one_winner(scene, monkeypatch, competing_outcome):
    store, clients, _ = scene
    case = owned(scene, status='submitted', complete=True)
    reviewer = clients['reviewer']
    assert reviewer.post(f'/review/{case.id}/claim', json={}).status_code == 200
    before = store.get(case.id)
    barrier, real_put = threading.Barrier(2), store.put

    def synchronized_put(candidate, *, expected_version=None):
        if candidate.id == case.id and expected_version == before.version:
            barrier.wait(timeout=5)  # both requests decide from the same persisted source version
        return real_put(candidate, expected_version=expected_version)

    monkeypatch.setattr(store, 'put', synchronized_put)
    with ThreadPoolExecutor(max_workers=2) as pool:
        pending = [pool.submit(reviewer.post, f'/review/{case.id}/decision',
                               json={'outcome': outcome, 'message': f'Written reason from request {index}.',
                                     'expected_version': before.version})
                   for index, outcome in enumerate(['refuse', competing_outcome])]
        responses = [result.result(timeout=10) for result in pending]
    assert sorted(r.status_code for r in responses) == [200, 409], [r.text for r in responses]
    winner = next(r.json() for r in responses if r.status_code == 200)
    saved = store.get(case.id)
    assert saved.decision.model_dump() == winner['decision']
    assert saved.status == winner['status'] and saved.version == before.version + 1
    assert len(saved.status_history) == len(before.status_history) + 1
    assert len(saved.messages) == len(before.messages) + 1
    assert saved.facts == before.facts and saved.section_c == before.section_c
    assert saved.evidence == before.evidence
    store.delete(case.id)


def test_refusal_rechecks_claim_after_a_concurrent_takeover(scene, monkeypatch):
    from engine.account_models import Claim

    store, clients, users = scene
    case = owned(scene, status='submitted')
    assert clients['reviewer'].post(f'/review/{case.id}/claim', json={}).status_code == 200
    before = store.get(case.id)
    real_put, raced = store.put, False

    def takeover_before_put(candidate, *, expected_version=None):
        nonlocal raced
        if candidate.id == case.id and not raced:
            raced = True
            concurrent = store.get(case.id)
            concurrent.claim = Claim(reviewer_id=users['second']['id'], reviewer_name='Second')
            real_put(concurrent, expected_version=concurrent.version)
        return real_put(candidate, expected_version=expected_version)

    monkeypatch.setattr(store, 'put', takeover_before_put)
    response = clients['reviewer'].post(f'/review/{case.id}/decision',
                                        json={'outcome': 'refuse', 'message': 'Administrative record not provided.',
                                              'expected_version': before.version})
    assert response.status_code == 409 and raced
    saved = store.get(case.id)
    assert saved.claim.reviewer_id == users['second']['id']
    assert saved.status == 'in_review' and saved.decision is None
    assert saved.messages == before.messages and saved.status_history == before.status_history
    assert saved.version == before.version + 1
    store.delete(case.id)
