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
    EvidenceClosure, ProvisionEvidenceGap, evidence_closures, group_evidence_gaps, rank_gaps,
    scoped_plan_items, uncovered_items)
from .models import Case, EvidenceItem, Fact, Source
from .professional import ProfessionalResult, professional_involvement
from .section_d import EvidenceType, section_d_plan
from .store import CaseStore


class EvidenceCreate(BaseModel):
    model_config = ConfigDict(extra='forbid')
    provision_id: str | None = Field(default=None, min_length=1)
    objective: str | None = None
    function: str | None = None
    evidence_type: EvidenceType
    description: str = Field(min_length=1, max_length=4000)
    responsible_party: str | None = Field(default=None, max_length=500)
    date: str | None = Field(default=None, max_length=80)
    file_id: str | None = Field(default=None, min_length=1, max_length=200)

    @model_validator(mode='after')
    def _pair(self):
        self.description = self.description.strip()
        if not self.description:
            raise ValueError('description is empty')
        self.provision_id = _blank_to_none(self.provision_id)
        self.responsible_party = _blank_to_none(self.responsible_party)
        self.date = _blank_to_none(self.date)
        self.file_id = _blank_to_none(self.file_id)
        if (self.objective is None) != (self.function is None):
            raise ValueError('objective and function must both be sent, or neither')
        if self.provision_id is None and self.objective is not None:
            raise ValueError('objective and function require a provision_id')
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


def _blank_to_none(value: str | None) -> str | None:
    if value is None:
        return None
    text = value.strip()
    return text or None


def _stored_file(case: Case, file_id: str) -> bool:
    """True when a fact already on the case points at this file. Bytes are not read."""
    return any(fact.source.type == 'file' and fact.source.ref == file_id for fact in case.facts)


def _user_text(field: str, value: str) -> Fact:
    """Applicant-typed listing metadata. This is not a file reference."""
    return Fact(field=field, value=value, kind='pointed', status='confirmed',
                source=Source(type='user_text', ref='applicant', quote=value))


def _listing_facts(item: EvidenceItem, body: EvidenceCreate) -> list[Fact]:
    """Title, responsible party, and date. Never a ``file_ref``."""
    facts = [_user_text(f'evidence.{item.id}.title', item.description)]
    if body.responsible_party:
        facts.append(_user_text(f'evidence.{item.id}.responsible_party', body.responsible_party))
    if body.date:
        facts.append(_user_text(f'evidence.{item.id}.date', body.date))
    return facts


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

    def open_items(case: Case):
        try:
            plan = section_d_plan(case, code()) if case.provisions else None
        except KeyError as error:
            raise HTTPException(404, error.args[0]) from error
        except ValueError as error:
            raise HTTPException(400, f'invalid provision id: {error}') from error
        return scoped_plan_items(case, plan.items) if plan else []

    @router.post('/cases/{case_id}/evidence', response_model=EvidenceCreated, status_code=201)
    def add_evidence(case_id: str, body: EvidenceCreate):
        case = get_case(case_id)
        if body.file_id is not None and not _stored_file(case, body.file_id):
            raise HTTPException(400, 'file_id does not match a stored file')
        kind = 'file' if body.file_id is not None else 'text'
        if body.provision_id is None:
            try:
                items = open_items(case)
            except HTTPException:
                items = []
            item = EvidenceItem(
                provision_id=None, objective=None, function=None, description=body.description,
                evidence_type=body.evidence_type, file_id=body.file_id, kind=kind,
                professional_required=None, status='evidence_listed')
            case.evidence.append(item)
            case.facts.extend(_listing_facts(item, body))
            cases().put(case)
            still_open = uncovered_items(items, case.evidence)
            return EvidenceCreated(
                evidence=item, gaps=rank_gaps(group_evidence_gaps(still_open)), closed=[])
        items = open_items(case)
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
            kind=kind, professional_required=None, status='evidence_listed')
        case.evidence.append(item)
        case.facts.extend(_listing_facts(item, body))
        cases().put(case)
        still_open = uncovered_items(items, case.evidence)
        return EvidenceCreated(
            evidence=item, gaps=rank_gaps(group_evidence_gaps(still_open)),
            closed=evidence_closures(before, still_open))

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
