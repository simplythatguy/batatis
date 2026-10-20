"""Text fitting for form fields, matched to pypdf's appearance-stream layout.

pypdf draws a multiline text field top-aligned, starting 2 pt from the left edge, clipped at 4 pt from the right
edge, with Helvetica line spacing of 1.156 x font size. `fit` wraps a value into a field rectangle at the largest
size between MAX_SIZE and MIN_SIZE, or returns None so the caller can move the value to the appendix.
"""
from __future__ import annotations

from reportlab.pdfbase.pdfmetrics import stringWidth

FONT = 'Helvetica'
MAX_SIZE = 10.0
MIN_SIZE = 6.0
LINE = 1.156                      # Helvetica bbox height / 1000, pypdf's leading factor
H_PAD = 7.0                       # 2 pt left inset + 4 pt right clip + 1 pt slack
V_PAD = 3.0                       # 1 pt border margin top and bottom + 1 pt slack

_REPLACE = {'–': '-', '—': '-', '‑': '-', '‘': "'", '’': "'", '“': '"',
            '”': '"', '…': '...', ' ': ' ', '•': '-', '\t': ' '}


def pdf_safe(value) -> str:
    """The form's /Helv font is single-byte; keep text to Latin-1 so no glyph is silently dropped."""
    s = ''.join(_REPLACE.get(ch, ch) for ch in str(value))
    s = '\n'.join(' '.join(line.split()) for line in s.replace('\r\n', '\n').split('\n'))
    return s.strip().encode('latin-1', 'replace').decode('latin-1')


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
