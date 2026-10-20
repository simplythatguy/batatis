"""Case-builder HTTP routes; storage/code access is supplied by the application's closures."""
from __future__ import annotations

from typing import Callable

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field

from .ccmc import CCMCRegistry, RegistrySearch, RegistryUnavailable
from .llm_gate import client_ip_from, search_retry_after
from .codes import Codes
from .completeness import Gap, check_completeness
from .process_fields import ProcessField, process_fields
from .professional import ProfessionalResult, professional_involvement
from .section_c import section_c_rows
from .section_d import SectionDPlan, section_d_plan
from .section_d_issues import SectionDIssue, section_d_issues
from .store import CaseStore


class SectionDRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    # Explicitly confirmed selections. No request field accepts generated process/evidence content.
    provisions: list[str] | None = Field(default=None, min_length=1)


def create_router(cases: Callable[[], CaseStore], code: Callable[[], Codes],
                  registry: CCMCRegistry | None = None) -> APIRouter:
    router = APIRouter(tags=['case building'])
    registry = registry or CCMCRegistry()

    def get_case(case_id: str):
        case = cases().get(case_id)
        if case is None:
            raise HTTPException(404, 'case not found')
        return case

    @router.post('/cases/{case_id}/section-d', response_model=SectionDPlan)
    def section_d(case_id: str, body: SectionDRequest | None = None):
        case = get_case(case_id)
        if body and body.provisions is not None:
            case.provisions = body.provisions
        try:
            case.section_c = section_c_rows(case.provisions, code())
            plan = section_d_plan(case, code())
        except KeyError as error:
            raise HTTPException(404, error.args[0]) from error
        except ValueError as error:
            raise HTTPException(400, f'invalid provision id: {error}') from error
        cases().put(case)
        return plan

    @router.get('/cases/{case_id}/section-d/issues', response_model=list[SectionDIssue])
    def section_d_issues_route(case_id: str):
        try:
            return section_d_issues(get_case(case_id), code())
        except KeyError as error:
            raise HTTPException(404, error.args[0]) from error

    @router.get('/cases/{case_id}/professional', response_model=ProfessionalResult)
    def professional(case_id: str):
        return professional_involvement(get_case(case_id), code())

    @router.get('/ccmc/search', response_model=RegistrySearch,
                responses={429: {'description': 'per-IP limit'}})
    def ccmc_search(request: Request, q: str = Query(min_length=1, max_length=200),
                    limit: int = Query(20, ge=1, le=50)):
        wait = search_retry_after(client_ip_from(request))
        if wait is not None:
            return JSONResponse(
                status_code=429,
                content={'detail': f'Search limit reached; try again in {wait} seconds'},
                headers={'Retry-After': str(wait)},
            )
        try:
            return registry.search(q, limit=limit)
        except ValueError as error:
            raise HTTPException(422, str(error)) from error
        except RegistryUnavailable as error:
            raise HTTPException(503, str(error)) from error

    @router.get('/cases/{case_id}/process-fields', response_model=list[ProcessField])
    def fields(case_id: str):
        return process_fields(get_case(case_id), code())

    @router.get('/cases/{case_id}/gaps', response_model=list[Gap])
    def gaps(case_id: str):
        return check_completeness(get_case(case_id), code())

    return router
