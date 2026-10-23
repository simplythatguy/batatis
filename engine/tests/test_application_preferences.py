"""Owner list organization through HTTP and the two real durable store adapters."""
from concurrent.futures import ThreadPoolExecutor, TimeoutError
from contextlib import ExitStack, contextmanager
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
import os
import secrets
import threading
import time
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from pydantic import ValidationError

from engine.access import AccessContext, current_access
from engine.account_models import Claim, Decision, MessageAuthor, StatusChange, StoredMessage, User
from engine.accounts import COOKIE, digest
from engine.api import create_app
from engine.models import Case, Fact, Source
from engine.retention import reset_purge_clock
from engine.store import CaseStore


@pytest.fixture(params=['sqlite', 'postgres'])
def scene(request, tmp_path, monkeypatch):
    monkeypatch.delenv('VERCEL', raising=False)
    monkeypatch.setenv('BATATIS_PROVIDER', 'fake')
    monkeypatch.setenv('BATATIS_LIVE', '0')
    reset_purge_clock()
    if request.param == 'postgres':
        url = os.environ.get('TEST_DATABASE_URL')
        if not url:
            pytest.skip('TEST_DATABASE_URL is not set; real isolated Postgres required')
        from engine.store_postgres import PostgresCaseStore
        store = PostgresCaseStore(url)
    else:
        store = CaseStore(tmp_path / 'preferences.sqlite')
    state = SimpleNamespace(store=store, clients={}, users={}, created=[])
    with ExitStack() as stack:
        app = create_app(store=store)
        for name, role, authority in [('owner', 'applicant', None), ('other', 'applicant', None),
                                      ('reviewer', 'reviewer', 'edmonton'), ('foreign', 'reviewer', 'calgary'),
                                      ('anonymous', None, None)]:
            client = stack.enter_context(TestClient(app, base_url='http://localhost'))
            state.clients[name] = client
            if role:
                user = User(email=secrets.token_hex(12) + '@example.test', name=name.title(),
                            role=role, authority=authority, onboarded=True)
                assert store.create_user(user)
                state.users[name] = user
                # Seed a real server-side session; HTTP still runs the normal auth dependency.
                token = secrets.token_urlsafe(32)
                store.save_session(digest(token), user.id, time.time() + 3600)
                client.cookies.set(COOKIE, token, domain='localhost.local')
        try:
            yield state
        finally:
            for case_id in state.created:
                store.delete(case_id)
            with store.account_db() as db:
                for user in state.users.values():
                    db.execute('DELETE FROM account_sessions WHERE user_id=?', (user.id,))
                    db.execute('DELETE FROM account_users WHERE id=?', (user.id,))
            reset_purge_clock()


def owned(scene, **changes):
    case = scene.store.put(Case(**({'title': 'SYNTHETIC application', 'authority': 'edmonton',
                                   'owner_id': scene.users['owner'].id} | changes)))
    scene.created.append(case.id)
    return case


def test_existing_application_defaults_are_false_without_changing_the_case(scene):
    case = owned(scene)
    before = scene.store.get(case.id)
    response = scene.clients['owner'].get('/api/me/applications')
    assert response.status_code == 200, response.text
    assert response.headers['cache-control'] == 'no-store'
    assert response.json()['applications'] == [{
        'id': case.id, 'title': 'SYNTHETIC application', 'status': 'draft', 'authority': 'edmonton',
        'updated_at': case.updated_at, 'submitted_at': None, 'completeness': None,
        'unread_messages': 0, 'reviewer': None, 'archived': False, 'pinned': False,
    }]
    assert scene.store.get(case.id) == before


def patch(client, case_id, changes, prefix='/api'):
    return client.patch(f'{prefix}/me/applications/{case_id}/preferences', json=changes)


def payload(response):
    return {key: value for key, value in response.json().items() if key != 'meta'}


