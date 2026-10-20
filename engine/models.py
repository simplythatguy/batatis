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

FactKind = Literal['exact', 'pointed', 'computed', 'proposed']
FactStatus = Literal['confirmed', 'unconfirmed']
SourceType = Literal['code', 'file', 'user_text', 'drawing', 'user_click', 'description']
AttributionStatus = Literal['direct', 'inherited from parent', 'no row in the attribution table']

INTENT_LABEL = 'NBC 2020 Intent Statements, explanatory only'


def new_id(prefix: str) -> str:
    return f'{prefix}_{uuid.uuid4().hex[:12]}'


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec='seconds')


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


class SectionCRow(BaseModel):
    provision_id: str
    citation: str
    attribution_status: AttributionStatus
    attributed_via: str | None = None          # codedb root_provision when status is inherits
    # Set when codedb attribution_status is none. Not a guessed pair.
    attribution: Literal['not_attributed'] | None = None
    attribution_label: str | None = None
    pairs: list[AttributionPair]
    intents: list[IntentBlock]
    intent_comparison: str | None = None       # match | differs | missing_in_intent | ... (codedb status)
    differs: bool = False                      # national 2020 intent attributed differently from NBC(AE) 2023
    only_in_intent: list[str] = []
    only_in_ae: list[str] = []
    related_root: str | None = None            # codedb heuristic (e.g. referenced sentence); never implied as a row
    related_root_method: str | None = None


class EvidenceItem(BaseModel):
    id: str = Field(default_factory=lambda: new_id('ev'))
    provision_id: str | None = None
    objective: str | None = None
    function: str | None = None
    description: str
    evidence_type: str | None = None
    file_id: str | None = None
    professional_required: bool | None = None
    # text: the applicant typed a listing. file: file_id names a stored file, or an older
    # row has a confirmed file-source evidence.<id>.file_ref fact.
    kind: Literal['text', 'file'] = 'text'
    # evidence_listed: the applicant listed evidence; not a check that it is sufficient,
    # and not a compliance determination. A stored ``provided`` is that same value.
    status: Literal['needed', 'evidence_listed', 'not_applicable'] = 'needed'

    @model_validator(mode='before')
    @classmethod
    def _provided_alias(cls, data):
        """Old cases stored ``provided``. Load them as ``evidence_listed`` and write that back."""
        if isinstance(data, dict) and data.get('status') == 'provided':
            return {**data, 'status': 'evidence_listed'}
        return data


class Gap(BaseModel):
    id: str = Field(default_factory=lambda: new_id('gap'))
    section: Literal['A', 'B', 'C', 'D', 'process']
    field: str
    message: str
    severity: Literal['blocking', 'warning'] = 'blocking'


def _confirmed_file_ref(facts: list[Fact], evidence_id: str) -> bool:
    """True when this evidence id has a confirmed file-source ``file_ref`` fact."""
    field = f'evidence.{evidence_id}.file_ref'
    for fact in facts:
        ref = fact.source.ref
        if (fact.field == field and fact.status == 'confirmed' and fact.kind != 'proposed'
                and fact.source.type == 'file' and isinstance(fact.value, str)
                and fact.value == ref and ref.strip()):
            return True
    return False


class Case(BaseModel):
    id: str = Field(default_factory=lambda: new_id('case'))
    title: str | None = None
    created_at: str = Field(default_factory=now)
    updated_at: str = Field(default_factory=now)
    jurisdiction: Jurisdiction | None = None
    facts: list[Fact] = []
    provisions: list[str] = []                 # Division B ids the applicant confirmed
    section_c: list[SectionCRow] = []
    evidence: list[EvidenceItem] = []
    gaps: list[Gap] = []

    @model_validator(mode='after')
    def _kind_from_stored_file(self):
        """An older row with a confirmed file-source file_ref is kind file. Otherwise leave kind."""
        for item in self.evidence:
            if _confirmed_file_ref(self.facts, item.id):
                item.kind = 'file'
        return self

    def export_facts(self) -> list[dict]:
        return [f.export() for f in self.facts]

    def export_blockers(self) -> list[str]:
        """Fact ids that keep export blocked: anything unconfirmed, including every proposed fact."""
        return [f['id'] for f in self.export_facts() if f['status'] != 'confirmed']
