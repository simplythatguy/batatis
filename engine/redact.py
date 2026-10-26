"""Remove personal information before text leaves Batatis for an AI provider.

Applicants are not asked to self-censor. Anything sent to a model or to Jev passes through
`scrub`, which replaces the applicant's own personal details (taken from the case facts) and
common personal patterns with neutral placeholders. Code text and citations are never passed
through here, so article numbers are untouched.
"""
from __future__ import annotations

import re
import secrets
from collections.abc import Callable, Iterable
from typing import Any

# Facts that hold names, addresses or identifiers of people and sites.
PERSONAL_FIELDS = {
    'owner', 'owner_name', 'owner_rep_name', 'representative', 'mailingAddress', 'mailing_address', 'municipalAddress',
    'municipal_address',
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


# Names introduced by contact phrasing ("call Priya Natarajan", "Dr. Ada Lin", "prepared by A. Engineer").
# Deliberately contextual: bare capitalized pairs are product and code terms far more often than people.
_NAME = r"(?:[A-Z]\.\s?|[A-Z][a-z'\-]+)(?:\s+(?:[A-Z]\.|[A-Z][a-z'\-]+)){0,2}"
_HONORIFIC = r"(?:Mr|Mrs|Ms|Miss|Mx|Dr|Prof)\.?\s+"
_LEAD = (r"(?i:my name is|i am|i'm|this is|contact|call|email|e-mail|text|ask|signed by|prepared by|"
         r"stamped by|sealed by|reviewed by|regards,|thanks,|thank you,)\s+")
NAMED = re.compile(r"\b(?:" + _LEAD + r"(?:" + _HONORIFIC + r")?|" + _HONORIFIC + r")" + _NAME)
_KEEP = re.compile(r"(?:" + _LEAD + r")?(?:" + _HONORIFIC + r")?")


def _name_span(match: re.Match) -> str:
    # Keep the lead-in words and any honorific; replace only the name itself.
    return _KEEP.match(match.group(0)).group(0) + '[name]'


def people_names(store: Any, case: Any, user: Any = None) -> list[str]:
    """Account names and emails connected to this case: the caller, the owner, reviewers, message authors."""
    names: set[str] = set()
    for person in (user, store.get_user(case.owner_id) if case is not None and getattr(case, 'owner_id', None)
                   and hasattr(store, 'get_user') else None):
        if person is not None:
            names.update(v for v in (getattr(person, 'name', None), getattr(person, 'email', None)) if v)
    if case is not None:
        for message in getattr(case, 'messages', None) or []:
            names.add(message.author.name)
        for change in getattr(case, 'status_history', None) or []:
            names.add(change.by_name)
        claim = getattr(case, 'claim', None)
        if claim is not None:
            names.add(claim.reviewer_name)
    return [name for name in names if isinstance(name, str) and len(name.strip()) >= 3]


def known_values(case: Any, extra: Iterable[str] = ()) -> list[str]:
    """Personal values the applicant entered, longest first so the full value wins over a part."""
    values: set[str] = {value.strip() for value in extra if isinstance(value, str) and value.strip()}
    for fact in getattr(case, 'facts', None) or []:
        field = str(getattr(fact, 'field', ''))
        if field in PERSONAL_FIELDS or field.endswith(PERSONAL_SUFFIXES):
            value = getattr(fact, 'value', None)
            if isinstance(value, str) and value.strip():
                values.add(value.strip())
    return sorted(values, key=len, reverse=True)


def scrub(text: str, known: Iterable[str] = (), *, replacement: Callable[[str], str] | None = None) -> str:
    if not text:
        return text
    for value in known:
        if not value:
            continue
        # Whole words and numeric tokens: "202" must not replace part of "2025" or "202.5".
        before = r'(?<!\w)(?<!\d[.,])' if value[0].isdigit() else r'(?<!\w)'
        after = r'(?!\w|[.,]\d)' if value[-1].isdigit() else r'(?!\w)'
        text = re.sub(before + re.escape(value) + after,
                      (lambda match: replacement(match.group())) if replacement else '[personal detail]',
                      text, flags=re.I)
    text = EMAIL.sub((lambda match: replacement(match.group())) if replacement else '[email]', text)

    def name_span(match):
        if replacement is None:
            return _name_span(match)
        lead = _KEEP.match(match.group()).group()
        return lead + replacement(match.group()[len(lead):])

    text = NAMED.sub(name_span, text)
    text = PHONE.sub((lambda match: replacement(match.group())) if replacement else '[phone]', text)
    text = STREET.sub((lambda match: replacement(match.group())) if replacement else '[address]', text)
    return POSTAL.sub((lambda match: replacement(match.group())) if replacement else '[postal code]', text)


_PERSONAL_TOKEN = re.compile(r'\[~[0-9a-f]{32}~\]')


def protect_personal_details(text: str, known: Iterable[str] = ()) -> tuple[str, dict[str, str]]:
    """Use the shared recognizers, retaining only local originals for a rewrite round trip."""
    originals = {}

    def opaque(value):
        token = '[~' + secrets.token_hex(16) + '~]'
        while token in text or token in originals:
            token = '[~' + secrets.token_hex(16) + '~]'
        originals[token] = value
        return token

    return scrub(text, known, replacement=opaque), originals


def restore_personal_details(text: str, originals: dict[str, str]) -> str:
    """Never guess which person a placeholder represents or lose/duplicate their facts."""
    if any(text.count(token) != 1 for token in originals) or any(
            token not in originals for token in _PERSONAL_TOKEN.findall(text)):
        raise ValueError('The rewrite changed a protected personal detail. Try selecting a shorter passage.')
    return _PERSONAL_TOKEN.sub(lambda match: originals[match.group()], text)


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