def test_pin_archive_restore_and_unpin_survive_reopen_without_case_writes(scene):
    case = owned(scene)
    client = scene.clients['owner']
    for changes, expected in [({'pinned': True}, {'archived': False, 'pinned': True}),
                              ({'archived': True}, {'archived': True, 'pinned': True}),
                              ({'archived': False}, {'archived': False, 'pinned': True}),
                              ({'pinned': False}, {'archived': False, 'pinned': False})]:
        response = patch(client, case.id, changes)
        assert response.status_code == 200, response.text
        assert payload(response) == expected
        assert response.headers['cache-control'] == 'no-store'
        store = (CaseStore(scene.store.path) if isinstance(scene.store, CaseStore)
                 else type(scene.store)(scene.store.url))
        with TestClient(create_app(store=store), base_url='http://localhost') as reopened:
            reopened.cookies.set(COOKIE, client.cookies.get(COOKIE), domain='localhost.local')
            items = reopened.get('/me/applications').json()['applications']
            assert len(items) == 1 and items[0]['id'] == case.id  # archives remain in the list
            assert {key: items[0][key] for key in ('archived', 'pinned')} == expected
            assert payload(reopened.get(f'/cases/{case.id}')) == case.model_dump(mode='json')
        assert scene.store.get(case.id) == case
        replay = patch(client, case.id, changes, prefix='')
        assert replay.status_code == 200 and payload(replay) == expected
        assert scene.store.get(case.id) == case


def test_store_partial_preferences_preserve_omitted_values_and_case_version(scene):
    case = owned(scene)
    store, user = scene.store, scene.users['owner']
    assert store.list_application_preferences(user.id) == {}
    assert store.patch_application_preferences(case.id, user, {'pinned': True}).model_dump() == {
        'archived': False, 'pinned': True}
    assert store.patch_application_preferences(case.id, user, {'archived': True}).model_dump() == {
        'archived': True, 'pinned': True}
    assert store.list_application_preferences(user.id)[case.id].model_dump() == {
        'archived': True, 'pinned': True}
    assert store.get_snapshot(case.id) == (case, case.version)


def stored_row(store, case_id):
    """The DB seam also checks that list metadata never rewrites opaque stored fields."""
    with store.account_db() as db:
        column = 'data' if db.postgres else 'json'
        return db.execute(f'SELECT {column},version,updated_at FROM cases WHERE id=?', (case_id,)).fetchone()


def preference_count(store, case_id):
    with store.account_db() as db:
        return db.execute('SELECT COUNT(*) FROM account_application_preferences WHERE application_id=?',
                          (case_id,)).fetchone()[0]


@pytest.mark.parametrize('status', ['draft', 'returned', 'submitted', 'in_review', 'accepted', 'refused', 'withdrawn'])
def test_organization_preserves_workflow_queue_notices_and_rename_gates(scene, status):
    reviewer = scene.users['reviewer']
    outcome = {'returned': 'return', 'accepted': 'accept', 'refused': 'refuse'}.get(status)
    case = owned(scene, status=status, title_is_manual=True,
        submitted_at='2026-10-22T00:00:00+00:00' if status != 'draft' else None,
        claim=Claim(reviewer_id=reviewer.id, reviewer_name=reviewer.name) if outcome or status == 'in_review' else None,
        decision=Decision(outcome=outcome, by_id=reviewer.id, by_name=reviewer.name,
                          message='SYNTHETIC officer reason, preserve verbatim.') if outcome else None,
        status_history=[StatusChange(by_id=reviewer.id, by_name=reviewer.name,
                                     from_status='in_review', to_status=status)] if outcome else [],
        messages=[StoredMessage(author=MessageAuthor(id=reviewer.id, name=reviewer.name, role='reviewer'),
                                body='SYNTHETIC stored notice', read_by=[reviewer.id])],
        facts=[Fact(field='project.description', value='SYNTHETIC proposed design', kind='pointed',
                    status='confirmed', source=Source(type='user_text', ref='sent-1', quote='SYNTHETIC proposed design'))])
    client = scene.clients['owner']
    row = stored_row(scene.store, case.id)
    before = client.get(f'/cases/{case.id}').json()
    queue = scene.clients['reviewer'].get('/review/queue').json()
    notices = {name: scene.clients[name].get('/me/notifications').json() for name in ('owner', 'reviewer')}
    account = scene.store.user_credentials(scene.users['owner'].email)
    cookie = client.cookies.get(COOKIE)

    for _ in range(2):  # an identical patch must have no lifecycle or version effect either
        response = patch(client, case.id, {'archived': True, 'pinned': True})
        assert response.status_code == 200, response.text
        assert payload(response) == {'archived': True, 'pinned': True}
        assert stored_row(scene.store, case.id) == row
        assert client.get(f'/cases/{case.id}').json() == before
        assert scene.clients['reviewer'].get('/review/queue').json() == queue
        for name, previous in notices.items():
            assert scene.clients[name].get('/me/notifications').json() == previous
    assert scene.store.user_credentials(scene.users['owner'].email) == account
    assert client.cookies.get(COOKIE) == cookie
    assert client.get('/auth/me').status_code == 200

    renamed = client.patch(f'/cases/{case.id}/title', json={'title': 'SYNTHETIC manual rename'})
    assert renamed.status_code == (200 if status in {'draft', 'returned'} else 409), renamed.text
    if status not in {'draft', 'returned'}:
        assert stored_row(scene.store, case.id) == row
        edited = client.post(f'/cases/{case.id}/facts', json={
            'field': 'project.answer', 'value': 'Must not save', 'kind': 'pointed',
            'source': {'type': 'user_text', 'ref': 'attempt'},
        })
        assert edited.status_code == 409, edited.text
        assert stored_row(scene.store, case.id) == row
    else:
        assert renamed.json()['title_is_manual'] is True


