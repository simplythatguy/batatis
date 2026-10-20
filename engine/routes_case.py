"""Case-builder HTTP routes; storage/code access is supplied by the application's closures."""
from __future__ import annotations

from typing import Callable

from fastapi import APIRouter, HTTPException, Query, Response
from pydantic import BaseModel, ConfigDict, Field, model_validator

from .ccmc import CCMCRegistry, RegistrySearch, RegistryUnavailable
from .codes import Codes
from .completeness import Gap, check_completeness
from .models import EvidenceItem, Fact, Source
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


class EvidenceCreate(BaseModel):
    """One supporting document the applicant is adding. The server assigns the id."""
    model_config = ConfigDict(extra='forbid')
    description: str = Field(min_length=1, max_length=4000)
    responsible_party: str | None = Field(default=None, max_length=500)
    date: str | None = Field(default=None, max_length=80)
    evidence_type: str | None = Field(default=None, max_length=200)

    @model_validator(mode='after')
    def _strip(self):
        self.description = self.description.strip()
        if not self.description:
            raise ValueError('description is empty')
        if self.responsible_party is not None:
            self.responsible_party = self.responsible_party.strip()
        if self.date is not None:
            self.date = self.date.strip()
        if self.evidence_type is not None:
            self.evidence_type = self.evidence_type.strip()
        return self


def _evidence_fact(field: str, value: str, source: Source) -> Fact:
    return Fact(field=field, value=value, kind='pointed', status='confirmed', source=source)


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

    @router.post('/cases/{case_id}/evidence', response_model=EvidenceItem, status_code=201)
    def add_evidence(case_id: str, body: EvidenceCreate):
        """Append one evidence item. A later save does not replace an earlier one."""
        case = get_case(case_id)
        item = EvidenceItem(description=body.description, evidence_type=body.evidence_type or None,
                            status='provided')
        case.evidence.append(item)
        prefix = f'evidence.{item.id}.'
        file_source = Source(type='file', ref=body.description, quote=body.description)
        applicant = Source(type='user_text', ref='Your evidence', quote=body.description)
        case.facts += [
            _evidence_fact(prefix + 'file_ref', body.description, file_source),
            _evidence_fact(prefix + 'title', body.description, applicant),
        ]
        if body.responsible_party:
            case.facts.append(_evidence_fact(
                prefix + 'responsible_party', body.responsible_party,
                Source(type='user_text', ref='Your evidence', quote=body.responsible_party)))
        if body.date:
            case.facts.append(_evidence_fact(
                prefix + 'date', body.date, Source(type='user_text', ref='Your evidence', quote=body.date)))
        cases().put(case)
        return item

    @router.delete('/cases/{case_id}/evidence/{evidence_id}', status_code=204)
    def delete_evidence(case_id: str, evidence_id: str):
        case = get_case(case_id)
        kept = [item for item in case.evidence if item.id != evidence_id]
        if len(kept) == len(case.evidence):
            raise HTTPException(404, 'evidence not found')
        prefix = f'evidence.{evidence_id}.'
        case.evidence = kept
        case.facts = [fact for fact in case.facts if not fact.field.startswith(prefix)]
        cases().put(case)
        return Response(status_code=204)

    return router
