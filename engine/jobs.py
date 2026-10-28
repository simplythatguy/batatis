"""Registered, durable case jobs and their supervised worker.

Run ``python -m engine.jobs worker`` on a long-lived host with the case database
configuration. No request background task is responsible for completing a job.
"""
from __future__ import annotations

import argparse
import asyncio
import contextvars
import hashlib
import json
import logging
import os
import re
import signal
import threading
import time
import uuid
from contextlib import asynccontextmanager, contextmanager
from dataclasses import dataclass, field
from typing import Any, Callable

from fastapi import HTTPException
from pydantic import BaseModel, TypeAdapter, ValidationError

from . import ai_access
from .access import AccessContext, current_access
from .account_models import User
from .models import Case
from .models_jobs import Job, WorkerHealth

logger = logging.getLogger(__name__)
COMMON_STAGES = {'queued', 'preparing', 'applying', 'completed'}
PROTECTED_FIELDS = {'id', 'version', 'created_at', 'updated_at', 'owner_id', 'authority', 'status',
                    'submitted_at', 'status_history', 'claim', 'decision', 'decision_history',
                    'submissions', 'return_snapshot', 'messages', 'professional_resolutions', 'applicant_draft'}


def canonical_hash(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                                     separators=(',', ':'), allow_nan=False).encode()).hexdigest()


@dataclass(frozen=True)
class ExecutionContext:
    store: Any
    user: User | None
    client_key: str
    progress: Callable[[str], None]


@dataclass(frozen=True)
class JobHandler:
    """A pure fingerprint, out-of-transaction compute, and short deterministic apply.

    ``apply`` receives the latest case. It may change only ``write_fields`` and
    must not perform I/O. All fields it reads belong in ``read_fields`` or the
    custom ``input_values`` fingerprint. Result validation precedes the write.
    """
    kind: str
    revision: str
    request_model: type[BaseModel]
    result_adapter: TypeAdapter
    read_fields: tuple[str, ...]
    write_fields: tuple[str, ...]
    stages: tuple[str, ...]
    compute: Callable[[Case, BaseModel, ExecutionContext], Any]
    apply: Callable[[Case, BaseModel, Any], None]
    result_path: str
    validate_input: Callable[[Case, BaseModel], None] = lambda case, body: None
    file_ids: Callable[[BaseModel], list[str]] = lambda body: []
    input_values: Callable[[Case, BaseModel], Any] | None = None
    uses_ai: Callable[[BaseModel], bool] = lambda body: False

    def fingerprint(self, case: Case, body: BaseModel) -> Any:
        return {'case': (self.input_values(case, body) if self.input_values else
                         case.model_dump(mode='json', include=set(self.read_fields))),
                'request': body.model_dump(mode='json', exclude={'expected_version'})}


@dataclass
class JobRegistry:
    _handlers: dict[str, JobHandler] = field(default_factory=dict)

    def register(self, handler: JobHandler) -> None:
        if not re.fullmatch(r'[a-z][a-z0-9_]{0,63}', handler.kind) or handler.kind in self._handlers:
            raise ValueError('job kind must be bounded and registered once')
        fields = set(Case.model_fields)
        if (not handler.revision or len(handler.revision) > 100 or
                set(handler.read_fields) - fields or set(handler.write_fields) - fields or
                set(handler.write_fields) & PROTECTED_FIELDS):
            raise ValueError('invalid job footprint')
        if any(not re.fullmatch(r'[a-z][a-z0-9_]{0,63}', stage) for stage in handler.stages):
            raise ValueError('job stages must be bounded public tokens')
        if not re.fullmatch(r'/[a-z][a-z0-9_/-]{0,99}', handler.result_path):
            raise ValueError('job result path must be a relative case endpoint')
        self._handlers[handler.kind] = handler

    def get(self, kind: str) -> JobHandler:
        try:
            return self._handlers[kind]
        except KeyError:
            raise LookupError('job handler is unavailable') from None


def default_registry(code: Callable) -> JobRegistry:
    from .routes_identify import create_job_handler as identify_handler
    from .routes_intake import create_job_handler as intake_handler
    registry = JobRegistry()
    registry.register(intake_handler(code))
    registry.register(identify_handler(code))
    return registry