def test_only_authenticated_owner_can_organize_even_legacy_and_unknown_ids(scene):
    case = owned(scene, status='submitted')
    legacy = owned(scene, owner_id=None)
    unknown = 'case_missing_' + secrets.token_hex(12)
    for name, client in scene.clients.items():
        for case_id in [case.id, legacy.id, unknown]:
            response = patch(client, case_id, {'archived': True})
            expected = 401 if name == 'anonymous' else 200 if name == 'owner' and case_id == case.id else 404
            assert response.status_code == expected, (name, case_id, response.text)
            if expected == 404:
                assert response.json()['detail'] == 'case not found'
    assert scene.store.get(case.id) == case
    assert scene.store.get(legacy.id) == legacy
    assert preference_count(scene.store, legacy.id) == 0
    assert preference_count(scene.store, unknown) == 0


def test_signed_in_reviewer_owns_preferences_only_for_their_own_application(scene):
    case = owned(scene, owner_id=scene.users['reviewer'].id, status='refused')
    client = scene.clients['reviewer']
    response = patch(client, case.id, {'pinned': True})
    assert response.status_code == 200, response.text
    assert payload(response) == {'archived': False, 'pinned': True}
    assert client.get('/me/applications').json()['applications'][0]['pinned'] is True
    assert patch(scene.clients['owner'], case.id, {'pinned': True}).status_code == 404
    assert client.patch(f'/cases/{case.id}/title', json={'title': 'Blocked'}).status_code == 409
    assert scene.store.get(case.id) == case


def test_signed_in_ownership_does_not_require_an_onboarded_role(scene):
    case = owned(scene, status='submitted')
    user = scene.users['owner'].model_copy(update={'role': None, 'onboarded': False})
    scene.store.update_user(user, revoke_sessions=False)
    response = patch(scene.clients['owner'], case.id, {'archived': True})
    assert response.status_code == 200, response.text
    assert payload(response) == {'archived': True, 'pinned': False}
    assert scene.store.get(case.id) == case


@pytest.mark.parametrize('body', [
    {}, {'archived': None}, {'pinned': None}, {'pinned': True, 'archived': None},
    {'archived': 0}, {'archived': 1}, {'pinned': 'true'}, {'pinned': 'false'},
    {'archived': 'yes'}, {'archived': 1.0}, {'archived': []}, {'pinned': {}},
    {'archived': True, 'status': 'withdrawn'}, {'pinned': True, 'owner_id': 'someone'},
    {'title': 'Forbidden'}, {'preferences': {'archived': True}}, [], None,
])
def test_nonempty_partial_strict_booleans_and_no_extra_fields(scene, body):
    case = owned(scene)
    response = patch(scene.clients['owner'], case.id, body)
    assert response.status_code == 422, response.text
    assert scene.store.list_application_preferences(scene.users['owner'].id) == {}
    assert scene.store.get(case.id) == case


@pytest.mark.parametrize('body', ['', 'null', '{"pinned":'])
def test_missing_or_malformed_json_does_not_write(scene, body):
    case = owned(scene)
    response = scene.clients['owner'].patch(f'/me/applications/{case.id}/preferences',
                                           content=body, headers={'content-type': 'application/json'})
    assert response.status_code == 422, response.text
    assert preference_count(scene.store, case.id) == 0
    assert scene.store.get(case.id) == case


