"""Field-level implementation details of the shared administrative policy.

No caller selects or combines independent rule lists. Completeness policy owns
which rules run and all projections consume its result.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

from .review.bulletin_gates import LOC_FIX, _missing, location_parts
from .completeness_elements import BY_FIELD, ELEMENTS, INTENT_LABEL, ElementSpec
from .review.ingest import Ingested, StoredValue, normalize_ws, quote_matches_bytes
from .models import INTENT_LABEL as MODEL_INTENT_LABEL
from .process_fields import _FIELDS, alternative_path

SELECTED_VARIANT = 'B'

_HISTORICAL = re.compile(r'\b(?:historical|history|superseded|not current|earlier edition)\b', re.I)
_OLD_EDITION = re.compile(r'\b(?:NBC\s*\(AE\)\s*2019|ABC\s*2014|NBC\s*2019|Alberta Building Code\s*2014)\b', re.I)
_PROVISION = re.compile(r'\d+(?:\.\d+){3}(?:\.\(\d+\)(?:\([a-z]\))?)?')
_GENERIC = re.compile(
    r'^(?:low risk|minimal risk|no risk|n/?a|not applicable|adequate|standard measures?|see attached|the measures are adequate)\.?$',
    re.I)
_STATUS = {'provided', 'listed', 'filled', 'short paragraph', 'beautifully explained'}
_STOP = {'this', 'that', 'with', 'from', 'have', 'been', 'will', 'your', 'into', 'over', 'than', 'then',
         'applicant', 'described', 'above', 'their', 'they', 'them', 'does', 'here', 'not', 'are', 'was'}
# Topic words are taken from repository descriptions of these ids, not from code sentences.
_TOPICS = {
    '9.10.15.5': frozenset({'limiting', 'distance', 'soffit', 'overhang', 'spatial'}),
    '9.8.2.1': frozenset({'stair', 'stairs', 'width', 'exit'}),
    '9.27.3.4': frozenset({'cladding', 'membrane', 'sheathing', 'housewrap', 'exterior'}),
    '9.10.9.16': frozenset({'fire', 'separation', 'dwelling'}),
}
_MEASURES = (
    ('limiting distance', re.compile(r'limiting distance:\s*([0-9]+(?:\.[0-9]+)?)\s*m', re.I)),
    ('storeys', re.compile(r'(?:^|\s)storeys:\s*([0-9]+)', re.I)),
    ('sprinklered', re.compile(r'sprinklered:\s*(yes|no)', re.I)),
    ('product thickness', re.compile(r'product thickness:\s*([0-9]+(?:\.[0-9]+)?)\s*mm', re.I)),
)


@dataclass
class QuoteSpan:
    text: str
    kind: str
    source_ref: str
    source: dict | None = None


@dataclass
class ElementVerdict:
    field: str
    template_section: str
    export_section: str
    export_field: str
    form_fields: list[str]
    label: str
    group: str
    verdict: str
    reason: str
    defect_class: str | None = None
    problem: str | None = None
    quotes: list[QuoteSpan] = field(default_factory=list)
    prompt: dict | None = None
    lookup_skipped: bool = False
    in_export_preflight: bool = False
    export_reason: str | None = None
    source: str = 'applicant'
    severity: str = 'warning'
    related_fields: list[str] = field(default_factory=list)
    citations: list[str] = field(default_factory=list)
    routed_to: str | None = None
    sources: list[dict] = field(default_factory=list)
    key: str = ''
    value: str | None = None
    certainty: str = 'not_found'
    pointers: list[dict] = field(default_factory=list)
    submission_blocking: bool = True
    fix_hint: str = ''
    finding_status: str | None = None


@dataclass
class VariantResult:
    variant: str
    document_id: str
    elements: list[ElementVerdict]
    skipped: str | None = None
    usage: None = None
    invented_values: int = 0


def format_export_reason(section: str, field_name: str, message: str, fix_hint: str) -> str:
    """Same sentence export uses for a blocking completeness gap."""
    return f'blocking gap in section {section}, {field_name}: {message} Fix: {fix_hint}'


def _presence_copy(label: str, problem: str) -> tuple[str, str]:
    if problem == 'blank':
        missing = f'the {label} (the field is blank).'
    elif problem == 'not_found':
        missing = f'a readable {label}; the field was not found. Please confirm it.'
    elif problem == 'placeholder':
        missing = f'a completed {label}; a placeholder does not supply this information.'
    else:
        missing = f'a confirmed {label}; its current value has not been confirmed.'
    return (f'Your application appears to be missing {missing}',
            f'Ask the applicant to enter or confirm the {label}; retain its source.')


def _process_fix(field_id: str) -> tuple[str, str] | None:
    for fid, label, prompt, structure, _pid in _FIELDS:
        if fid == field_id:
            return (f'Your application appears to be missing the applicant-written {label.lower()}.',
                    prompt + ' ' + ' '.join(structure))
    return None


@lru_cache(maxsize=1)
def _crosswalks() -> tuple[dict, ...]:
    path = Path(__file__).resolve().parents[1] / 'research/precedents/index.json'
    if not path.exists():
        return ()
    rows = json.loads(path.read_text(encoding='utf-8'))
    return tuple(
        article for precedent in rows
        if re.search(r'\b(?:2014|2019)\b', precedent.get('code_edition', ''))
        for article in precedent.get('articles_varied', [])
        if article.get('original_division') == 'B' and article.get('ae2023_provision')
        and 'successor' in article.get('status', ''))


def _tokens(text: str) -> set[str]:
    return {word for word in re.findall(r'[a-z0-9]+', text.casefold()) if len(word) > 3 and word not in _STOP}


def _value(doc: Ingested, key: str) -> str:
    stored = doc.values.get(key)
    return '' if stored is None else stored.value


def _quote_for(doc: Ingested, stored: StoredValue | None, fallback: str = '') -> list[QuoteSpan]:
    if stored and stored.quote and quote_matches_bytes(stored.quote, doc.data, doc.text, ledger=doc.ledger):
        return [QuoteSpan(stored.quote, 'exact' if stored.kind == 'exact' else 'pointed', stored.source_ref or doc.ref,
                          stored.source)]
    if stored and stored.kind == 'exact':
        return [QuoteSpan(stored.value, 'exact', stored.source_ref or stored.form_field or doc.ref, stored.source)]
    if fallback and quote_matches_bytes(fallback, doc.data, doc.text, ledger=doc.ledger):
        return [QuoteSpan(fallback, 'pointed', doc.ref)]
    return []


def _prompt(spec: ElementSpec) -> dict:
    target = f'process.{spec.field}' if spec.export_section == 'process' else spec.field
    return {'question': spec.question, 'field': target, 'form_fields': list(spec.form_fields), 'source': spec.source}


def _finish(spec: ElementSpec, doc: Ingested, verdict: str, reason: str, *, problem: str | None = None,
            defect_class: str | None = None, quotes: list[QuoteSpan] | None = None,
            lookup_skipped: bool = False, preflight: bool = False) -> ElementVerdict:
    export_reason = None
    if preflight and verdict == 'missing' and doc.kind == 'form':
        copied = _process_fix(spec.export_field) if spec.export_section == 'process' else None
        if copied:
            message, fix_hint = copied
        else:
            message, fix_hint = _presence_copy(spec.label, problem or 'not_found')
        export_reason = format_export_reason(spec.export_section, spec.export_field, message, fix_hint)
    return ElementVerdict(
        field=spec.field, template_section=spec.template_section, export_section=spec.export_section,
        export_field=spec.export_field, form_fields=list(spec.form_fields), label=spec.label, group=spec.group,
        verdict=verdict, reason=reason, defect_class=defect_class, problem=problem, quotes=quotes or [],
        prompt=_prompt(spec) if verdict in ('missing', 'unclear') else None,
        lookup_skipped=lookup_skipped, in_export_preflight=bool(export_reason), export_reason=export_reason,
        source=spec.source)


def _stored_state(doc: Ingested, spec: ElementSpec) -> tuple[str, str | None, StoredValue | None]:
    stored = doc.values.get(spec.field)
    if stored is None:
        if doc.kind == 'form':
            return 'missing', 'not_found', None
        return 'present', None, None
    if stored.status == 'not_found':
        return 'unclear', 'not_found', stored
    if not stored.confirmed:
        return 'unclear', 'unconfirmed', stored
    if stored.explicit_blank or not stored.value.strip():
        return 'missing', 'blank', stored
    from .completeness import _missing
    # Only a whole answer is a placeholder. Real prose can discuss an unknown.
    placeholder = _missing(stored.value) or _PLACEHOLDER.fullmatch(
        normalize_ws(stored.value).strip(" .!?;:'\""))
    if spec.field == 'legal_description' and not placeholder:
        # A legal description is a list of parts ("Lot 12, Block 3, Plan TBD"); each part is a whole answer.
        parts = [re.sub(r'^(?:lot|block|plan|qtr|sec|twp|rge|mer|ats_[a-z]+)\s+', '', part.strip(), flags=re.I)
                 for part in stored.value.split(',')]
        placeholder = any(_missing(part) or _PLACEHOLDER.fullmatch(part.strip(" .!?;:'\"")) for part in parts)
    if placeholder:
        return 'missing', 'placeholder', stored
    folded = normalize_ws(stored.value).casefold().strip(" '")
    if folded in _STATUS or (spec.field == 'representative' and folded in {'none', 'no representative'}):
        return 'status', None, stored
    return 'filled', None, stored


_PLACEHOLDER = re.compile(
    r"\b(?:tbd|to be determined|to be provided|unknown|placeholder|don't have it yet|do not have it yet)\b",
    re.I)


def _provision_ids(doc: Ingested) -> list[str]:
    if doc.case is not None:
        return list(dict.fromkeys(doc.case.provisions))
    blob = _value(doc, 'section_c.article')
    unverified = {mention.token.rstrip('.') for mention in doc.mentions}
    found = []
    for token in _PROVISION.findall(blob):
        root = token.rstrip('.')
        if root in unverified or any(root.startswith(item) for item in unverified):
            continue
        found.append(token)
    return found


def _edition_problem(doc: Ingested) -> tuple[str, str, list[QuoteSpan]] | None:
    blob = ' '.join((
        _value(doc, 'section_c.article'), _value(doc, 'code_or_standard'), _value(doc, 'heading'),
        doc.section_text.get('C', '')))
    quote = _quote_for(doc, doc.values.get('section_c.article'), _value(doc, 'section_c.article'))
    if _OLD_EDITION.search(blob) and not _HISTORICAL.search(blob):
        return ('unclear', 'The citation uses a superseded edition as if it were current. Ask which NBC(AE) 2023 '
                'provision applies, or ask the applicant to label this as historical context.', quote)
    article = _value(doc, 'section_c.article')
    heading = _value(doc, 'heading')
    if _HISTORICAL.search(blob) or '2023' not in (_value(doc, 'code_or_standard') + blob):
        return None
    root = _PROVISION.search(article)
    if not root:
        return None
    article_root = root.group(0).split('.(')[0].rstrip('.')
    for mapping in _crosswalks():
        original = mapping['original_citation'].rstrip('.')
        title = mapping.get('ae2023_title') or ''
        if article_root != original or not title or title.casefold() not in heading.casefold():
            continue
        successor = mapping.get('ae2023_provision') or 'the precedent index successor'
        return ('unclear',
                f'This number is paired with the heading "{title}", which the precedent index maps to {successor} '
                'when an earlier edition is cited as current. Equivalence is not verified. Ask the applicant to '
                'confirm the NBC(AE) 2023 provision or to label the old number as historical.',
                quote + _quote_for(doc, doc.values.get('heading'), heading))
    return None


def _contradictions(doc: Ingested) -> list[tuple[str, str, str]]:
    body = doc.section_text.get('B', '')
    attachment = doc.section_text.get('attachment', '')
    found = []
    for label, pattern in _MEASURES:
        left = pattern.search(body)
        if left:
            for right in pattern.finditer(attachment):
                if left.group(1).casefold() != right.group(1).casefold():
                    found.append((label, left.group(0), right.group(0)))
    return found


def _relevant(doc: Ingested, spec: ElementSpec) -> ElementVerdict:
    ids = sorted(_provision_ids(doc))
    if not ids:
        return _finish(spec, doc, 'unclear', 'No benchmark is selected for the limited keyword screen. '
                       'Ask the code reviewer to confirm relevance.', lookup_skipped=True)
    stored = doc.values.get('alternative_description')
    description = _value(doc, 'alternative_description') or doc.section_text.get('B', '')
    if not description.strip() or (stored and (not stored.confirmed or _missing(stored.value))):
        return _finish(spec, doc, 'unclear', 'Keyword screening was skipped for ' + ', '.join(ids)
                       + ': the current description is missing or unconfirmed. Ask the code reviewer to '
                       'review the confirmed description and every selected benchmark.', lookup_skipped=True,
                       quotes=_quote_for(doc, stored))
    matches, mismatches, unsupported = [], [], []
    for pid in ids:
        root = re.match(r'(\d+(?:\.\d+){3})', pid)
        topics = _TOPICS.get(root.group(1) if root else '')
        if not topics:
            unsupported.append(pid)
        elif _tokens(description) & topics:
            matches.append(pid)
        else:
            mismatches.append(pid)
    coverage = []
    if matches:
        coverage.append('Topic words overlap for ' + ', '.join(matches) + '.')
    if mismatches:
        coverage.append('No topic-word overlap was found for ' + ', '.join(mismatches)
                        + '; ask the code reviewer to review these benchmarks against the described departure.')
    if unsupported:
        coverage.append('Keyword screening was skipped for ' + ', '.join(unsupported)
                        + ' because no topic rule is available; relevance remains uncertain.')
    coverage.append('This limited keyword screen does not determine legal relevance or applicability; '
                    'the code reviewer must review every selected reference.')
    return _finish(spec, doc, 'unclear' if mismatches or unsupported else 'present', ' '.join(coverage),
                   problem='topic_mismatch' if mismatches else None,
                   defect_class='D15' if mismatches else None, lookup_skipped=bool(unsupported),
                   quotes=_quote_for(doc, stored, description) + _quote_for(doc, doc.values.get('section_c.article')))


def _one(doc: Ingested, spec: ElementSpec, codes, engineering: bool, heuristics: bool) -> ElementVerdict:
    if spec.field == 'section_b.consistency':
        if doc.ledger:
            return _finish(spec, doc, 'unclear',
                           'Attachment contents have not been read. Saved metadata cannot establish consistency '
                           'with Section B; ask the reviewer to compare the actual documents.', lookup_skipped=True)
        if not heuristics:
            return _finish(spec, doc, 'present', 'This variant does not compare Section B with attachments.')
        found = _contradictions(doc)
        if not found:
            return _finish(spec, doc, 'present', 'No conflict was detected for the supported labelled values. '
                           'Other document comparisons require human review.')
        label, left, right = found[0]
        return _finish(spec, doc, 'unclear',
                       f'Section B and an attachment disagree on {label}. Ask which value is correct. '
                       'The review does not pick one.',
                       problem='contradiction', defect_class='D14',
                       quotes=[QuoteSpan(text, 'pointed', doc.ref)
                               for text in dict.fromkeys(text for _label, left, right in found for text in (left, right))])
    if spec.field == 'section_c.edition':
        state, problem, stored = _stored_state(doc, BY_FIELD['code_or_standard'])
        if state in ('missing', 'unclear'):
            element = _finish(spec, doc, 'missing' if state == 'missing' and stored else 'unclear',
                              'The current code and edition are missing or unconfirmed. Confirm the latest '
                              'code label before checking its edition; do not reuse an older answer.',
                              problem=problem, quotes=_quote_for(doc, stored), lookup_skipped=True)
            element.prompt['field'] = stored.input_field if stored and stored.input_field else 'code_or_standard'
            return element
        problem = _edition_problem(doc)
        if not problem:
            return _finish(spec, doc, 'present', 'No superseded edition is presented as current.')
        _verdict, reason, quotes = problem
        return _finish(spec, doc, 'unclear', reason, problem='superseded_edition', defect_class='D06', quotes=quotes)
    if spec.field == 'section_c.relevance':
        if not heuristics:
            return _finish(spec, doc, 'present', 'This variant does not screen whether the cited provision addresses the departure.')
        return _relevant(doc, spec)
    if spec.field in ('responsible_professional', 'professional_qualifications'):
        return _professional(doc, spec, engineering)
    if spec.field == 'supporting_doc':
        return _supporting(doc, spec, heuristics)
    if spec.field in ('rationale', 'risk_assessment', 'mitigating_measures', 'assumptions_and_limits',
                      'maintenance_operation', 'qualifications'):
        return _process(doc, spec, heuristics)
    if spec.field == 'single_location':
        return _single_location(doc, spec)

    state, problem, stored = _stored_state(doc, spec)
    if spec.field == 'section_c.intent' and state in ('filled', 'status'):
        return _intent(doc, spec, state, stored)
    if state == 'present' and stored is None and doc.kind != 'form':
        return _finish(spec, doc, 'present', 'This summary does not mark the field blank.')
    if state == 'status':
        return _finish(spec, doc, 'present', 'The summary states that this element was supplied.',
                       quotes=_quote_for(doc, stored))
    if state == 'filled':
        return _finish(spec, doc, 'present', f'The {spec.label} is in the document.', quotes=_quote_for(doc, stored))
    if state == 'unclear':
        return _finish(spec, doc, 'unclear', f'The {spec.label} is not a confirmed fact. Ask the applicant to confirm it.',
                       problem=problem or 'unconfirmed', defect_class=_presence_class(spec.field),
                       quotes=_quote_for(doc, stored))
    reason_problem = problem or 'not_found'
    message, _fix = _presence_copy(spec.label, reason_problem)
    return _finish(spec, doc, 'missing', message, problem=reason_problem,
                   defect_class=_presence_class(spec.field), quotes=_quote_for(doc, stored), preflight=True)


def _on_variance(doc: Ingested) -> bool:
    if doc.case is not None:
        return alternative_path(doc.case)
    stored = doc.values.get('pathway') or doc.values.get('path')
    if stored is None or not stored.confirmed or not stored.value.strip():
        return True
    return stored.value.strip().casefold() not in {'acceptable', 'acceptable_solution'}


def _gate(spec: ElementSpec, doc: Ingested, verdict: str, reason: str, *, problem: str | None = None,
          defect_class: str | None = None, quotes: list[QuoteSpan] | None = None, fix_hint: str = '') -> ElementVerdict:
    export_reason = None
    if verdict == 'missing' and doc.kind == 'form':
        export_reason = format_export_reason(spec.export_section, spec.export_field, reason, fix_hint)
    return ElementVerdict(
        field=spec.field, template_section=spec.template_section, export_section=spec.export_section,
        export_field=spec.export_field, form_fields=list(spec.form_fields), label=spec.label, group=spec.group,
        verdict=verdict, reason=reason, defect_class=defect_class, problem=problem, quotes=quotes or [],
        prompt=_prompt(spec) if verdict in ('missing', 'unclear') else None,
        in_export_preflight=bool(export_reason), export_reason=export_reason, source=spec.source)


def _single_location(doc: Ingested, spec: ElementSpec) -> ElementVerdict:
    # IB-2026-10-01: one registration for one specific location. A comma is part of one civic address.
    if not _on_variance(doc):
        return _gate(spec, doc, 'present',
                     'IB-2026-10-01 applies to variance registration. This record is on the acceptable-solution path.')
    scope = doc.values.get('scope')
    if scope and scope.status == 'not_found':
        element = _gate(spec, doc, 'unclear',
            'The site or jurisdiction-wide scope could not be read. Check the indicated source before treating this as one location.',
            problem='not_found', quotes=_quote_for(doc, scope), fix_hint=LOC_FIX)
        element.prompt['field'] = 'scope'
        return element
    if scope and scope.confirmed and scope.value.casefold() in ('jurisdiction', 'jurisdiction-wide', 'jurisdiction wide', 'all locations'):
        element = _gate(spec, doc, 'missing',
            'This variance is stated to cover a jurisdiction instead of one specific location (IB-2026-10-01).',
            problem='multiple_locations', defect_class='IB-LOC', quotes=_quote_for(doc, scope), fix_hint=LOC_FIX)
        element.prompt['field'] = 'scope'
        return element
    civic_stored = doc.values.get('civic_address')
    # Ingest already selected the latest civic alias. Older physical aliases are
    # revisions, not extra sites. Only explicit additional-location fields add sites.
    extra_values = [doc.values[key] for key in ('additional_location', 'second_location', 'extra_location')
                    if key in doc.values]
    inputs = ([civic_stored] if civic_stored else []) + extra_values
    quotes = [quote for stored in inputs for quote in _quote_for(doc, stored)]
    pending = [stored for stored in inputs if not stored.confirmed]
    target = pending[0] if pending else civic_stored
    if pending:
        element = _gate(spec, doc, 'unclear', 'The latest location answer is not confirmed. Ask the applicant '
                        'to confirm it; do not reuse an older address or choose a location.',
                        problem='unconfirmed', quotes=quotes)
    elif civic_stored is None or _missing(civic_stored.value):
        element = _gate(spec, doc, 'missing' if civic_stored else 'unclear',
                        'No confirmed project location is supplied. Ask the applicant to enter or confirm '
                        'the current civic address; do not reuse an older address or choose a location.',
                        problem='blank' if civic_stored else 'not_found', quotes=quotes)
    else:
        locations = location_parts(civic_stored.value, [stored.value for stored in extra_values
                                                        if not _missing(stored.value)])
        if len(locations) == 1:
            return _gate(spec, doc, 'present', 'One location is listed for this variance (IB-2026-10-01).',
                         quotes=quotes)
        element = _gate(
            spec, doc, 'missing',
            'Your application appears to be missing a single location for this variance; more than one location is listed (IB-2026-10-01).',
            problem='multiple_locations', defect_class='IB-LOC', quotes=quotes, fix_hint=LOC_FIX)
    element.prompt['field'] = target.input_field if target and target.input_field else 'municipal_address'
    return element


def _presence_class(field_name: str) -> str | None:
    return {
        'owner_name': 'D01', 'application_date': 'D02', 'signature': 'D02',
        'owner_rep_signature_date': 'D02', 'civic_address': 'D03', 'legal_description': 'D04',
        'section_c.article': 'D16',
    }.get(field_name)


def _intent(doc: Ingested, spec: ElementSpec, state: str, stored: StoredValue | None) -> ElementVerdict:
    if state == 'status':
        return _finish(spec, doc, 'present', 'The summary states that the intent was filled.', quotes=_quote_for(doc, stored))
    value = stored.value if stored else ''
    if 'explanatory only' in value.casefold() or MODEL_INTENT_LABEL.casefold() in value.casefold():
        return _finish(spec, doc, 'present', 'The intent statement keeps the national explanatory label.',
                       quotes=_quote_for(doc, stored))
    if re.fullmatch(r'(?:[^.;]*\.\s*)*No NBC 2020 intent statement(?:[;.][^;]*)?', value.strip(), re.I):
        # The cell says no national intent statement is presented, so there is nothing to label.
        return _finish(spec, doc, 'present', 'No national intent statement is presented in this row.',
                       quotes=_quote_for(doc, stored))
    if doc.kind != 'form':
        return _finish(spec, doc, 'present', 'The summary does not present an unlabelled intent statement.',
                       quotes=_quote_for(doc, stored))
    return _finish(spec, doc, 'unclear',
                   'The intent statement is presented without the national explanatory label. It is not Alberta law. '
                   f'Ask the applicant to use the label: {INTENT_LABEL}.',
                   problem='intent_label', defect_class='D08', quotes=_quote_for(doc, stored))


def _process(doc: Ingested, spec: ElementSpec, heuristics: bool) -> ElementVerdict:
    if not _on_variance(doc):
        return _finish(spec, doc, 'present', 'Alternative-path process fields do not apply to the saved acceptable-solution path.')
    state, problem, stored = _stored_state(doc, spec)
    if state == 'present' and stored is None:
        return _finish(spec, doc, 'present', 'This summary does not mark the field blank.')
    if state == 'missing':
        copied = _process_fix(spec.field)
        message = copied[0] if copied else _presence_copy(spec.label, problem or 'blank')[0]
        defect = {'risk_assessment': 'D09', 'mitigating_measures': 'D10', 'assumptions_and_limits': 'D11'}.get(spec.field)
        return _finish(spec, doc, 'missing', message, problem=problem, defect_class=defect,
                       quotes=_quote_for(doc, stored), preflight=True)
    if state == 'unclear':
        reason = ('The complete applicant passage could not be established. Check the indicated sources.'
                  if problem == 'not_found' else 'The latest process answer is not a confirmed applicant passage. '
                  'Ask the applicant to confirm it; do not reuse an earlier answer.')
        return _finish(spec, doc, 'unclear', reason,
                       problem=problem or 'unconfirmed', quotes=_quote_for(doc, stored))
    if state == 'status':
        return _finish(spec, doc, 'present', 'The summary states that this process field was supplied. It does not quote the text.',
                       quotes=_quote_for(doc, stored))
    value = stored.value if stored else ''
    if heuristics and spec.field == 'assumptions_and_limits' and re.search(r'stated as fact', value, re.I):
        return _finish(spec, doc, 'unclear',
                       'The assumptions text is stated as a fact. Ask the applicant to label it as an assumption '
                       'and to address the limit they named. The review does not rewrite it.',
                       problem='stated_as_fact', defect_class='D11', quotes=_quote_for(doc, stored))
    if (heuristics and spec.field == 'assumptions_and_limits' and value.strip()
            and not re.search(r'\b(?:assum\w*|limit\w*|unverified|unknown|only|subject to|uncertain\w*)\b', value, re.I)):
        return _finish(spec, doc, 'unclear',
                       'This passage does not distinguish assumptions or limits from established facts. '
                       'Ask the applicant to label what is assumed and what remains unverified.',
                       problem='stated_as_fact', defect_class='D11', quotes=_quote_for(doc, stored))
    if heuristics and spec.field == 'risk_assessment' and (_GENERIC.match(normalize_ws(value)) or len(value.split()) < 5):
        return _finish(spec, doc, 'unclear',
                       'The risk assessment is generic or too thin to describe this departure. Ask the applicant '
                       'to write the risks. The review does not draft them.',
                       problem='generic', defect_class='D09', quotes=_quote_for(doc, stored))
    if heuristics and spec.field == 'mitigating_measures':
        if _GENERIC.match(normalize_ws(value)) or len(value.split()) <= 2:
            return _finish(spec, doc, 'unclear',
                           'The mitigating measures are generic or too thin to address the departure. Ask the applicant '
                           'what measures address the cited objective. The review does not draft them.',
                           problem='thin', defect_class='D10', quotes=_quote_for(doc, stored))
        context = _value(doc, 'alternative_description') + ' ' + _value(doc, 'risk_assessment')
        if context.strip() and not (_tokens(value) & _tokens(context)):
            return _finish(spec, doc, 'unclear',
                           'The mitigating measures do not use the terms of the described departure. Ask the applicant '
                           'how the measures address that departure. The review does not draft them.',
                           problem='unrelated', defect_class='D10', quotes=_quote_for(doc, stored))
    return _finish(spec, doc, 'present', f'The {spec.label} is in the document.', quotes=_quote_for(doc, stored))


def _supporting(doc: Ingested, spec: ElementSpec, heuristics: bool) -> ElementVerdict:
    state, problem, stored = _stored_state(doc, spec)
    if state == 'present' and stored is None:
        return _finish(spec, doc, 'present', 'This summary does not mark a supporting document blank.')
    if state == 'missing':
        message, _fix = _presence_copy(spec.label, problem or 'blank')
        return _finish(spec, doc, 'missing', message, problem=problem or 'blank', defect_class='D13',
                       quotes=_quote_for(doc, stored), preflight=True)
    value = stored.value if stored else ''
    if state == 'unclear':
        return _finish(spec, doc, 'unclear', 'The latest document listing is not confirmed. '
                       'Listing a document does not establish attached bytes, authentication or review.',
                       problem='unconfirmed', quotes=_quote_for(doc, stored))
    if re.search(r'\b(to follow|tbd|not received)\b', value, re.I):
        return _finish(spec, doc, 'unclear',
                       'The supporting document is a placeholder, not evidence in the file. Ask the applicant who will '
                       'provide it and when. The review does not treat a promise as a document.',
                       problem='no_evidence', defect_class='D13', quotes=_quote_for(doc, stored))
    if heuristics and re.search(r'brochure only', value, re.I):
        return _finish(spec, doc, 'unclear',
                       'The only supporting document named is a manufacturer brochure. Ask who is responsible for it '
                       'and what else will be provided. The review does not judge the product.',
                       problem='brochure_only', defect_class='D13', quotes=_quote_for(doc, stored))
    return _finish(spec, doc, 'present', 'A supporting document is named (not reviewed). '
                   'This does not establish attached bytes, professional authentication or technical performance.',
                   quotes=_quote_for(doc, stored))


def _professional(doc: Ingested, spec: ElementSpec, engineering: bool) -> ElementVerdict:
    if not engineering:
        return _finish(spec, doc, 'present',
                       'The application does not state that a registered professional is required. This is not a decision that one is unnecessary.')
    key = 'professional_name' if spec.field == 'responsible_professional' else 'professional_qualifications'
    stored = doc.values.get(key)
    if stored is None or stored.explicit_blank or not stored.value.strip():
        problem = 'professional_unnamed' if spec.field == 'responsible_professional' else 'qualifications_missing'
        return _finish(spec, doc, 'missing',
                       'Your application appears to be missing a named registered professional required for this work.'
                       if problem == 'professional_unnamed' else
                       'Your application appears to be missing the qualifications of the responsible professional.',
                       problem=problem, defect_class='D12', quotes=_quote_for(doc, stored), preflight=True)
    return _finish(spec, doc, 'present', f'The {spec.label} is named by the applicant.', quotes=_quote_for(doc, stored))


