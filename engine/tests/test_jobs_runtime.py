"""Durable public/runtime acceptance on SQLite and optional isolated PostgreSQL schemas."""
from __future__ import annotations

import json
import os
import secrets
import subprocess
import sys
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from pydantic import BaseModel, ConfigDict, Field, TypeAdapter

from engine import ai_access, llm_gate
from engine.access import AccessContext, current_access
from engine.account_models import MessageAuthor, StoredMessage, User
from engine.api import create_app
from engine.jobs import JobHandler, JobRegistry, JobRuntime, in_process_enabled
from engine.jobs_store import LostLease
from engine.models import Case, Fact, Source
from engine.routes_intake import IntakeRequest, create_job_handler
from engine.store import CaseStore
from engine.tests._network_guard import block_network


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    for key in ('VERCEL', 'BATATIS_LIVE', 'BATATIS_LIVE_ELEPHANT', 'BATATIS_AI_ACCESS_CODES',
                'BATATIS_IDENTIFY_CONFIG', 'BATATIS_STORE', 'DATABASE_URL'):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv('BATATIS_JOBS_WORKER', '0')
    monkeypatch.setenv('BATATIS_PROVIDER', 'fake')
    monkeypatch.setenv('BATATIS_IDENTIFY_RATE_LIMIT', '1000')
    llm_gate.reset_for_tests()
    blocked = block_network(monkeypatch)
    yield
    assert blocked == []
    llm_gate.reset_for_tests()


@pytest.fixture(params=['sqlite', 'postgres'])
def database(request, tmp_path):
    if request.param == 'sqlite':
        path = tmp_path / 'jobs.sqlite'
        yield CaseStore(path), lambda: CaseStore(path)
        return
    url = os.environ.get('TEST_DATABASE_URL')
    if not url:
        pytest.skip('TEST_DATABASE_URL is not configured')
    import psycopg
    from psycopg import sql
    from psycopg.conninfo import make_conninfo
    from engine.store_postgres import PostgresCaseStore
    schema = 'jobs_test_' + uuid.uuid4().hex
    with psycopg.connect(url, autocommit=True) as con:
        con.execute(sql.SQL('CREATE SCHEMA {}').format(sql.Identifier(schema)))
    scoped_url = make_conninfo(url, options=f'-c search_path={schema}')
    try:
        yield PostgresCaseStore(scoped_url), lambda: PostgresCaseStore(scoped_url)
    finally:
        with psycopg.connect(url, autocommit=True) as con:
            con.execute(sql.SQL('DROP SCHEMA {} CASCADE').format(sql.Identifier(schema)))


class Clock:
    def __init__(self):
        self.value = time.time()

    def __call__(self):
        return self.value

    def advance(self, seconds):
        self.value += seconds


class Input(BaseModel):
    model_config = ConfigDict(extra='forbid')
    note: str = Field(default='Computed title', max_length=100)
    expected_version: int | None = Field(default=None, ge=1)


class Output(BaseModel):
    title: str = Field(max_length=100)


def generic_handler(compute=None, apply=None):
    def default_compute(case, body, context):
        context.progress('work')
        return Output(title=body.note)

    def default_apply(case, body, output):
        case.title = output.title

    return JobHandler(kind='slow_test', revision='v1', request_model=Input, result_adapter=TypeAdapter(Output),
                      read_fields=('facts', 'title'), write_fields=('title',), stages=('work',),
                      compute=compute or default_compute, apply=apply or default_apply, result_path='/summary')


def runtime_for(store, handler=None, **kwargs):
    registry = JobRegistry()
    registry.register(handler or generic_handler())
    return JobRuntime(store, registry, backoff_seconds=0, **kwargs)


def actor(store):
    user = User(email='owner@example.test', name='Owner Name', role='applicant', onboarded=True)
    assert store.create_user(user)
    return user


def fact(value, field='storeys'):
    return Fact(field=field, value=value, kind='pointed', status='confirmed',
                source=Source(type='user_text', ref='Applicant', quote=str(value)))