def test_store_also_rejects_invalid_partial_updates(scene):
    case = owned(scene)
    for changes in [{}, {'archived': 1}, {'pinned': None}, {'pinned': True, 'status': 'withdrawn'}]:
        with pytest.raises(ValidationError):
            scene.store.patch_application_preferences(case.id, scene.users['owner'], changes)
    assert scene.store.get(case.id) == case
    assert preference_count(scene.store, case.id) == 0


def test_list_scopes_do_not_leak_archives_or_preferences_between_accounts(scene):
    archived = owned(scene)
    active = owned(scene, title='SYNTHETIC active')
    other = owned(scene, owner_id=scene.users['other'].id)
    legacy = owned(scene, owner_id=None)
    assert patch(scene.clients['owner'], archived.id, {'archived': True, 'pinned': True}).status_code == 200
    assert patch(scene.clients['other'], other.id, {'pinned': True}).status_code == 200
    owner_items = {item['id']: item for item in scene.clients['owner'].get('/me/applications').json()['applications']}
    assert set(owner_items) == {archived.id, active.id}
    assert owner_items[archived.id]['archived'] is True and owner_items[archived.id]['pinned'] is True
    assert owner_items[active.id]['archived'] is False and owner_items[active.id]['pinned'] is False
    other_items = scene.clients['other'].get('/me/applications').json()['applications']
    assert [item['id'] for item in other_items] == [other.id]
    assert other_items[0]['archived'] is False and other_items[0]['pinned'] is True
    assert scene.clients['anonymous'].get('/me/applications').status_code == 401
    assert scene.store.list_application_preferences(scene.users['reviewer'].id) == {}
    assert preference_count(scene.store, legacy.id) == 0


def test_preferences_are_account_relative_after_an_ownership_change(scene):
    case = owned(scene, status='submitted')
    assert patch(scene.clients['owner'], case.id, {'archived': True, 'pinned': True}).status_code == 200
    case.owner_id = scene.users['other'].id
    scene.store.put(case, expected_version=case.version)
    assert scene.clients['owner'].get('/me/applications').json()['applications'] == []
    assert scene.store.list_application_preferences(scene.users['owner'].id) == {}
    assert patch(scene.clients['owner'], case.id, {'pinned': False}).status_code == 404
    item = scene.clients['other'].get('/me/applications').json()['applications'][0]
    assert item['archived'] is False and item['pinned'] is False
    assert patch(scene.clients['other'], case.id, {'pinned': True}).status_code == 200
    assert scene.store.list_application_preferences(scene.users['other'].id)[case.id].model_dump() == {
        'archived': False, 'pinned': True}
    assert preference_count(scene.store, case.id) == 2
    assert scene.clients['other'].delete(f'/cases/{case.id}').status_code == 204
    assert preference_count(scene.store, case.id) == 0


def test_application_list_rechecks_ownership_after_candidate_read(scene, monkeypatch):
    case = owned(scene, owner_id=scene.users['reviewer'].id, status='submitted')
    assert patch(scene.clients['reviewer'], case.id, {'archived': True}).status_code == 200
    get = scene.store.get
    transferred = False

    def read_after_transfer(case_id):
        nonlocal transferred
        if case_id == case.id and not transferred:
            transferred = True

            def transfer():
                current = get(case_id)
                current.owner_id = scene.users['other'].id
                scene.store.put(current, expected_version=current.version)

            # A database writer commits between the list's candidate query and
            # hydration. This user retains reviewer read access, not ownership.
            with ThreadPoolExecutor(max_workers=1) as writer:
                writer.submit(transfer).result(timeout=10)
        return get(case_id)

    monkeypatch.setattr(scene.store, 'get', read_after_transfer)
    response = scene.clients['reviewer'].get('/me/applications')
    assert response.status_code == 200, response.text
    assert response.json()['applications'] == []


def test_anonymous_is_rejected_before_valid_json_body_validation(scene):
    case = owned(scene)
    for changes in [{}, {'pinned': 'true'}, {'archived': None}]:
        response = patch(scene.clients['anonymous'], case.id, changes)
        assert response.status_code == 401, response.text
    assert preference_count(scene.store, case.id) == 0


