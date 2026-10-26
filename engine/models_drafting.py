"""Saved applicant writing and its provenance; independent of the case/fact models."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .ccmc import RegistrySearch


class DraftModel(BaseModel):
    model_config = ConfigDict(extra='forbid')


class DraftSource(DraftModel):
    id: str
    kind: Literal['description', 'fact', 'document', 'code', 'section_c', 'guidance',
                  'precedent_structure', 'professional_screen', 'registry']
    ref: str
    page: int | None = None
    label: str
    text: str
    url: str | None = None
    metadata: dict[str, str | int | bool | None] = Field(default_factory=dict)


class DraftCitation(DraftModel):
    source_id: str = Field(min_length=1, max_length=100)
    quote: str = Field(min_length=1, max_length=8000)


class DraftClaim(DraftModel):
    text: str = Field(min_length=1, max_length=3000)
    kind: Literal['fact', 'assumption', 'plan']
    sources: list[DraftCitation] = Field(min_length=1, max_length=8)


class DraftQuestion(DraftModel):
    text: str = Field(min_length=1, max_length=1000)
    why: str = Field(min_length=1, max_length=1500)
    routed_to: Literal['applicant', 'professional']
    sources: list[DraftCitation] = Field(min_length=1, max_length=8)


def assembled_text(claims: list[DraftClaim]) -> str:
    """The only prose saved as an answer. Assumptions and future work stay labelled."""
    prefixes = {'fact': '', 'assumption': 'Assumption: ', 'plan': 'Plan: '}
    return '\n\n'.join(prefixes[claim.kind] + claim.text for claim in claims)


class ApplicantDraft(DraftModel):
    id: str
    generation_id: str
    input_fingerprint: str
    field: str
    title: str
    text: str
    claims: list[DraftClaim] = Field(max_length=16)
    questions: list[DraftQuestion] = Field(max_length=12)
    status: Literal['draft', 'accepted', 'rejected'] = 'draft'
    generated_at: str
    decided_at: str | None = None
    decided_by: str | None = None
    decision_expected_version: int | None = None
    accepted_fact_id: str | None = None
    replaces_fact_id: str | None = None       # only a verified intake-read rough Section B passage

    @model_validator(mode='after')
    def _only_claim_prose(self):
        if self.text != assembled_text(self.claims):
            raise ValueError('draft text must be assembled solely from its cited claims')
        if not self.claims and not self.questions:
            raise ValueError('a draft needs writing or an explicit gap question')
        return self


class DraftGeneration(DraftModel):
    id: str
    generated_at: str
    provider: str
    model: str
    effort: str
    auditor_model: str
    validation: Literal['grounded'] = 'grounded'
    input_tokens: int | None = None
    output_tokens: int | None = None
    audit_input_tokens: int | None = None
    audit_output_tokens: int | None = None


class DraftRegistryQuery(DraftModel):
    query: str
    source_id: str
    quote: str
    start: int
    end: int


class DraftingRecord(DraftModel):
    schema_version: Literal['batatis.applicant_drafts.v1'] = 'batatis.applicant_drafts.v1'
    input_fingerprint: str
    generated_at: str
    stale: bool = False
    stale_reasons: list[str] = Field(default_factory=list)
    sources: list[DraftSource]
    drafts: list[ApplicantDraft]
    generations: list[DraftGeneration]
    registry_searches: list[RegistrySearch] = Field(default_factory=list)
    registry_queries: list[DraftRegistryQuery] = Field(default_factory=list)
    notices: list[str] = Field(default_factory=list)
