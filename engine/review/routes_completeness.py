"""Read-only saved-case administrative review. Never resolves or dispatches a provider."""
from __future__ import annotations

from typing import Callable, Literal

from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel, ConfigDict, ValidationError
from starlette.concurrency import run_in_threadpool

from ..codes import CodeDbMissing, Codes
from ..completeness_report import CompletenessResponse, saved_case_response
from ..completeness_variants import SELECTED_VARIANT
from ..store import CaseBackend

REQUEST_MAX_BYTES = 1024
PRIVATE_HEADERS = {'Cache-Control': 'no-store'}


class CompletenessRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    variant: Literal['A', 'B', 'C'] | None = None


async def _request_body(request: Request) -> CompletenessRequest:
    """Cap before JSON decoding; unsupported documents cannot trigger ingestion."""
    declared = request.headers.get('content-length')
    if declared is not None:
        try:
            size = int(declared)
        except ValueError:
            raise HTTPException(400, 'invalid Content-Length', headers=PRIVATE_HEADERS) from None
        if size < 0:
            raise HTTPException(400, 'invalid Content-Length', headers=PRIVATE_HEADERS)
        if size > REQUEST_MAX_BYTES:
            raise HTTPException(413, 'completeness request too large', headers=PRIVATE_HEADERS)
    data = bytearray()
    async for chunk in request.stream():
        if len(data) + len(chunk) > REQUEST_MAX_BYTES:
            raise HTTPException(413, 'completeness request too large', headers=PRIVATE_HEADERS)
        data.extend(chunk)
    if not data:
        return CompletenessRequest()
    try:
        return CompletenessRequest.model_validate_json(bytes(data))
    except ValidationError:
        raise HTTPException(422, 'unsupported completeness request; only a saved-case variant is accepted',
                            headers=PRIVATE_HEADERS) from None


def create_router(cases: Callable[[], CaseBackend], code: Callable[[], Codes]) -> APIRouter:
    router = APIRouter(tags=['administrative completeness'])

    @router.post('/cases/{case_id}/completeness', response_model=CompletenessResponse)
    async def completeness(case_id: str, request: Request, response: Response):
        store = cases()
        snapshot = await run_in_threadpool(store.get_snapshot, case_id)
        if snapshot is None:
            raise HTTPException(404, 'case not found', headers=PRIVATE_HEADERS)
        case, version = snapshot
        body = await _request_body(request)
        variant = body.variant or SELECTED_VARIANT
        if variant == 'C':
            raise HTTPException(503, 'provider-assisted completeness is unavailable', headers=PRIVATE_HEADERS)
        # Check the case first. No resolver, ingestion, lookup or provider fallback
        # is run for an absent case or an unavailable variant.
        try:
            codes = await run_in_threadpool(code)
            report = await run_in_threadpool(saved_case_response, case, codes, variant, store=store)
        except HTTPException as exc:
            raise HTTPException(exc.status_code, exc.detail,
                                headers={**(exc.headers or {}), **PRIVATE_HEADERS}) from None
        except CodeDbMissing:
            raise HTTPException(503, 'code database not found', headers=PRIVATE_HEADERS) from None
        except KeyError:
            raise HTTPException(503, 'code source unavailable for completeness review', headers=PRIVATE_HEADERS) from None
        current = await run_in_threadpool(store.get_snapshot, case_id)
        if current is None:
            raise HTTPException(404, 'case not found', headers=PRIVATE_HEADERS)
        if current[1] != version or current[0].model_dump() != case.model_dump():
            raise HTTPException(409, 'case was updated concurrently', headers=PRIVATE_HEADERS)
        response.headers.update(PRIVATE_HEADERS)
        return report

    return router
