"""Text helpers for intake: sentence spans, number words, units and quote location.

Ported from PR #30 (`description_facts.py`: number words, feet and square feet) and PR #36
(`fact_extraction.py`: sentence units with offsets). Rules match the applicant's own wording, so every
span here is a slice of the source text; conversions happen in code, never by rewriting the text.
"""
from __future__ import annotations

import re
import math

FT_TO_M = 0.3048
SQFT_TO_M2 = 0.09290304

_ONES = {
    'one': 1, 'two': 2, 'three': 3, 'four': 4, 'five': 5, 'six': 6, 'seven': 7, 'eight': 8, 'nine': 9,
    'ten': 10, 'eleven': 11, 'twelve': 12, 'thirteen': 13, 'fourteen': 14, 'fifteen': 15, 'sixteen': 16,
    'seventeen': 17, 'eighteen': 18, 'nineteen': 19,
}
_TENS = {'twenty': 20, 'thirty': 30, 'forty': 40, 'fifty': 50, 'sixty': 60, 'seventy': 70, 'eighty': 80,
         'ninety': 90}
_SINGLE = '|'.join(sorted(('one', 'two', 'three', 'four', 'five', 'six', 'seven', 'eight', 'nine'),
                          key=len, reverse=True))
_WORD = (rf"(?:(?:{'|'.join(_TENS)})(?:[-\s](?:{_SINGLE}))?|{'|'.join(sorted(_ONES, key=len, reverse=True))}"
         r"|a\s+hundred|one\s+hundred)")
# A number as written: 1,200 / 0.3 / twenty-four / a hundred. Use inside a larger pattern with re.I.
NUMBER = rf'(?:\d{{1,3}}(?:,\d{{3}})+(?:\.\d+)?|\d+(?:\.\d+)?|{_WORD})'


def number(token: str) -> int | float | None:
    """The value of a NUMBER match. None when the token is not a number."""
    raw = ' '.join(token.lower().replace('-', ' ').split())
    if re.fullmatch(r'[\d,]+(?:\.\d+)?', raw):
        value = float(raw.replace(',', ''))
        return int(value) if value.is_integer() and '.' not in raw else value
    if raw in ('a hundred', 'one hundred'):
        return 100
    if raw in _ONES:
        return _ONES[raw]
    parts = raw.split()
    if parts and parts[0] in _TENS and len(parts) <= 2:
        tail = _ONES.get(parts[1], None) if len(parts) == 2 else 0
        if tail is not None and tail < 10:
            return _TENS[parts[0]] + tail
    return None


def rounded(value: float) -> float:
    return round(value + 0.0, 2)


# Abbreviations whose period is not a sentence end when lower case or a digit follows (sq. ft. of,
# e.g. the, approx. 20). Inc. and Ltd. never end a sentence on their own in applicant prose.
_ABBREV = re.compile(r'\b(?i:sq|ft|no|fig|approx|vs|etc|e\.g|i\.e|o\.c|u\.s)\.$')
_COMPANY = re.compile(r'\b(?i:inc|ltd|corp|mr|mrs|ms|dr|prof|st)\.$')


def sentences(text: str) -> list[tuple[int, int]]:
    """Sentence spans (start, end) with surrounding whitespace trimmed. Lines are boundaries."""
    spans: list[tuple[int, int]] = []

    def emit(a: int, b: int) -> None:
        while a < b and text[a].isspace():
            a += 1
        while b > a and text[b - 1].isspace():
            b -= 1
        if a < b:
            spans.append((a, b))

    start = 0
    for i, ch in enumerate(text):
        if ch == '\n':
            emit(start, i)
            start = i + 1
        elif ch in '.?!':
            nxt = text[i + 1] if i + 1 < len(text) else ''
            if nxt and not nxt.isspace():
                continue
            if ch == '.':
                tail = text[max(start, i - 6):i + 1]
                after = text[i + 1:].lstrip()[:1]
                if _COMPANY.search(tail) or (_ABBREV.search(tail) and after and not after.isupper()):
                    continue
            emit(start, i + 1)
            start = i + 1
    emit(start, len(text))
    return spans


def sentence_at(spans: list[tuple[int, int]], index: int) -> tuple[int, int] | None:
    return next(((a, b) for a, b in spans if a <= index < b), None)


