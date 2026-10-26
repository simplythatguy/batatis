"""Transactional job state on the case store's existing SQLite/Postgres connection.

Transactions are short: lock actor, case, then job. No provider or file parsing
runs here. Heartbeats/claims lock only jobs, so saves do not wait for AI work.
"""
from __future__ import annotations

import json
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable

from fastapi import HTTPException

from . import ai_access
from .access import authorize_case
from .account_models import User
from .models import Case
from .models_jobs import Job, JobError, JobList, WorkerHealth
from .store import case_with_stored_files

MIGRATIONS = (
    """CREATE TABLE IF NOT EXISTS background_jobs (
        id TEXT PRIMARY KEY,
        case_id TEXT NOT NULL REFERENCES cases(id) ON DELETE CASCADE,
        kind TEXT NOT NULL,
        actor_user_id TEXT REFERENCES account_users(id) ON DELETE CASCADE,
        actor_scope TEXT NOT NULL,
        payload_json TEXT NOT NULL,
        input_fingerprint TEXT NOT NULL,
        handler_revision TEXT NOT NULL,
        state TEXT NOT NULL CHECK(state IN ('queued','running','succeeded','failed','cancelled','superseded')),
        stage TEXT NOT NULL,
        attempts INTEGER NOT NULL DEFAULT 0 CHECK(attempts >= 0),
        max_attempts INTEGER NOT NULL CHECK(max_attempts BETWEEN 1 AND 5),
        base_version INTEGER NOT NULL,
        result_version INTEGER,
        created_at DOUBLE PRECISION NOT NULL,
        updated_at DOUBLE PRECISION NOT NULL,
        started_at DOUBLE PRECISION,
        finished_at DOUBLE PRECISION,
        next_attempt_at DOUBLE PRECISION,
        heartbeat_at DOUBLE PRECISION,
        lease_expires_at DOUBLE PRECISION,
        lease_token INTEGER NOT NULL DEFAULT 0,
        lease_owner TEXT,
        ai_granted BOOLEAN NOT NULL,
        ai_required BOOLEAN NOT NULL DEFAULT FALSE,
        client_key TEXT NOT NULL,
        result_path TEXT NOT NULL,
        error_json TEXT,
        UNIQUE(case_id, kind, actor_scope, input_fingerprint),
        CHECK(attempts <= max_attempts))""",
    """CREATE TABLE IF NOT EXISTS background_job_requests (
        case_id TEXT NOT NULL REFERENCES cases(id) ON DELETE CASCADE,
        kind TEXT NOT NULL,
        actor_scope TEXT NOT NULL,
        key_digest TEXT NOT NULL,
        request_fingerprint TEXT NOT NULL,
        job_id TEXT NOT NULL REFERENCES background_jobs(id) ON DELETE CASCADE,
        PRIMARY KEY(case_id,kind,actor_scope,key_digest))""",
    'CREATE INDEX IF NOT EXISTS background_jobs_ready ON background_jobs(state,next_attempt_at,created_at)',
    'CREATE INDEX IF NOT EXISTS background_jobs_case ON background_jobs(case_id,created_at)',
    'CREATE INDEX IF NOT EXISTS background_jobs_actor ON background_jobs(actor_user_id)',
    'CREATE INDEX IF NOT EXISTS background_job_requests_job ON background_job_requests(job_id)',
    """CREATE TABLE IF NOT EXISTS background_job_workers (
        id TEXT PRIMARY KEY, started_at DOUBLE PRECISION NOT NULL, heartbeat_at DOUBLE PRECISION NOT NULL)""",
)

COLUMNS = ('id', 'case_id', 'kind', 'actor_user_id', 'actor_scope', 'payload_json', 'input_fingerprint',
           'handler_revision', 'state', 'stage', 'attempts', 'max_attempts', 'base_version', 'result_version',
           'created_at', 'updated_at', 'started_at', 'finished_at', 'next_attempt_at', 'heartbeat_at',
           'lease_expires_at', 'lease_token', 'lease_owner', 'ai_granted', 'ai_required', 'client_key',
           'result_path', 'error_json')
