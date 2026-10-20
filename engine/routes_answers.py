"""Routes that let an applicant answer a completeness gap.

Evidence is stored as the applicant supplied it. This module does not generate
professional evidence, mark anything verified, or decide that a design complies.
"""
from __future__ import annotations

from typing import Callable

from fastapi import APIRouter, HTTPException, Response
from pydantic import BaseModel, ConfigDict, Field, model_validator

from .building_facts import BuildingFactsUpdate, write_building_facts
from .codes import Codes
from .description_facts import DescriptionExtract, extract_description
from .evidence_gaps import (
    EvidenceClosure, ProvisionEvidenceGap, evidence_closures, group_evidence_gaps, uncovered_items)
from .models import Case, EvidenceItem, Fact, Source
from .professional import ProfessionalResult, professional_involvement
from .section_d import EvidenceType, section_d_plan
from .store import CaseStore


class EvidenceCreate(BaseModel):
    model_config = ConfigDict(extra='forbid')
    provision_id: str = Field(min_length=1)
    objective: str | None = None
    function: str | None = None
    evidence_type: EvidenceType
    description: str = Field(min_length=1, max_length=4000)
    file_id: str | None = Field(default=None, min_length=1, max_length=200)

    @model_validator(mode='after')
    def _pair(self):
        if (self.objective is None) != (self.function is None):
            raise ValueError('objective and function must both be sent, or neither')
        self.description = self.description.strip()
        if not self.description:
            raise ValueError('description is empty')
        if self.file_id is not None:
            self.file_id = self.file_id.strip()
            if not self.file_id:
                raise ValueError('file_id is empty')
        return self


class EvidenceCreated(BaseModel):
    evidence: EvidenceItem
    gaps: list[ProvisionEvidenceGap]
    closed: list[EvidenceClosure]


class BuildingFactsResponse(BaseModel):
    updated: list[str]
    professional: ProfessionalResult
    case: Case


class DescriptionBody(BaseModel):
    model_config = ConfigDict(extra='forbid')
    text: str = Field(min_length=1, max_length=8000)


class DescriptionFactView(BaseModel):
    field: str
    value: str | float | int | bool | None
    source: str
    quote: str
    status: str


class DescriptionResponse(BaseModel):
    alternative_description: str | None
    facts: list[DescriptionFactView]


def _fact_from_extract(extracted) -> Fact:
    return Fact(field=extracted.field, value=extracted.value, kind='pointed', status='unconfirmed',
                source=Source(type='description', ref='description', quote=extracted.quote))


def _views(extracted: DescriptionExtract) -> list[DescriptionFactView]:
    return [DescriptionFactView(field=fact.field, value=fact.value, source=fact.source,
                                quote=fact.quote, status='unconfirmed') for fact in extracted.facts]


def create_answers_router(cases: Callable[[], CaseStore], code: Callable[[], Codes]) -> APIRouter:
    router = APIRouter(tags=['answer gaps'])

    def get_case(case_id: str) -> Case:
        case = cases().get(case_id)
        if case is None:
            raise HTTPException(404, 'case not found')
        return case

    @router.post('/cases/{case_id}/evidence', response_model=EvidenceCreated, status_code=201)
    def add_evidence(case_id: str, body: EvidenceCreate):
        case = get_case(case_id)
        try:
            plan = section_d_plan(case, code()) if case.provisions else None
        except KeyError as error:
            raise HTTPException(404, error.args[0]) from error
        except ValueError as error:
            raise HTTPException(400, f'invalid provision id: {error}') from error
        items = plan.items if plan else []
        matched = [item for item in items if item.provision_id == body.provision_id]
        if not matched:
            raise HTTPException(400, 'confirm this Division B benchmark before attaching evidence')
        if body.objective is not None:
            pair = next((item for item in matched
                         if item.objective == body.objective and item.function == body.function), None)
            if pair is None:
                raise HTTPException(400, 'that objective/function pair is not on the attribution for this provision')
        before = uncovered_items(items, case.evidence)
        item = EvidenceItem(
            provision_id=body.provision_id, objective=body.objective, function=body.function,
            description=body.description, evidence_type=body.evidence_type, file_id=body.file_id,
            professional_required=None, status='evidence_listed')
        case.evidence.append(item)
        cases().put(case)
        still_open = uncovered_items(items, case.evidence)
        return EvidenceCreated(
            evidence=item, gaps=group_evidence_gaps(still_open),
            closed=evidence_closures(before, still_open))

    @router.delete('/cases/{case_id}/evidence/{evidence_id}', status_code=204)
    def delete_evidence(case_id: str, evidence_id: str):
        case = get_case(case_id)
        kept = [item for item in case.evidence if item.id != evidence_id]
        if len(kept) == len(case.evidence):
            raise HTTPException(404, 'evidence not found')
        case.evidence = kept
        cases().put(case)
        return Response(status_code=204)

    @router.put('/cases/{case_id}/facts', response_model=BuildingFactsResponse)
    def put_facts(case_id: str, body: BuildingFactsUpdate):
        case = get_case(case_id)
        try:
            updated = write_building_facts(case, body)
        except ValueError as error:
            raise HTTPException(422, str(error)) from error
        cases().put(case)
        return BuildingFactsResponse(
            updated=updated, professional=professional_involvement(case, code()), case=cases().get(case_id))

    @router.post('/cases/{case_id}/description', response_model=DescriptionResponse)
    def describe(case_id: str, body: DescriptionBody):
        case = get_case(case_id)
        extracted = extract_description(body.text.strip())
        for fact in extracted.facts:
            case.facts.append(_fact_from_extract(fact))
        if extracted.alternative_description:
            case.facts.append(Fact(
                field='alternative_description', value=extracted.alternative_description, kind='pointed',
                status='unconfirmed', source=Source(
                    type='description', ref='description', quote=extracted.alternative_description)))
        cases().put(case)
        views = _views(extracted)
        if extracted.alternative_description:
            views.append(DescriptionFactView(
                field='alternative_description', value=extracted.alternative_description,
                source='description', quote=extracted.alternative_description, status='unconfirmed'))
        return DescriptionResponse(
            alternative_description=extracted.alternative_description, facts=views)

    return router