_WH = re.compile(r'(?i)^(?:what|how|why|when|where|which|who|can|could|do|does|is|are|should|would|will)\b')
_OWN_PLAN = re.compile(
    r'(?i)^(?:(?:can|could|may|should|would|will)\s+(?:I|we)\s+|'
    r'is\s+it\s+possible\s+(?:for\s+(?:me|us)\s+)?to\s+|'
    r'am\s+I\s+allowed\s+to\s+|are\s+we\s+allowed\s+to\s+|'
    r'do\s+(?:I|we)\s+need\s+a\s+variance\s+to\s+)'
    r'(?:build|add|use|install|replace|remove|omit|make|convert|renovate|have|put|leave|design|keep)\b')


# A question about Batatis, a professional or examples is a question to the tool, whatever its opening verb.
_ABOUT_TOOL = re.compile(r'(?i)\b(?:batatis|this\s+(?:app|tool|site)|you|examples?|explain|hir(?:e|ing)|professionals?)\b')


def is_question(sentence: str) -> bool:
    """A question to the tool, not a statement that merely sits beside one."""
    stripped = sentence.strip()
    return not (_OWN_PLAN.match(stripped) and not _ABOUT_TOOL.search(stripped)) and (stripped.endswith('?') or (bool(_WH.match(stripped)) and '?' in stripped))


def _exact(value: float) -> float:
    """Float noise removed, precision kept: stored values may sit right at a rule threshold."""
    return float(f'{value:.12g}')


def measurement(text: str, dimension: str) -> int | float:
    """A whole numeric answer in the field's metric unit. Unknown units never disappear."""
    raw = text.strip().lower().rstrip('.').replace('′', "'").replace('″', '"')
    if raw.startswith('.'):
        raw = '0' + raw
    n = rf'(?P<n>{NUMBER})'
    feet = re.fullmatch(rf'{n}\s*(?:feet|foot|ft\.?|\')\s*(?:(?:and\s+)?(?P<in>\d+(?:\.\d+)?)\s*(?:inches|inch|in\.?|"))?', raw, re.I)
    if dimension == 'length' and feet:
        inches = float(feet.group('in') or 0)
        if inches >= 12:
            raise ValueError('Inches must be less than 12.')
        value = number(feet.group('n'))
        if value is None or not math.isfinite(value):
            raise ValueError('Enter a finite number.')
        return _exact((value + inches / 12) * FT_TO_M)
    match = re.fullmatch(rf'{n}\s*(?P<unit>.*?)', raw, re.I)
    if not match:
        raise ValueError('Enter one number with its unit.')
    value, unit = number(match.group('n')), match.group('unit').strip()
    if value is None or not math.isfinite(value):
        raise ValueError('Enter a finite number.')
    if not unit:
        return value
    if dimension == 'count':
        if re.fullmatch(r'storeys?|stories|story|units?|homes?|suites?|dwellings?', unit):
            return value
        raise ValueError('Enter a whole count, without distance or area units.')
    lengths = {'m': 1, 'metre': 1, 'metres': 1, 'meter': 1, 'meters': 1,
               'cm': .01, 'centimetres': .01, 'centimeters': .01,
               'mm': .001, 'millimetres': .001, 'millimeters': .001,
               'in': .0254, 'inch': .0254, 'inches': .0254, '"': .0254}
    if dimension == 'length' and unit in lengths:
        return _exact(value * lengths[unit])
    if dimension == 'area':
        normalized = re.sub(r'[\s.^]', '', unit).replace('²', '2')
        if normalized in ('m2', 'sqm', 'squaremetres', 'squaremeters'):
            return value
        if normalized in ('ft2', 'sqft', 'squarefeet', 'squarefoot'):
            return _exact(value * SQFT_TO_M2)
    raise ValueError('Use m² or ft².' if dimension == 'area' else 'Use m, cm, mm, or ft and in.')


def spaced(text: str) -> str:
    """Whitespace collapsed to single spaces: the comparison form for quotes."""
    return ' '.join(text.split())


def find_quote(source: str, quote: str) -> tuple[int, int] | None:
    """Span of `quote` in `source`, allowing any run of whitespace where the quote has whitespace."""
    words = quote.split()
    if not words:
        return None
    match = re.compile(r'\s+'.join(re.escape(word) for word in words)).search(source)
    return (match.start(), match.end()) if match else None


def contains(source: str, quote: str) -> bool:
    return bool(quote.strip()) and spaced(quote) in spaced(source)
