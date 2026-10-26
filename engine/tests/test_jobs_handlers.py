"""Existing algorithms over the durable seam, including the actual standalone worker command."""
from __future__ import annotations

import json
import os
import subprocess
import sys
from dataclasses import replace
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from engine import ai_access
from engine.api import create_app
from engine.codes import Codes
from engine.identify.http_models import IdentifyRequest
from engine.jobs import ExecutionContext, default_registry
from engine.jobs_store import LostLease
from engine.models import Case
from engine.models_jobs import Job
from engine.routes_identify import create_job_handler as identify_handler
from engine.routes_intake import IntakeRequest
from engine.tests.test_jobs_runtime import (Clock, Input, Output, actor, database, fact, generic_handler,
                                            offline, runtime_for)


def plain(response):
    return {key: value for key, value in response.json().items() if key != 'meta'}


def test_acceptance_is_quick_without_computing_and_validates_exact_public_shape(database, monkeypatch):
    store, _ = database
    from engine.intake import service

    def forbidden(*args, **kwargs):
        pytest.fail('enqueue must never compute')

    monkeypatch.setattr(service, 'run', forbidden)
    app = create_app(store)
    client = TestClient(app)
    case = store.put(Case())
    start = client.post(f'/cases/{case.id}/intake/jobs', json={'text': 'A house', 'model': False},
                        headers={'Idempotency-Key': 'same-request'})
    assert start.status_code == 202
    Job.model_validate(plain(start))
    assert set(plain(start)) == set(Job.model_fields)
    assert plain(start)['state'] == 'queued' and plain(start)['attempts'] == 0
    assert start.headers['cache-control'] == 'no-store'
    assert start.headers['location'].endswith('/jobs/' + start.json()['id'])
    again = client.post(f'/cases/{case.id}/intake/jobs', json={'text': 'A house', 'model': False},
                        headers={'Idempotency-Key': 'same-request'})
    assert plain(again) == plain(start)
    mismatch = client.post(f'/cases/{case.id}/intake/jobs', json={'text': 'Another house', 'model': False},
                           headers={'Idempotency-Key': 'same-request'})
    assert mismatch.status_code == 409
    assert client.get(f'/cases/{case.id}/jobs?kind=intake').json()['items'][0]['id'] == start.json()['id']
    assert client.get(f'/cases/{case.id}/jobs?limit=101').status_code == 422
    assert client.post(f'/cases/{case.id}/intake/jobs', json={'text': 'A house', 'model': False},
                       headers={'Idempotency-Key': 'x' * 201}).status_code == 422


def test_jobs_and_sync_intake_use_identical_algorithm(database):
    store, _ = database
    app = create_app(store)
    client = TestClient(app)
    text = 'A two-storey house in Calgary. We propose a small bedroom window without a window well.'
    sync_case, job_case = store.put(Case()), store.put(Case())
    synchronous = client.post(f'/cases/{sync_case.id}/intake', json={'text': text, 'model': False})
    assert synchronous.status_code == 200
    start = client.post(f'/cases/{job_case.id}/intake/jobs', json={'text': text, 'model': False})
    assert start.status_code == 202
    assert app.state.jobs().run_once()
    state = client.get(start.headers['location']).json()
    assert state['state'] == 'succeeded'
    asynchronous = client.get(state['result_url'])
    assert asynchronous.status_code == 200
    meaningful = lambda response: [(item['field'], item['value'], item['kind'], item['status'])
                                   for item in response.json()['facts']]
    assert meaningful(synchronous) == meaningful(asynchronous)
    assert synchronous.json()['record']['plan'] == asynchronous.json()['record']['plan']