def test_generic_kind_rejoins_concurrent_equivalent_requests_and_keys(database):
    store, fresh = database
    case = store.put(Case())
    runtime = runtime_for(store)
    barrier = threading.Barrier(6)

    def start(index):
        barrier.wait()
        other = runtime_for(fresh())
        return other.enqueue(case.id, 'slow_test', Input(), None, idempotency_key=f'key-{index}')

    with ThreadPoolExecutor(max_workers=6) as pool:
        jobs = list(pool.map(start, range(6)))
    assert len({job.id for job in jobs}) == 1
    assert jobs[0].attempts == 0
    with pytest.raises(HTTPException) as rejected:
        runtime.enqueue(case.id, 'slow_test', Input(note='Different'), None, idempotency_key='key-0')
    assert rejected.value.status_code == 409
    assert runtime.run_once()
    assert not runtime.run_once()
    # The exact key rejoins after the result advanced the case version.
    repeated = runtime.enqueue(case.id, 'slow_test', Input(), None, idempotency_key='key-0')
    assert repeated.id == jobs[0].id and repeated.state == 'succeeded'
    assert store.get(case.id).version == 2


def test_new_runtime_recovers_persisted_input_without_http_context(database):
    store, fresh = database
    user = actor(store)
    case = store.put(Case(owner_id=user.id))
    first = runtime_for(store)
    started = first.enqueue(case.id, 'slow_test', Input(), user)
    second = runtime_for(fresh())
    # A stale ambient read-only request must not control a background execution.
    token = current_access.set(AccessContext(None, 'read'))
    grant = ai_access.GRANTED.set(False)
    try:
        assert second.run_once()
    finally:
        current_access.reset(token)
        ai_access.GRANTED.reset(grant)
    result = second.repository.get(case.id, started.id, user.id)
    assert result.state == 'succeeded' and result.result_version == 2


def test_expired_lease_cannot_renew_or_commit_and_result_applies_once(database):
    store, _ = database
    clock = Clock()
    runtime = runtime_for(store, clock=clock, lease_seconds=10, heartbeat_interval=1)
    case = store.put(Case())
    job = runtime.enqueue(case.id, 'slow_test', Input(), None)
    first = runtime.repository.claim('crashed')
    prepared = runtime.repository.prepare(first, runtime.registry.get('slow_test'))
    clock.advance(11)
    assert not runtime.repository.heartbeat(first)
    second = runtime.repository.claim('replacement')
    assert second.token > first.token
    with pytest.raises(LostLease):
        runtime.repository.complete(first, runtime.registry.get('slow_test'), prepared.body,
                                    Output(title='Old worker'), ai_granted=True)
    replacement = runtime.repository.prepare(second, runtime.registry.get('slow_test'))
    assert runtime.repository.complete(second, runtime.registry.get('slow_test'), replacement.body,
                                       Output(title='Replacement'), ai_granted=True)
    with pytest.raises(LostLease):
        runtime.repository.complete(second, runtime.registry.get('slow_test'), replacement.body,
                                    Output(title='Duplicate'), ai_granted=True)
    assert store.get(case.id).title == 'Replacement'
    assert store.get(case.id).version == 2
    assert runtime.repository.get(case.id, job.id, None).attempts == 2


def test_long_computation_heartbeats_keep_worker_registry_available(database):
    store, _ = database
    clock = Clock()
    runtime = runtime_for(store, clock=clock, lease_seconds=60, heartbeat_interval=10)
    case = store.put(Case())
    runtime.enqueue(case.id, 'slow_test', Input(), None)
    lease = runtime.repository.claim('long-computation')
    for _ in range(8):
        clock.advance(30)
        assert runtime.repository.heartbeat(lease)
        assert runtime.health(case.id).worker_available
        assert runtime.health(case.id).running == 1
    clock.advance(61)
    assert not runtime.health(case.id).worker_available


@pytest.mark.parametrize('change', ['editor', 'fact', 'unrelated'])
def test_save_while_intake_is_blocked_never_waits_for_compute_or_loses_edits(database, monkeypatch, change):
    store, _ = database
    from engine.intake import service
    entered, release = threading.Event(), threading.Event()
    original = service.run

    def blocked(*args, **kwargs):
        entered.set()
        assert release.wait(10)
        return original(*args, **kwargs)

    monkeypatch.setattr(service, 'run', blocked)
    app = create_app(store)
    client = TestClient(app)
    case = client.post('/cases').json()
    path = f"/cases/{case['id']}"
    started = client.post(path + '/intake/jobs', json={'text': 'A two-storey house with a small window.', 'model': False})
    assert started.status_code == 202
    runtime = app.state.jobs()
    with ThreadPoolExecutor(max_workers=2) as pool:
        worker = pool.submit(runtime.run_once)
        try:
            assert entered.wait(5)
            patch = {'expected_version': case['version']}
            if change == 'editor':
                patch['applicant_draft'] = {'question_text': {'permit': {'base': '', 'value': 'Still typing'}}}
            elif change == 'fact':
                patch['facts'] = [fact(3).model_dump(mode='json')]
            else:
                patch['selected_articles'] = []
            saved = pool.submit(client.patch, path + '/draft', json=patch).result(timeout=3)
            assert saved.status_code == 200, saved.text
            assert not worker.done()
            assert client.get(started.headers['location']).json()['stage'] == 'reading'
        finally:
            release.set()
        assert worker.result(timeout=8)
    final = client.get(started.headers['location']).json()
    latest = client.get(path).json()
    if change == 'fact':
        assert final['state'] == 'superseded'
        assert latest['facts'][-1]['value'] == 3
        assert latest['intake'] is None
    else:
        assert final['state'] == 'succeeded' and final['result_version'] == 3
        if change == 'editor':
            assert latest['applicant_draft']['question_text']['permit']['value'] == 'Still typing'
        else:
            assert latest['selected_articles'] == []


