"""Communication must not stale the applicant's content-edit acknowledgement."""
from contextlib import ExitStack, contextmanager
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
import json
import os
import sqlite3
import threading
import time
import uuid

from fastapi.testclient import TestClient
import pytest

from engine.account_models import User
from engine.accounts import COOKIE, digest
from engine.api import create_app
from engine.models import Case
from engine.store import CaseStore
from engine.tests.case_builder_fixtures import fact


@pytest.fixture(params=['sqlite', 'postgres'])
def communication_scene(request, tmp_path, monkeypatch):
    monkeypatch.delenv('VERCEL', raising=False)
    monkeypatch.setenv('BATATIS_LIVE', '0')
    if request.param == 'postgres':
        if not os.environ.get('TEST_DATABASE_URL'):
            pytest.skip('TEST_DATABASE_URL is not set; real Postgres required')
        from engine.store_postgres import PostgresCaseStore
        store = PostgresCaseStore(os.environ['TEST_DATABASE_URL'])
    else:
        store = CaseStore(tmp_path / 'communications.sqlite')
    app = create_app(store=store)
    with ExitStack() as stack:
        clients, users = {}, {}
        for name, role in [('owner', 'applicant'), ('officer', 'reviewer')]:
            user = User(email=f'{name}-{uuid.uuid4().hex}@example.test', name=name, role=role, onboarded=True,
                        authority='edmonton' if role == 'reviewer' else None,
                        applicant_type='contractor' if role == 'applicant' else None)
            assert store.create_user(user)
            token = f'journey_{uuid.uuid4().hex}'.ljust(43, '_')
            store.save_session(digest(token), user.id, time.time() + 3600)
            client = stack.enter_context(TestClient(app, base_url='http://localhost'))
            client.cookies.set(COOKIE, token)
            clients[name], users[name] = client, user
        case = store.put(Case(title='Synthetic returned application', owner_id=users['owner'].id,
                              authority='edmonton', status='submitted'))
        assert clients['officer'].post(f'/review/{case.id}/claim', json={}).status_code == 200
        returned = clients['officer'].post(f'/review/{case.id}/decision', json={
            'outcome': 'return', 'message': 'Please correct the legal description.'})
        assert returned.status_code == 200, returned.text
        try:
            yield store, clients, users, case.id
        finally:
            store.delete(case.id)
            with store.account_db() as db:
                for user in users.values():
                    db.execute('DELETE FROM account_users WHERE id=?', (user.id,))


def test_open_return_read_correct_and_versioned_save(communication_scene):
    store, clients, users, case_id = communication_scene
    owner = clients['owner']
    opened = owner.get(f'/cases/{case_id}').json()
    known = opened['version']
    messages = owner.get(f'/cases/{case_id}/messages').json()['messages']
    assert not messages[-1]['read_by_me']
    assert owner.post(f'/cases/{case_id}/messages/read', json={}).status_code == 204
    assert store.get(case_id).updated_at == opened['updated_at']  # reading is not retention-extending activity
    corrected = owner.post(f'/cases/{case_id}/facts', json=fact('legal_description', 'Lot 2, Block 3').model_dump())
    assert corrected.status_code == 200, corrected.text
    # This is the browser's conservative consecutive-write acknowledgement rule.
    if corrected.json()['version'] == known + 1:
        known = corrected.json()['version']
    saved = owner.post(f'/cases/{case_id}/section-d', json={'provisions': [], 'expected_version': known})
    assert saved.status_code == 200, (
        f"Opening the return left known={known}, server={store.get_version(case_id)}; {saved.text}")
    assert users['owner'].id in store.get(case_id).messages[-1].read_by


def listing(version, slot='synthetic-report'):
    return {'operation': 'create', 'evidence_id': slot, 'expected_version': version,
            'title': 'Synthetic applicant listing', 'description': 'Synthetic metadata only',
            'evidence_type': 'evaluation'}


def test_applicant_cannot_post_but_can_read_historical_replies(communication_scene):
    from engine.account_models import MessageAuthor, StoredMessage
    store, clients, users, case_id = communication_scene
    case = store.get(case_id)
    historical = StoredMessage(author=MessageAuthor(id=users['owner'].id, name='owner', role='applicant'),
                               body='Synthetic historical applicant reply.', read_by=[users['owner'].id])
    case.messages.append(historical)
    store.put(case, expected_version=case.version)
    before = store.get(case_id).model_dump()
    rejected = clients['owner'].post(f'/cases/{case_id}/messages', json={'body': 'Synthetic new reply.'})
    assert rejected.status_code == 403, rejected.text
    assert store.get(case_id).model_dump() == before
    thread = clients['owner'].get(f'/cases/{case_id}/messages').json()['messages']
    assert any(message['id'] == historical.id and message['body'] == historical.body for message in thread)


