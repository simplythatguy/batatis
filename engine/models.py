"""Case record shared by every way in (describe, site plan, officer review).

Every value is a Fact that points at its source. A fact's kind says how it was obtained:
  exact     - copied from the code database or a form field
  pointed   - a span the model selected from the user's words or files (never generated)
  computed  - code over exact and pointed values
  proposed  - model judgement; shown with confidence and never exported as confirmed
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, Field, model_validator
from .account_models import ApplicationStatus, Claim, Decision, StatusChange, StoredMessage

from .relevance_models import RelevanceRecord

FactKind = Literal['exact', 'pointed', 'computed', 'proposed']
FactStatus = Literal['confirmed', 'unconfirmed']
SourceType = Literal['code', 'file', 'user_text', 'drawing', 'user_click', 'officer', 'professional']
RouteTarget = Literal['officer', 'professional', 'applicant']
AttributionStatus = Literal['direct', 'inherited from parent', 'no row in the attribution table']

INTENT_LABEL = 'NBC 2020 Intent Statements, explanatory only'


def new_id(prefix: str) -> str:
    return f'{prefix}_{uuid.uuid4().hex[:12]}'


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec='microseconds')


class Source(BaseModel):
    type: SourceType
    ref: str                                   # provision id, file name, message id, sheet id ...
    page: int | None = None
    bbox: tuple[float, float, float, float] | None = None
    quote: str | None = None


class Fact(BaseModel):
    id: str = Field(default_factory=lambda: new_id('fact'))
    field: str
    value: str | float | int | bool | None
    kind: FactKind
    source: Source
    confidence: float | None = Field(default=None, ge=0, le=1)
    status: FactStatus = 'unconfirmed'
    formula: str | None = None                 # computed facts only: the formula as shown to the user
    inputs: list[str] = []                     # computed facts only: ids of the facts the formula reads

    @model_validator(mode='after')
    def _proposed_is_never_confirmed(self):
        if self.kind == 'proposed' and self.status == 'confirmed':
            raise ValueError('a proposed fact cannot be confirmed; record the confirmation as a new fact '
                             'with a user_click source')
        if self.kind != 'computed' and (self.formula is not None or self.inputs):
            raise ValueError('formula and inputs belong to computed facts only')
        return self

    def export(self) -> dict:
        """Export form. Re-checks the invariant so a mutated instance still cannot leak as confirmed."""
        out = self.model_dump()
        if self.kind == 'proposed':
            out['status'] = 'unconfirmed'
        return out


class Jurisdiction(BaseModel):
    id: str                                    # e.g. "calgary", "edmonton", "alberta-other"
    name: str
    authority: str | None = None


class AttributionPair(BaseModel):
    function: str
    function_text: str | None = None
    objective: str
    objective_text: str | None = None
    bracket: str
    clauses: list[str] = []                    # [] = whole sentence
    application_note: str | None = None
    table: str
    pdf_page: int


class IntentBlock(BaseModel):
    label: str = INTENT_LABEL
    provision_id: str
    objective: str | None
    brackets: list[str]
    notes: list[str]
    intents: list[str]
    pdf_page: int


class Explainer(BaseModel):
    """Short note on a Section C row. A quote is copied from codedb; the note never finds compliance."""
    text: str
    quote: str
    source: Literal['ai_written', 'deterministic']


class SectionCRow(BaseModel):
    provision_id: str
    citation: str
    attribution_status: AttributionStatus
    attributed_via: str | None = None          # parent provision when inherited
    pairs: list[AttributionPair]
    intents: list[IntentBlock]
    intent_comparison: str | None = None       # match | differs | missing_in_intent | ... (codedb status)
    differs: bool = False                      # national 2020 intent attributed differently from NBC(AE) 2023
    only_in_intent: list[str] = []
    only_in_ae: list[str] = []
    related_root: str | None = None            # codedb heuristic (e.g. referenced sentence); never implied as a row
    related_root_method: str | None = None
    explainer: Explainer | None = None         # deterministic template, or null when there is nothing to quote


class EvidenceItem(BaseModel):
    id: str = Field(default_factory=lambda: new_id('ev'))
    objective: str | None = None
    function: str | None = None
    description: str
    evidence_type: str | None = None
    professional_required: bool | None = None
    status: Literal['needed', 'evidence_listed', 'not_applicable'] = 'needed'
    # text: the applicant listed it and no file is attached. file: a confirmed file-source file_ref exists.
    kind: Literal['text', 'file'] = 'text'

    @model_validator(mode='before')
    @classmethod
    def _provided_loads_as_listed(cls, data):
        """A stored provided row is evidence_listed. Old cases load, and the next write stores the new token."""
        if isinstance(data, dict) and data.get('status') == 'provided':
            return {**data, 'status': 'evidence_listed'}
        return data


class Gap(BaseModel):
    id: str = Field(default_factory=lambda: new_id('gap'))
    section: Literal['A', 'B', 'C', 'D', 'process']
    field: str
    message: str
    severity: Literal['blocking', 'warning'] = 'blocking'
    routed_to: RouteTarget | None = None


class Case(BaseModel):
    id: str = Field(default_factory=lambda: new_id('case'))
    title: str | None = None
    owner_id: str | None = None
    authority: str | None = None
    status: ApplicationStatus = 'draft'
    submitted_at: str | None = None
    status_history: list[StatusChange] = Field(default_factory=list)
    claim: Claim | None = None
    decision: Decision | None = None
    messages: list[StoredMessage] = Field(default_factory=list)
    created_at: str = Field(default_factory=now)
    updated_at: str = Field(default_factory=now)
    version: int = Field(default=1, ge=1)      # acknowledgment of the store's row version, never input authority
    jurisdiction: Jurisdiction | None = None
    facts: list[Fact] = []
    provisions: list[str] = []                 # Division B ids the applicant confirmed
    section_c: list[SectionCRow] = []
    evidence: list[EvidenceItem] = []
    gaps: list[Gap] = []
    relevance: RelevanceRecord | None = None   # explicit scoring only; GET recomputes its staleness

    @model_validator(mode='after')
    def _kind_follows_the_file(self):
        """kind is file only when a confirmed file-source file_ref exists. Otherwise it is text."""
        for item in self.evidence:
            prefix = f'evidence.{item.id}.file_ref'
            fact = next((entry for entry in reversed(self.facts) if entry.field == prefix), None)
            has_file = (
                fact is not None and fact.status == 'confirmed' and fact.kind != 'proposed'
                and fact.source.type == 'file' and fact.value == fact.source.ref
                and isinstance(fact.source.ref, str) and fact.source.ref.strip())
            item.kind = 'file' if has_file else 'text'
        return self

    def export_facts(self) -> list[dict]:
        return [f.export() for f in self.facts]

    def export_blockers(self) -> list[str]:
        """Fact ids that keep export blocked: anything unconfirmed, including every proposed fact."""
        return [f['id'] for f in self.export_facts() if f['status'] != 'confirmed']