def test_schema_documents_exact_preference_seam(scene):
    from engine.schema_export import schema
    defs = schema()['$defs']
    result = defs['ApplicationPreferences']
    body = defs['ApplicationPreferencesPatch']
    assert set(result['required']) == {'archived', 'pinned'}
    assert set(body['properties']) == {'archived', 'pinned'}
    assert body['additionalProperties'] is False and body['minProperties'] == 1
    for name in ('archived', 'pinned'):
        assert result['properties'][name]['type'] == body['properties'][name]['type'] == 'boolean'
        assert defs['ApplicationSummary']['properties'][name]['default'] is False
        assert name in defs['ApplicationSummary']['required']
    route = scene.clients['owner'].get('/openapi.json').json()['paths'][
        '/me/applications/{application_id}/preferences']['patch']
    assert route['requestBody']['required'] is True
    assert route['responses']['200']['content']['application/json']['schema']['$ref'].endswith('/ApplicationPreferences')


def test_concurrent_independent_http_partial_patches_keep_both_updates(scene):
    case = owned(scene, status='refused')
    before = stored_row(scene.store, case.id)
    client = scene.clients['owner']
    for _ in range(5):
        assert patch(client, case.id, {'archived': False, 'pinned': False}).status_code == 200
        barrier = threading.Barrier(2)

        def apply(changes):
            barrier.wait(timeout=10)
            return patch(client, case.id, changes)

        with ThreadPoolExecutor(max_workers=2) as workers:
            futures = [workers.submit(apply, changes) for changes in ({'archived': True}, {'pinned': True})]
            responses = [future.result(timeout=15) for future in futures]
        assert [response.status_code for response in responses] == [200, 200]
        flags = scene.store.list_application_preferences(scene.users['owner'].id)[case.id]
        assert flags.model_dump() == {'archived': True, 'pinned': True}
        assert stored_row(scene.store, case.id) == before


@contextmanager
def locked_case(store, case_id):
    with store.account_db() as db:
        column, lock = ('data', ' FOR UPDATE') if db.postgres else ('json', '')
        row = db.execute(f'SELECT {column} FROM cases WHERE id=?' + lock, (case_id,)).fetchone()
        yield db, row[0] if db.postgres else json.loads(row[0])


@pytest.mark.parametrize('change', ['delete', 'owner', 'expiry'])
@pytest.mark.parametrize('existing', [False, True])
def test_waiting_store_patch_rechecks_current_existence_owner_and_retention(scene, change, existing):
    case = owned(scene)
    store, user = scene.store, scene.users['owner']
    if existing:
        assert store.patch_application_preferences(case.id, user, {'pinned': True}) is not None
    started = threading.Event()

    def waiting_patch():
        started.set()
        return store.patch_application_preferences(case.id, user, {'archived': True})

    with ThreadPoolExecutor(max_workers=1) as workers:
        with locked_case(store, case.id) as (db, data):
            future = workers.submit(waiting_patch)
            assert started.wait(timeout=5)
            with pytest.raises(TimeoutError):
                future.result(timeout=0.05)  # the case lock is held by this transaction
            if change == 'delete':
                db.execute('DELETE FROM cases WHERE id=?', (case.id,))
            else:
                if change == 'owner':
                    data['owner_id'] = scene.users['other'].id
                else:
                    data['created_at'] = (datetime.now(timezone.utc) - timedelta(days=8)).isoformat()
                if db.postgres:
                    from psycopg.types.json import Jsonb
                    db.execute('UPDATE cases SET data=? WHERE id=?', (Jsonb(data), case.id))
                else:
                    db.execute('UPDATE cases SET json=? WHERE id=?', (json.dumps(data), case.id))
        if change == 'owner':
            with pytest.raises(HTTPException) as error:
                future.result(timeout=10)
            assert error.value.status_code == 404
            assert scene.store.list_application_preferences(user.id) == {}
            assert preference_count(store, case.id) == int(existing)
        else:
            assert future.result(timeout=10) is None
            assert store.get(case.id) is None
            assert preference_count(store, case.id) == 0


