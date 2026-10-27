"""Public durable-job records. Inputs, actor identities and lease fences stay private."""
from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

JobKind = Annotated[str, Field(pattern=r'^[a-z][a-z0-9_]{0,63}$')]
JobState = Literal['queued', 'running', 'succeeded', 'failed', 'cancelled', 'superseded']


class JobError(BaseModel):
    code: Literal['processing_failed', 'worker_lost', 'access_changed', 'input_changed', 'invalid_input',
                  'handler_unavailable']
    message: str
    stage: str
    retryable: bool


class Job(BaseModel):
    model_config = ConfigDict(extra='forbid')
    id: str
    case_id: str
    kind: JobKind
    state: JobState
    stage: str
    attempts: int
    max_attempts: int
    base_version: int
    result_version: int | None
    created_at: str
    updated_at: str
    started_at: str | None
    finished_at: str | None
    next_attempt_at: str | None
    heartbeat_at: str | None
    lease_expires_at: str | None
    error: JobError | None
    can_retry: bool
    result_url: str | None


class JobList(BaseModel):
    items: list[Job]


class WorkerHealth(BaseModel):
    worker_available: bool
    last_heartbeat_at: str | None
    queued: int
    running: int
    execution: Literal['external_required', 'in_process', 'external']
