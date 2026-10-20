"""HTTP shape for POST /cases/{id}/completeness. Grouped by SCC template Part 1 A–D."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from .bulletin_gates import applicant_reminder
from .completeness_elements import NOTICE, SECTION_TITLES
from .completeness_variants import VariantResult, format_export_reason


class IntakePromptModel(BaseModel):
    model_config = ConfigDict(extra='forbid')
    question: str
    field: str
    form_fields: list[str]
    source: Literal['applicant', 'registered_professional']


class QuoteModel(BaseModel):
    model_config = ConfigDict(extra='forbid')
    text: str
    kind: Literal['exact', 'pointed']
    source_ref: str


class ElementModel(BaseModel):
    model_config = ConfigDict(extra='forbid')
    field: str
    template_section: Literal['A', 'B', 'C', 'D']
    export_section: Literal['A', 'B', 'C', 'D', 'process']
    export_field: str
    form_fields: list[str]
    label: str
    group: str = ''
    verdict: Literal['present', 'missing', 'unclear']
    reason: str
    defect_class: str | None = None
    problem: str | None = None
    quotes: list[QuoteModel] = Field(default_factory=list)
    prompt: IntakePromptModel | None = None
    lookup_skipped: bool = False
    in_export_preflight: bool = False
    source: Literal['applicant', 'registered_professional']


class SectionModel(BaseModel):
    model_config = ConfigDict(extra='forbid')
    section: Literal['A', 'B', 'C', 'D']
    title: str
    elements: list[ElementModel]


class ReviewModel(BaseModel):
    model_config = ConfigDict(extra='forbid')
    document_id: str
    sections: list[SectionModel]
    reasons_by_section: dict[str, list[str]]
    export_reasons: list[str]
    invented_values: int


class LLMUsageModel(BaseModel):
    model_config = ConfigDict(extra='forbid')
    provider: str | None = None
    model: str | None = None
    input_tokens: int = 0
    output_tokens: int = 0
    latency_s: float = 0.0
    estimated_usd: float = 0.0
    skipped: str | None = None


class ReminderModel(BaseModel):
    """IB-2025-11-18 copy of the issued variance. Not a present/missing/unclear verdict and not an export blocker."""

    model_config = ConfigDict(extra='forbid')
    verdict: Literal['reminder'] = 'reminder'
    bulletin_ids: list[str]
    text: str
    links: list[str]


class CompletenessResponse(BaseModel):
    model_config = ConfigDict(extra='forbid')
    schema_version: Literal['batatis.completeness.v1'] = 'batatis.completeness.v1'
    variant: str
    administrative_only: Literal[True] = True
    not_a_compliance_determination: Literal[True] = True
    notice: str = NOTICE
    reviews: list[ReviewModel]
    reminder: ReminderModel
    llm: LLMUsageModel | None = None


def _review(result: VariantResult, export_reasons: list[str] | None = None) -> ReviewModel:
    grouped: dict[str, list[ElementModel]] = {key: [] for key in 'ABCD'}
    for element in result.elements:
        grouped[element.template_section].append(ElementModel(
            field=element.field, template_section=element.template_section, export_section=element.export_section,
            export_field=element.export_field, form_fields=element.form_fields, label=element.label, group=element.group,
            verdict=element.verdict, reason=element.reason, defect_class=element.defect_class, problem=element.problem,
            quotes=[QuoteModel(text=quote.text, kind='exact' if quote.kind == 'exact' else 'pointed',
                               source_ref=quote.source_ref) for quote in element.quotes],
            prompt=None if element.prompt is None else IntakePromptModel(**element.prompt),
            lookup_skipped=element.lookup_skipped, in_export_preflight=element.in_export_preflight,
            source=element.source if element.source in ('applicant', 'registered_professional') else 'applicant'))
    reasons = export_reasons if export_reasons is not None else [
        element.export_reason for element in result.elements if element.export_reason]
    by_section: dict[str, list[str]] = {}
    for reason in reasons:
        section = 'process'
        for token in ('A', 'B', 'C', 'D', 'process'):
            if f'section {token},' in reason:
                section = token
                break
        by_section.setdefault(section, []).append(reason)
    return ReviewModel(
        document_id=result.document_id,
        sections=[SectionModel(section=key, title=SECTION_TITLES[key], elements=grouped[key]) for key in 'ABCD'],
        reasons_by_section=by_section, export_reasons=reasons, invented_values=result.invented_values)


def build_response(variant: str, results: list[VariantResult], *, export_reasons: list[str] | None = None,
                   llm: LLMUsageModel | None = None) -> CompletenessResponse:
    reviews = []
    for index, result in enumerate(results):
        reviews.append(_review(result, export_reasons if index == 0 else None))
    reminder = applicant_reminder()
    return CompletenessResponse(
        variant=variant, reviews=reviews, llm=llm,
        reminder=ReminderModel(verdict='reminder', bulletin_ids=list(reminder['bulletin_ids']),
                               text=reminder['text'], links=list(reminder['links'])))


def gaps_to_export_reasons(gaps) -> list[str]:
    return [format_export_reason(gap.section, gap.field, gap.message, gap.fix_hint)
            for gap in gaps if gap.severity == 'blocking']