@pytest.mark.parametrize('status', ['draft', 'returned', 'submitted', 'in_review', 'accepted', 'refused', 'withdrawn'])
def test_existing_delete_policy_removes_files_and_all_account_preferences(scene, status):
    case = owned(scene, status=status)
    file = scene.store.put_file(case.id, 'SYNTHETIC.pdf', b'%PDF-1.4 SYNTHETIC')
    assert patch(scene.clients['owner'], case.id, {'pinned': True, 'archived': True}).status_code == 200
    before = stored_row(scene.store, case.id)
    for name in ('other', 'reviewer', 'foreign', 'anonymous'):
        denied = scene.clients[name].delete(f'/cases/{case.id}')
        assert denied.status_code == 404, denied.text
        assert stored_row(scene.store, case.id) == before
        assert scene.store.get_file(case.id, file['id']) is not None
        assert preference_count(scene.store, case.id) == 1
    response = scene.clients['owner'].delete(f'/api/cases/{case.id}')
    assert response.status_code == 204 and response.content == b''
    assert scene.store.get(case.id) is None
    assert scene.store.get_file(case.id, file['id']) is None
    assert preference_count(scene.store, case.id) == 0
    assert patch(scene.clients['owner'], case.id, {'pinned': True}).status_code == 404
    assert scene.clients['owner'].delete(f'/cases/{case.id}').status_code == 404


def test_existing_store_delete_rechecks_latest_owner_under_lock(scene):
    case = owned(scene, status='accepted')
    file = scene.store.put_file(case.id, 'SYNTHETIC.pdf', b'%PDF-1.4 SYNTHETIC')
    assert patch(scene.clients['owner'], case.id, {'pinned': True}).status_code == 200
    started = threading.Event()

    def waiting_delete():
        token = current_access.set(AccessContext(scene.users['owner'], 'delete'))
        try:
            started.set()
            return scene.store.delete(case.id)
        finally:
            current_access.reset(token)

    with ThreadPoolExecutor(max_workers=1) as workers:
        with locked_case(scene.store, case.id) as (db, data):
            future = workers.submit(waiting_delete)
            assert started.wait(timeout=5)
            with pytest.raises(TimeoutError):
                future.result(timeout=0.05)
            data['owner_id'] = scene.users['other'].id
            if db.postgres:
                from psycopg.types.json import Jsonb
                db.execute('UPDATE cases SET data=? WHERE id=?', (Jsonb(data), case.id))
            else:
                db.execute('UPDATE cases SET json=? WHERE id=?', (json.dumps(data), case.id))
        with pytest.raises(HTTPException) as error:
            future.result(timeout=10)
        assert error.value.status_code == 404
    assert scene.store.get(case.id).owner_id == scene.users['other'].id
    assert scene.store.get_file(case.id, file['id']) is not None
    assert preference_count(scene.store, case.id) == 1


@pytest.mark.parametrize('access', ['purge', 'preferences', 'fact'])
def test_retention_deletes_preferences_and_files_between_sweeps(scene, access):
    case = owned(scene)
    store, client = scene.store, scene.clients['owner']
    file = store.put_file(case.id, 'SYNTHETIC.pdf', b'%PDF-1.4 SYNTHETIC')
    assert patch(client, case.id, {'archived': True}).status_code == 200  # consume the HTTP sweep window
    case.created_at = (datetime.now(timezone.utc) - timedelta(days=8)).isoformat()
    store.put(case, expected_version=case.version)
    if access == 'purge':
        assert store.purge_expired() >= 1
    elif access == 'preferences':
        response = patch(client, case.id, {'pinned': True})
        assert response.status_code == 404, response.text
    else:
        assert store.add_fact(case.id, Fact(field='scope', value='site', kind='pointed',
                                          source=Source(type='user_text', ref='expired'))) is None
    assert preference_count(store, case.id) == 0
    assert store.get_file(case.id, file['id']) is None
    assert store.get(case.id) is None
    assert store.purge_expired() == 0


def test_account_deletion_cascades_preferences_without_rewriting_the_case(scene):
    case = owned(scene)
    user = scene.users['owner']
    assert patch(scene.clients['owner'], case.id, {'pinned': True}).status_code == 200
    before = stored_row(scene.store, case.id)
    # No public account-deletion route exists; test the account DB deletion seam.
    with scene.store.account_db() as db:
        db.execute('DELETE FROM account_users WHERE id=?', (user.id,))
    assert preference_count(scene.store, case.id) == 0
    assert stored_row(scene.store, case.id) == before
    assert scene.store.patch_application_preferences(case.id, user, {'archived': True}) is None
    assert patch(scene.clients['owner'], case.id, {'archived': True}).status_code == 401
    assert scene.clients['owner'].get('/auth/me').status_code == 401


