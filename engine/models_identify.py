"""Code identification results stored on a case and returned by /cases/{id}/identify.

A ranking is a candidate list, not a code determination. `committed` means the identification
returned the article under the calibrated Part 9 rule; it never adds a provision to the case.
Every article id, citation and quote here comes from the code database; model text is kept only
when its quote was found word for word in the article.
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, ValidationInfo, field_validator, model_validator

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


class IdentifyResult(BaseModel):
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
