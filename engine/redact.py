"""Remove personal information before text leaves Batatis for an AI provider.

Applicants are not asked to self-censor. Anything sent to a model or to Jev passes through
`scrub`, which replaces the applicant's own personal details (taken from the case facts) and
common personal patterns with neutral placeholders. Code text and citations are never passed
through here, so article numbers are untouched.
"""
from __future__ import annotations

import re
from typing import Any, Iterable

# Facts that hold names, addresses or identifiers of people and sites.
PERSONAL_FIELDS = {
    'owner', 'owner_name', 'representative', 'mailingAddress', 'mailing_address', 'municipalAddress',
    'civic_address', 'legalDescription', 'legal_description', 'permit', 'permit_number',
    'professional.name', 'professional.registration_number', 'professional.seal', 'applicant.name',
    'applicant.email', 'applicant.phone',
}
PERSONAL_SUFFIXES = ('.responsible_party', '.responsible', '.issuer', '.email', '.phone')

EMAIL = re.compile(r'\b[\w.+-]+@[\w-]+(?:\.[\w-]+)+\b')
# A trailing period ends a sentence; a period followed by a digit would continue a number.
PHONE = re.compile(r'(?<![\w.])(?:\+?1[\s.-]?)?(?:\(\d{3}\)\s?|\d{3}[\s.-])\d{3}[\s.-]\d{4}(?!\w|\.\d)'
                   r'|(?<![\w.])\d{10}(?!\w|\.\d)')
POSTAL = re.compile(r'\b[ABCEGHJ-NPRSTVXY]\d[ABCEGHJ-NPRSTV-Z][ -]?\d[ABCEGHJ-NPRSTV-Z]\d\b', re.I)
STREET = re.compile(
    r'\b\d{1,6}[A-Za-z]?\s+(?:[A-Z0-9][\w\'-]*\s+){0,4}'
    r'(?:Street|St|Avenue|Ave|Road|Rd|Drive|Dr|Boulevard|Blvd|Crescent|Cres|Way|Lane|Ln|Court|Ct|Place|Pl'
    r'|Trail|Close|Gate|Terrace|Heights|Point|Manor|Common|Green|Grove|Landing|Highway|Hwy|Circle|Cir)\b\.?'
    r'(?:\s+(?:NW|NE|SW|SE))?')


def known_values(case: Any) -> list[str]:
    """Personal values the applicant entered, longest first so the full value wins over a part."""
    values: set[str] = set()
    for fact in getattr(case, 'facts', None) or []:
        field = str(getattr(fact, 'field', ''))
        if field in PERSONAL_FIELDS or field.endswith(PERSONAL_SUFFIXES):
            value = getattr(fact, 'value', None)
            if isinstance(value, str) and len(value.strip()) >= 3:
                values.add(value.strip())
    return sorted(values, key=len, reverse=True)


def scrub(text: str, known: Iterable[str] = ()) -> str:
    if not text:
        return text
    for value in known:
        text = re.sub(re.escape(value), '[personal detail]', text, flags=re.I)
    text = EMAIL.sub('[email]', text)
    text = PHONE.sub('[phone]', text)
    text = STREET.sub('[address]', text)
    return POSTAL.sub('[postal code]', text)


def scrub_obj(value: Any, known: Iterable[str] = ()) -> Any:
    """Scrub every string inside JSON-like data."""
    known = list(known)
    if isinstance(value, str):
        return scrub(value, known)
    if isinstance(value, list):
        return [scrub_obj(item, known) for item in value]
    if isinstance(value, dict):
        return {key: scrub_obj(item, known) for key, item in value.items()}
    return value
