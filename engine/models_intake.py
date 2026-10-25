"""Intake records: where each extracted fact came from, and what was read from each file.

Stored on `Case.intake`. The facts themselves live in the case ledger (`Case.facts`). This record
adds the pointer the ledger has no room for: which pass found the fact (rules, form or model), the
character span in the text it was read from, and a per-file report that says "not read" with a
reason instead of guessing. Nothing here confirms a fact; the applicant does that.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, Field, field_validator

Method = Literal['rules', 'form', 'model']
FileStatus = Literal['read', 'partly_read', 'not_read']
FormKind = Literal['scc_variance', 'acroform']
ModelStatus = Literal['off', 'fake', 'live', 'gate_closed', 'failed', 'not_needed']


class FactPointer(BaseModel):
    """One extracted fact and where it sits. `start`/`end` index the source text: the description,
    or the page text of `page` (text layer order). Form values have no span."""
    fact_id: str
    field: str
    method: Method
    source_ref: str                         # 'description' or a case file id
    page: int | None = None                 # 1-based
    start: int | None = None
    end: int | None = None
    verified: bool = True                   # false for a model value the rules could not re-derive (proposed)


class FileReport(BaseModel):
    file_id: str
    name: str
    status: FileStatus
    reason: str | None = None               # always set when status is not 'read'
    pages: int | None = None
    pages_read: list[int] = []
    pages_not_read: list[int] = []
    form: FormKind | None = None
    form_fields_read: int = 0
    form_fields_skipped: list[str] = []     # officer, signature and unmapped fields, by name
    facts: int = 0


class ModelPass(BaseModel):
    status: ModelStatus
    model: str | None = None
    reason: str | None = None
    pointed: int = 0                        # quote found and the value re-derived from it by the rules
    proposed: int = 0                       # quote found, value not re-derived: stored as `proposed`
    dropped: int = 0                        # quote not in the source: never stored
    input_tokens: int = 0
    output_tokens: int = 0


class FieldConflict(BaseModel):
    """The text gives two different values for one field, so neither was stored. The planner asks."""
    field: str
    values: list[str | int | float | bool] = []
    quotes: list[str] = []
    source_ref: str
    page: int | None = None


class UnresolvedCitation(BaseModel):
    """An article number the applicant typed that is not in NBC(AE) 2023, 2nd printing."""
    entered: str
    source_ref: str
    page: int | None = None


class Regime(BaseModel):
    """A safety-codes regime other than the building code."""
    id: str
    name: str                               # how the applicant would say it
    code: str                               # the regulation and code it falls under
    framework: Literal['national_model_code', 'no_division_c_framework']
    coverage: Literal['roadmap', 'not_covered']   # roadmap: planned in Batatis, not built
    route: str                              # where to take the request


class ScopeCheck(BaseModel):
    status: Literal['in_scope', 'redirect', 'overridden']
    regime: Regime | None = None
    message: str | None = None
    cue: str | None = None                  # the applicant's words that decided it
    start: int | None = None                # span of `cue` in the description
    end: int | None = None
    scores: dict[str, int] = {}
    override_allowed: bool = True


class Half(BaseModel):
    """One of the two things an accepted variance needs. They are kept distinct on purpose."""
    id: Literal['variance_request', 'alternative_solution']
    label: str
    basis: str
    who: str
    what: str


class Fork(BaseModel):
    """Acceptable-solution path or alternative-solution path, read early (before Section C)."""
    variance_needed: Literal['likely', 'not_indicated', 'unknown']
    explanation: str
    cues: list[str] = []                    # the applicant's words that decided it
    halves: list[Half] = []


class Question(BaseModel):
    """At most five per plan. The shape of identify's open questions plus why it is asked and what it unblocks."""
    id: str
    field: str
    text: str
    why: str
    unblocks: list[str] = []                # in words: what an answer lets Batatis decide
    splits: list[str] = []                  # current candidate articles the answer separates (from codedb)
    priority: Literal['critical', 'administrative'] = 'critical'
    kind: Literal['missing', 'conflict'] = 'missing'
    provision: str | None = None


class PlanSource(BaseModel):
    title: str
    url: str | None = None


class PreApplicationStep(BaseModel):
    id: str
    title: str
    text: str
    origin: Literal['pack', 'generic']
    sources: list[PlanSource] = []


