"""Pre-fill facts an applicant already stated in pasted description text.

The cues are the words they typed. This module does not decide that a letter is a
professional's, and it never writes ``professional_confirmed``.
"""
from __future__ import annotations

import re

from .identify.storeys import parse_storeys
from .identify.title import _CITY, _CITY_CANON
from .models import Case, EvidenceItem, Fact, Source

_NO_CCMC = re.compile(r'\bno\s+ccmc\b', re.I)
_NO_AIR = re.compile(r'\bno\s+air[-\s]?leakage test\b', re.I)
_NO_BRACE = re.compile(r'\bno\s+bracing design\b', re.I)
_DRAFT_LETTER = re.compile(r'\bunsigned draft engineer letter\b', re.I)
_UNSIGNED = re.compile(r'\bunsigned\s+letter\b', re.I)
_DATA_SHEET = re.compile(r'\bproduct data sheet\b', re.I)
_PERMEANCE = re.compile(r'\bUS lab permeance(?: test)? summary\b', re.I)
_MANUFACTURER = re.compile(r'\bmanufactur(?:e|er|ers|ing)\b', re.I)
_ACROSS = re.compile(r'\b(?:province[-\s]?wide|across alberta)\b', re.I)
_ONE_SITE = re.compile(r'\b(?:one site|pilot house)\b', re.I)
_SINGLE = re.compile(r'\bsingle[- ]family\b', re.I)
_UNSPRINKLERED = re.compile(r'\bunsprinklered\b', re.I)
_SPRINKLERED = re.compile(r'\bsprinklered\b', re.I)
_AREA = re.compile(r'\b(about\s+)?(\d+(?:\.\d+)?)\s*m(?:2|²)\b', re.I)

LETTER_DESCRIPTION = 'letter, unsigned'
LETTER_EVIDENCE_ID = 'ev_letter_unsigned'
DRAFT_LETTER_DESCRIPTION = 'unsigned draft engineer letter'
DRAFT_LETTER_EVIDENCE_ID = 'ev_unsigned_draft_engineer_letter'
DATA_SHEET_DESCRIPTION = 'product data sheet'
DATA_SHEET_EVIDENCE_ID = 'ev_product_data_sheet'
PERMEANCE_DESCRIPTION = 'US lab permeance summary'
PERMEANCE_EVIDENCE_ID = 'ev_us_lab_permeance_summary'
SCOPE_BOTH = 'province-wide; one site'

_CCMC_FIELD = 'ccmc_evaluation'
_LETTER_FIELD = 'evidence.letter'


def _has_field(case: Case, field: str) -> bool:
    return any(fact.field == field for fact in case.facts)


def _pointed(field: str, value, quote: str, *, status: str = 'unconfirmed') -> Fact:
    return Fact(
        field=field, value=value, kind='pointed', status=status,
        source=Source(type='user_text', ref='description', quote=quote),
    )


def _add_fact(case: Case, field: str, value, quote: str, *, status: str = 'unconfirmed') -> None:
    if _has_field(case, field):
        return
    case.facts.append(_pointed(field, value, quote, status=status))


def _add_evidence(case: Case, evidence_id: str, description: str, *, status: str) -> None:
    if any(item.id == evidence_id or item.description == description for item in case.evidence):
        return
    case.evidence.append(EvidenceItem(
        id=evidence_id,
        description=description,
        evidence_type=None,
        professional_required=None,
        status=status,
    ))


def _scope_value(text: str) -> tuple[str, str] | None:
    across = _ACROSS.search(text)
    one = _ONE_SITE.search(text)
    if across and one:
        return SCOPE_BOTH, f'{across.group(0)}; {one.group(0)}'
    if across:
        return 'province-wide', across.group(0)
    if one:
        return 'one site', one.group(0)
    return None


def apply_pasted_text(case: Case, text: str | None) -> None:
    """Record facts the description already states. Never a confirmed professional."""
    if not text:
        return
    maker = _MANUFACTURER.search(text)
    if maker:
        _add_fact(case, 'role', 'manufacturer', maker.group(0))
    storeys = parse_storeys(text)
    if storeys is not None:
        count, quote = storeys
        _add_fact(case, 'building.storeys', count, quote, status='confirmed')
    area = _AREA.search(text)
    if area:
        number = area.group(2)
        shown = f'about {number} m²' if area.group(1) else f'{number} m²'
        _add_fact(case, 'building.area', shown, area.group(0))
    family = _SINGLE.search(text)
    if family:
        _add_fact(case, 'occupancy', 'single_family', family.group(0))
    dry = _UNSPRINKLERED.search(text)
    wet = None if dry else _SPRINKLERED.search(text)
    if dry:
        _add_fact(case, 'building.sprinklered', False, dry.group(0))
    elif wet:
        _add_fact(case, 'building.sprinklered', True, wet.group(0))
    city = _CITY.search(text)
    if city:
        _add_fact(case, 'site.city', _CITY_CANON[city.group(1).casefold()], city.group(0))
    scope = _scope_value(text)
    if scope is not None:
        value, quote = scope
        _add_fact(case, 'scope', value, quote)
    ccmc = _NO_CCMC.search(text)
    if ccmc:
        _add_fact(case, _CCMC_FIELD, False, ccmc.group(0))
    air = _NO_AIR.search(text)
    if air:
        _add_fact(case, 'air_leakage_test', False, air.group(0))
    brace = _NO_BRACE.search(text)
    if brace:
        _add_fact(case, 'bracing_design', False, brace.group(0))
    sheet = _DATA_SHEET.search(text)
    if sheet:
        _add_fact(case, 'evidence.product_data_sheet', DATA_SHEET_DESCRIPTION, sheet.group(0))
        _add_evidence(case, DATA_SHEET_EVIDENCE_ID, DATA_SHEET_DESCRIPTION, status='provided')
    permeance = _PERMEANCE.search(text)
    if permeance:
        _add_fact(case, 'evidence.permeance', PERMEANCE_DESCRIPTION, permeance.group(0))
        _add_evidence(case, PERMEANCE_EVIDENCE_ID, PERMEANCE_DESCRIPTION, status='provided')
    draft = _DRAFT_LETTER.search(text)
    if draft:
        _add_fact(case, _LETTER_FIELD, DRAFT_LETTER_DESCRIPTION, draft.group(0))
        _add_evidence(case, DRAFT_LETTER_EVIDENCE_ID, DRAFT_LETTER_DESCRIPTION, status='provided')
    else:
        letter = _UNSIGNED.search(text)
        if letter:
            _add_fact(case, _LETTER_FIELD, LETTER_DESCRIPTION, letter.group(0))
            _add_evidence(case, LETTER_EVIDENCE_ID, LETTER_DESCRIPTION, status='needed')
    # Pasted text never confirms a professional. Leave any existing fact untouched.
