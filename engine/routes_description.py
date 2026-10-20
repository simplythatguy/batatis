"""Paste a description, read the extracted facts, confirm or correct a field."""
from __future__ import annotations

from typing import Callable

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict, Field, model_validator

from .codes import CodeDbMissing, Codes
from .fact_extraction import (
    ApplicantRole, Installation, Scope, Sprinklered, apply_patch, blank_facts, gaps_summary,
    record_description, unavailable_summary,
)
from .professional import Occupancy
from .store import CaseStore


class DescriptionIn(BaseModel):
    model_config = ConfigDict(extra='forbid')
    text: str = Field(min_length=1, max_length=8000)


class FactsPatch(BaseModel):
    """Scalar corrections. Omitted fields stay as they are. An empty body is rejected."""
    model_config = ConfigDict(extra='forbid')
    applicant_role: ApplicantRole | None = None
    owner_name: str | None = None
    municipal_address: str | None = None
    mailing_address: str | None = None
    legal_description: str | None = None
    permit_number: str | None = None
    municipality: str | None = None
    jurisdiction_scope: Scope | None = None
    occupancy: Occupancy | None = None
    storeys: int | None = Field(default=None, ge=1)
    building_area_m2: float | None = Field(default=None, gt=0)
    dwelling_units: int | None = Field(default=None, ge=1)
    sprinklered: Sprinklered | None = None
    product_or_assembly: str | None = None
    installation_status: Installation | None = None
    proposed_alternative: str | None = None
    required_acceptable_solution: str | None = None
    project_name: str | None = None

    @model_validator(mode='after')
    def _not_empty(self):
        if not self.model_fields_set:
            raise ValueError('empty facts patch')
        if any(getattr(self, name) is None for name in self.model_fields_set):
            raise ValueError('null is not a fact value')
        return self


def create_router(cases: Callable[[], CaseStore], code: Callable[[], Codes]) -> APIRouter:
    router = APIRouter(tags=['description'])

    def get_case(case_id: str):
        case = cases().get(case_id)
        if case is None:
            raise HTTPException(404, 'case not found')
        return case

    def codes_or_none():
        try:
            return code()
        except CodeDbMissing:
            return None

    @router.post('/cases/{case_id}/description')
    def post_description(case_id: str, body: DescriptionIn):
        case = get_case(case_id)
        facts = record_description(case, body.text, codes_or_none())
        cases().put(case)
        text = facts.proposed_alternative.value
        return {'facts': facts.model_dump(mode='json'), 'alternative_description': text, 'proposed_alternative': text}

    @router.get('/cases/{case_id}/facts')
    def get_facts(case_id: str):
        case = get_case(case_id)
        facts = case.intake_facts if case.intake_facts else blank_facts().model_dump(mode='json')
        return facts

    @router.patch('/cases/{case_id}/facts')
    def patch_facts(case_id: str, body: FactsPatch):
        case = get_case(case_id)
        updates = body.model_dump(exclude_unset=True)
        facts = apply_patch(case, updates)
        cases().put(case)
        try:
            summary = gaps_summary(case, code())
        except CodeDbMissing:
            summary = unavailable_summary(case)
        return {'facts': facts.model_dump(mode='json'), 'gaps_summary': summary}

    return router