@contextmanager
def actor_context(user: User | None):
    """Fresh durable actor state; never inherit a browser's stale privileges."""
    access_token = current_access.set(AccessContext(user, 'edit'))
    ai_token = ai_access.GRANTED.set(ai_access.granted(user))
    try:
        yield
    finally:
        ai_access.GRANTED.reset(ai_token)
        current_access.reset(access_token)


class JobRuntime:
    def __init__(self, store, registry: JobRegistry, *, lease_seconds: float = 60,
                 heartbeat_interval: float = 10, max_attempts: int = 3,
                 backoff_seconds: float = 5, clock: Callable[[], float] = time.time,
                 execution: str = 'external'):
        from .jobs_store import JobStore
        if not 1 <= max_attempts <= 5 or lease_seconds <= 0 or not 0 < heartbeat_interval < lease_seconds / 2:
            raise ValueError('invalid job attempt/lease policy')
        if not 0 <= backoff_seconds <= 300:
            raise ValueError('invalid job backoff')
        self.registry, self.store = registry, store
        self.lease_seconds, self.heartbeat_interval = lease_seconds, heartbeat_interval
        self.execution = execution
        self.repository = JobStore(store, lease_seconds=lease_seconds, max_attempts=max_attempts,
                                   backoff_seconds=backoff_seconds, clock=clock)

    def enqueue(self, case_id: str, kind: str, body: BaseModel, user: User | None, *,
                idempotency_key: str | None = None, client_ip: str = 'unknown',
                admit: Callable[[], None] | None = None) -> Job:
        if idempotency_key is not None and (not 1 <= len(idempotency_key) <= 200 or
                                            any(not 33 <= ord(c) <= 126 for c in idempotency_key)):
            raise HTTPException(422, 'Idempotency-Key must contain 1–200 visible ASCII characters')
        handler = self.registry.get(kind)
        # Normalize defaults and reject extra fields even for callers outside HTTP.
        body = handler.request_model.model_validate(body.model_dump(mode='json'))
        job = self.repository.enqueue(case_id, handler, body, user.id if user else None,
                                      idempotency_key=idempotency_key,
                                      client_key='job:' + canonical_hash(client_ip), admit=admit)
        if job is None:
            raise HTTPException(404, 'case not found')
        return job

    def retry(self, case_id: str, job_id: str, user: User | None) -> Job:
        return self.repository.retry(case_id, job_id, user.id if user else None, self.registry)

    def health(self, case_id: str | None = None, user: User | None = None) -> WorkerHealth:
        return self.repository.health(case_id, user.id if user else None, execution=self.execution)

    def run_once(self, *, worker_id: str | None = None) -> bool:
        """Claim and complete at most one attempt. Safe to call from a fresh process."""
        from .jobs_store import HandlerContractError, LostLease
        worker_id = worker_id or 'worker_' + uuid.uuid4().hex
        lease = self.repository.claim(worker_id)
        if lease is None:
            return False
        try:
            handler = self.registry.get(lease.kind)
        except LookupError:
            self.repository.fail(lease, code='handler_unavailable', retryable=False)
            return True
        try:
            prepared = self.repository.prepare(lease, handler)
            if prepared is None:
                return True
            stopped = threading.Event()

            def heartbeat():
                while not stopped.wait(self.heartbeat_interval):
                    try:
                        if not self.repository.heartbeat(lease):
                            return
                    except Exception as error:
                        # No raw exceptions: driver/provider errors can carry private text.
                        logger.warning('job heartbeat unavailable: %s', type(error).__name__)
                        return

            # This thread only renews a durable lease. Work is owned by the caller,
            # supervised by the CLI or ASGI lifespan, and recoverable without it.
            beater = threading.Thread(target=heartbeat, name='job-heartbeat', daemon=False)
            beater.start()
            try:
                def progress(stage: str):
                    if stage not in COMMON_STAGES | set(handler.stages):
                        raise ValueError('unregistered job stage')
                    if not self.repository.heartbeat(lease, stage=stage):
                        raise LostLease()

                context = ExecutionContext(self.store, prepared.user, prepared.client_key, progress)
                # Clear all ambient request context, then establish only the durable actor.
                def compute():
                    with actor_context(prepared.user):
                        return handler.compute(prepared.case, prepared.body, context)
                output = contextvars.Context().run(compute)
                # Revalidate even mutated model/dataclass instances. Suppress
                # serializer warnings, which can include private result values.
                output = handler.result_adapter.validate_python(
                    handler.result_adapter.dump_python(output, warnings=False))
                progress('applying')
                self.repository.complete(lease, handler, prepared.body, output,
                                         ai_granted=prepared.ai_granted)
            finally:
                stopped.set()
                beater.join()
        except LostLease:
            pass
        except HTTPException as error:
            self.repository.fail(lease, code='invalid_input' if error.status_code < 500 else 'processing_failed',
                                 retryable=error.status_code >= 500 or error.status_code == 429)
        except ValidationError:
            self.repository.fail(lease, code='invalid_input', retryable=False)
        except HandlerContractError:
            self.repository.fail(lease, code='invalid_input', retryable=False)
        except Exception as error:
            logger.warning('job attempt failed: %s', type(error).__name__)
            self.repository.fail(lease, code='processing_failed', retryable=True)
        return True