def test_receipt_marks_only_the_displayed_snapshot(communication_scene):
    store, clients, users, case_id = communication_scene
    owner, officer = clients['owner'], clients['officer']
    displayed = owner.get(f'/cases/{case_id}/messages').json()['messages']
    version = store.get_version(case_id)
    unseen = officer.post(f'/cases/{case_id}/messages', json={'body': 'Synthetic note arriving after display.'})
    assert unseen.status_code == 201
    receipt = {'message_ids': [message['id'] for message in displayed]}
    assert owner.post(f'/cases/{case_id}/messages/read', json=receipt).status_code == 204
    current = store.get(case_id)
    assert current.version == version
    assert all(users['owner'].id in message.read_by for message in current.messages if message.id in receipt['message_ids'])
    assert users['owner'].id not in current.messages[-1].read_by
    assert next(app for app in owner.get('/me/applications').json()['applications'] if app['id'] == case_id)['unread_messages'] == 1
    before = current.model_dump()
    assert owner.post(f'/cases/{case_id}/messages/read', json=receipt).status_code == 204
    assert owner.post(f'/cases/{case_id}/messages/read', json={'message_ids': []}).status_code == 204
    assert store.get(case_id).model_dump() == before


def test_conversation_and_idempotent_receipts_keep_content_revision(communication_scene, monkeypatch):
    store, clients, _, case_id = communication_scene
    owner, officer = clients['owner'], clients['officer']
    version = store.get_version(case_id)
    before = store.get(case_id).model_dump()
    assert owner.post(f'/cases/{case_id}/messages', json={'body': 'Synthetic rejected applicant reply.'}).status_code == 403
    assert store.get(case_id).model_dump() == before
    for client, text in [(officer, 'Synthetic officer notice.'), (officer, 'Synthetic officer follow-up.')]:
        response = client.post(f'/cases/{case_id}/messages', json={'body': text})
        assert response.status_code == 201, response.text
        assert response.json()['body'] == text and response.json()['read_by_me']
        assert store.get_version(case_id) == version
    for client in (owner, officer):
        assert client.post(f'/cases/{case_id}/messages/read', json={}).status_code == 204
        before = store.get(case_id).model_dump()
        monkeypatch.setattr('engine.account_store.now', lambda: '2099-01-01T00:00:00+00:00')
        assert client.post(f'/cases/{case_id}/messages/read', json={}).status_code == 204
        assert store.get(case_id).model_dump() == before
        assert all(message['read_by_me'] for message in client.get(f'/cases/{case_id}/messages').json()['messages'])
    assert store.get_version(case_id) == version


@pytest.mark.parametrize('route', ['section-d', 'evidence', 'identify'])
@pytest.mark.parametrize('external_edit', [False, True], ids=['communication-only', 'external-content-edit'])
def test_communication_survives_content_snapshot_race(communication_scene, monkeypatch, route, external_edit):
    store, clients, users, case_id = communication_scene
    owner, officer = clients['owner'], clients['officer']
    version = store.get_version(case_id)
    entered, release = threading.Event(), threading.Event()
    original_put = store.put

    def held_put(case, *, expected_version=None):
        if case.id == case_id and expected_version == version:
            entered.set()
            assert release.wait(15), 'test did not release content save'
        return original_put(case, expected_version=expected_version)

    monkeypatch.setattr(store, 'put', held_put)
    body = (listing(version) if route == 'evidence' else
            {'prose': 'Synthetic proposed exterior insulation board.', 'expected_version': version}
            if route == 'identify' else {'provisions': [], 'expected_version': version})
    with ThreadPoolExecutor(max_workers=1) as pool:
        pending = pool.submit(owner.post, f'/cases/{case_id}/{route}', json=body)
        try:
            assert entered.wait(15), 'content route did not reach its CAS save'
            note = officer.post(f'/cases/{case_id}/messages', json={'body': 'Synthetic concurrent follow-up.'})
            assert note.status_code == 201, note.text
            assert owner.post(f'/cases/{case_id}/messages/read', json={}).status_code == 204
            reply = owner.post(f'/cases/{case_id}/messages', json={'body': 'Synthetic concurrent reply.'})
            assert reply.status_code == 403, reply.text
            second = officer.post(f'/cases/{case_id}/messages', json={'body': 'Synthetic second concurrent follow-up.'})
            assert second.status_code == 201, second.text
            assert owner.post(f'/cases/{case_id}/messages/read', json={}).status_code == 204
            assert officer.post(f'/cases/{case_id}/messages/read', json={}).status_code == 204
            if external_edit:
                external = owner.post(f'/cases/{case_id}/facts',
                                      json=fact('owner_name', 'Synthetic concurrent content edit').model_dump())
                assert external.status_code == 200, external.text
        finally:
            release.set()
        saved = pending.result(timeout=15)
    assert saved.status_code == (409 if external_edit else 200), saved.text
    current = store.get(case_id)
    assert current.version == version + 1
    assert {note.json()['id'], second.json()['id']} <= {message.id for message in current.messages}
    assert all(message.body != 'Synthetic concurrent reply.' for message in current.messages)
    assert all(set(message.read_by) == {users['owner'].id, users['officer'].id} for message in current.messages)
    if external_edit:
        assert current.facts[-1].value == 'Synthetic concurrent content edit'
        assert current.evidence == [] and current.identify is None
    elif route == 'identify':
        assert saved.json()['trace']['usd'] == 0


