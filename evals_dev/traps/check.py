"""Mis-citation traps for code identification and for a citation check.

The code database validator answers whether an identifier exists. These traps
answer whether that identifier is the wrong provision for this question.
Identify returns article ids; the same match is used for either list.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

_CASES = Path(__file__).with_name('mis_citations.json')
_ARTICLE = re.compile(
    r'(?<![\w.])(?:Table\s+)?\d{1,2}(?:\.\d{1,3}){1,6}\.?(?:\(\d{1,2}\)(?:\([a-z]{1,2}\))?)?',
    re.I)


def load_traps() -> list[dict]:
    return json.loads(_CASES.read_text())


def _key(provision: str) -> str:
    return re.sub(r'\s+', '', provision).casefold().rstrip('.')


def _segments(provision: str) -> tuple[int, ...]:
    root = _key(provision).split('(')[0]
    return tuple(int(part) for part in root.split('.') if part)


def cites(prohibited: str, cited: str) -> bool:
    """True when `cited` is the prohibited provision, including a sentence under a prohibited article."""
    ban = _key(prohibited)
    got = _key(cited)
    if ban.startswith('table') or got.startswith('table'):
        return ban == got
    if '(' in ban:
        return got == ban or got.startswith(ban + '(')
    banned = _segments(ban)
    found = _segments(got)
    return found[:len(banned)] == banned


def violations(trap: dict, cited: list[str]) -> list[dict]:
    """Prohibited provisions among `cited`. Mentioning one only to reject it is the caller's job."""
    found = []
    for ban in trap.get('must_not_cite') or []:
        if any(cites(ban['provision'], item) for item in cited):
            found.append(ban)
    return found


def citations_in(text: str) -> list[str]:
    return [match.group(0) for match in _ARTICLE.finditer(text)]
