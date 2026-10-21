"""Ported from PR #12 (backend/identify-api). Read a storey count out of the applicant's own words.

'two-storey', '2 storeys', and 'bungalow' are the phrases the identify questions
were asking again. The count is the number they wrote, with the matched words kept
as the source quote.
"""
from __future__ import annotations

import re

_NUM = {
    'one': 1, 'two': 2, 'three': 3, 'four': 4, 'five': 5, 'six': 6, 'seven': 7, 'eight': 8,
    'nine': 9, 'ten': 10, 'eleven': 11, 'twelve': 12,
}
_TOKEN = rf'(?:\d+|{"|".join(sorted(_NUM, key=len, reverse=True))})'
_ONE = re.compile(r'\b(?:bungalows?|one[- ]storey|single[- ]storey)\b', re.I)
_COUNT = re.compile(rf'\b({_TOKEN})[-\u2013\s](?:storeys?|stories)\b', re.I)


def _number(token: str) -> int:
    token = token.lower()
    return _NUM[token] if token in _NUM else int(token)


def parse_storeys(text: str) -> tuple[int, str] | None:
    """Highest storey count named in `text`, and the words that named it.

    A bungalow, a one-storey building, and a single-storey building are 1.
    A later higher count in the same text wins: 'two-storey bungalow' is 2.
    """
    if not text:
        return None
    found: list[tuple[int, str]] = []
    for match in _ONE.finditer(text):
        found.append((1, match.group(0)))
    for match in _COUNT.finditer(text):
        found.append((_number(match.group(1)), match.group(0)))
    if not found:
        return None
    return max(found, key=lambda item: item[0])