def test_messages_same_content_version_are_preserved_at_apply(database):
    store, _ = database
    user = actor(store)
    case = store.put(Case(owner_id=user.id))
    runtime = runtime_for(store)
    job = runtime.enqueue(case.id, 'slow_test', Input(), user)
    lease = runtime.repository.claim('worker')
    prepared = runtime.repository.prepare(lease, runtime.registry.get('slow_test'))
    message = StoredMessage(author=MessageAuthor(id=user.id, name=user.name, role=user.role), body='New message')
    store.mutate_messages(case.id, user, lambda current: current.messages.append(message))
    assert runtime.repository.complete(lease, runtime.registry.get('slow_test'), prepared.body,
                                       Output(title='Complete'), ai_granted=True)
    assert store.get(case.id).messages[0].id == message.id
    assert runtime.repository.get(case.id, job.id, user.id).state == 'succeeded'


@pytest.mark.parametrize('change', ['delete_case', 'delete_account', 'owner', 'status', 'ai_access'])
def test_revocation_and_deletion_during_compute_cannot_resurrect_or_apply(database, monkeypatch, change):
    store, _ = database
    user = actor(store)
    if change == 'ai_access':
        code = 'an-access-code-with-enough-entropy'
        monkeypatch.setenv('BATATIS_AI_ACCESS_CODES', json.dumps({'team': code}))
        user.ai_access = 'team'
        user.ai_access_fingerprint = ai_access.fingerprint(code)
        store.update_user(user)
    case = store.put(Case(owner_id=user.id))
    handler = replace(generic_handler(), uses_ai=lambda body: True)
    runtime = runtime_for(store, handler)
    job = runtime.enqueue(case.id, 'slow_test', Input(), user, idempotency_key='delete-with-actor')
    lease = runtime.repository.claim('worker')
    prepared = runtime.repository.prepare(lease, runtime.registry.get('slow_test'))
    if change == 'delete_case':
        store.delete(case.id)
    elif change == 'delete_account':
        with store.account_db() as db:
            db.execute('DELETE FROM account_users WHERE id=?', (user.id,))
    elif change == 'ai_access':
        user.ai_access = user.ai_access_fingerprint = None
        store.update_user(user)
    else:
        current = store.get(case.id)
        if change == 'owner':
            current.owner_id = 'another-owner'
        else:
            current.status = 'submitted'
        store.put(current, expected_version=current.version)
    if change in {'delete_case', 'delete_account'}:
        with pytest.raises(LostLease):
            runtime.repository.complete(lease, runtime.registry.get('slow_test'), prepared.body,
                                        Output(title='Must never appear'), ai_granted=prepared.ai_granted)
        with store.account_db() as db:
            assert db.execute('SELECT COUNT(*) FROM background_jobs').fetchone()[0] == 0
            assert db.execute('SELECT COUNT(*) FROM background_job_requests').fetchone()[0] == 0
    else:
        assert not runtime.repository.complete(lease, runtime.registry.get('slow_test'), prepared.body,
                                               Output(title='Must never appear'), ai_granted=prepared.ai_granted)
        with store.account_db() as db:
            assert db.execute('SELECT state FROM background_jobs WHERE id=?', (job.id,)).fetchone()[0] == 'cancelled'
    latest = store.get(case.id)
    assert latest is None if change == 'delete_case' else latest.title is None


