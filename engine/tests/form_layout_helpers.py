"""Assertions over a form field's visible boxes, including source-style continuations."""
import pypdfium2 as pdfium

from engine.export.g3 import norm
from engine.pdfium_lock import pdfium_locked


def segments(result, name):
    return sorted((p for p in result.placements if p.field == name), key=lambda p: (p.page, -p.rect[3]))


def shown_fields(result):
    return {name: norm(' '.join(line for p in segments(result, name) for line in p.lines))
            for name in dict.fromkeys(p.field for p in result.placements)}


@pdfium_locked
def drawn(result, placements):
    with pdfium.PdfDocument(result.pdf) as doc:
        return norm(' '.join(doc[p.page].get_textpage().get_text_bounded(*p.rect) for p in placements))