class PreApplication(BaseModel):
    """'Before you submit': meet the authority having jurisdiction and emergency services early."""
    jurisdiction_id: str | None = None
    jurisdiction_name: str | None = None
    resolved_by: str | None = None          # 'case' (the case's jurisdiction), 'description' (unconfirmed) or None
    steps: list[PreApplicationStep] = []


class RouteBullet(BaseModel):
    claim: str
    citations: list[PlanSource]


class RouteNotice(BaseModel):
    """Product acceptance versus a site variance, for manufacturers and jurisdiction-wide requests."""
    summary: str
    bullets: list[RouteBullet]


class IntakePlan(BaseModel):
    next: Literal['redirect', 'questions', 'identify']
    scope: ScopeCheck
    fork: Fork
    questions: list[Question] = []
    not_sure: list[str] = []                # question ids answered "not sure"; never asked again, never blocking
    pre_application: PreApplication = Field(default_factory=PreApplication)
    route_notice: RouteNotice | None = None
    candidates_seen: int = 0                # identify candidates the ranking used (0 before identify runs)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec='microseconds')


class EvidenceRef(BaseModel):
    """An exact excerpt of the request or of one page of an attached file, checked against that text."""
    source_ref: str                         # 'description' or a case file id
    page: int | None = None                 # 1-based; None for the request and single-page text files
    quote: str


class ReviewedDocument(BaseModel):
    file_id: str
    kind: str                               # what the document is, in a few words (an appeal decision, a design guide)
    title: str | None = None
    author: str | None = None
    date: str | None = None
    status: str | None = None               # e.g. concept only, superseded, decided; never an approval of the design


ReviewFlagKind = Literal['outside_alberta', 'code_edition', 'other_discipline', 'record_status', 'outcome_known',
                         'not_read']


class ReviewFlag(BaseModel):
    kind: ReviewFlagKind
    text: str                               # Batatis's own sentence
    evidence: list[EvidenceRef] = []


FactStatus = Literal['stated', 'existing', 'proposed', 'assumed', 'decided', 'argued', 'condition', 'recommended',
                     'tested']


class ReviewFact(BaseModel):
    text: str                               # a plain restatement whose numbers all occur in the evidence
    status: FactStatus
    evidence: list[EvidenceRef]


class ReviewConflict(BaseModel):
    text: str
    evidence: list[EvidenceRef]             # at least two excerpts that disagree


class CitedProvision(BaseModel):
    cited: str                              # as the document writes it
    code: str | None = None                 # the code or edition the document names for it
    resolves_to: str | None = None          # the NBC(AE) 2023 2nd printing provision id, when it resolves
    division: str | None = None
    evidence: list[EvidenceRef] = []


class ReviewItem(BaseModel):
    text: str
    why: str


class DocumentReview(BaseModel):
    """What the model read across every readable page, kept only where it checks out against the text.

    Facts, conflicts and cited provisions carry excerpts that occur in the named page. Missing items,
    questions and flags are Batatis's own words and never say that a design complies, is safe or is approved."""
    status: ModelStatus
    model: str | None = None                # an opaque version (engine/public_names.py), never a provider pin
    effort: str | None = None
    reason: str | None = None
    documents: list[ReviewedDocument] = []
    flags: list[ReviewFlag] = []
    facts: list[ReviewFact] = []
    conflicts: list[ReviewConflict] = []
    provisions: list[CitedProvision] = []
    missing: list[ReviewItem] = []
    questions: list[ReviewItem] = []
    pages_sent: int = 0
    dropped: int = 0                        # model items removed because their excerpt or numbers did not check out
    input_tokens: int = 0
    output_tokens: int = 0

    @field_validator('model')
    @classmethod
    def _model_is_an_opaque_version(cls, value):
        from .public_names import public_review_model
        return public_review_model(value)


class IntakeRecord(BaseModel):
    ran_at: str = Field(default_factory=_now)
    text_sha256: str | None = None
    pointers: list[FactPointer] = []
    files: list[FileReport] = []
    model: ModelPass = Field(default_factory=lambda: ModelPass(status='off'))
    conflicts: list[FieldConflict] = []
    unresolved_citations: list[UnresolvedCitation] = []
    plan: IntakePlan | None = None
    review: DocumentReview | None = None