def test_execution_reloads_current_names_and_ai_access_context(database, monkeypatch):
    store, _ = database
    user = actor(store)
    code = 'an-access-code-with-enough-entropy'
    monkeypatch.setenv('BATATIS_AI_ACCESS_CODES', json.dumps({'team': code}))
    user.ai_access, user.ai_access_fingerprint = 'team', ai_access.fingerprint(code)
    store.update_user(user)
    sent = []

    def transport(system, text, schema):
        assert ai_access.allowed()
        sent.append(text)
        return {'facts': []}, {}

    handler = create_job_handler(lambda: None, transport_factory=lambda ip: (transport, 'fake'))
    runtime = runtime_for(store, handler)
    case = store.put(Case(owner_id=user.id))
    store.patch_draft(case.id, {'applicant_draft': {'choices': {'private': 'PRIVATE-UNSENT-EDITOR'}}},
                      expected_version=case.version)
    runtime.enqueue(case.id, 'intake', IntakeRequest(text='New Current Name proposes a house, email x@y.test.'), user)
    user.name = 'New Current Name'
    store.update_user(user)
    assert runtime.run_once()
    assert sent and all('New Current Name' not in value and 'x@y.test' not in value for value in sent)
    assert all('PRIVATE-UNSENT-EDITOR' not in value for value in sent)
    assert not ai_access.GRANTED.get()


def test_bounded_retry_backoff_generic_errors_and_explicit_identity(database):
    store, _ = database
    clock = Clock()
    attempts = []

    def fail(case, body, context):
        attempts.append(1)
        context.progress('work')
        raise RuntimeError('PRIVATE-PROVIDER-PAYLOAD owner@example.test')

    runtime = runtime_for(store, generic_handler(compute=fail), clock=clock)
    runtime.repository.backoff_seconds = 5
    case = store.put(Case())
    started = runtime.enqueue(case.id, 'slow_test', Input(), None)
    assert runtime.run_once()
    queued = runtime.repository.get(case.id, started.id, None)
    assert queued.state == 'queued' and queued.error.stage == 'work' and queued.attempts == 1
    assert 'PRIVATE' not in queued.model_dump_json() and 'owner@' not in queued.model_dump_json()
    assert not runtime.run_once()
    clock.advance(5)
    assert runtime.run_once()
    clock.advance(10)
    assert runtime.run_once()
    exhausted = runtime.repository.get(case.id, started.id, None)
    assert exhausted.state == 'failed' and exhausted.attempts == 3 and not exhausted.can_retry
    assert len(attempts) == 3
    with pytest.raises(HTTPException) as rejected:
        runtime.retry(case.id, started.id, None)
    assert rejected.value.status_code == 409
    # A cancelled identity is requeued, with the same input/key and lifetime budget.
    other_case = store.put(Case())
    other = runtime.enqueue(other_case.id, 'slow_test', Input(), None, idempotency_key='stable')
    cancelled = runtime.repository.cancel(other_case.id, other.id, None)
    assert cancelled.can_retry
    retried = runtime.retry(other_case.id, other.id, None)
    assert retried.id == other.id and retried.attempts == 0 and retried.state == 'queued'


def test_cancel_fences_live_worker_and_retry_keeps_identity(database):
    store, _ = database
    runtime = runtime_for(store)
    case = store.put(Case())
    job = runtime.enqueue(case.id, 'slow_test', Input(), None)
    lease = runtime.repository.claim('worker')
    prepared = runtime.repository.prepare(lease, runtime.registry.get('slow_test'))
    assert runtime.repository.cancel(case.id, job.id, None).state == 'cancelled'
    assert not runtime.repository.heartbeat(lease)
    with pytest.raises(LostLease):
        runtime.repository.complete(lease, runtime.registry.get('slow_test'), prepared.body,
                                    Output(title='Cancelled'), ai_granted=True)
    assert runtime.retry(case.id, job.id, None).id == job.id
    assert runtime.run_once()
    final = runtime.repository.get(case.id, job.id, None)
    assert final.attempts == 2 and final.state == 'succeeded'


def test_result_validation_and_apply_footprint_cannot_change_capabilities(database):
    store, _ = database
    case = store.put(Case())

    def unsafe_apply(current, body, output):
        current.owner_id = 'injected-owner'
        current.title = output.title

    runtime = runtime_for(store, generic_handler(apply=unsafe_apply))
    job = runtime.enqueue(case.id, 'slow_test', Input(), None)
    runtime.run_once()
    assert store.get(case.id).owner_id is None and store.get(case.id).version == 1
    assert runtime.repository.get(case.id, job.id, None).state == 'failed'
    invalid = replace(generic_handler(), kind='invalid_test', compute=lambda *args: {'title': 'x' * 101})
    runtime.registry.register(invalid)
    bad = runtime.enqueue(case.id, 'invalid_test', Input(), None)
    runtime.run_once()
    assert runtime.repository.get(case.id, bad.id, None).state == 'failed'
    assert store.get(case.id).version == 1