SELECT = ','.join(COLUMNS)
ACTIVE = {'queued', 'running'}
MESSAGES = {
    'processing_failed': 'Processing could not be completed.',
    'worker_lost': 'The worker stopped before completing this attempt.',
    'access_changed': 'Access changed before this work could be completed.',
    'input_changed': 'Application inputs changed before this work could be applied.',
    'invalid_input': 'This work could not be completed with the supplied input.',
    'handler_unavailable': 'This type of background work is currently unavailable.',
}


class LostLease(BaseException):
    """Stop stale work, including through algorithms' broad Exception fallbacks.

    Like asyncio.CancelledError, this must not become a provider fallback/retry.
    The runtime catches it explicitly without reporting a processing failure.
    """


class HandlerContractError(Exception):
    """Invalid apply logic is terminal; repeating paid computation cannot repair it."""


@dataclass(frozen=True)
class Lease:
    id: str
    case_id: str
    kind: str
    token: int
    owner: str


@dataclass(frozen=True)
class Prepared:
    case: Case
    body: Any
    user: User | None
    ai_granted: bool
    client_key: str


def timestamp(stamp: float | None) -> str | None:
    return datetime.fromtimestamp(stamp, timezone.utc).isoformat(timespec='milliseconds') if stamp is not None else None


def error_json(code: str, stage: str, retryable: bool) -> str:
    return JobError(code=code, message=MESSAGES[code], stage=stage, retryable=retryable).model_dump_json()


def row_dict(row) -> dict | None:
    return dict(zip(COLUMNS, row)) if row is not None else None


def public_job(row: dict) -> Job:
    keys = ('id', 'case_id', 'kind', 'state', 'stage', 'attempts', 'max_attempts', 'base_version', 'result_version')
    fields = {key: row[key] for key in keys}
    fields.update({key: timestamp(row[key]) for key in
                   ('created_at', 'updated_at', 'started_at', 'finished_at', 'next_attempt_at',
                    'heartbeat_at', 'lease_expires_at')})
    return Job(**fields, error=JobError.model_validate_json(row['error_json']) if row['error_json'] else None,
               can_retry=row['state'] in {'failed', 'cancelled'} and row['attempts'] < row['max_attempts'],
               result_url=f"/cases/{row['case_id']}{row['result_path']}" if row['state'] == 'succeeded' else None)


