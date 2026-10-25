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


def lines_at(text: str, width: float, size: float) -> list[str]:
    """Greedy word wrap at one size that never gives up: a word wider than the box is broken at its edge."""
    lines: list[str] = []
    for para in text.split('\n'):
        cur = ''
        for word in para.split(' '):
            if stringWidth(word, FONT, size) > width:
                if cur:
                    lines.append(cur)
                part, used = '', 0.0
                for char in word:
                    advance = stringWidth(char, FONT, size)
                    if part and used + advance > width:
                        lines.append(part)
                        part, used = '', 0.0
                    part += char
                    used += advance
                cur = part
                continue
            trial = f'{cur} {word}' if cur else word
            if stringWidth(trial, FONT, size) <= width:
                cur = trial
            else:
                lines.append(cur)
                cur = word
        lines.append(cur)
    return lines


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


def fit_start(head: str, body: str, tail: str, rect: tuple[float, float, float, float],
              max_size: float = MAX_SIZE, min_size: float = MIN_SIZE) -> str | None:
    """`head`, the longest whole-word start of `body`, then `tail`, as one string that fits; None if none does.

    For source text whose whole passage is carried elsewhere: `tail` names where. Adding words never takes
    fewer lines, so the longest fitting start is found by bisection.
    """
    words = body.split(' ')

    def start(count: int) -> str:
        return (head + ' '.join(words[:count])).rstrip() + tail

    low, high = -1, len(words) + 1      # `low` words fit (-1: not even head and tail); `high` words do not
    while high - low > 1:
        mid = (low + high) // 2
        if fit(start(mid), rect, max_size, min_size) is not None:
            low = mid
        else:
            high = mid
    return None if low < 0 else start(low)