def test_worker_crash_process_persists_claim_for_recovery(database):
    store, fresh = database
    runtime = runtime_for(store)
    case = store.put(Case())
    job = runtime.enqueue(case.id, 'slow_test', Input(), None)
    environment = os.environ.copy()
    if hasattr(store, 'path'):
        environment.update(BATATIS_STORE='file', BATATIS_CASES=str(store.path))
    else:
        environment.update(BATATIS_STORE='postgres', DATABASE_URL=store.url)
    script = ('import os\nfrom engine.store import open_store\n'
              'from engine.jobs_store import JobStore\n'
              'repo=JobStore(open_store(),lease_seconds=1,backoff_seconds=0)\n'
              "assert repo.claim('crashed-process')\nos._exit(17)\n")
    crashed = subprocess.run([sys.executable, '-c', script], env=environment, capture_output=True, timeout=15)
    assert crashed.returncode == 17, crashed.stderr.decode()
    clock = Clock()
    clock.advance(5)
    replacement = runtime_for(fresh(), clock=clock)
    assert replacement.run_once()
    final = replacement.repository.get(case.id, job.id, None)
    assert final.state == 'succeeded' and final.attempts == 2


def test_http_scoping_no_store_and_current_reviewer_permissions(database):
    store, _ = database
    app = create_app(store)
    owner, stranger, reviewer = TestClient(app), TestClient(app), TestClient(app)
    owner_user = actor(store)
    other = User(email='stranger@example.test', name='Stranger')
    officer = User(email='reviewer@example.test', name='Officer', role='reviewer', authority='calgary', onboarded=True)
    store.create_user(other)
    store.create_user(officer)
    from engine.accounts import COOKIE, digest
    for client, user in ((owner, owner_user), (stranger, other), (reviewer, officer)):
        token = secrets.token_urlsafe(32)
        store.save_session(digest(token), user.id, time.time() + 3600)
        client.cookies.set(COOKIE, token)
    case = store.put(Case(owner_id=owner_user.id, authority='calgary'))
    path = f'/cases/{case.id}'
    started = owner.post(path + '/intake/jobs', json={'text': 'A new house', 'model': False},
                         headers={'Idempotency-Key': 'example'})
    assert started.status_code == 202
    job_url = started.headers['location']
    for reply in (owner.get(job_url), owner.get(path + '/jobs'), owner.get(path + '/jobs/health')):
        assert reply.status_code == 200 and reply.headers['cache-control'] == 'no-store'
    assert stranger.get(job_url).status_code == 404
    assert reviewer.get(job_url).status_code == 404
    unrelated = store.put(Case(owner_id=owner_user.id))
    assert owner.get(f'/cases/{unrelated.id}/jobs/{started.json()["id"]}').status_code == 404
    current = store.get(case.id)
    current.status = 'submitted'
    store.put(current, expected_version=current.version)
    assert reviewer.get(job_url).status_code == 200
    assert reviewer.post(job_url + '/cancel').status_code == 404
    officer.authority = 'edmonton'
    store.update_user(officer, revoke_sessions=False)
    assert reviewer.get(job_url).status_code == 404


def test_nonvercel_lifespan_default_and_vercel_external_health(database, monkeypatch):
    store, _ = database
    monkeypatch.delenv('BATATIS_JOBS_WORKER')
    assert in_process_enabled()
    app = create_app(store)
    case = store.put(Case())
    runtime = app.state.jobs()
    job = runtime.enqueue(case.id, 'intake', IntakeRequest(text='A new house', model=False), None)
    with TestClient(app) as client:
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            if client.get(f'/cases/{case.id}/jobs/{job.id}').json()['state'] == 'succeeded':
                break
            time.sleep(0.02)
        else:
            pytest.fail('lifespan worker did not execute accepted work')
    monkeypatch.setenv('VERCEL', '1')
    monkeypatch.setenv('BATATIS_JOBS_WORKER', '1')
    assert not in_process_enabled()
    # Supplied store is a test double for the same-database hosted path.
    hosted = create_app(store)
    with TestClient(hosted) as client:
        new_case = store.put(Case())
        accepted = client.post(f'/cases/{new_case.id}/intake/jobs', json={'text': 'A house', 'model': False})
        assert accepted.status_code == 202 and accepted.json()['state'] == 'queued'
        health = client.get(f'/cases/{new_case.id}/jobs/health').json()
        assert health['execution'] == 'external_required' and health['queued'] == 1
        assert not health['worker_available']
