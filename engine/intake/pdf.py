"""Read a dropped PDF: form values exactly, the text layer with page and box, and nothing else.

PDF validation is ported from PR #21 (`engine/files.py`: magic header and a parse that fails closed).
A page with no text layer (a scan or a photo) is reported "not read" with its reason; Batatis does
not run OCR and never guesses what an image says. Boxes are PDF user-space points, origin at the
bottom-left of the page: (left, bottom, right, top).
"""
from __future__ import annotations

import io
import json
from dataclasses import dataclass, field
from pathlib import Path

import pypdfium2 as pdfium
from pypdf import PdfReader

MAX_PAGES = 60
SCC_MAP = Path(__file__).resolve().parents[1] / 'export' / 'field_maps' / 'scc_2026-10.json'
# The SCC form's own heading, used to recognise a flattened copy that has lost its fields.
SCC_HEADING = ('Variance Form for Proposed Alternative Solution', 'Safety Codes Council')

NOT_A_PDF = 'This file is not a readable PDF.'
ENCRYPTED = 'The PDF is password-protected, so it was not read.'
NO_TEXT = ('This page has no text layer (it looks like a scan or a photo). Batatis does not read images, '
           'so nothing was taken from it. Type the facts, or attach a PDF with selectable text.')
FLATTENED_SCC = ('This looks like a flattened copy of the SCC variance form: its fill-in fields are gone, so '
                 'the values cannot be told apart from the printed form. Attach the fillable PDF instead.')
FORM_ONLY = ('The form fields were read. The pages have no text layer, so nothing else was taken from them.')
TOO_LONG = f'Only the first {MAX_PAGES} pages were read.'


class NotAPdf(Exception):
    """The bytes are not a readable PDF."""


@dataclass
class Widget:
    name: str
    kind: str                                   # 'text', 'checkbox', 'signature', 'button'
    value: str | bool | None
    page: int                                   # 1-based
    rect: tuple[float, float, float, float]


@dataclass
class Page:
    number: int
    text: str
    boxes: list[tuple[float, float, float, float] | None] = field(default_factory=list, repr=False)

    def box(self, start: int, end: int) -> tuple[float, float, float, float] | None:
        found = [b for b in self.boxes[start:end] if b is not None]
        if not found:
            return None
        return (round(min(b[0] for b in found), 2), round(min(b[1] for b in found), 2),
                round(max(b[2] for b in found), 2), round(max(b[3] for b in found), 2))


@dataclass
class PdfContent:
    pages: int
    text_pages: list[Page]
    blank_pages: list[int]
    widgets: list[Widget]
    form: str | None                            # 'scc_variance', 'acroform' or None
    reason: str | None = None                   # set when nothing at all could be read
    truncated: bool = False


def is_pdf(data: bytes) -> bool:
    head = data[:1024]
    if head.startswith(b'\xef\xbb\xbf'):
        head = head[3:]
    return head.lstrip(b' \t\r\n').startswith(b'%PDF-')


def _scc_fields() -> set[str]:
    data = json.loads(SCC_MAP.read_text(encoding='utf-8'))
    return set(data['text_fields']) | set(data['checkboxes'])


def _widgets(reader: PdfReader) -> list[Widget]:
    out = []
    for number, page in enumerate(reader.pages, start=1):
        for ref in page.get('/Annots') or []:
            annot = ref.get_object()
            if annot.get('/Subtype') != '/Widget':
                continue
            parent = annot.get('/Parent')
            parent = parent.get_object() if parent is not None else {}
            name = annot.get('/T') or parent.get('/T')
            kind = annot.get('/FT') or parent.get('/FT')
            if name is None or kind is None:
                continue
            raw = annot.get('/V', parent.get('/V'))
            rect = tuple(round(float(x), 2) for x in annot.get('/Rect', (0, 0, 0, 0)))
            if kind == '/Tx':
                value = str(raw).strip() if raw is not None and str(raw).strip() else None
                out.append(Widget(str(name), 'text', value, number, rect))
            elif kind == '/Btn':
                flags = int(annot.get('/Ff', parent.get('/Ff', 0)) or 0)
                if flags & (1 << 16):                   # pushbutton: no value
                    out.append(Widget(str(name), 'button', None, number, rect))
                    continue
                # A widget's own appearance state; radio children never use the group's inherited value.
                state = annot.get('/AS')
                if state is None and not flags & (1 << 15):
                    state = raw
                on = state is not None and str(state) not in ('None', '/Off', '')
                out.append(Widget(str(name), 'checkbox', True if on else None, number, rect))
            elif kind == '/Sig':
                out.append(Widget(str(name), 'signature', None, number, rect))
            else:
                out.append(Widget(str(name), 'button', None, number, rect))
    return out


def _text_pages(data: bytes, limit: int) -> tuple[list[Page], list[int]]:
    pages, blank = [], []
    pdf = pdfium.PdfDocument(data)
    try:
        for index in range(min(len(pdf), limit)):
            page = pdf[index]
            textpage = page.get_textpage()
            try:
                count = textpage.count_chars()
                text = textpage.get_text_range(0, count) if count else ''
                if not text.strip():
                    blank.append(index + 1)
                    continue
                boxes = []
                for i in range(count):
                    try:
                        boxes.append(textpage.get_charbox(i))
                    except pdfium.PdfiumError:
                        boxes.append(None)               # generated characters (line breaks) have no box
                pages.append(Page(index + 1, text, boxes))
            finally:
                textpage.close()
                page.close()
    finally:
        pdf.close()
    return pages, blank


def read_pdf(data: bytes) -> PdfContent:
    """Everything this PDF lets Batatis read. Raises NotAPdf for bytes that are not a PDF."""
    if not is_pdf(data):
        raise NotAPdf()
    try:
        reader = PdfReader(io.BytesIO(data))
        if reader.is_encrypted and not reader.decrypt(''):
            return PdfContent(0, [], [], [], None, ENCRYPTED)
        count = len(reader.pages)
        widgets = _widgets(reader)
    except NotAPdf:
        raise
    except Exception as exc:
        raise NotAPdf() from exc
    names = {w.name for w in widgets}
    scc = _scc_fields()
    form = 'scc_variance' if len(names & scc) >= 8 else ('acroform' if widgets else None)
    try:
        pages, blank = _text_pages(data, MAX_PAGES)
    except pdfium.PdfiumError as exc:
        raise NotAPdf() from exc
    if form is None and pages and all(h in pages[0].text for h in SCC_HEADING):
        return PdfContent(count, [], [], [], None, FLATTENED_SCC)
    return PdfContent(count, pages, blank, widgets, form, truncated=count > MAX_PAGES)
