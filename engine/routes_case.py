"""Case-builder HTTP routes; storage/code access is supplied by the application's closures."""
from __future__ import annotations

import base64
from typing import Callable, Literal

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field

from .ccmc import CCMCRegistry, RegistrySearch, RegistryUnavailable
from .codes import Codes
from .completeness import Gap, check_completeness
from .completeness_report import CompletenessResponse, LLMUsageModel, build_response, gaps_to_export_reasons
from .completeness_variants import SELECTED_VARIANT, run_variant
from .ingest import IngestError, ingest_bytes, ingested_from_case
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


class DocumentUpload(BaseModel):
    model_config = ConfigDict(extra='forbid')
    filename: str = Field(min_length=1, max_length=200)
    content_base64: str = Field(min_length=1)


class CompletenessRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    variant: Literal['A', 'B', 'C'] | None = None
    documents: list[DocumentUpload] = Field(default_factory=list)


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

    @router.get('/ccmc/search', response_model=RegistrySearch)
    def ccmc_search(q: str = Query(min_length=1, max_length=200), limit: int = Query(20, ge=1, le=50)):
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

    def open_codes():
        try:
            return code()
        except FileNotFoundError:
            return None

    @router.post('/cases/{case_id}/completeness', response_model=CompletenessResponse)
    def completeness(case_id: str, body: CompletenessRequest | None = None):
        """Administrative gaps for Part 1 sections A–D. Does not certify compliance or safety."""
        case = get_case(case_id)
        variant = (body.variant if body and body.variant else None) or SELECTED_VARIANT
        codes = open_codes()
        llm = None
        try:
            if body and body.documents:
                documents = []
                for upload in body.documents:
                    documents.extend(ingest_bytes(base64.b64decode(upload.content_base64), upload.filename))
            else:
                documents = [ingested_from_case(case)]
            if variant == 'C':
                from .llm_judgement import build_client
                llm = build_client()
            results = [run_variant(variant, document, codes, llm) for document in documents]
        except IngestError as error:
            raise HTTPException(422, f'invented value: {error}') from error
        export_reasons = None
        if codes is not None and not (body and body.documents):
            export_reasons = gaps_to_export_reasons(check_completeness(case, codes))
        usage = next((result.usage for result in results if result.usage), None)
        skipped = next((result.skipped for result in results if result.skipped), None)
        llm_model = None
        if variant == 'C':
            llm_model = LLMUsageModel(
                provider=usage.provider if usage else None, model=usage.model if usage else None,
                input_tokens=usage.input_tokens if usage else 0, output_tokens=usage.output_tokens if usage else 0,
                latency_s=usage.latency_s if usage else 0, estimated_usd=usage.usd if usage else 0,
                skipped=skipped)
        return build_response(variant, results, export_reasons=export_reasons, llm=llm_model)

    return router
