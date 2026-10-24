"""HTTP shape for POST /cases/{id}/completeness. Grouped by SCC template Part 1 A–D."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from .review.bulletin_gates import applicant_reminder
from .completeness_elements import NOTICE, SECTION_TITLES
from .completeness_variants import ElementVerdict, VariantResult, VariantUnavailable, format_export_reason, run_variant
from .copyright import NRC_PUBLICATION_URL
from .models import Source


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
    severity: Literal['blocking', 'warning'] = 'warning'
    related_fields: list[str] = Field(default_factory=list)
    citations: list[str] = Field(default_factory=list)
    routed_to: Literal['officer', 'professional', 'applicant'] | None = None
    sources: list[Source] = Field(default_factory=list)
    url: str | None = None


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
    case_id: str
    case_version: int = Field(ge=1)
    case_updated_at: str


def _review(result: VariantResult, export_reasons: list[str] | None = None) -> ReviewModel:
    grouped: dict[str, list[ElementModel]] = {key: [] for key in 'ABCD'}
    for element in result.elements:
        grouped[element.template_section].append(ElementModel(
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


def saved_case_response(case, codes, variant: str = 'B') -> CompletenessResponse:
    """Original B screens plus authoritative current administrative/export policy.

    This function has no store or provider and cannot save, submit or export. The
    caller must supply a normalized snapshot and revalidate it before publishing.
    """
    from .completeness import Gap, check_completeness
    from .review.evidence_gaps import group_evidence_gaps, list_documents
    from .export.scc import _FIELD_KEYS, _latest, blockers, confirmed_values, load_field_map
    from .review.ingest import ingested_from_case
    from .process_fields import _FIELDS, latest_fact
    from .professional import _STATUS_FIELDS
    from .section_d import section_d_plan

    document = ingested_from_case(case)
    result = run_variant(variant, document, codes)
    gaps = check_completeness(case, codes)
    fmap = load_field_map()
    reasons = blockers(case, fmap, codes)
    # Old document-presence rules never define the current official gate.
    for element in result.elements:
        element.in_export_preflight = False
        element.export_reason = None
    # Current policy, including not_engaged/source-failure precedence, owns these
    # tasks. The old engineering_required-only screen is not authoritative.
    result.elements = [element for element in result.elements
                       if element.field not in ('responsible_professional', 'professional_qualifications')]
    by_field = {element.field: element for element in result.elements}
    by_field['provisions'] = by_field['section_c.article']
    process_specs = {key: (label, question) for key, label, question, _structure, _pid in _FIELDS}
    # Map authoritative export keys to existing presentation elements. Physical
    # aliases remain input targets, never independent versions of a logical field.
    by_field['request_date'] = by_field['application_date']
    by_field['municipal_address'] = by_field['civic_address']
    by_field['owner_rep_name'] = by_field['representative']
    for key in process_specs:
        if key in by_field:
            by_field[f'process.{key}'] = by_field[key]

    def add_gap(gap):
        element = by_field.get(gap.field)
        source = 'registered_professional' if gap.field == 'professional_qualifications' else 'applicant'
        target = f'process.{gap.field}' if gap.section == 'process' else gap.field
        if element is None:
            label, question = process_specs.get(gap.field, (gap.field.replace('_', ' '), gap.fix_hint))
            element = ElementVerdict(
                field=gap.field, template_section='B' if gap.section == 'process' else gap.section,
                export_section=gap.section, export_field=gap.field, form_fields=[], label=label,
                group='Current administrative policy', verdict='missing', reason=gap.message,
                source=source)
            result.elements.append(element)
            by_field[gap.field] = element
        else:
            question = gap.fix_hint
            # Keep the useful distinction between an absent and unconfirmed value.
            element.verdict = 'unclear' if element.problem == 'unconfirmed' else 'missing'
            if element.related_fields:
                if gap.message not in element.reason:
                    element.reason += ' ' + gap.message
            else:
                element.reason = gap.message
        element.severity = 'blocking' if element.in_export_preflight else gap.severity
        element.routed_to = gap.routed_to
        element.in_export_preflight = element.in_export_preflight or gap.severity == 'blocking'
        element.related_fields = list(dict.fromkeys([*element.related_fields, gap.field]))
        if gap.citation and gap.citation not in element.citations:
            element.citations.append(gap.citation)
        if element.prompt and len(element.related_fields) > 1 and question not in element.prompt['question']:
            question = element.prompt['question'] + ' ' + question
        element.prompt = {'question': question, 'field': target, 'form_fields': element.form_fields, 'source': source}
        if gap.field == 'professional_requirement' and gap.severity == 'warning':
            element.verdict = 'unclear'

    # Reuse canonical valid-provision planning. A malformed reference must remain
    # a located gap instead of aborting the complete report or inventing coverage.
    plan_items = []
    for provision_id in dict.fromkeys(case.provisions):
        try:
            plan_items.extend(section_d_plan(case.model_copy(update={'provisions': [provision_id]}), codes).items)
        except (KeyError, ValueError):
            continue
    grouped = group_evidence_gaps(gaps, plan_items)
    grouped_fields = {gap.field for group in grouped for gap in group.gaps}
    for gap in gaps:
        if gap.field not in grouped_fields:
            add_gap(gap)
    for group in grouped:
        citations = list(dict.fromkeys(gap.citation for gap in group.gaps if gap.citation))
        result.elements.append(ElementVerdict(
            field=group.field, template_section='D', export_section='D', export_field=group.field,
            form_fields=[], label=f'Documents for Sentence {group.provision_id}', group='Supporting documents',
            verdict='missing', reason=f'Your application appears to be missing documents for Sentence {group.provision_id}. '
            + group.wording, source='applicant', severity='blocking', in_export_preflight=True,
            related_fields=[gap.field for gap in group.gaps], citations=citations,
            prompt={'question': list_documents(group.provision_id), 'field': group.gaps[0].field,
                    'form_fields': [], 'source': 'applicant'}))

    # The saved ledger may supply a legal description as components, not a single
    # text fact. Canonical policy accepts either complete component set.
    if not any(gap.field == 'legal_description' for gap in gaps) and by_field['legal_description'].verdict == 'missing':
        element = by_field['legal_description']
        element.verdict, element.reason, element.prompt = 'present', 'The confirmed legal-description components are supplied.', None
    paired = by_field['section_c.pair_match']
    if case.section_c and not any(gap.section == 'C' for gap in gaps):
        paired.verdict, paired.reason, paired.lookup_skipped, paired.prompt = (
            'present', 'Every saved row matches the canonical attribution and intent payload, including its scope.', False, None)

    # Include every extra exporter guard, not just deterministic completeness.
    for gap in case.gaps:
        add_gap(Gap(**gap.model_dump(), fix_hint='Resolve this saved administrative finding with its reviewer.'))
    latest = _latest(case)
    for field_name, entry in latest.items():
        if entry.export()['status'] != 'confirmed':
            element = by_field.get(field_name)
            if element is None:
                add_gap(Gap(id=f'export:unconfirmed:{entry.id}', section='B', field=entry.field,
                            message='The latest saved fact is unconfirmed; confirm or withdraw it before official export.',
                            fix_hint='Review the latest value and its source; do not restore an older answer.'))
            else:
                element.in_export_preflight, element.severity = True, 'blocking'
                if element.verdict == 'present':
                    # A field may be optional on this pathway, but its current
                    # pending answer still needs the exporter's confirmation task.
                    element.verdict, element.problem = 'unclear', 'unconfirmed'
                    element.reason = 'The latest saved fact is unconfirmed; confirm or withdraw it before official export.'
                    element.prompt = {
                        'question': 'Confirm the latest value and its source, or withdraw it; do not restore an older answer.',
                        'field': entry.field, 'form_fields': element.form_fields, 'source': element.source}
                if element.prompt:
                    element.prompt['field'] = entry.field
    values = confirmed_values(case)
    for field_name in fmap['required_facts']:
        if field_name not in values:
            logical = {'request_date': 'application_date', 'municipal_address': 'civic_address'}.get(field_name, field_name)
            element = by_field[logical]
            element.in_export_preflight, element.severity = True, 'blocking'
            element.related_fields = list(dict.fromkeys([*element.related_fields, field_name]))
            if element.prompt:
                current = latest.get(field_name)
                element.prompt['field'] = current.field if current is not None else field_name
            elif element.verdict == 'present':
                element.verdict, element.reason = 'missing', f'The official form requires the saved field {field_name}.'
                element.prompt = {'question': f'Enter or confirm the {element.label} for the official form.',
                                  'field': field_name, 'form_fields': element.form_fields, 'source': 'applicant'}
    for element in result.elements:
        source_facts = []
        stored = document.values.get(element.field)
        if stored and stored.source:
            element.sources.append(stored.source)
        for quote in element.quotes:
            if quote.source is not None and quote.source not in element.sources:
                element.sources.append(quote.source)
        if element.prompt:
            target = element.prompt['field']
            source_facts.append(latest.get(_FIELD_KEYS.get(target, target)))
        source_facts.extend(latest.get(_FIELD_KEYS.get(field, field)) for field in element.related_fields)
        if element.field == 'professional_requirement':
            source_facts.append(latest_fact(case, *_STATUS_FIELDS))
        for entry in source_facts:
            if entry is not None and entry.source.model_dump() not in element.sources:
                element.sources.append(entry.source.model_dump())
    return build_response(variant, [result], export_reasons=reasons, case_id=case.id,
                          case_version=case.version, case_updated_at=case.updated_at)
