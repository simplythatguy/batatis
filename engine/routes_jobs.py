"""Case-scoped job recovery, status and controls. No inputs or provider data here."""
from __future__ import annotations

from typing import Callable

from fastapi import APIRouter, BackgroundTasks, Query, Request, Response

from .jobs import JobRuntime, schedule_hosted_drain
from .models_jobs import Job, JobList, WorkerHealth


def create_router(jobs: Callable[[], JobRuntime]) -> APIRouter:
    router = APIRouter(tags=['background jobs'])

    def actor(request: Request):
        return getattr(request.state, 'user', None)

    @router.get('/cases/{case_id}/jobs', response_model=JobList)
    def listing(case_id: str, request: Request, response: Response,
                kind: str | None = Query(default=None, pattern=r'^[a-z][a-z0-9_]{0,63}$'),
                limit: int = Query(default=50, ge=1, le=100)):
        response.headers['Cache-Control'] = 'no-store'
        user = actor(request)
        return jobs().repository.list(case_id, user.id if user else None, kind=kind, limit=limit)

    @router.get('/cases/{case_id}/jobs/health', response_model=WorkerHealth)
    def health(case_id: str, request: Request, response: Response, background: BackgroundTasks):
        response.headers['Cache-Control'] = 'no-store'
        runtime = jobs()
        report = runtime.health(case_id, actor(request))
        if report.queued or report.running:
            schedule_hosted_drain(background.add_task, runtime)
        return report

    @router.get('/cases/{case_id}/jobs/{job_id}', response_model=Job)
    def status(case_id: str, job_id: str, request: Request, response: Response):
        response.headers['Cache-Control'] = 'no-store'
        user = actor(request)
        return jobs().repository.get(case_id, job_id, user.id if user else None)

    @router.post('/cases/{case_id}/jobs/{job_id}/cancel', response_model=Job)
    def cancel(case_id: str, job_id: str, request: Request, response: Response):
        response.headers['Cache-Control'] = 'no-store'
        user = actor(request)
        return jobs().repository.cancel(case_id, job_id, user.id if user else None)

    @router.post('/cases/{case_id}/jobs/{job_id}/retry', response_model=Job, status_code=202)
    def retry(case_id: str, job_id: str, request: Request, response: Response, background: BackgroundTasks):
        response.headers['Cache-Control'] = 'no-store'
        runtime = jobs()
        job = runtime.retry(case_id, job_id, actor(request))
        schedule_hosted_drain(background.add_task, runtime)
        return job

    return router
