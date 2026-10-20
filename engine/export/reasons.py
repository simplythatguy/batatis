"""Structured export blockers.

The HTTP body puts these objects on ``detail.reasons``, next to ``detail.message``.
``gap_id`` is stable for the same case content: completeness ids, or an id derived from
the section and field. Sections on the object are the form sections A–D. A process-section
gap keeps its completeness id and is reported under D.
"""
from __future__ import annotations

from typing import Literal

from ..completeness import check_completeness
from ..models import Case

FormSection = Literal['A', 'B', 'C', 'D']

_FIELD_SECTION = {
    'owner_name': 'A', 'owner': 'A', 'representative': 'A', 'owner_rep_name': 'A',
    'applicant_name': 'A', 'mailing_address': 'A', 'mailingAddress': 'A',
    'request_date': 'A', 'application_date': 'A', 'date': 'A',
    'municipal_address': 'B', 'municipalAddress': 'B', 'civic_address': 'B', 'address': 'B',
    'legal_description': 'B', 'legalDescription': 'B', 'alternative_description': 'B',
    'alternative': 'B', 'scope': 'B', 'jurisdiction': 'B', 'authority': 'B',
}


def form_section(section: str, field: str = '') -> FormSection:
    if section in ('A', 'B', 'C', 'D'):
        return section
    inferred = _FIELD_SECTION.get(field)
    if inferred in ('A', 'B', 'C', 'D'):
        return inferred
    if field.startswith('section_c') or field.startswith('provisions'):
        return 'C'
    return 'D'


def _label(message: str, field: str) -> str:
    prefix = 'Your application appears to be missing '
    if message.startswith(prefix):
        return message[len(prefix):]
    return message or field


def _item(section: str, gap_id: str, fact_key: str | None, label: str, fix_hint: str,
          severity: str = 'blocking') -> dict:
    return {
        'section': form_section(section, fact_key or ''),
        'gap_id': gap_id,
        'fact_key': fact_key,
        'label': label,
        'fix_hint': fix_hint,
        'severity': severity,
    }


def blocker_rows(case: Case, fmap: dict, codes, latest: dict, values: dict) -> tuple[list[str], list[dict]]:
    """Parallel string reasons and structured reasons, deduped in string order."""
    paired: list[tuple[str, dict]] = []
    for fact in latest.values():
        if fact.export()['status'] == 'confirmed':
            continue
        text = f'unconfirmed {fact.kind} fact "{fact.field}" ({fact.id})'
        paired.append((text, _item(
            _FIELD_SECTION.get(fact.field, 'B'), f'unconfirmed:{fact.field}', fact.field,
            text, 'Confirm this fact, or remove it, before a final export.')))
    for gap in check_completeness(case, codes):
        if gap.severity != 'blocking':
            continue
        text = f'blocking gap in section {gap.section}, {gap.field}: {gap.message} Fix: {gap.fix_hint}'
        paired.append((text, _item(
            gap.section, gap.id, gap.field, _label(gap.message, gap.field), gap.fix_hint, gap.severity)))
    seen_stored: dict[tuple[str, str], int] = {}
    for gap in case.gaps:
        if gap.severity != 'blocking':
            continue
        key = (gap.section, gap.field)
        n = seen_stored.get(key, 0)
        seen_stored[key] = n + 1
        gap_id = f'stored:{gap.section}:{gap.field}' if n == 0 else f'stored:{gap.section}:{gap.field}:{n}'
        text = f'blocking gap in section {gap.section}, {gap.field}: {gap.message}'
        paired.append((text, _item(
            gap.section, gap_id, gap.field, _label(gap.message, gap.field),
            'Resolve this item before a final export.', gap.severity)))
    for key in fmap['required_facts']:
        if key in values:
            continue
        text = f'required field "{key}" is empty'
        paired.append((text, _item(
            _FIELD_SECTION.get(key, 'B'), f'required:{key}', key, text,
            'Enter or confirm this required field before a final export.')))
    if not case.section_c:
        text = 'Section C has no provisions'
        paired.append((text, _item(
            'C', 'section_c:empty', None, text,
            'Confirm the Division B benchmark and its Section C rows before a final export.')))
    strings: list[str] = []
    items: list[dict] = []
    seen: set[str] = set()
    for text, item in paired:
        if text in seen:
            continue
        seen.add(text)
        strings.append(text)
        items.append(item)
    return strings, items