def test_jobs_and_sync_identify_use_identical_algorithms_and_stages(database):
    codes = Codes()
    store, _ = database
    app = create_app(store, codes)
    client = TestClient(app)
    text = 'A two-storey single detached house. The north wall is 0.3 m from the side property line with a vented soffit.'
    sync_case, job_case = store.put(Case()), store.put(Case())
    synchronous = client.post(f'/cases/{sync_case.id}/identify', json={'prose': text})
    assert synchronous.status_code == 200, synchronous.text
    start = client.post(f'/cases/{job_case.id}/identify/jobs', json={'prose': text})
    assert start.status_code == 202
    runtime = app.state.jobs()
    stages = []
    heartbeat = runtime.repository.heartbeat

    def observed(lease, *, stage=None):
        if stage is not None:
            stages.append(stage)
        return heartbeat(lease, stage=stage)

    runtime.repository.heartbeat = observed
    assert runtime.run_once()
    final = client.get(start.headers['location']).json()
    assert final['state'] == 'succeeded', final
    saved = client.get(final['result_url']).json()
    assert saved['mode'] == synchronous.json()['mode'] == 'fake'
    assert [(item['provision'], item['status']) for item in saved['articles']] == [
        (item['provision'], item['status']) for item in synchronous.json()['articles']]
    assert {'screen', 'rerank', 'verify', 'questions', 'applying'} <= set(stages)
    assert store.get(job_case.id).provisions == []


def test_cancel_between_real_identify_stages_stops_without_fallback(database, caplog):
    codes = Codes()
    store, _ = database
    app = create_app(store, codes)
    runtime = app.state.jobs()
    case = store.put(Case())
    job = runtime.enqueue(case.id, 'identify', IdentifyRequest(prose='A house with a small bedroom window'), None)
    heartbeat = runtime.repository.heartbeat

    def cancel_after_screen(lease, *, stage=None):
        if stage == 'rerank':
            runtime.repository.cancel(case.id, job.id, None)
        return heartbeat(lease, stage=stage)

    runtime.repository.heartbeat = cancel_after_screen
    assert runtime.run_once()
    final = runtime.repository.get(case.id, job.id, None)
    assert final.state == 'cancelled'
    assert store.get(case.id).identify is None
    assert 'keyword fallback' not in caplog.text


def test_identify_keeps_latest_private_editor_but_supersedes_new_facts(database):
    codes = Codes()
    store, _ = database
    handler = identify_handler(lambda: codes)
    for edited_fact in (False, True):
        runtime = runtime_for(store, handler)
        case = store.put(Case(facts=[fact('A new house with a small window', 'project.description')]))
        job = runtime.enqueue(case.id, 'identify', IdentifyRequest(), None)
        lease = runtime.repository.claim('worker')
        prepared = runtime.repository.prepare(lease, handler)
        output = handler.compute(prepared.case, prepared.body,
                                 ExecutionContext(store, None, 'local', lambda stage: None))
        patch = ({'facts': [fact(4).model_dump(mode='json')]} if edited_fact else
                 {'applicant_draft': {'choices': {'risk': 'unfinished'}}})
        store.patch_draft(case.id, patch, expected_version=case.version)
        committed = runtime.repository.complete(lease, handler, prepared.body, output, ai_granted=prepared.ai_granted)
        final = runtime.repository.get(case.id, job.id, None)
        assert committed is not edited_fact
        if edited_fact:
            assert final.state == 'superseded' and store.get(case.id).identify is None
        else:
            assert final.state == 'succeeded' and store.get(case.id).applicant_draft.choices['risk'] == 'unfinished'


def test_expiry_after_provider_compute_cascades_job_and_never_recreates_case(database):
    store, _ = database
    runtime = runtime_for(store)
    case = store.put(Case())
    runtime.enqueue(case.id, 'slow_test', Input(), None, idempotency_key='retained-with-case')
    lease = runtime.repository.claim('worker')
    prepared = runtime.repository.prepare(lease, runtime.registry.get('slow_test'))
    expired = (datetime.now(timezone.utc) - timedelta(days=8)).isoformat()
    with store.account_db() as db:
        db.execute('UPDATE cases SET updated_at=? WHERE id=?', (expired, case.id))
    assert not runtime.repository.complete(lease, runtime.registry.get('slow_test'), prepared.body,
                                           Output(title='Do not recreate'), ai_granted=True)
    assert store.get(case.id) is None
    with store.account_db() as db:
        assert db.execute('SELECT COUNT(*) FROM background_jobs').fetchone()[0] == 0
        assert db.execute('SELECT COUNT(*) FROM background_job_requests').fetchone()[0] == 0


