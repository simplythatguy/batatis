"""HTTP shape for POST /cases/{id}/completeness. Grouped by SCC template Part 1 A–D."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from .review.bulletin_gates import applicant_reminder
from .completeness_elements import NOTICE, SECTION_TITLES
from .completeness_variants import ElementVerdict, VariantResult, VariantUnavailable, format_export_reason, run_variant
from .copyright import NRC_PUBLICATION_URL
from .models import Source
from .models_completeness import AdministrativeReport


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
    # Keep applicant passages distinct from NRC prose in the HTTP attribution guard.
    source: dict


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
    severity: Literal['blocking', 'warning', 'info'] = 'warning'
    related_fields: list[str] = Field(default_factory=list)
    citations: list[str] = Field(default_factory=list)
    routed_to: Literal['officer', 'professional', 'applicant'] | None = None
    sources: list[Source] = Field(default_factory=list)
    url: str | None = None
    key: str = ''
    value: str | None = None
    certainty: Literal['present', 'blank', 'not_found', 'not_applicable'] = 'not_found'


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
    source: dict = Field(default_factory=lambda: {'type': 'scc_bulletin'})


class CompletenessResponse(BaseModel):
    model_config = ConfigDict(extra='forbid')
    schema_version: Literal['batatis.completeness.v1'] = 'batatis.completeness.v1'
    variant: Literal['A', 'B']
    administrative_only: Literal[True] = True
    not_a_compliance_determination: Literal[True] = True
    notice: str = NOTICE
    reviews: list[ReviewModel]
    reminder: ReminderModel
    llm: LLMUsageModel | None = None
    policy: AdministrativeReport | None = None
    case_id: str
    case_version: int = Field(ge=1)
    case_updated_at: str


def _review(result: VariantResult, export_reasons: list[str] | None = None) -> ReviewModel:
    grouped: dict[str, list[ElementModel]] = {key: [] for key in 'ABCD'}
    for element in result.elements:
        grouped[element.template_section].append(ElementModel(
            key=element.key, value=element.value, certainty=element.certainty,
            field=element.field, template_section=element.template_section, export_section=element.export_section,
            export_field=element.export_field, form_fields=element.form_fields, label=element.label, group=element.group,
            verdict=element.verdict, reason=element.reason, defect_class=element.defect_class, problem=element.problem,
            quotes=[QuoteModel(text=quote.text, kind='exact' if quote.kind == 'exact' else 'pointed',
                               source_ref=quote.source_ref,
                               source=quote.source if quote.source is not None else
                               {'type': 'case_record', 'ref': quote.source_ref}) for quote in element.quotes],
            prompt=None if element.prompt is None else IntakePromptModel(**element.prompt),
            lookup_skipped=element.lookup_skipped, in_export_preflight=element.in_export_preflight,
            source=element.source if element.source in ('applicant', 'registered_professional') else 'applicant',
            severity=element.severity, related_fields=element.related_fields, citations=element.citations,
            routed_to=element.routed_to, sources=element.sources,
            url=NRC_PUBLICATION_URL if any(citation.startswith('NBC(AE)') for citation in element.citations) else None))
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
                   case_id: str, case_version: int, case_updated_at: str,
                   llm: LLMUsageModel | None = None) -> CompletenessResponse:
    if variant not in ('A', 'B'):
        raise VariantUnavailable('provider-assisted completeness is unavailable')
    if any(result.variant != variant for result in results):
        raise ValueError('completeness result variant does not match the report')
    reviews = []
    for index, result in enumerate(results):
        reviews.append(_review(result, export_reasons if index == 0 else None))
    reminder = applicant_reminder()
    return CompletenessResponse(
        variant=variant, reviews=reviews, llm=llm, case_id=case_id, case_version=case_version,
        case_updated_at=case_updated_at,
        reminder=ReminderModel(verdict='reminder', bulletin_ids=list(reminder['bulletin_ids']),
                               text=reminder['text'], links=list(reminder['links'])))


def gaps_to_export_reasons(gaps) -> list[str]:
    return [format_export_reason(gap.section, gap.field, gap.message, gap.fix_hint)
            for gap in gaps if gap.severity == 'blocking']


def saved_case_response(case, codes, variant: str = 'B', *, store=None) -> CompletenessResponse:
    """Read-only applicant projection of the same policy used by export and officer review."""
    from .export.package import prepare_package
    if variant not in ('A', 'B'):
        raise VariantUnavailable('provider-assisted completeness is unavailable')
    policy = prepare_package(case, codes, store=store).policy
    response = build_response(variant, [_applicant_projection(policy, case, codes, variant)],
        export_reasons=policy.report.export_reasons, case_id=case.id,
        case_version=case.version, case_updated_at=case.updated_at)
    response.policy = policy.report
    return response


def _applicant_projection(policy, case, codes, variant):
    """Group existing findings for the screen; every decision remains in policy.items."""
    from copy import deepcopy
    from .review.evidence_gaps import group_evidence_gaps, list_documents
    from .section_d import section_d_plan
    result = deepcopy(policy.variant_result(variant, case.id))
    plan_items = []
    for provision in case.provisions:
        try:
            plan_items.extend(section_d_plan(case.model_copy(update={'provisions': [provision]}), codes).items)
        except (KeyError, ValueError):
            continue
    grouped = group_evidence_gaps(policy.gaps, plan_items)
    grouped_fields = {gap.field for group in grouped for gap in group.gaps}
    result.elements = [element for element in result.elements if element.field not in grouped_fields]
    for group in grouped:
        result.elements.append(ElementVerdict(
            key=f'evidence:{group.provision_id}', field=group.field, template_section='D', export_section='D',
            export_field=group.field, form_fields=[], label=f'Documents for Sentence {group.provision_id}',
            group='Supporting documents', verdict='missing', reason=' '.join(gap.message for gap in group.gaps),
            severity='blocking', in_export_preflight=True, related_fields=[gap.field for gap in group.gaps],
            citations=list(dict.fromkeys(gap.citation for gap in group.gaps if gap.citation)),
            prompt={'question': list_documents(group.provision_id), 'field': group.gaps[0].field,
                    'form_fields': [], 'source': 'applicant'}))
    by_field = {}
    for element in result.elements:
        previous = by_field.get(element.field)
        if previous is None:
            by_field[element.field] = element
            continue
        if element.reason not in previous.reason:
            previous.reason += ' ' + element.reason
        previous.sources.extend(source for source in element.sources if source not in previous.sources)
        previous.related_fields.extend(field for field in element.related_fields if field not in previous.related_fields)
        previous.citations.extend(citation for citation in element.citations if citation not in previous.citations)
        previous.in_export_preflight |= element.in_export_preflight
    result.elements = list(by_field.values())
    return result