def test_additive_migration_preserves_old_cases_and_sessions(scene):
    case = owned(scene, status='submitted')
    before = stored_row(scene.store, case.id)
    with scene.store.account_db() as db:
        db.execute('DROP TABLE account_application_preferences')
    reopened = (CaseStore(scene.store.path) if isinstance(scene.store, CaseStore)
                else type(scene.store)(scene.store.url))
    assert stored_row(reopened, case.id) == before
    assert scene.clients['owner'].get('/auth/me').status_code == 200
    item = scene.clients['owner'].get('/me/applications').json()['applications'][0]
    assert item['archived'] is False and item['pinned'] is False
    assert patch(scene.clients['owner'], case.id, {'pinned': True}).status_code == 200
    assert reopened.list_application_preferences(scene.users['owner'].id)[case.id].pinned is True


def test_preferences_preserve_stored_source_hash_review_versions_and_closeout(scene):
    from engine.models_review import InformationRequest, InputFile, ReviewSession
    from engine.review.sessions import Sessions

    reviewer = scene.users['reviewer']
    case = owned(scene, status='accepted', decision=Decision(outcome='accept', by_id=reviewer.id,
                 by_name=reviewer.name, message='SYNTHETIC existing administrative decision'))
    data = b'%PDF-1.4\nSYNTHETIC existing source bytes; not professional evidence.'
    source_hash = sha256(data).hexdigest()
    file = scene.store.put_file(case.id, 'SYNTHETIC.pdf', data)
    sessions = Sessions(scene.store)
    for version in (1, 2):
        sessions.add(ReviewSession(package_id=case.id, case_id=case.id, authority='edmonton',
            version=version, case_version=case.version, created_at=case.created_at,
            created_by_name='SYNTHETIC reviewer', input_kind='case',
            files=[InputFile(name='SYNTHETIC.pdf', sha256=source_hash, size=len(data), role='attachment')],
            information_request=InformationRequest(intro='SYNTHETIC prior review', items=[])))
    sessions.record_closeout(case.id, case.decision.at, case.created_at, reviewer.name)
    before = sessions.list(case.id)
    raw = sessions.get(case.id, 2)[1]
    closeout = sessions.closeout(case.id)
    case_row = stored_row(scene.store, case.id)
    for changes in ({'archived': True}, {'pinned': True}, {'archived': False}):
        assert patch(scene.clients['owner'], case.id, changes).status_code == 200
        assert stored_row(scene.store, case.id) == case_row
        assert sessions.list(case.id) == before
        assert sessions.get(case.id, 2)[1] == raw
        assert sessions.closeout(case.id) == closeout
        assert sha256(scene.store.get_file(case.id, file['id'])['data']).hexdigest() == source_hash


def test_database_write_failure_is_not_reported_as_saved(scene):
    case = owned(scene)
    client, store = scene.clients['owner'], scene.store
    assert patch(client, case.id, {'pinned': True}).status_code == 200
    before = stored_row(store, case.id)
    with store.account_db() as db:
        if db.postgres:
            db.execute('ALTER TABLE account_application_preferences ADD CONSTRAINT reject_archive CHECK (NOT archived)')
        else:
            db.execute("CREATE TRIGGER reject_archive BEFORE INSERT ON account_application_preferences "
                       "WHEN NEW.archived BEGIN SELECT RAISE(ABORT, 'SYNTHETIC write rejection'); END")
    try:
        with TestClient(create_app(store=store), base_url='http://localhost', raise_server_exceptions=False) as failing:
            failing.cookies.set(COOKIE, client.cookies.get(COOKIE), domain='localhost.local')
            response = patch(failing, case.id, {'archived': True})
            assert response.status_code == 500, response.text
        assert stored_row(store, case.id) == before
        assert store.list_application_preferences(scene.users['owner'].id)[case.id].model_dump() == {
            'archived': False, 'pinned': True}
    finally:
        with store.account_db() as db:
            db.execute('ALTER TABLE account_application_preferences DROP CONSTRAINT reject_archive'
                       if db.postgres else 'DROP TRIGGER reject_archive')
