"""Pre-fill facts an applicant already stated in pasted description text.

The cues are the words they typed. This module does not decide that a letter is a
professional's, and it never writes ``professional_confirmed``.
"""
from __future__ import annotations

import re

from .models import Case, EvidenceItem, Fact, Source

_NO_CCMC = re.compile(r'\bno\s+ccmc\b', re.I)
_UNSIGNED = re.compile(r'\bunsigned\s+letter\b', re.I)
LETTER_DESCRIPTION = 'letter, unsigned'
LETTER_EVIDENCE_ID = 'ev_letter_unsigned'
_CCMC_FIELD = 'ccmc_evaluation'
_LETTER_FIELD = 'evidence.letter'


def _has_field(case: Case, field: str) -> bool:
    return any(fact.field == field for fact in case.facts)


def _pointed(field: str, value, quote: str) -> Fact:
    return Fact(
        field=field, value=value, kind='pointed', status='unconfirmed',
        source=Source(type='user_text', ref='description', quote=quote),
    )


def apply_pasted_text(case: Case, text: str | None) -> None:
    """Record a stated lack of a CCMC evaluation, and an unsigned letter that is not a professional's."""
    if not text:
        return
    ccmc = _NO_CCMC.search(text)
    if ccmc and not _has_field(case, _CCMC_FIELD):
        case.facts.append(_pointed(_CCMC_FIELD, False, ccmc.group(0)))
    letter = _UNSIGNED.search(text)
    if letter and not _has_field(case, _LETTER_FIELD):
        case.facts.append(_pointed(_LETTER_FIELD, LETTER_DESCRIPTION, letter.group(0)))
    if letter and not any(item.id == LETTER_EVIDENCE_ID or item.description == LETTER_DESCRIPTION
                          for item in case.evidence):
        case.evidence.append(EvidenceItem(
            id=LETTER_EVIDENCE_ID,
            description=LETTER_DESCRIPTION,
            evidence_type=None,
            professional_required=None,
            status='needed',
        ))
    # Pasted text never confirms a professional. Leave any existing fact untouched.
