"""Provider-free saved-case input for the original deterministic completeness rules.

This slice reads the current fact ledger, never file bytes. Document/PDF ingestion
from PR 11 is deliberately unavailable. A quote is copied from a stored source;
an unconfirmed/proposed revision masks the earlier answer instead of reviving it.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field, replace

from ..models import Case, Fact
from ..process_fields import PROCESS_ALIASES, latest_fact


class IngestError(ValueError):
    pass


def normalize_ws(text: str) -> str:
    return re.sub(r'\s+', ' ', text).strip()


def quote_in_text(quote: str, text: str) -> bool:
    return bool(normalize_ws(quote)) and normalize_ws(quote) in normalize_ws(text)


def quote_matches_bytes(quote: str, data: bytes, extracted: str, *, ledger: bool = False) -> bool:
    """Ledger quotes must actually occur in the copied ledger, not merely set a flag."""
    if ledger:
        return quote_in_text(quote, extracted)
    try:
        return quote_in_text(quote, data.decode('utf-8'))
    except UnicodeError:
        return False  # Binary document ingestion is unavailable in this saved-case slice.


@dataclass
class StoredValue:
    field: str
    value: str
    kind: str
    quote: str | None
    form_field: str | None = None
    explicit_blank: bool = False
    confirmed: bool = True
    source_ref: str = ''
    source: dict | None = None
    input_field: str | None = None


@dataclass
class Mention:
    quote: str
    token: str
    why: str


@dataclass
class Ingested:
    ref: str
    data: bytes
    text: str
    kind: str
    values: dict[str, StoredValue] = field(default_factory=dict)
    section_text: dict[str, str] = field(default_factory=dict)
    mentions: list[Mention] = field(default_factory=list)
    form_fields: dict[str, str] = field(default_factory=dict)
    submission_id: str | None = None
    ledger: bool = False
    case: Case | None = None


_ALIASES = {
    'owner_name': ('owner_name', 'owner', 'section_a.owner_name'),
    'application_date': ('application_date', 'request_date', 'date', 'section_a.date'),
    'representative': ('representative', 'owner_rep_name', 'applicant_name'),
    'mailing_address': ('mailing_address', 'mailingAddress'),
    'civic_address': ('civic_address', 'municipal_address', 'municipalAddress', 'address'),
    'legal_description': ('legal_description', 'legalDescription', 'section_b.legal_description'),
    'alternative_description': ('alternative_description', 'alternative'),
    'professional_name': ('professional_name', 'responsible_professional', 'professional.name'),
    'division_c_2_3_1': ('division_c_2_3_1', 'division_c_documentation', 'div_c_2_3_1'),
}
_ALIASES.update({key: tuple(f'process.{alias}' for alias in aliases) + aliases
                 for key, aliases in PROCESS_ALIASES.items()})


def _stored(fact: Fact, logical: str) -> StoredValue:
    value = '' if fact.value is None else str(fact.value)
    quote = fact.source.quote or ''
    confirmed = fact.status == 'confirmed' and fact.kind != 'proposed'
    if not quote and fact.source.type == 'user_text':
        quote = value                    # typed by the applicant, saved before typed answers carried a quote
    if fact.kind == 'pointed' and value.strip() and not quote_in_text(value, quote):
        confirmed = False
    return StoredValue(logical, value, 'exact' if fact.kind == 'exact' else 'pointed',
                       value if fact.kind == 'exact' else quote or None,
                       explicit_blank=not value.strip(), confirmed=confirmed, source_ref=fact.source.ref,
                       source=fact.source.model_dump(), input_field=fact.field)


def ingested_from_case(case: Case) -> Ingested:
    """Copy the snapshot's latest facts; no store, lookup, ingestion or generation side effects."""
    doc = Ingested(case.id, b'', '', 'form', submission_id=case.id, ledger=True, case=case)
    for fact in case.facts:
        doc.values[fact.field] = _stored(fact, fact.field)
    for logical, aliases in _ALIASES.items():
        fact = latest_fact(case, *aliases)
        if fact is not None:
            doc.values[logical] = _stored(fact, logical)

    def from_record(key: str, value: str, location: str):
        if key not in doc.values and value:
            doc.values[key] = StoredValue(key, value, 'exact', value, source_ref=f'{case.id}#{location}')

    # The current selection, including an explicit clear, wins over old typed
    # article facts. Do not revive a withdrawn benchmark from narrative text.
    article = '; '.join(case.provisions)
    doc.values['section_c.article'] = StoredValue('section_c.article', article, 'exact', article,
        explicit_blank=not article, source_ref=f'{case.id}#provisions')
    from_record('section_c.intent', '; '.join(dict.fromkeys(
        intent.label for row in case.section_c for intent in row.intents)), 'section_c.intents')
    from_record('code_or_standard', '; '.join(dict.fromkeys(row.citation for row in case.section_c)), 'section_c.citation')
    from_record('supporting_doc', '; '.join(entry.description for entry in case.evidence
                                          if entry.status == 'evidence_listed'), 'evidence')
    if 'supporting_doc' not in doc.values:
        titles = [stored for key, stored in doc.values.items()
                  if key.startswith('evidence.') and key.endswith(('.title', '.description')) and stored.confirmed]
        if titles:
            doc.values['supporting_doc'] = replace(titles[0], field='supporting_doc')
    doc.text = '\n'.join(dict.fromkeys(stored.quote for stored in doc.values.values() if stored.quote))
    doc.section_text = {
        'A': '', 'B': doc.values.get('alternative_description', StoredValue('', '', '', None)).value,
        'C': '; '.join(row.citation for row in case.section_c),
        'D': doc.values.get('supporting_doc', StoredValue('', '', '', None)).value,
        'process': '', 'attachment': '',
    }
    return doc


def ingest_bytes(data: bytes, ref: str = 'upload') -> list[Ingested]:
    raise IngestError('document ingestion is unavailable; review the acknowledged saved case')


def ingest_path(path) -> list[Ingested]:
    # Fail before reading a path, including when a CLI caller bypasses HTTP validation.
    raise IngestError('document ingestion is unavailable; review the acknowledged saved case')
