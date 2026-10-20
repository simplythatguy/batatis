"""Three completeness variants behind one interface.

A — presence, placeholder, edition label, intent label, blank process fields.
B — A plus deterministic screens for generic or unrelated process text,
    Section B / attachment contradictions, article-topic mismatch, brochure-only
    evidence, and assumptions stated as facts.
C — A plus a provider-backed judgement step. Findings that do not quote the
    document are dropped. With no API key, C is skipped and is not scored.

The selected default is B: it is the best variant that runs without a key.
A live run can replace it if C's success rate is higher.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

from .bulletin_gates import DOC_FIX, LOC_FIX, _missing, location_parts
from .completeness_elements import BY_FIELD, ELEMENTS, INTENT_LABEL, ElementSpec
from .ingest import Ingested, StoredValue, normalize_ws, quote_matches_bytes
from .llm_judgement import JUDGEMENT_FIELDS, LLMUsage, judge_document
from .models import INTENT_LABEL as MODEL_INTENT_LABEL
from .process_fields import _FIELDS

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


@dataclass
class VariantResult:
    variant: str
    document_id: str
    elements: list[ElementVerdict]
    skipped: str | None = None
    usage: LLMUsage | None = None
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
    rows = json.loads(path.read_text())
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
        return [QuoteSpan(stored.quote, stored.kind if stored.kind == 'pointed' else 'pointed', doc.ref)]
    if stored and stored.kind == 'exact':
        return [QuoteSpan(stored.value, 'exact', stored.form_field or doc.ref)]
    if fallback and quote_matches_bytes(fallback, doc.data, doc.text, ledger=doc.ledger):
        return [QuoteSpan(fallback, 'pointed', doc.ref)]
    return []


def _prompt(spec: ElementSpec) -> dict:
    return {'question': spec.question, 'field': spec.field, 'form_fields': list(spec.form_fields), 'source': spec.source}


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
    if not stored.confirmed:
        return 'unclear', 'unconfirmed', stored
    if stored.explicit_blank or not stored.value.strip():
        return 'missing', 'blank', stored
    if _PLACEHOLDER.search(stored.value):
        return 'missing', 'placeholder', stored
    folded = normalize_ws(stored.value).casefold().strip(" '")
    if folded in _STATUS or (spec.field == 'representative' and folded in {'none', 'no representative'}):
        return 'status', None, stored
    return 'filled', None, stored


_PLACEHOLDER = re.compile(
    r"\b(?:tbd|to be determined|to be provided|unknown|placeholder|don't have it yet|do not have it yet)\b",
    re.I)


def _provision_ids(doc: Ingested) -> list[str]:
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
        left, right = pattern.search(body), pattern.search(attachment)
        if left and right and left.group(1).casefold() != right.group(1).casefold():
            found.append((label, left.group(0), right.group(0)))
    return found


def _relevant(doc: Ingested) -> tuple[str, str, list[QuoteSpan]] | None:
    ids = _provision_ids(doc)
    if not ids:
        return None
    root_match = re.match(r'(\d+(?:\.\d+){3})', ids[0])
    topics = _TOPICS.get(root_match.group(1) if root_match else '')
    if not topics:
        return None
    description = _value(doc, 'alternative_description') or doc.section_text.get('B', '')
    if _tokens(description) & topics:
        return None
    return ('unclear',
            'The cited provision does not address the departure described in Section B. Ask the applicant which '
            'benchmark they are varying. This is not a finding that another article applies.',
            _quote_for(doc, doc.values.get('alternative_description'), description)
            + _quote_for(doc, doc.values.get('section_c.article')))


def apply_rules(doc: Ingested, codes) -> list[ElementVerdict]:
    elements = []
    engineering = (_value(doc, 'engineering_required').strip().casefold() in {'yes', 'true'})
    for spec in ELEMENTS:
        elements.append(_one(doc, spec, codes, engineering, heuristics=False))
    return elements


def _one(doc: Ingested, spec: ElementSpec, codes, engineering: bool, heuristics: bool) -> ElementVerdict:
    if spec.field == 'section_b.consistency':
        if not heuristics:
            return _finish(spec, doc, 'present', 'This variant does not compare Section B with attachments.')
        found = _contradictions(doc)
        if not found:
            return _finish(spec, doc, 'present', 'Section B and the attachments do not show a conflicting value.')
        label, left, right = found[0]
        return _finish(spec, doc, 'unclear',
                       f'Section B and an attachment disagree on {label}. Ask which value is correct. '
                       'The review does not pick one.',
                       problem='contradiction', defect_class='D14',
                       quotes=[QuoteSpan(left, 'pointed', doc.ref), QuoteSpan(right, 'pointed', doc.ref)])
    if spec.field == 'section_c.edition':
        problem = _edition_problem(doc)
        if not problem:
            return _finish(spec, doc, 'present', 'No superseded edition is presented as current.')
        _verdict, reason, quotes = problem
        return _finish(spec, doc, 'unclear', reason, problem='superseded_edition', defect_class='D06', quotes=quotes)
    if spec.field == 'section_c.relevance':
        if not heuristics:
            return _finish(spec, doc, 'present', 'This variant does not screen whether the cited provision addresses the departure.')
        problem = _relevant(doc)
        if not problem:
            return _finish(spec, doc, 'present', 'No topic mismatch was found for a confirmed provision id.')
        _verdict, reason, quotes = problem
        return _finish(spec, doc, 'unclear', reason, problem='irrelevant', defect_class='D15', quotes=quotes)
    if spec.field == 'section_c.provision_found':
        return _provision(doc, spec, codes)
    if spec.field == 'section_c.pair_match':
        return _pairs(doc, spec, codes)
    if spec.field in ('responsible_professional', 'professional_qualifications'):
        return _professional(doc, spec, engineering)
    if spec.field == 'supporting_doc':
        return _supporting(doc, spec, heuristics)
    if spec.field in ('risk_assessment', 'mitigating_measures', 'assumptions_and_limits'):
        return _process(doc, spec, heuristics)
    if spec.field == 'division_c_2_3_1':
        return _division_c_documentation(doc, spec)
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
                       problem='unconfirmed', quotes=_quote_for(doc, stored))
    reason_problem = problem or 'not_found'
    message, _fix = _presence_copy(spec.label, reason_problem)
    return _finish(spec, doc, 'missing', message, problem=reason_problem,
                   defect_class=_presence_class(spec.field), quotes=_quote_for(doc, stored), preflight=True)


def _on_variance(doc: Ingested) -> bool:
    stored = doc.values.get('pathway') or doc.values.get('path')
    if stored is None or not stored.value.strip():
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


def _division_c_documentation(doc: Ingested, spec: ElementSpec) -> ElementVerdict:
    # IB-2025-11-18. The 10-day copy is a reminder, not this gate.
    if not _on_variance(doc):
        return _gate(spec, doc, 'present',
                     'IB-2025-11-18 applies to a variance. This record is on the acceptable-solution path.')
    state, problem, stored = _stored_state(doc, spec)
    if state in ('filled', 'status') or (state == 'present' and stored is None):
        return _gate(spec, doc, 'present',
                     'The Division C Section 2.3.1 documentation is included (IB-2025-11-18).',
                     quotes=_quote_for(doc, stored))
    if state == 'unclear':
        return _gate(spec, doc, 'unclear',
                     'The Division C Section 2.3.1 documentation is not a confirmed fact. Ask the applicant to confirm it (IB-2025-11-18).',
                     problem='unconfirmed', quotes=_quote_for(doc, stored))
    reason = ('Your application appears to be missing the Division C Section 2.3.1 documentation '
              'for this alternative solution (IB-2025-11-18).')
    return _gate(spec, doc, 'missing', reason, problem=problem or 'not_found', defect_class='IB-DOC',
                 quotes=_quote_for(doc, stored), fix_hint=DOC_FIX)


def _single_location(doc: Ingested, spec: ElementSpec) -> ElementVerdict:
    # IB-2026-10-01: one registration for one specific location. A comma is part of one civic address.
    if not _on_variance(doc):
        return _gate(spec, doc, 'present',
                     'IB-2026-10-01 applies to variance registration. This record is on the acceptable-solution path.')
    civic = _value(doc, 'civic_address')
    extras = []
    quotes: list[QuoteSpan] = []
    civic_stored = doc.values.get('civic_address')
    quotes.extend(_quote_for(doc, civic_stored))
    municipal = doc.values.get('municipal_address')
    if (civic_stored and municipal and not _missing(civic_stored.value) and not _missing(municipal.value)
            and civic_stored.value.strip() != municipal.value.strip()):
        civic = civic_stored.value
        extras.append(municipal.value)
        quotes.extend(_quote_for(doc, municipal))
    for key in ('additional_location', 'second_location', 'extra_location'):
        stored = doc.values.get(key)
        if stored is None:
            continue
        quotes.extend(_quote_for(doc, stored))
        if not _missing(stored.value):
            extras.append(stored.value)
    if len(location_parts(civic, extras)) <= 1:
        return _gate(spec, doc, 'present', 'One location is listed for this application (IB-2026-10-01).',
                     quotes=quotes if extras or civic else [])
    return _gate(
        spec, doc, 'missing',
        'Your application appears to be missing one registration for a single location; more than one location is listed (IB-2026-10-01).',
        problem='multiple_locations', defect_class='IB-LOC', quotes=quotes, fix_hint=LOC_FIX)


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
    if doc.kind != 'form':
        return _finish(spec, doc, 'present', 'The summary does not present an unlabelled intent statement.',
                       quotes=_quote_for(doc, stored))
    return _finish(spec, doc, 'unclear',
                   'The intent statement is presented without the national explanatory label. It is not Alberta law. '
                   f'Ask the applicant to use the label: {INTENT_LABEL}.',
                   problem='intent_label', defect_class='D08', quotes=_quote_for(doc, stored))


def _process(doc: Ingested, spec: ElementSpec, heuristics: bool) -> ElementVerdict:
    state, problem, stored = _stored_state(doc, spec)
    if state == 'present' and stored is None:
        return _finish(spec, doc, 'present', 'This summary does not mark the field blank.')
    if state == 'missing':
        copied = _process_fix(spec.field)
        message = copied[0] if copied else _presence_copy(spec.label, problem or 'blank')[0]
        defect = {'risk_assessment': 'D09', 'mitigating_measures': 'D10', 'assumptions_and_limits': 'D11'}[spec.field]
        return _finish(spec, doc, 'missing', message, problem=problem, defect_class=defect,
                       quotes=_quote_for(doc, stored), preflight=True)
    if state == 'status':
        return _finish(spec, doc, 'present', 'The summary states that this process field was supplied. It does not quote the text.',
                       quotes=_quote_for(doc, stored))
    value = stored.value if stored else ''
    if heuristics and spec.field == 'assumptions_and_limits' and re.search(r'stated as fact', value, re.I):
        return _finish(spec, doc, 'unclear',
                       'The assumptions text is stated as a fact. Ask the applicant to label it as an assumption '
                       'and to address the limit they named. The review does not rewrite it.',
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
    if re.search(r'\b(to follow|tbd|not received)\b', value, re.I):
        return _finish(spec, doc, 'unclear',
                       'The supporting document is a placeholder, not evidence in the file. Ask the applicant who will '
                       'provide it and when. The review does not treat a promise as a document.',
                       problem='no_evidence', defect_class='D13', quotes=_quote_for(doc, stored))
    responsible = doc.values.get('responsible_party')
    if responsible is not None and (responsible.explicit_blank or not responsible.value.strip()):
        return _finish(spec, doc, 'missing',
                       'Your application appears to be missing a responsible person for the supporting document.',
                       problem='no_responsible', defect_class='D13', quotes=_quote_for(doc, responsible), preflight=True)
    dated = doc.values.get('document_date')
    if dated is not None and (dated.explicit_blank or not dated.value.strip()):
        return _finish(spec, doc, 'unclear',
                       'The supporting document has no date. Ask the applicant for the issue or revision date.',
                       problem='no_date', defect_class='D13', quotes=_quote_for(doc, dated))
    if heuristics and re.search(r'brochure only', value, re.I):
        return _finish(spec, doc, 'unclear',
                       'The only supporting document named is a manufacturer brochure. Ask who is responsible for it '
                       'and what else will be provided. The review does not judge the product.',
                       problem='brochure_only', defect_class='D13', quotes=_quote_for(doc, stored))
    return _finish(spec, doc, 'present', 'A supporting document is named.', quotes=_quote_for(doc, stored))


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


def _provision(doc: Ingested, spec: ElementSpec, codes) -> ElementVerdict:
    ids = _provision_ids(doc)
    if codes is None or not ids:
        return _finish(spec, doc, 'present', 'Provision existence was not looked up.' if codes is None else
                       'No confirmed provision id is claimed.', lookup_skipped=codes is None)
    try:
        record = codes.provision(ids[0], 'B')
    except Exception:
        return _finish(spec, doc, 'present', 'Provision existence was not looked up.', lookup_skipped=True)
    if record is None:
        return _finish(spec, doc, 'missing',
                       f'Your application appears to be missing a verified benchmark: provision {ids[0]} was not found '
                       'in NBC(AE) 2023, 2nd printing.',
                       problem='not_found_in_code', defect_class='D05',
                       quotes=_quote_for(doc, doc.values.get('section_c.article')))
    return _finish(spec, doc, 'present', 'The provision id was found in the code database.')


def _pairs(doc: Ingested, spec: ElementSpec, codes) -> ElementVerdict:
    ids = _provision_ids(doc)
    objective, function = _value(doc, 'objective'), _value(doc, 'function')
    if codes is None or not ids or not objective or not function:
        return _finish(spec, doc, 'present', 'Objective and function were not compared with the attribution table.',
                       lookup_skipped=True)
    try:
        from .section_c import section_c_rows
        rows = section_c_rows([ids[0]], codes)
    except Exception:
        return _finish(spec, doc, 'present', 'Objective and function were not compared because the provision was not available.',
                       lookup_skipped=True)
    pairs = {(pair.function, pair.objective) for row in rows for pair in row.pairs}
    if pairs and (function, objective) not in pairs:
        shown = ', '.join(f'{func}-{obj}' for func, obj in sorted(pairs)[:8]) or 'no row'
        return _finish(spec, doc, 'unclear',
                       'The supplied objective/function pair is not in the Division B attribution table for this '
                       f'provision. The table rows include: {shown}. Ask the applicant to confirm the lookup. '
                       'Do not substitute a remembered pair.',
                       problem='wrong_pair', defect_class='D07',
                       quotes=_quote_for(doc, doc.values.get('objective')) + _quote_for(doc, doc.values.get('function')))
    return _finish(spec, doc, 'present', 'The supplied objective and function match a table row for this provision.')


def apply_heuristics(doc: Ingested, codes) -> list[ElementVerdict]:
    engineering = (_value(doc, 'engineering_required').strip().casefold() in {'yes', 'true'})
    return [_one(doc, spec, codes, engineering, heuristics=True) for spec in ELEMENTS]


def apply_llm(doc: Ingested, elements: list[ElementVerdict], findings: list[dict]) -> list[ElementVerdict]:
    by_field = {item.field: item for item in findings}
    updated = []
    for element in elements:
        finding = by_field.get(element.field)
        if finding is None or element.verdict == 'missing':
            updated.append(element)
            continue
        spec = BY_FIELD[element.field]
        quotes = [QuoteSpan(quote, 'pointed', doc.ref) for quote in finding.get('quotes') or []]
        updated.append(_finish(
            spec, doc, finding.get('verdict') or 'unclear',
            str(finding.get('reason') or 'The judgement step quoted a span that needs an applicant answer.'),
            problem=finding.get('problem'), defect_class=finding.get('defect_class'), quotes=quotes))
    return updated


def _invented(doc: Ingested, elements: list[ElementVerdict]) -> int:
    bad = 0
    for element in elements:
        for quote in element.quotes:
            if quote.kind == 'exact':
                if doc.form_fields and quote.text not in doc.form_fields.values():
                    bad += 1
                continue
            if not quote_matches_bytes(quote.text, doc.data, doc.text, ledger=doc.ledger):
                bad += 1
    return bad


def run_variant(variant: str, doc: Ingested, codes=None, llm=None) -> VariantResult:
    if variant not in ('A', 'B', 'C'):
        raise ValueError(f'unknown variant {variant}')
    if variant == 'C' and llm is None:
        elements = apply_rules(doc, codes)
        return VariantResult(variant, doc.submission_id or doc.ref, elements, skipped='no API key',
                             invented_values=_invented(doc, elements))
    if variant == 'B':
        elements = apply_heuristics(doc, codes)
        usage = None
    elif variant == 'C':
        elements = apply_rules(doc, codes)
        findings, usage = judge_document(doc, llm)
        elements = apply_llm(doc, elements, findings)
    else:
        elements = apply_rules(doc, codes)
        usage = None
    return VariantResult(variant, doc.submission_id or doc.ref, elements, usage=usage,
                         invented_values=_invented(doc, elements))