def test_expired_during_apply_rolls_back_case_and_success_together(database):
    store, _ = database
    clock = Clock()

    def expired_apply(case, body, output):
        case.title = output.title
        clock.advance(61)

    handler = generic_handler(apply=expired_apply)
    runtime = runtime_for(store, handler, clock=clock)
    case = store.put(Case())
    job = runtime.enqueue(case.id, 'slow_test', Input(), None)
    lease = runtime.repository.claim('worker')
    prepared = runtime.repository.prepare(lease, handler)
    with pytest.raises(LostLease):
        runtime.repository.complete(lease, handler, prepared.body, Output(title='Too late'), ai_granted=True)
    assert store.get(case.id).version == 1 and store.get(case.id).title is None
    assert runtime.repository.get(case.id, job.id, None).state == 'running'


def test_revoked_before_execution_prevents_any_compute(database, monkeypatch):
    store, _ = database
    user = actor(store)
    code = 'a-long-current-access-code-123456'
    monkeypatch.setenv('BATATIS_AI_ACCESS_CODES', json.dumps({'team': code}))
    user.ai_access, user.ai_access_fingerprint = 'team', ai_access.fingerprint(code)
    store.update_user(user)

    def forbidden(*args):
        pytest.fail('revoked account must never compute')

    runtime = runtime_for(store, replace(generic_handler(compute=forbidden), uses_ai=lambda body: True))
    case = store.put(Case(owner_id=user.id))
    job = runtime.enqueue(case.id, 'slow_test', Input(), user)
    user.ai_access = user.ai_access_fingerprint = None
    store.update_user(user)
    assert runtime.run_once()
    final = runtime.repository.get(case.id, job.id, user.id)
    assert final.state == 'cancelled' and final.error.code == 'access_changed'


def test_worker_cannot_drop_original_ai_access_policy(database, monkeypatch):
    store, _ = database
    user = actor(store)
    monkeypatch.setenv('BATATIS_AI_ACCESS_CODES', json.dumps({'team': 'a-long-current-access-code-123456'}))

    def forbidden(*args):
        pytest.fail('worker policy mismatch must not enable paid AI')

    runtime = runtime_for(store, replace(generic_handler(compute=forbidden), uses_ai=lambda body: True))
    case = store.put(Case(owner_id=user.id))
    job = runtime.enqueue(case.id, 'slow_test', Input(), user)
    monkeypatch.delenv('BATATIS_AI_ACCESS_CODES')
    assert runtime.run_once()
    assert runtime.repository.get(case.id, job.id, user.id).state == 'cancelled'


def test_deterministic_kind_does_not_acquire_ai_access_requirement(database, monkeypatch):
    store, _ = database
    user = actor(store)
    code = 'a-long-current-access-code-123456'
    monkeypatch.setenv('BATATIS_AI_ACCESS_CODES', json.dumps({'team': code}))
    user.ai_access, user.ai_access_fingerprint = 'team', ai_access.fingerprint(code)
    store.update_user(user)
    runtime = runtime_for(store)
    case = store.put(Case(owner_id=user.id))
    job = runtime.enqueue(case.id, 'slow_test', Input(), user)
    user.ai_access = user.ai_access_fingerprint = None
    store.update_user(user)
    assert runtime.run_once()
    assert runtime.repository.get(case.id, job.id, user.id).state == 'succeeded'


def test_cli_worker_once_and_health_use_existing_database(database):
    store, _ = database
    case = store.put(Case())
    from engine.jobs import JobRuntime
    runtime = JobRuntime(store, default_registry(lambda: None))
    job = runtime.enqueue(case.id, 'intake', IntakeRequest(text='A new house', model=False), None)
    environment = os.environ.copy()
    environment.update(BATATIS_JOBS_WORKER='0')
    if hasattr(store, 'path'):
        environment.update(BATATIS_STORE='file', BATATIS_CASES=str(store.path))
    else:
        environment.update(BATATIS_STORE='postgres', DATABASE_URL=store.url)
    ran = subprocess.run([sys.executable, '-m', 'engine.jobs', 'worker', '--once'],
                         env=environment, capture_output=True, timeout=20)
    assert ran.returncode == 0, ran.stderr.decode()
    assert runtime.repository.get(case.id, job.id, None).state == 'succeeded'
    health = subprocess.run([sys.executable, '-m', 'engine.jobs', 'health'],
                            env=environment, capture_output=True, timeout=15)
    assert health.returncode == 0, health.stderr.decode()
    result = json.loads(health.stdout)
    assert result['queued'] == 0 and result['running'] == 0 and not result['worker_available']