def test_communication_does_not_make_stale_content_writes_valid(communication_scene):
    store, clients, _, case_id = communication_scene
    owner, officer = clients['owner'], clients['officer']
    version = owner.get(f'/cases/{case_id}').json()['version']
    # Another applicant session made a real content edit after this session opened.
    external = owner.post(f'/cases/{case_id}/facts', json=fact('owner_name', 'Synthetic external owner').model_dump())
    assert external.status_code == 200
    assert officer.post(f'/cases/{case_id}/messages', json={'body': 'Synthetic follow-up after external edit.'}).status_code == 201
    assert owner.post(f'/cases/{case_id}/messages/read', json={}).status_code == 204
    for route, body in [
        ('section-d', {'provisions': [], 'expected_version': version}),
        ('evidence', listing(version)),
        ('identify', {'prose': 'Synthetic exterior insulation board.', 'expected_version': version}),
    ]:
        rejected = owner.post(f'/cases/{case_id}/{route}', json=body)
        assert rejected.status_code == 409, (route, rejected.text)
        assert rejected.json()['detail'] == 'case was updated concurrently'
    stored = store.get(case_id)
    assert stored.version == external.json()['version'] == version + 1
    assert stored.facts[-1].value == 'Synthetic external owner'
    assert stored.evidence == [] and stored.identify is None


def test_concurrent_posts_and_receipts_preserve_every_message(communication_scene):
    store, clients, users, case_id = communication_scene
    version = store.get_version(case_id)
    bodies = [f'Synthetic concurrent message {n}.' for n in range(12)]

    def post(index):
        return clients['officer'].post(f'/cases/{case_id}/messages', json={'body': bodies[index]})

    with ThreadPoolExecutor(max_workers=6) as pool:
        responses = list(pool.map(post, range(len(bodies))))
    assert [response.status_code for response in responses] == [201] * len(bodies)
    assert len({response.json()['id'] for response in responses}) == len(bodies)
    with ThreadPoolExecutor(max_workers=2) as pool:
        receipts = list(pool.map(lambda client: client.post(f'/cases/{case_id}/messages/read', json={}), clients.values()))
    assert [receipt.status_code for receipt in receipts] == [204, 204]
    saved = store.get(case_id)
    assert saved.version == version and len(saved.messages) == len(bodies) + 1
    assert set(bodies) <= {message.body for message in saved.messages}
    assert all(set(message.read_by) == {users['owner'].id, users['officer'].id} for message in saved.messages)


def test_stale_unversioned_case_writer_locks_before_merging_thread(communication_scene, monkeypatch):
    store, clients, users, case_id = communication_scene
    stale = store.get(case_id)
    version = stale.version
    note = clients['officer'].post(f'/cases/{case_id}/messages', json={'body': 'Synthetic note after the case snapshot.'})
    assert note.status_code == 201
    assert clients['owner'].post(f'/cases/{case_id}/messages/read', json={}).status_code == 204
    stale.title = 'Synthetic unversioned content change'
    entered, release = threading.Event(), threading.Event()
    original_connect = store._connect if isinstance(store, CaseStore) else store._conn

    def paused_connect():
        con = original_connect()

        def before_write(statement):
            # put(None) has already read/merged its thread and is about to write.
            if statement.startswith('INSERT INTO cases '):
                entered.set()
                assert release.wait(10), 'test did not release unversioned content save'

        con.set_trace_callback(before_write)
        return con

    @contextmanager
    def paused_postgres_connection():
        with original_connect() as con:
            class HeldConnection:
                def execute(self, statement, params=()):
                    if statement.startswith('UPDATE cases SET data='):
                        entered.set()
                        assert release.wait(10), 'test did not release unversioned content save'
                    return con.execute(statement, params)

                def __getattr__(self, name):
                    return getattr(con, name)
            yield HeldConnection()

    monkeypatch.setattr(store, '_connect' if isinstance(store, CaseStore) else '_conn',
                        paused_connect if isinstance(store, CaseStore) else paused_postgres_connection)
    with ThreadPoolExecutor(max_workers=1) as pool:
        pending = pool.submit(store.put, stale)
        try:
            assert entered.wait(10), 'unversioned writer did not reach its whole-case write'
            # A deferred BEGIN acquired only at INSERT would still permit this
            # reservation. An atomic message writer must be excluded since the read.
            if isinstance(store, CaseStore):
                with sqlite3.connect(store.path, timeout=0) as competing:
                    with pytest.raises(sqlite3.OperationalError, match='locked'):
                        competing.execute('BEGIN IMMEDIATE')
            else:
                from psycopg.errors import LockNotAvailable
                with original_connect() as competing:
                    competing.execute("SET lock_timeout='100ms'")
                    with pytest.raises(LockNotAvailable):
                        competing.execute('SELECT id FROM cases WHERE id=%s FOR UPDATE', (case_id,))
                    competing.rollback()
        finally:
            release.set()
        saved = pending.result(timeout=10)
    current = store.get(case_id)
    assert current.version == saved.version == version + 1
    assert current.title == 'Synthetic unversioned content change'
    assert note.json()['id'] in {message.id for message in current.messages}
    assert all(users['owner'].id in message.read_by for message in current.messages)


