"""Code identification results stored on a case and returned by /cases/{id}/identify.

A ranking is a candidate list, not a code determination. `committed` means the identification
returned the article under the calibrated Part 9 rule; it never adds a provision to the case.
Every article id, citation and quote here comes from the code database; model text is kept only
when its quote was found word for word in the article.
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, ValidationInfo, field_validator, model_validator
from .models_scope import PartScopeAssessment

from .public_names import (UNAVAILABLE, VERIFIER_UNAVAILABLE, public_config, public_label, public_method,
                           public_model_id, public_ranker, public_spend, public_stage_model, public_text)

Decision = Literal['yes', 'no', 'not_sure']
IdentifyMode = Literal['live', 'fake', 'bm25_fallback']
ArticleStatus = Literal['committed', 'choice', 'candidate', 'fallback']


class Term(BaseModel):
    """An objective (OS1.2) or functional statement (F03) attributed to the provision, by lookup."""
    id: str
    label: str | None = None


class IdentifyArticle(BaseModel):
    rank: int
    provision: str                              # Division B article id, e.g. 9.10.15.5.
    provision_id: str | None = None             # sentence id when the quote sits in exactly one sentence
    division: Literal['B'] = 'B'
    title: str
    part: int
    citation: str | None = None
    link: str
    quote: str | None = None                    # verbatim from codedb (verifier quote checked, or first words)
    quote_source: Literal['verifier', 'codedb'] | None = None
    reason: str | None = None                   # verifier's one line; never a compliance claim
    probability: float | None = None            # rerank probability (none for the keyword fallback)
    screen_probability: float | None = None
    verifier: Literal['picked', 'not_picked', 'not_run'] = 'not_run'
    status: ArticleStatus
    commit_reason: str
    objectives: list[Term] = []
    functions: list[Term] = []
    attribution_missing: bool = True
    decision: Decision | None = None
    open_question_id: str | None = None


class QuotedChoice(BaseModel):
    """'The code says X. Does your design do something different?' The id sits behind a disclosure."""
    id: str
    provision: str
    provision_id: str | None = None
    title: str
    part: int
    citation: str | None = None
    quote: str
    question: str


class OpenQuestion(BaseModel):
    id: str
    field: str
    text: str
    why: str
    provision: str | None = None


class BenchmarkRecord(BaseModel):
    """The benchmark acceptable solution: the quoted Division B sentence the design departs from,
    a one-line departure the applicant confirms, and its objective and function codes by lookup."""
    identified: bool
    role: Literal['benchmark_acceptable_solution'] = 'benchmark_acceptable_solution'
    basis: Literal['committed', 'top_choice', 'applicant', 'none'] = 'none'
    provision: str | None = None
    provision_id: str | None = None
    citation: str | None = None
    sentence: str | None = None                 # verbatim codedb text of provision_id (or the quote's article)
    departure: str | None = None
    departure_status: Literal['none', 'proposed', 'confirmed'] = 'none'
    objectives: list[Term] = []
    functions: list[Term] = []
    attribution_missing: bool = True
    requirement: dict | None = None             # numeric requirement in the sentence vs confirmed facts (requirement.py)
    question: str | None = None


class ProcessRef(BaseModel):
    """A process reference listed on every case, read-only: how an alternative solution is allowed and documented."""
    provision_id: str
    division: Literal['A', 'C']
    title: str
    citation: str
    text: str
    role: str
    pdf_page: int | None = None
    read_only: Literal[True] = True


class DroppedPick(BaseModel):
    article: str
    reason: str


class StageRecord(BaseModel):
    stage: str
    method: str
    model: str | None = None
    seconds: float = 0
    requests: int = 0
    input_tokens: int | None = 0
    output_tokens: int | None = 0
    errors: int = 0
    detail: str | None = None

    @model_validator(mode='before')
    @classmethod
    def _stage_model_has_its_scoring_role(cls, value):
        if isinstance(value, dict) and 'model' in value:
            return {**value, 'model': public_stage_model(value.get('method'), value['model'])}
        return value

    @field_validator('method')
    @classmethod
    def _method_names_no_service(cls, value):
        return public_method(value)

    @field_validator('model')
    @classmethod
    def _model_is_an_opaque_version(cls, value):
        return public_model_id(value)


class IdentifyTrace(BaseModel):
    config: dict
    config_hash: str
    exhaustive: bool
    articles_expected: int
    articles_scored: int
    ranker: str
    fallback_reason: str | None = None
    verifier: str
    picks: list[str] = []
    dropped: list[DroppedPick] = []
    stages: list[StageRecord] = []
    spend: dict = {}
    usd: float | None = 0
    seconds: float = 0

    # What a client reads about how the run went names no provider, model pin or credential (engine/public_names.py).
    # The same checks clean a result stored before they existed when it loads.
    @field_validator('config')
    @classmethod
    def _config_names_no_service(cls, value):
        return public_config(value)

    @field_validator('ranker')
    @classmethod
    def _ranker_names_no_service(cls, value):
        return public_ranker(value)

    @field_validator('fallback_reason')
    @classmethod
    def _reason_names_no_service(cls, value):
        return public_text(value, UNAVAILABLE)

    @field_validator('verifier')
    @classmethod
    def _verifier_state_names_no_service(cls, value):
        return public_text(value, VERIFIER_UNAVAILABLE)

    @field_validator('spend')
    @classmethod
    def _spend_is_by_role(cls, value):
        return public_spend(value)


class ArticleDecision(BaseModel):
    decision: Decision
    open_question_id: str | None = None
    decided_at: str


class RequirementSource(BaseModel):
    """Provenance verified against both CodeDB's docs row and build metadata.

    Hashes identify the registered extraction/PDF; they do not certify the parser.
    """
    doc: Literal['NBC-AE'] = 'NBC-AE'
    label: Literal['NBC(AE) 2023 p2'] = 'NBC(AE) 2023 p2'
    text_sha256: str
    pdf_sha256: str
    build_version: str
    corpus_sha256: str


class RequirementEvidence(BaseModel):
    """An actual matched passage or reference, never an arbitrary opening sentence."""
    id: str
    division: Literal['A', 'B', 'C']
    provision_id: str                         # a real provision or note id in the verified source
    kind: Literal['provision', 'heading', 'note']
    quote: str
    citation: str
    pdf_page: int | None = None
    pdf_page_end: int | None = None
    source_sha256: str
    contextual: bool = False                 # notes explain; they are not normative requirements


class RequirementDiscovery(BaseModel):
    kind: Literal['lexical', 'explicit', 'reference', 'reverse_reference', 'administrative', 'human', 'previous']
    detail: str
    from_requirement: str | None = None
    path: list[str] = Field(default_factory=list)  # one discovery path, not every walk through a cycle
    evidence: RequirementEvidence | None = None
    evidence_id: str | None = None             # shared exact passage in requirement_evidence
    evidence_ids: list[str] = Field(default_factory=list)


class RequirementCondition(BaseModel):
    field: str
    status: Literal['unknown', 'provided', 'conflict'] = 'unknown'
    fact_ids: list[str] = Field(default_factory=list)
    # A provided input is not a finding that a source condition is satisfied.


class RequirementLink(BaseModel):
    source_requirement: str
    target_requirement: str
    evidence_ids: list[str] = Field(default_factory=list)


class RequirementRecord(BaseModel):
    """A source-qualified candidate, with applicability separate from discovery.

    Records group an article's matched sentences/clauses. Inclusion requires a human
    decision; a reference edge or keyword match never proves applicability or a departure.
    """
    id: str
    provision_id: str | None = None            # article id; absent when current source cannot be verified
    division: Literal['A', 'B', 'C'] | None = None
    title: str = ''
    role: Literal['varied', 'supporting', 'admin', 'conditional', 'unresolved'] = 'unresolved'
    disposition: Literal['include', 'review', 'exclude'] = 'review'
    applicability: Literal['unknown', 'confirmed', 'needs_review'] = 'unknown'
    human_confirmed: bool = False
    confirmation_fingerprint: str | None = None
    confirmation_reason: str | None = None
    confirmed_at: str | None = None
    needs_review: bool = True
    source_status: Literal['verified', 'unavailable'] = 'verified'
    citation: str | None = None
    quote: str | None = None
    quote_provision_id: str | None = None
    pdf_page: int | None = None
    pdf_page_end: int | None = None
    source_sha256: str | None = None
    discoveries: list[RequirementDiscovery] = Field(default_factory=list)
    evidence: list[RequirementEvidence] = Field(default_factory=list)
    evidence_ids: list[str] = Field(default_factory=list)  # all passages; shared text is stored once
    conditions: list[RequirementCondition] = Field(default_factory=list)
    review_reasons: list[str] = Field(default_factory=list)


class RequirementGap(BaseModel):
    code: str
    message: str
    reference: str | None = None              # unresolved input/source text; never a fabricated citation
    from_requirement: str | None = None
    evidence: RequirementEvidence | None = None
    evidence_id: str | None = None


class RequirementCoverage(BaseModel):
    source: RequirementSource | None = None
    scan_status: Literal['not_run', 'scanned', 'unavailable'] = 'not_run'
    graph_status: Literal['not_run', 'traversed', 'traversed_with_gaps'] = 'not_run'
    applicability_status: Literal['not_determined'] = 'not_determined'
    exhaustive: Literal[False] = False
    articles_by_division: dict[str, int] = Field(default_factory=dict)
    provisions_scanned: int = 0
    notes_scanned: int = 0
    query_chunks: int = 0
    discovered: int = 0
    human_confirmed: int = 0
    gaps: list[RequirementGap] = Field(default_factory=list)
    limits: list[str] = Field(default_factory=list)
    provider_requests: Literal[0] = 0


class RequirementSet(BaseModel):
    """Additive ledger fields; old stored results load with an explicit not-run state."""
    requirements: list[RequirementRecord] = Field(default_factory=list)
    requirement_evidence: list[RequirementEvidence] = Field(default_factory=list)
    requirement_links: list[RequirementLink] = Field(default_factory=list)
    requirement_status: Literal['not_run', 'needs_review', 'source_unavailable'] = 'not_run'
    requirement_coverage: RequirementCoverage = Field(default_factory=RequirementCoverage)
    input_fingerprint: str | None = None
    scope_assessments: list[PartScopeAssessment] = Field(default_factory=list)


class IdentifyResult(RequirementSet):
    mode: IdentifyMode
    source: str                                 # 'live', 'fake' or 'bm25 fallback'
    label: str
    narrowed: bool
    message: str | None = None
    articles: list[IdentifyArticle] = []
    committed: list[str] = []
    choices: list[QuotedChoice] = []
    questions: list[str] = []
    open_questions: list[OpenQuestion] = []
    benchmark: BenchmarkRecord
    process_refs: list[ProcessRef] = []
    model_ids: dict[str, str | None] = {}
    commit_policy: dict = {}
    engineering_required: Literal['depends'] = 'depends'
    title: str | None = None
    scored_at: str
    description_sha256: str
    input_sha256: str | None = None           # parent-composed facts/documents/answers fingerprint
    input_coverage_gaps: list[str] = Field(default_factory=list)
    stale: bool = False
    persisted: bool = False
    case_version: int | None = None             # the case version after this read or write; send it back as expected_version
    cached: bool = False
    decisions: dict[str, ArticleDecision] = Field(default_factory=dict)
    trace: IdentifyTrace

    @field_validator('label')
    @classmethod
    def _label_names_no_service(cls, value, info: ValidationInfo):
        return public_label(value, info.data.get('mode'))

    @field_validator('model_ids')
    @classmethod
    def _model_ids_are_opaque_versions(cls, value):
        return {stage: public_model_id(pin) for stage, pin in value.items()}
