"""Explicit scoring actions and reads of stored results. GET never calls a provider."""
from __future__ import annotations

import logging
from typing import Callable

from fastapi import APIRouter, HTTPException, Request, Response

from .codes import Codes
from .identify import Judge, identify
from .llm_gate import client_ip_from, relevance_retry_after
from .models import Case, now
from .relevance import (CaseScorings, RelevanceInProgress, RelevanceUnavailable, current_record,
                        description, live_judge, relevance_record)
from .relevance_models import RelevanceRecord
from .store import CaseBackend, VersionConflict
from .redact import known_values, scrub

logger = logging.getLogger(__name__)


def _failure_reason(error: Exception) -> str:
    """Log technical categories without provider bodies, credentials, or applicant prose."""
    if isinstance(error, RelevanceUnavailable):
        return str(error)  # only the two fixed gate messages from live_judge()
    cause = error.__cause__ or error
    return f'{type(error).__name__}/{type(cause).__name__}: {getattr(cause, "code", "provider failure")}'


def _save_record(store: CaseBackend, case_id: str, record: RelevanceRecord) -> RelevanceRecord:
    """Attach to the latest case using both backends' existing optimistic write contract.

    A concurrent description edit is preserved and the result is marked stale. A deleted
    or expired case is never recreated by a completed provider request.
    """
    for _ in range(5):
        snapshot = store.get_snapshot(case_id)
        if snapshot is None:
            raise HTTPException(404, 'case not found')
        case, version = snapshot
        case.relevance = current_record(record, case)
        try:
            return store.put(case, expected_version=version).relevance
        except VersionConflict as error:
            if error.actual is None:
                raise HTTPException(404, 'case not found') from error
    raise HTTPException(409, 'case was updated concurrently')


def create_router(cases: Callable[[], CaseBackend], code: Callable[[], Codes],
                  judge_factory: Callable[[], Judge] | None = None) -> APIRouter:
    router = APIRouter(tags=['code relevance'])
    scorings = CaseScorings()
    make_judge = judge_factory or live_judge

    def get_case(case_id: str) -> Case:
        case = cases().get(case_id)
        if case is None:
            raise HTTPException(404, 'case not found')
        return case

    @router.get('/cases/{case_id}/relevance', response_model=RelevanceRecord)
    def get_relevance(case_id: str, response: Response):
        response.headers['Cache-Control'] = 'no-store'
        case = get_case(case_id)
        if case.relevance is None:
            raise HTTPException(404, 'not scored')
        return current_record(case.relevance, case)

    @router.post('/cases/{case_id}/relevance', response_model=RelevanceRecord)
    def score_relevance(case_id: str, request: Request, response: Response):
        response.headers['Cache-Control'] = 'no-store'
        try:
            with scorings.claim(case_id):
                case = get_case(case_id)
                text = description(case)
                if not text.strip():
                    raise HTTPException(409, 'Describe your project first')
                codes = code()
                try:
                    judge = make_judge()
                except Exception as error:
                    logger.warning('Relevance scoring unavailable: %s', _failure_reason(error))
                    raise HTTPException(503, 'Relevance scoring unavailable') from None
                wait = relevance_retry_after(client_ip_from(request))
                if wait is not None:
                    raise HTTPException(429, f'Relevance limit reached; try again in {wait} seconds',
                                        headers={'Retry-After': str(wait)})
                try:
                    # Jev sees the description with personal details removed; the stored hash
                    # stays on the applicant's own text so staleness is unaffected.
                    outbound = scrub(text, known_values(case))
                    result = identify(outbound, codes.db_path, judge=judge, rerank_n=60)
                    record = relevance_record(result, text, now())
                except Exception as error:
                    logger.warning('Relevance scoring unavailable: %s', _failure_reason(error))
                    raise HTTPException(503, 'Relevance scoring unavailable') from None
                logger.info('Relevance scored: case=%s model=%s articles=%s requests=%s errors=%s '
                            'screen_seconds=%.3f rerank_seconds=%.3f',
                            case_id, result.model, len(result.screen), result.usage['requests'], result.usage['errors'],
                            result.screen_seconds, result.rerank_seconds)
                return _save_record(cases(), case_id, record)
        except RelevanceInProgress:
            raise HTTPException(409, 'Relevance scoring already in progress', headers={'Retry-After': '1'}) from None

    return router