def worker_loop(runtime: JobRuntime, stop: threading.Event, *, poll_interval: float = 1,
                once: bool = False, worker_id: str | None = None) -> None:
    if not 0.01 <= poll_interval <= 60:
        raise ValueError('poll interval must be between 0.01 and 60 seconds')
    worker_id = worker_id or 'worker_' + uuid.uuid4().hex
    try:
        while not stop.is_set():
            try:
                worked = runtime.run_once(worker_id=worker_id)
            except Exception as error:
                logger.warning('job worker unavailable: %s', type(error).__name__)
                if once:
                    raise
                worked = False
            if once:
                return
            if not worked:
                stop.wait(min(poll_interval, runtime.heartbeat_interval))
    finally:
        try:
            runtime.repository.worker_stopped(worker_id)
        except Exception as error:
            logger.warning('job worker shutdown unavailable: %s', type(error).__name__)


def in_process_enabled() -> bool:
    # The lifespan loop stays off on Vercel. Accepted work is drained by the
    # request that queued it, and again by health checks while it is still waiting.
    return not os.environ.get('VERCEL') and os.environ.get('BATATIS_JOBS_WORKER') != '0'


def drain_hosted(runtime: JobRuntime) -> None:
    """Finish one ready attempt, then remove this attempt's worker row."""
    worker_id = 'hosted_' + uuid.uuid4().hex
    try:
        runtime.run_once(worker_id=worker_id)
    finally:
        try:
            runtime.repository.worker_stopped(worker_id)
        except Exception as error:
            logger.warning('hosted worker shutdown unavailable: %s', type(error).__name__)


def schedule_hosted_drain(add_task: Callable[..., Any], runtime: JobRuntime) -> None:
    """Queue one attempt after the response on Vercel.

    The job row is already committed. If this function dies, the lease expires
    and a later health check can claim the same attempt.
    """
    if os.environ.get('VERCEL'):
        add_task(drain_hosted, runtime)


def worker_lifespan(get_runtime: Callable[[], JobRuntime]):
    @asynccontextmanager
    async def lifespan(_app):
        if not in_process_enabled():
            yield
            return
        stop = threading.Event()
        task = asyncio.create_task(asyncio.to_thread(worker_loop, get_runtime(), stop))
        try:
            yield
        finally:
            stop.set()
            # Graceful shutdown drains the current bounded provider attempt. Abrupt
            # process death is handled by lease expiry in another worker.
            await task
    return lifespan


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['worker', 'health'])
    parser.add_argument('--once', action='store_true', help='process at most one ready attempt, then exit')
    parser.add_argument('--poll-interval', type=float, default=float(os.environ.get('BATATIS_JOBS_POLL_SECONDS', '1')))
    parser.add_argument('--lease-seconds', type=float, default=60)
    parser.add_argument('--heartbeat-interval', type=float, default=10)
    args = parser.parse_args(argv)
    from .codes import Codes
    from .store import open_store
    cached: list = []

    def code():
        if not cached:
            cached.append(Codes())
        return cached[0]

    runtime = JobRuntime(open_store(), default_registry(code), lease_seconds=args.lease_seconds,
                         heartbeat_interval=args.heartbeat_interval)
    if args.command == 'health':
        print(runtime.health().model_dump_json())
        return
    stop = threading.Event()
    for sig in (signal.SIGTERM, signal.SIGINT):
        signal.signal(sig, lambda *_: stop.set())
    worker_loop(runtime, stop, poll_interval=args.poll_interval, once=args.once)


if __name__ == '__main__':
    main()