class JobStore:
    def __init__(self, store, *, lease_seconds: float = 60, max_attempts: int = 3,
                 backoff_seconds: float = 5, clock: Callable[[], float] = time.time):
        self.store, self.clock = store, clock
        self.lease_seconds, self.max_attempts, self.backoff_seconds = lease_seconds, max_attempts, backoff_seconds
        with store.account_db() as db:
            if db.postgres:
                db.execute('SELECT pg_advisory_xact_lock(727275)')
            for statement in MIGRATIONS:
                db.execute(statement)
            if db.postgres:
                columns = {row[0] for row in db.execute("SELECT column_name FROM information_schema.columns "
                                                       "WHERE table_schema=current_schema() AND table_name='background_jobs'")}
            else:
                columns = {row[1] for row in db.execute('PRAGMA table_info(background_jobs)')}
            if 'ai_required' not in columns:
                db.execute('ALTER TABLE background_jobs ADD COLUMN ai_required BOOLEAN NOT NULL DEFAULT FALSE')
                db.execute('UPDATE background_jobs SET ai_required=?', (ai_access.required(),))

    @staticmethod
    def _lock(db, *, skip=False) -> str:
        return (' FOR UPDATE SKIP LOCKED' if skip else ' FOR UPDATE') if db.postgres else ''

    def _actor(self, db, actor_id: str | None) -> User | None:
        if actor_id is None:
            return None
        # A commit's current privilege snapshot must stay stable through its write.
        lock = ' FOR SHARE' if db.postgres else ''
        row = db.execute('SELECT data FROM account_users WHERE id=?' + lock, (actor_id,)).fetchone()
        if row is None:
            raise HTTPException(404, 'case not found')
        return User.model_validate(json.loads(row[0])['user'])

    def _case(self, db, case_id: str) -> tuple[Case, dict] | None:
        column = 'data' if db.postgres else 'json'
        row = db.execute(f'SELECT {column},version FROM cases WHERE id=?' + self._lock(db), (case_id,)).fetchone()
        if row is None or self.store._purge_expired(db.con, case_id):
            return None
        data = json.loads(row[0]) if isinstance(row[0], str) else row[0]
        files = {item[0] for item in db.execute('SELECT id FROM case_files WHERE case_id=?', (case_id,))}
        return case_with_stored_files(data, files, int(row[1])), data

    def _authorized(self, db, case_id: str, actor_id: str | None, mode: str):
        user = self._actor(db, actor_id)
        saved = self._case(db, case_id)
        if saved is None:
            return None
        case, data = saved
        authorize_case(case, user, mode=mode)
        return case, data, user

    @staticmethod
    def _job(db, case_id: str, job_id: str, *, lock=False) -> dict | None:
        tail = ' FOR UPDATE' if lock and db.postgres else ''
        return row_dict(db.execute(f'SELECT {SELECT} FROM background_jobs WHERE id=? AND case_id=?' + tail,
                                   (job_id, case_id)).fetchone())

    def _fingerprint(self, db, handler, case: Case, body) -> str:
        from .jobs import canonical_hash
        files = []
        for file_id in handler.file_ids(body):
            # Uploaded IDs are immutable. No PDF bytes are duplicated or parsed at enqueue.
            row = db.execute('SELECT id,name,size,created_at FROM case_files WHERE case_id=? AND id=?',
                             (case.id, file_id)).fetchone()
            if row is None:
                raise HTTPException(404, 'file not found')
            files.append([str(value) for value in row])
        return canonical_hash({'kind': handler.kind, 'revision': handler.revision,
                               'authority': [case.owner_id, case.status, case.authority],
                               'input': handler.fingerprint(case, body), 'files': files,
                               'writes': case.model_dump(mode='json', include=set(handler.write_fields))})

    def enqueue(self, case_id, handler, body, actor_id, *, idempotency_key, client_key, admit=None) -> Job | None:
        from .jobs import canonical_hash
        payload = body.model_dump_json()
        request_fingerprint = canonical_hash(body.model_dump(mode='json'))
        scope = actor_id or ''
        key_digest = canonical_hash(idempotency_key) if idempotency_key is not None else None
        with self.store.account_db() as db:
            authorized = self._authorized(db, case_id, actor_id, 'edit')
            if authorized is None:
                return None
            case, _, user = authorized
            if key_digest is not None:
                old = db.execute('SELECT job_id,request_fingerprint FROM background_job_requests '
                                 'WHERE case_id=? AND kind=? AND actor_scope=? AND key_digest=?',
                                 (case_id, handler.kind, scope, key_digest)).fetchone()
                if old:
                    if old[1] != request_fingerprint:
                        raise HTTPException(409, 'Idempotency-Key was already used for a different request')
                    return public_job(self._job(db, case_id, old[0]))
            expected = getattr(body, 'expected_version', None)
            if expected is not None and expected != case.version:
                raise HTTPException(409, 'case was updated concurrently')
            handler.validate_input(case, body)
            fingerprint = self._fingerprint(db, handler, case, body)
            old = db.execute(f'SELECT {SELECT} FROM background_jobs WHERE case_id=? AND kind=? '
                             'AND actor_scope=? AND input_fingerprint=?',
                             (case_id, handler.kind, scope, fingerprint)).fetchone()
            if old is not None:
                saved = row_dict(old)
            else:
                if admit is not None:
                    admit()  # Existing admission limiter only; no I/O or model call.
                stamp = self.clock()
                job_id = 'job_' + uuid.uuid4().hex
                db.execute('INSERT INTO background_jobs '
                           '(id,case_id,kind,actor_user_id,actor_scope,payload_json,input_fingerprint,handler_revision,'
                           'state,stage,attempts,max_attempts,base_version,created_at,updated_at,next_attempt_at,'
                           'ai_granted,ai_required,client_key,result_path) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',
                           (job_id, case_id, handler.kind, actor_id, scope, payload, fingerprint, handler.revision,
                            'queued', 'queued', 0, self.max_attempts, case.version, stamp, stamp, stamp,
                            handler.uses_ai(body) and ai_access.granted(user),
                            handler.uses_ai(body) and ai_access.required(), client_key, handler.result_path))
                saved = self._job(db, case_id, job_id)
            if key_digest is not None:
                db.execute('INSERT INTO background_job_requests '
                           '(case_id,kind,actor_scope,key_digest,request_fingerprint,job_id) VALUES (?,?,?,?,?,?)',
                           (case_id, handler.kind, scope, key_digest, request_fingerprint, saved['id']))
            return public_job(saved)

    def get(self, case_id: str, job_id: str, actor_id: str | None) -> Job:
        result = None
        with self.store.account_db() as db:
            if self._authorized(db, case_id, actor_id, 'read') is not None:
                row = self._job(db, case_id, job_id)
                result = public_job(row) if row is not None else None
        if result is None:
            raise HTTPException(404, 'job not found')
        return result

    def list(self, case_id: str, actor_id: str | None, *, kind: str | None = None, limit: int = 50) -> JobList:
        result = None
        with self.store.account_db() as db:
            if self._authorized(db, case_id, actor_id, 'read') is not None:
                where = 'case_id=?' + (' AND kind=?' if kind else '')
                params = (case_id, kind, limit) if kind else (case_id, limit)
                rows = db.execute(f'SELECT {SELECT} FROM background_jobs WHERE {where} '
                                  'ORDER BY created_at DESC,id DESC LIMIT ?', params).fetchall()
                result = JobList(items=[public_job(row_dict(row)) for row in rows])
        if result is None:
            raise HTTPException(404, 'case not found')
        return result

    def _terminal(self, db, row: dict, state: str, *, code: str | None = None, retryable=False,
                  result_version: int | None = None):
        stamp = self.clock()
        error = error_json(code, row['stage'], retryable) if code else None
        db.execute('UPDATE background_jobs SET state=?,stage=?,updated_at=?,finished_at=?,next_attempt_at=NULL,'
                   'lease_owner=NULL,lease_expires_at=NULL,lease_token=lease_token+1,result_version=?,error_json=? '
                   'WHERE id=?',
                   (state, 'completed' if state == 'succeeded' else row['stage'], stamp, stamp,
                    result_version, error, row['id']))

    def cancel(self, case_id: str, job_id: str, actor_id: str | None) -> Job:
        result = None
        with self.store.account_db() as db:
            if self._authorized(db, case_id, actor_id, 'edit') is not None:
                row = self._job(db, case_id, job_id, lock=True)
                if row is not None:
                    if row['state'] in ACTIVE:
                        self._terminal(db, row, 'cancelled')
                    result = public_job(self._job(db, case_id, job_id))
        if result is None:
            raise HTTPException(404, 'job not found')
        return result

    def retry(self, case_id: str, job_id: str, actor_id: str | None, registry) -> Job:
        result = None
        with self.store.account_db() as db:
            authorized = self._authorized(db, case_id, actor_id, 'edit')
            if authorized is not None:
                case, _, user = authorized
                row = self._job(db, case_id, job_id, lock=True)
                if row is not None:
                    if row['state'] in ACTIVE | {'succeeded'}:
                        return public_job(row)
                    if row['state'] == 'superseded' or row['attempts'] >= row['max_attempts']:
                        raise HTTPException(409, 'job cannot be retried; submit current inputs as new work')
                    try:
                        handler = registry.get(row['kind'])
                    except LookupError:
                        raise HTTPException(409, 'job handler is unavailable') from None
                    body = handler.request_model.model_validate_json(row['payload_json'])
                    handler.validate_input(case, body)
                    if (row['actor_user_id'] != actor_id or self._fingerprint(db, handler, case, body) != row['input_fingerprint']
                            or (row['ai_granted'] and not ai_access.granted(user))):
                        raise HTTPException(409, 'job inputs or access changed; submit current inputs as new work')
                    stamp = self.clock()
                    db.execute("UPDATE background_jobs SET state='queued',stage='queued',updated_at=?,next_attempt_at=?,"
                               'finished_at=NULL,lease_owner=NULL,lease_expires_at=NULL,lease_token=lease_token+1 '
                               'WHERE id=?', (stamp, stamp, job_id))
                    result = public_job(self._job(db, case_id, job_id))
        if result is None:
            raise HTTPException(404, 'job not found')
        return result

    def _worker_heartbeat(self, db, worker_id: str):
        stamp = self.clock()
        db.execute('DELETE FROM background_job_workers WHERE heartbeat_at<?', (stamp - 86400,))
        db.execute('INSERT INTO background_job_workers(id,started_at,heartbeat_at) VALUES (?,?,?) '
                   'ON CONFLICT(id) DO UPDATE SET heartbeat_at=excluded.heartbeat_at', (worker_id, stamp, stamp))

    def worker_stopped(self, worker_id: str):
        with self.store.account_db() as db:
            db.execute('DELETE FROM background_job_workers WHERE id=?', (worker_id,))

    def _backoff(self, attempts: int) -> float:
        return min(300, self.backoff_seconds * 2 ** max(0, attempts - 1))

    def _failed_attempt(self, db, row: dict, *, code: str, retryable: bool):
        if retryable and row['attempts'] < row['max_attempts']:
            stamp = self.clock()
            db.execute("UPDATE background_jobs SET state='queued',stage='queued',updated_at=?,next_attempt_at=?,"
                       'lease_owner=NULL,lease_expires_at=NULL,lease_token=lease_token+1,error_json=? WHERE id=?',
                       (stamp, stamp + self._backoff(row['attempts']),
                        error_json(code, row['stage'], retryable), row['id']))
        else:
            self._terminal(db, row, 'failed', code=code, retryable=retryable)

    def claim(self, worker_id: str) -> Lease | None:
        with self.store.account_db() as db:
            self._worker_heartbeat(db, worker_id)
            expired = db.execute(f'SELECT {SELECT} FROM background_jobs WHERE state=\'running\' '
                                 'AND lease_expires_at<=? ORDER BY lease_expires_at LIMIT 32' + self._lock(db, skip=True),
                                 (self.clock(),)).fetchall()
            for row in expired:
                self._failed_attempt(db, row_dict(row), code='worker_lost', retryable=True)
            row = row_dict(db.execute(f'SELECT {SELECT} FROM background_jobs WHERE state=\'queued\' '
                                      'AND next_attempt_at<=? AND attempts<max_attempts '
                                      'ORDER BY next_attempt_at,created_at,id LIMIT 1' + self._lock(db, skip=True),
                                      (self.clock(),)).fetchone())
            if row is None:
                return None
            stamp = self.clock()
            token = row['lease_token'] + 1
            db.execute("UPDATE background_jobs SET state='running',stage='preparing',attempts=attempts+1,"
                       'updated_at=?,started_at=COALESCE(started_at,?),heartbeat_at=?,lease_expires_at=?,'
                       'next_attempt_at=NULL,finished_at=NULL,lease_token=?,lease_owner=?,error_json=NULL WHERE id=?',
                       (stamp, stamp, stamp, stamp + self.lease_seconds, token, worker_id, row['id']))
            return Lease(row['id'], row['case_id'], row['kind'], token, worker_id)

    def _fenced(self, db, lease: Lease) -> dict:
        row = self._job(db, lease.case_id, lease.id, lock=True)
        if (row is None or row['state'] != 'running' or row['lease_token'] != lease.token or
                row['lease_owner'] != lease.owner or row['lease_expires_at'] <= self.clock()):
            raise LostLease()
        return row

    def heartbeat(self, lease: Lease, *, stage: str | None = None) -> bool:
        with self.store.account_db() as db:
            self._worker_heartbeat(db, lease.owner)
            try:
                row = self._fenced(db, lease)
            except LostLease:
                return False
            stamp = self.clock()
            db.execute('UPDATE background_jobs SET heartbeat_at=?,lease_expires_at=?,updated_at=?,stage=? WHERE id=?',
                       (stamp, stamp + self.lease_seconds, stamp, stage or row['stage'], lease.id))
        return True

    def _execution_snapshot(self, db, lease: Lease, handler, *, ai_granted: bool | None = None):
        hint = self._job(db, lease.case_id, lease.id)
        if hint is None:
            raise LostLease()
        try:
            user = self._actor(db, hint['actor_user_id'])
            saved = self._case(db, lease.case_id)
            if saved is None:
                return None
            case, data = saved
            authorize_case(case, user, mode='edit')
        except HTTPException:
            row = self._fenced(db, lease)
            self._terminal(db, row, 'cancelled', code='access_changed')
            return None
        row = self._fenced(db, lease)
        if ((hint['ai_required'] and not ai_access.required()) or
                ((hint['ai_granted'] or ai_granted) and not ai_access.granted(user))):
            self._terminal(db, row, 'cancelled', code='access_changed')
            return None
        if row['handler_revision'] != handler.revision:
            self._terminal(db, row, 'failed', code='handler_unavailable')
            return None
        body = handler.request_model.model_validate_json(row['payload_json'])
        try:
            fingerprint = self._fingerprint(db, handler, case, body)
        except HTTPException:
            fingerprint = None
        if row['input_fingerprint'] != fingerprint:
            self._terminal(db, row, 'superseded', code='input_changed')
            return None
        return row, case, data, user, body

    def prepare(self, lease: Lease, handler) -> Prepared | None:
        with self.store.account_db() as db:
            snapshot = self._execution_snapshot(db, lease, handler)
            if snapshot is None:
                return None
            row, case, _, user, body = snapshot
            handler.validate_input(case, body)
            return Prepared(case, body, user, handler.uses_ai(body) and ai_access.granted(user), row['client_key'])

    def complete(self, lease: Lease, handler, body, output, *, ai_granted: bool) -> bool:
        with self.store.account_db() as db:
            snapshot = self._execution_snapshot(db, lease, handler, ai_granted=ai_granted)
            if snapshot is None:
                return False
            row, case, data, _, current_body = snapshot
            before = case.model_dump(mode='json')
            handler.apply(case, current_body, output)
            after = case.model_dump(mode='json', warnings=False)
            changed = {key for key in after if before.get(key) != after[key]}
            if changed - set(handler.write_fields):
                raise HandlerContractError('job apply exceeded its declared footprint')
            validated = Case.model_validate(after)
            after = validated.model_dump(mode='json', include=changed)
            # Patch only declared changed fields into the actual current JSON. Private
            # editors, messages and unknown forward-compatible fields never round-trip.
            data = {**data, **{key: after[key] for key in changed}, 'updated_at': timestamp(self.clock())}
            column = 'data' if db.postgres else 'json'
            if db.postgres:
                from psycopg.types.json import Jsonb
                payload = Jsonb(data)
            else:
                payload = json.dumps(data, ensure_ascii=False)
            written = db.execute(f'UPDATE cases SET {column}=?,version=version+1,updated_at=? '
                                 'WHERE id=? AND version=? RETURNING version',
                                 (payload, data['updated_at'], case.id, case.version)).fetchone()
            if written is None:
                raise LostLease()
            # Check time again after deterministic apply. An expired lease rolls back
            # the case write as well; the next claimant will fence this attempt.
            self._fenced(db, lease)
            self._terminal(db, row, 'succeeded', result_version=int(written[0]))
        return True

    def fail(self, lease: Lease, *, code: str, retryable: bool):
        with self.store.account_db() as db:
            try:
                row = self._fenced(db, lease)
            except LostLease:
                return
            self._failed_attempt(db, row, code=code, retryable=retryable)

    def health(self, case_id: str | None, actor_id: str | None, *, execution: str) -> WorkerHealth:
        missing = False
        with self.store.account_db() as db:
            if case_id is not None and self._authorized(db, case_id, actor_id, 'read') is None:
                missing = True
            last = db.execute('SELECT MAX(heartbeat_at) FROM background_job_workers').fetchone()[0]
            where = ' AND case_id=?' if case_id is not None else ''
            rows = db.execute('SELECT state,COUNT(*) FROM background_jobs WHERE state IN (\'queued\',\'running\')'
                              + where + ' GROUP BY state', (case_id,) if case_id else ()).fetchall()
        if missing:
            raise HTTPException(404, 'case not found')
        counts = dict(rows)
        return WorkerHealth(worker_available=last is not None and last > self.clock() - self.lease_seconds,
                            last_heartbeat_at=timestamp(last), queued=counts.get('queued', 0),
                            running=counts.get('running', 0), execution=execution)
