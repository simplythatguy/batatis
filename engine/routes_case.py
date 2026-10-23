"""Case-builder HTTP routes; storage/code access is supplied by the application's closures."""
from __future__ import annotations

from typing import Callable

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from .ccmc import CCMCRegistry, RegistrySearch, RegistryUnavailable
from .codes import Codes
from .completeness import Gap, check_completeness
from .process_fields import ProcessField, process_fields
from .reference_selection import replace_references
from .routes_evidence import EvidenceDelete, delete_listing
from .professional import ProfessionalResult, professional_involvement
from .section_c import section_c_rows
from .section_d import SectionDPlan, section_d_plan
from .section_d_issues import SectionDIssue, section_d_issues
from .llm_gate import client_ip_from, search_retry_after
from .models import Case, Jurisdiction, SelectedArticle
from .store import CaseBackend, VersionConflict
from .account_models import reviewing_authority
from .identify.title import normalize_title


class TitleRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    title: str = Field(min_length=1, max_length=500, strict=True)

    @field_validator('title', mode='before')
    @classmethod
    def _single_line(cls, value):
        return normalize_title(value)


class SectionDRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    # Explicitly confirmed selections. No request field accepts generated process/evidence content.
    provisions: list[str] | None = None
    expected_version: int | None = Field(default=None, ge=1, strict=True)

    @model_validator(mode='after')
    def _explicit_selection_requires_version(self):
        if 'provisions' in self.model_fields_set:
            if self.provisions is None:
                raise ValueError('provisions must be omitted or a list; null is ambiguous')
            if self.expected_version is None:
                raise ValueError('expected_version is required when replacing or clearing provisions')
        return self


class JurisdictionRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    jurisdiction: Jurisdiction | None
    expected_version: int = Field(ge=1, strict=True)


class SelectedArticlesRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    selected_articles: list[SelectedArticle] = Field(max_length=500)
    expected_version: int = Field(ge=1, strict=True)

    @field_validator('selected_articles')
    @classmethod
    def _unique_cards(cls, value):
        if len({item.id for item in value}) != len(value):
            raise ValueError('selected card ids must be unique')
        if len({item.provision for item in value}) != len(value):
            raise ValueError('selected provisions must be unique')
        return value


def create_router(cases: Callable[[], CaseBackend], code: Callable[[], Codes],
                  registry: CCMCRegistry | None = None) -> APIRouter:
    router = APIRouter(tags=['case building'])
    registry = registry or CCMCRegistry()

    def get_case(case_id: str):
        case = cases().get(case_id)
        if case is None:
            raise HTTPException(404, 'case not found')
        return case

    @router.put('/cases/{case_id}/selected-articles', response_model=Case)
    def save_selected_articles(case_id: str, body: SelectedArticlesRequest):
        store = cases()
        snapshot = store.get_snapshot(case_id)
        if snapshot is None:
            raise HTTPException(404, 'case not found')
        case, version = snapshot
        if body.expected_version != version:
            raise HTTPException(409, 'case was updated concurrently')
        if body.selected_articles:
            codes = code()
            for article in body.selected_articles:
                if codes.provision(article.provision, 'B') is None:
                    raise HTTPException(404, 'provision not found')
        # This snapshot never confirms a benchmark, creates citation facts, or rebuilds C/D.
        case.selected_articles = body.selected_articles
        try:
            return store.put(case, expected_version=version)
        except VersionConflict as error:
            if error.actual is None:
                raise HTTPException(404, 'case not found') from error
            raise HTTPException(409, 'case was updated concurrently') from error

    @router.patch('/cases/{case_id}/title', response_model=Case)
    def rename_title(case_id: str, body: TitleRequest):
        try:
            saved = cases().rename_title(case_id, body.title)
        except VersionConflict as error:
            raise HTTPException(409, 'case was updated concurrently') from error
        if saved is None:
            raise HTTPException(404, 'case not found')
        return saved

    @router.put('/cases/{case_id}/jurisdiction', response_model=Case)
    def set_jurisdiction(case_id: str, body: JurisdictionRequest):
        store = cases()
        snapshot = store.get_snapshot(case_id)
        if snapshot is None:
            raise HTTPException(404, 'case not found')
        case, version = snapshot
        if body.expected_version != version:
            raise HTTPException(409, 'case was updated concurrently')
        case.jurisdiction = body.jurisdiction
        if case.owner_id:
            case.authority = reviewing_authority(body.jurisdiction.id if body.jurisdiction else None)
        try:
            return store.put(case, expected_version=version)
        except VersionConflict as error:
            if error.actual is None:
                raise HTTPException(404, 'case not found') from error
            raise HTTPException(409, 'case was updated concurrently') from error

    @router.post('/cases/{case_id}/section-d', response_model=SectionDPlan)
    def section_d(case_id: str, body: SectionDRequest | None = None):
        store = cases()
        snapshot = store.get_snapshot(case_id)
        if snapshot is None:
            raise HTTPException(404, 'case not found')
        case, version = snapshot
        if body and body.expected_version is not None and body.expected_version != version:
            raise HTTPException(409, 'case was updated concurrently')
        explicit = body is not None and 'provisions' in body.model_fields_set
        provisions = body.provisions if explicit else case.provisions
        try:
            # An empty rebuild/withdrawal needs no corpus and cannot invent a benchmark.
            codes = code() if provisions else None
            rows = section_c_rows(provisions, codes) if provisions else []
            if explicit:
                replace_references(case, provisions, rows)
            else:
                case.section_c = rows
                case.gaps = []
            plan = section_d_plan(case, codes)
        except KeyError as error:
            raise HTTPException(404, error.args[0]) from error
        except ValueError as error:
            raise HTTPException(400, f'invalid provision id: {error}') from error
        try:
            saved = store.put(case, expected_version=version)
        except VersionConflict as error:
            if error.actual is None:
                raise HTTPException(404, 'case not found') from error
            raise HTTPException(409, 'case was updated concurrently') from error
        plan.case_version = saved.version
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

    @router.get('/ccmc/search', response_model=RegistrySearch)
    def ccmc_search(request: Request, q: str = Query(min_length=1, max_length=200),
                    limit: int = Query(20, ge=1, le=50)):
        wait = search_retry_after(client_ip_from(request))
        if wait is not None:
            raise HTTPException(429, f'Search limit reached; try again in {wait} seconds',
                                headers={'Retry-After': str(wait)})
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

    @router.delete('/cases/{case_id}/evidence/{evidence_id}', response_model=Case)
    def delete_evidence(case_id: str, evidence_id: str, body: EvidenceDelete):
        return delete_listing(cases(), case_id, evidence_id, body.expected_version)

    return router
