"""Wire types for identify and the article decision.

Serialization keeps fields the response already carries (`extra='allow'`), including
ranking detail the card model does not name one by one. `section_c_row` is the
same `SectionCRow` the rest of the engine returns.
"""
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from engine.models import SectionCRow


class AnswerIn(BaseModel):
    """One answer. `question_id` is the question's stable id, which is the fact field."""

    model_config = ConfigDict(extra='forbid')
    field: str | None = None
    question_id: str | None = None
    answer: str = ''


class IdentifyRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    prose: str = Field(min_length=1)
    answers: list[AnswerIn] = []


class DecisionRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    decision: Literal['yes', 'no', 'not_sure']


class Term(BaseModel):
    model_config = ConfigDict(extra='allow')
    id: str
    label: str | None = None


class ArticleBenchmark(BaseModel):
    """Numeric comparison for one resolved sentence. Distinct from the top-level benchmark."""

    model_config = ConfigDict(extra='allow')
    provision_id: str | None = None
    requirement_snippet: str | None = None
    required_value: float | None = None
    required_unit: str | None = None
    proposed_value: float | None = None
    proposed_unit: str | None = None
    fact_id: str | None = None
    comparison: Literal['below', 'above', 'equal'] | None = None


class CardExplainer(BaseModel):
    model_config = ConfigDict(extra='allow')
    text: str | None = None
    quote: str | None = None
    source: str | None = None
    label: str | None = None


class OpenQuestion(BaseModel):
    model_config = ConfigDict(extra='allow')
    id: str | None = None
    field: str | None = None
    text: str = ''
    why: str = ''
    status: str | None = None
    disambiguates: list[str] = []
    answer: str | float | int | bool | None = None


class ArticleCard(BaseModel):
    model_config = ConfigDict(extra='allow')
    rank: int | None = None
    provision: str | None = None
    provision_id: str | None = None
    link: str | None = None
    url: str | None = None
    printing: str | None = None
    page: int | None = None
    citation: str | None = None
    title: str | None = None
    snippet: str | None = None
    status: str | None = None
    verifier_status: str | None = None
    suggested: bool | None = None
    decision: Literal['yes', 'no', 'not_sure'] | None = None
    open_question_id: str | None = None
    excluded: bool | None = None
    why: str | None = None
    objectives: list[Term] = []
    functions: list[Term] = []
    attribution_missing: bool | None = None
    benchmark_acceptable_solution: str | None = None
    benchmark: ArticleBenchmark | None = None
    explainer: CardExplainer | None = None


class AcceptableBenchmark(BaseModel):
    model_config = ConfigDict(extra='allow')
    identified: bool | None = None
    provision: str | None = None
    division: str | None = None
    role: str | None = None
    explanation: str | None = None
    quote: str | None = None
    citation: str | None = None
    question: str | None = None
    section_c: list[dict[str, Any]] = []


class IdentifyResponse(BaseModel):
    """Ranked article cards. Identify does not accept an article onto the case."""

    model_config = ConfigDict(extra='allow')
    mode: Literal['live', 'cached_demo', 'bm25_fallback'] = 'bm25_fallback'
    cached: bool = False
    persisted: bool = False
    source: str | None = None
    articles: list[ArticleCard] = []
    section_c: list[dict[str, Any]] = []
    questions: list[str] = []
    open_questions: list[OpenQuestion] = []
    benchmark: AcceptableBenchmark | None = None
    variance_needed: str | None = None
    variance_explanation: str | None = None
    intake_action: str | None = None
    redirect_to: str | None = None
    engineering_required: str | None = None
    engineering_answer: str | None = None
    title: str | None = None
    model_ids: dict[str, Any] | None = None


class DecisionResponse(IdentifyResponse):
    """The identify payload plus the Section C rows a `yes` decision wrote."""

    section_c_row: list[SectionCRow] | None = None
