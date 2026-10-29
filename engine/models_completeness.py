"""Shared administrative policy contract; presentation and workflow do not own rules."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from .models import Source


class PolicyPointer(BaseModel):
    model_config = ConfigDict(extra='forbid')
    file: str
    page: int | None = None
    form_field: str | None = None
    bbox: tuple[float, float, float, float] | None = None
    quote: str | None = None


class AdministrativeItem(BaseModel):
    model_config = ConfigDict(extra='forbid')
    key: str
    field: str
    section: Literal['A', 'B', 'C', 'D', 'process']
    label: str
    verdict: Literal['present', 'missing', 'unclear']
    reason_code: str
    reason: str
    value: str | None = None
    certainty: Literal['present', 'blank', 'not_found', 'not_applicable']
    finding_status: Literal['blank', 'not_found', 'missing', 'unclear'] | None = None
    severity: Literal['blocking', 'warning', 'info']
    routed_to: Literal['applicant', 'officer', 'professional']
    export_blocking: bool
    submission_blocking: bool = True
    fix_hint: str = ''
    citations: list[str] = Field(default_factory=list)
    sources: list[Source] = Field(default_factory=list)
    pointers: list[PolicyPointer] = Field(default_factory=list)


class AdministrativeReport(BaseModel):
    model_config = ConfigDict(extra='forbid')
    schema_version: Literal['batatis.administrative_completeness.v1'] = 'batatis.administrative_completeness.v1'
    policy_version: Literal['2026-10-26'] = '2026-10-26'
    stage: Literal['preparation'] = 'preparation'
    administrative_only: Literal[True] = True
    not_a_compliance_determination: Literal[True] = True
    items: list[AdministrativeItem]
    export_reasons: list[str]
    ready_for_export: bool


class ProfessionalDeclaration(BaseModel):
    model_config = ConfigDict(extra='forbid')
    involvement: Literal['professional_involved', 'not_required', 'unresolved']
    requirement: Literal['yes', 'no', 'depends']
    applicant_confirmation: bool
    name: str
    role: str
    basis: str
    owner: str
    location: str
    pathway: str = 'alternative'
    bound_to_application: bool = False
    pointer: PolicyPointer


def field_label(field: str) -> str:
    """What people see for a gap's field. An open question from accepted draft wording is keyed by
    draft id; people see what it is, not the key."""
    if field.startswith('drafting.questions.'):
        return 'Open question from the drafted wording'
    return field.replace('_', ' ')