@pytest.mark.parametrize('operation', ['messages', 'messages/read'])
def test_message_write_reauthorizes_current_row_under_lock(communication_scene, monkeypatch, operation):
    store, clients, _, case_id = communication_scene
    entered, release = threading.Event(), threading.Event()
    original_mutation = store.mutate_messages

    def held_mutation(*args, **kwargs):
        entered.set()
        assert release.wait(10), 'test did not release communication'
        return original_mutation(*args, **kwargs)

    monkeypatch.setattr(store, 'mutate_messages', held_mutation)
    with ThreadPoolExecutor(max_workers=1) as pool:
        pending = pool.submit(clients['officer'].post, f'/cases/{case_id}/{operation}',
                              json={'body': 'Synthetic stale-authority message.'} if operation == 'messages' else {})
        try:
            assert entered.wait(10), 'communication route did not authorize the initial case'
            changed = store.get(case_id)
            changed.authority = 'calgary'
            store.put(changed, expected_version=changed.version)
            before = store.get(case_id).model_dump()
        finally:
            release.set()
        rejected = pending.result(timeout=10)
    assert rejected.status_code == 404, rejected.text
    assert store.get(case_id).model_dump() == before


def test_notice_rechecks_self_review_after_concurrent_ownership_change(communication_scene, monkeypatch):
    store, clients, users, case_id = communication_scene
    original_mutation = store.mutate_messages

    def ownership_change(*args, **kwargs):
        changed = store.get(case_id)
        changed.owner_id = users['officer'].id
        store.put(changed, expected_version=changed.version)
        return original_mutation(*args, **kwargs)

    monkeypatch.setattr(store, 'mutate_messages', ownership_change)
    before = store.get(case_id)
    rejected = clients['officer'].post(f'/cases/{case_id}/messages', json={'body': 'Synthetic self-review note must not save.'})
    assert rejected.status_code == 404, rejected.text
    after = store.get(case_id)
    assert after.owner_id == users['officer'].id and after.version == before.version + 1
    assert after.messages == before.messages and after.decision == before.decision


def test_communication_rechecks_expiry_and_commits_purge(communication_scene, monkeypatch):
    store, clients, _, case_id = communication_scene
    original_mutation = store.mutate_messages

    def expired_mutation(*args, **kwargs):
        # Expire after request authorization and before the storage lock.
        with store.account_db() as db:
            column = 'data' if db.postgres else 'json'
            raw = db.execute(f'SELECT {column} FROM cases WHERE id=?', (case_id,)).fetchone()[0]
            raw = raw if db.postgres else json.loads(raw)
            raw['status'] = 'refused'
            raw['updated_at'] = (datetime.now(timezone.utc) - timedelta(days=731)).isoformat()
            from psycopg.types.json import Jsonb
            db.execute(f'UPDATE cases SET {column}=?, updated_at=? WHERE id=?',
                       (Jsonb(raw) if db.postgres else json.dumps(raw), raw['updated_at'], case_id))
        return original_mutation(*args, **kwargs)

    monkeypatch.setattr(store, 'mutate_messages', expired_mutation)
    assert clients['owner'].post(f'/cases/{case_id}/messages/read', json={}).status_code == 404
    # Inspect raw storage, since get() itself could otherwise hide a rolled-back purge.
    with store.account_db() as db:
        assert db.execute('SELECT 1 FROM cases WHERE id=?', (case_id,)).fetchone() is None
