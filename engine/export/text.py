"""Text fitting for form fields, matched to pypdf's appearance-stream layout.

pypdf draws a multiline text field top-aligned, starting 2 pt from the left edge, clipped at 4 pt from the right
edge, with Helvetica line spacing of 1.156 x font size. `fit` wraps a value into a field rectangle at the largest
size between MAX_SIZE and MIN_SIZE, or returns None so the caller can move the value to the appendix.
"""
from __future__ import annotations

import re
import unicodedata

from reportlab.pdfbase.pdfmetrics import stringWidth

FONT = 'Helvetica'
MAX_SIZE = 10.0
MIN_SIZE = 6.0
LINE = 1.156                      # Helvetica bbox height / 1000, pypdf's leading factor
H_PAD = 7.0                       # 2 pt left inset + 4 pt right clip + 1 pt slack
V_PAD = 3.0                       # 1 pt border margin top and bottom + 1 pt slack

_REPLACE = {'–': '-', '—': '-', '‑': '-', '‘': "'", '’': "'", '“': '"',
            '”': '"', '…': '...', ' ': ' ', '•': '-', '\t': ' ', '−': '-',
            '≤': '<=', '≥': '>=', '≈': '~=', 'μ': 'µ', '⋅': '*', '∕': '/'}
_SUPER = str.maketrans('⁰¹²³⁴⁵⁶⁷⁸⁹⁺⁻⁼⁽⁾ⁿ', '0123456789+-=()n')
_SUB = str.maketrans('₀₁₂₃₄₅₆₇₈₉₊₋₌₍₎', '0123456789+-=()')


def faithful_font_text(value, encoding: str = 'cp1252') -> str:
    """Use explicit notation for unsupported scientific glyphs; never replace a value with '?'.

    The official form uses a single-byte font. Common ²/³ remain intact. Other exponent
    runs become ^(...), subscripts become _(...), and unknown symbols retain their codepoint
    and Unicode name so a reader can recover the source meaning rather than guess.
    """
    science = {'−': '-', '≤': '<=', '≥': '>=', '≈': '~=', 'μ': 'µ', '⋅': '*', '∕': '/'}
    text = ''.join(science.get(ch, ch) for ch in str(value))
    text = re.sub('[⁰¹²³⁴⁵⁶⁷⁸⁹⁺⁻⁼⁽⁾ⁿ]+',
        lambda m: m.group() if all(ch in '¹²³' for ch in m.group()) else '^(' + m.group().translate(_SUPER) + ')', text)
    text = re.sub('[₀₁₂₃₄₅₆₇₈₉₊₋₌₍₎]+', lambda m: '_(' + m.group().translate(_SUB) + ')', text)
    out = []
    for char in text:
        try:
            char.encode(encoding)
            out.append(char)
        except UnicodeEncodeError:
            out.append(f'[U+{ord(char):04X} {unicodedata.name(char, "UNNAMED CHARACTER")}]')
    return ''.join(out)


def pdf_safe(value) -> str:
    """Fit the form's font with faithful text fallbacks for unsupported symbols."""
    s = faithful_font_text(''.join(_REPLACE.get(ch, ch) for ch in str(value)), encoding='latin-1')
    s = '\n'.join(' '.join(line.split()) for line in s.replace('\r\n', '\n').split('\n'))
    return s.strip()


def wrap(text: str, width: float, size: float) -> list[str] | None:
    """Greedy word wrap; None when a single word is wider than the field."""
    lines: list[str] = []
    for para in text.split('\n'):
        cur = ''
        for word in para.split(' '):
            if stringWidth(word, FONT, size) > width:
                return None
            trial = f'{cur} {word}' if cur else word
            if stringWidth(trial, FONT, size) <= width:
                cur = trial
            else:
                lines.append(cur)
                cur = word
        lines.append(cur)
    return lines


CONTINUED_IN_APPENDIX = '… (continued in appendix)'


def fit_words(text: str, rect: tuple[float, float, float, float], max_size: float = MAX_SIZE,
              min_size: float = MIN_SIZE) -> str:
    """Fit text in a form cell, cutting only on a word boundary.

    The form font has no ellipsis glyph, so the continuation marker is stored as
    the latin-1 fallback of ``CONTINUED_IN_APPENDIX``.
    """
    shown = pdf_safe(text)
    if not shown:
        return ''
    if fit(shown, rect, max_size, min_size) is not None:
        return shown
    suffix = pdf_safe(CONTINUED_IN_APPENDIX)
    words = shown.split(' ')
    best = suffix if fit(suffix, rect, max_size, min_size) is not None else ''
    lo, hi = 0, len(words)
    while lo <= hi:
        mid = (lo + hi) // 2
        head = ' '.join(words[:mid]).strip()
        candidate = f'{head} {suffix}'.strip() if head else suffix
        if candidate and fit(candidate, rect, max_size, min_size) is not None:
            best = candidate
            lo = mid + 1
        else:
            hi = mid - 1
    return best


def fit(text: str, rect: tuple[float, float, float, float], max_size: float = MAX_SIZE,
        min_size: float = MIN_SIZE) -> tuple[list[str], float] | None:
    width = rect[2] - rect[0] - H_PAD
    height = rect[3] - rect[1] - V_PAD
    size = max_size
    while size >= min_size - 1e-9:
        lines = wrap(text, width, size)
        if lines is not None and len(lines) * LINE * size <= height:
            return lines, size
        size = round(size - 0.5, 1)
    return None
