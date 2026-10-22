"""Read uploaded PDFs for the package review. Reads only; never writes a value.

An uploaded PDF is one of: the SCC variance form with live AcroForm fields
(fillable), the SCC form flattened (text drawn on the page, no fields), an
attachment, or unreadable (no text layer, encrypted, not a PDF).

Field states:
- present: text was read in the field (fillable /V, or text inside the field
  rectangle of a flattened page).
- blank: certain. Fillable: the field exists and has no value. Flattened: the
  page has a text layer that matches the blank form, the rectangle holds no
  text and nothing else (image, drawing) was added inside it.
- not_found: Batatis could not tell. Ask the officer to look at the pointer.

Flattened reading uses the widget rectangles of the hash-checked blank form for
the field map's version (engine/export field maps).
"""
from __future__ import annotations

import hashlib
import io
import re
from dataclasses import dataclass, field
from functools import lru_cache

from ..export import scc

FORM_TITLE = 'Variance Form for Proposed Alternative Solution'
FORM_PAGES = 5
TEMPLATE_MATCH = 0.8


@dataclass
class FieldValue:
    name: str                       # the form's own /T value
    page: int                       # 0-based
    rect: tuple[float, float, float, float] | None
    status: str                     # present | blank | not_found
    value: str = ''
    reason: str = ''


@dataclass
class PageText:
    page: int                       # 0-based
    text: str


@dataclass
class ReadFile:
    name: str
    sha256: str
    size: int
    pages: int
    role: str                       # scc_form_fillable | scc_form_flattened | attachment | unreadable
    form_version: str | None = None
    fields: dict[str, FieldValue] = field(default_factory=dict)
    signatures: dict[str, FieldValue] = field(default_factory=dict)
    text_pages: list[PageText] = field(default_factory=list)   # attachment pages, or form pages after the form
    note: str = ''
    data: bytes = b''

    def locate(self, page: int, quote: str) -> tuple[float, float, float, float] | None:
        return locate(self.data, page, quote)

    def passage_has_marks(self, page: int, heading: tuple[str, int] | None,
                          stop: tuple[str, int] | None) -> bool:
        """Non-text objects between passage boundaries make text-only presence uncertain.

        Boundaries carry their offsets in the newline-normalized extracted page text.
        Unmatched or reversed boundaries cannot establish a readable, empty region.
        Coordinates and object boxes use the same PDF-point convention as flattened fields.
        """
        import pypdfium2 as pdfium
        try:
            doc = pdfium.PdfDocument(self.data)
            pdf_page = doc[page]
            textpage = pdf_page.get_textpage()
            after = _boundary_box(textpage, heading) if heading else None
            before = _boundary_box(textpage, stop) if stop else None
            if (heading and after is None) or (stop and before is None):
                return True
            if after and before and after[1] <= before[3]:
                return True
            top = after[3] if after else float('inf')
            bottom = before[3] if before else float('-inf')
            boxes = _object_boxes(pdf_page) | _annotation_boxes(pdf_page)
            return any(y0 < top and y1 > bottom for _x0, y0, _x1, y1 in boxes)
        except Exception:  # noqa: BLE001 - unreadable graphics must not establish a blank passage
            return True

    def unreadable_pages(self) -> list[int]:
        """Textless drawn pages, raster regions or annotation appearances in attachment/appendix pages.

        Paths on otherwise readable pages can be table borders/backgrounds, including in
        the official export. Paths inside a labelled passage are checked by passage_has_marks.
        """
        import pypdfium2 as pdfium
        import pypdfium2.raw as raw
        try:
            doc = pdfium.PdfDocument(self.data)
            unreadable = []
            for page in self.text_pages:
                pdf_page = doc[page.page]
                if _annotation_boxes(pdf_page) or (not page.text.strip() and _object_boxes(pdf_page)) or any(
                        obj.type == raw.FPDF_PAGEOBJ_IMAGE for obj in pdf_page.get_objects(max_depth=4)):
                    unreadable.append(page.page)
            return unreadable
        except Exception:  # noqa: BLE001 - a failed inspection cannot establish absence
            return [page.page for page in self.text_pages]


@dataclass(frozen=True)
class FormVersion:
    version: str
    fmap: dict
    blank: bytes
    rects: dict[str, tuple[float, float, float, float]]
    pages: dict[str, int]
    template_text: tuple[str, ...]            # normalised text of each blank page
    template_objects: tuple[frozenset, ...]   # non-text object boxes on each blank page


def _norm(text: str) -> str:
    return re.sub(r'\s+', ' ', text or '').strip()


def mapped_widgets(fmap: dict) -> set[str]:
    names = set(fmap['text_fields']) | set(fmap['checkboxes'])
    for row in fmap['section_c_rows'] + fmap['section_d_rows']:
        names.update(row.values())
    return names


def signature_widgets(fmap: dict) -> list[str]:
    # Applicant signatures are on page 2 of the 2026-10 form; officer signatures are skipped.
    return [name for name in fmap['skipped'].get('signature', []) if name in ('Signature1', 'Signature2')]


def _object_boxes(page) -> frozenset:
    import pypdfium2.raw as raw
    boxes = set()
    for obj in page.get_objects(max_depth=4):
        if obj.type in (raw.FPDF_PAGEOBJ_TEXT, raw.FPDF_PAGEOBJ_FORM):
            continue
        try:
            bounds = obj.get_bounds() if hasattr(obj, 'get_bounds') else obj.get_pos()   # pypdfium2 5 / 4
            boxes.add(tuple(round(v) for v in bounds))
        except Exception:  # noqa: BLE001 - an object without bounds cannot be compared
            continue
    return frozenset(boxes)


def _annotation_boxes(page) -> frozenset:
    """Normal-view annotation appearances are separate from page-content objects.

    Compare normal rendering with annotations on/off: flags, appearance states and invisible
    drawing modes must not be guessed from /Contents or object counts. This detects ink only,
    never OCRs or reads applicant text. Legacy flattened-field extraction remains unchanged.
    """
    import ctypes
    import pypdfium2.raw as raw
    from PIL import ImageChops
    rects = []
    count = raw.FPDFPage_GetAnnotCount(page)
    if count < 0:
        raise ValueError('Annotation inventory could not be read.')
    for index in range(count):
        annotation = raw.FPDFPage_GetAnnot(page, index)
        if not annotation:
            raise ValueError('Annotation could not be opened.')
        try:
            flags = raw.FPDFAnnot_GetFlags(annotation)
            if flags & (raw.FPDF_ANNOT_FLAG_HIDDEN | raw.FPDF_ANNOT_FLAG_NOVIEW):
                continue
            rect = raw.FS_RECTF()
            if not raw.FPDFAnnot_GetRect(annotation, ctypes.byref(rect)):
                raise ValueError('Annotation bounds could not be read.')
            rects.append((rect.left, rect.bottom, rect.right, rect.top))
        finally:
            raw.FPDFPage_CloseAnnot(annotation)
    if not rects:
        return frozenset()
    with_annots = page.render(scale=1, draw_annots=True, may_draw_forms=False)
    without_annots = page.render(scale=1, draw_annots=False, may_draw_forms=False)
    difference = ImageChops.difference(with_annots.to_pil().convert('RGB'), without_annots.to_pil().convert('RGB'))
    width, height = difference.size

    def pixel(x, y):
        px, py = ctypes.c_int(), ctypes.c_int()
        if not raw.FPDF_PageToDevice(page, 0, 0, width, height, 0, x, y, ctypes.byref(px), ctypes.byref(py)):
            raise ValueError('Annotation page coordinates could not be read.')
        return px.value, py.value

    def point(x, y):
        px, py = ctypes.c_double(), ctypes.c_double()
        if not raw.FPDF_DeviceToPage(page, 0, 0, width, height, 0, x, y, ctypes.byref(px), ctypes.byref(py)):
            raise ValueError('Annotation render coordinates could not be read.')
        return px.value, py.value

    boxes = set()
    for x0, y0, x1, y1 in rects:
        a, b = pixel(x0, y0), pixel(x1, y1)
        crop = (max(0, min(a[0], b[0]) - 1), max(0, min(a[1], b[1]) - 1),
                min(width, max(a[0], b[0]) + 1), min(height, max(a[1], b[1]) + 1))
        if crop[0] >= crop[2] or crop[1] >= crop[3]:
            continue
        ink = difference.crop(crop).getbbox()
        if ink:
            a = point(crop[0] + ink[0], crop[1] + ink[1])
            b = point(crop[0] + ink[2], crop[1] + ink[3])
            boxes.add((min(a[0], b[0]), min(a[1], b[1]), max(a[0], b[0]), max(a[1], b[1])))
    return frozenset(boxes)


@lru_cache(maxsize=4)
def _version(version: str, path: str) -> FormVersion | None:
    import pypdfium2 as pdfium
    fmap = scc.load_field_map(version)
    try:
        blank = scc.load_form(path or None, fmap)
    except scc.ExportError:
        return None
    rects = scc._rects(blank, fmap)
    from pypdf import PdfReader
    pages = {name: page for page, name, _ in scc._widgets(PdfReader(io.BytesIO(blank)).pages)}
    doc = pdfium.PdfDocument(blank)
    texts = tuple(_norm(doc[i].get_textpage().get_text_range()) for i in range(len(doc)))
    objects = tuple(_object_boxes(doc[i]) for i in range(len(doc)))
    return FormVersion(version, fmap, blank, rects, pages, texts, objects)


def form_versions() -> list[FormVersion]:
    """Every version-keyed field map whose blank form is available on this deployment."""
    out = []
    for path in sorted(scc.MAP_DIR.glob('*.json')):
        found = _version(path.stem, str(scc.form_path()))
        if found is not None:
            out.append(found)
    return out


def field_maps() -> list[dict]:
    return [scc.load_field_map(path.stem) for path in sorted(scc.MAP_DIR.glob('*.json'))]


def _template_score(page_text: str, template: str) -> float:
    words = template.split()
    if not words:
        return 0.0
    lines = [' '.join(words[i:i + 6]) for i in range(0, len(words), 6)]
    return sum(1 for line in lines if line in page_text) / len(lines)


def locate(data: bytes, page: int, quote: str) -> tuple[float, float, float, float] | None:
    """Bounding box of the first occurrence of `quote` on a 0-based page, or None."""
    import pypdfium2 as pdfium
    quote = _norm(quote)[:200]
    if not quote or not data:
        return None
    try:
        doc = pdfium.PdfDocument(data)
        textpage = doc[page].get_textpage()
        searcher = textpage.search(quote, match_case=False)
        hit = searcher.get_next()
        if not hit:
            return None
        start, count = hit
        boxes = [textpage.get_charbox(i) for i in range(start, start + count)]
    except Exception:  # noqa: BLE001 - a pointer without a box is still a pointer
        return None
    return (round(min(b[0] for b in boxes), 1), round(min(b[1] for b in boxes), 1),
            round(max(b[2] for b in boxes), 1), round(max(b[3] for b in boxes), 1))


def _boundary_box(textpage, boundary: tuple[str, int]) -> tuple[float, float, float, float] | None:
    """Pair a text offset with the same PDFium search occurrence, never the first by default."""
    quote, offset = boundary
    quote = _norm(quote)[:200]
    if not quote:
        return None
    text = textpage.get_text_range().replace('\r\n', '\n').replace('\r', '\n')
    matches = list(re.finditer(r'\s+'.join(re.escape(word) for word in quote.split()), text, re.I))
    occurrence = next((index for index, match in enumerate(matches) if match.start() == offset), None)
    if occurrence is None:
        return None
    searcher = textpage.search(quote, match_case=False)
    hits = []
    while hit := searcher.get_next():
        hits.append(hit)
    if len(hits) != len(matches):
        return None   # extraction and geometry disagree; do not guess a boundary
    start, count = hits[occurrence]
    boxes = [textpage.get_charbox(index) for index in range(start, start + count)]
    return (min(b[0] for b in boxes), min(b[1] for b in boxes),
            max(b[2] for b in boxes), max(b[3] for b in boxes))


def _fillable(reader, data: bytes, name: str, fmaps: list[dict]) -> ReadFile | None:
    try:
        fields = reader.get_fields() or {}
    except Exception:  # noqa: BLE001
        return None
    if not fields:
        return None
    best = None
    for fmap in fmaps:
        wanted = mapped_widgets(fmap)
        share = len(wanted & set(fields)) / len(wanted)
        if share >= TEMPLATE_MATCH and (best is None or share > best[0]):
            best = (share, fmap)
    if best is None:
        return None
    fmap = best[1]
    pages = {}
    rects = {}
    for page_no, widget_name, widget in scc._widgets(reader.pages):
        pages.setdefault(widget_name, page_no)
        rects.setdefault(widget_name, tuple(round(float(v), 1) for v in widget['/Rect']))
    out = ReadFile(name, '', len(data), len(reader.pages), 'scc_form_fillable', fmap['version'], data=data)
    for widget_name in sorted(mapped_widgets(fmap)):
        if widget_name not in fields:
            out.fields[widget_name] = FieldValue(widget_name, pages.get(widget_name, 0), None, 'not_found',
                                                 reason='This field is missing from the uploaded form.')
            continue
        raw_value = fields[widget_name].get('/V')
        value = '' if raw_value is None else str(raw_value)
        if widget_name in fmap['checkboxes']:
            value = '' if value in ('', '/Off', 'Off') else value
        status = 'present' if _norm(value) else 'blank'
        out.fields[widget_name] = FieldValue(widget_name, pages.get(widget_name, 0), rects.get(widget_name),
                                             status, _norm(value) if status == 'present' else '',
                                             'The fillable field is empty.' if status == 'blank' else '')
    for widget_name in signature_widgets(fmap):
        signed = widget_name in fields and fields[widget_name].get('/V') is not None
        out.signatures[widget_name] = FieldValue(
            widget_name, pages.get(widget_name, 1), rects.get(widget_name), 'present' if signed else 'not_found',
            'digital signature present (not validated)' if signed else '',
            '' if signed else 'No digital signature value. A wet or image signature cannot be read; check the page.')
    out.text_pages = _page_texts(data, range(FORM_PAGES, len(reader.pages)))
    return out


def _page_texts(data: bytes, pages) -> list[PageText]:
    import pypdfium2 as pdfium
    doc = pdfium.PdfDocument(data)
    out = []
    for index in pages:
        text = doc[index].get_textpage().get_text_range()
        out.append(PageText(index, text.replace('\r\n', '\n').replace('\r', '\n')))
    return out


def _flattened(data: bytes, name: str, versions: list[FormVersion], fmaps: list[dict]) -> ReadFile | None:
    import pypdfium2 as pdfium
    doc = pdfium.PdfDocument(data)
    if len(doc) < FORM_PAGES:
        return None
    first = _norm(doc[0].get_textpage().get_text_range())
    if FORM_TITLE.casefold() not in first.casefold():
        return None
    for version in versions:
        # Page 1 identifies the form; any other page with a text layer must match its template page too.
        # A page with no text layer (scanned) does not disqualify the form; its fields become not found.
        texts = [_norm(doc[i].get_textpage().get_text_range()) for i in range(FORM_PAGES)]
        scores = [_template_score(texts[i], version.template_text[i]) for i in range(FORM_PAGES)
                  if i == 0 or texts[i]]
        if min(scores) < TEMPLATE_MATCH:
            continue
        out = ReadFile(name, '', len(data), len(doc), 'scc_form_flattened', version.version, data=data)
        for widget_name in sorted(mapped_widgets(version.fmap)) + signature_widgets(version.fmap):
            page_no = version.pages.get(widget_name, 0)
            rect = version.rects[widget_name]
            page = doc[page_no]
            text = _norm(page.get_textpage().get_text_bounded(*rect))
            if widget_name in signature_widgets(version.fmap):
                out.signatures[widget_name] = FieldValue(
                    widget_name, page_no, rect, 'not_found', '',
                    'A signature on a flattened form cannot be read. Check the signature box on the page.')
                continue
            if text:
                state = FieldValue(widget_name, page_no, rect, 'present', text)
            elif page.get_textpage().count_chars() == 0:
                state = FieldValue(widget_name, page_no, rect, 'not_found',
                                   reason='The page has no text layer (it may be scanned). Check the box on the page.')
            elif _added_marks(page, rect, version.template_objects[page_no]):
                state = FieldValue(widget_name, page_no, rect, 'not_found',
                                   reason='Something other than text is drawn in this box (handwriting, an image '
                                          'or a stamp). Check the box on the page.')
            else:
                state = FieldValue(widget_name, page_no, rect, 'blank', reason='No text is in this box on the page.')
            if widget_name in version.fmap['checkboxes']:
                # A flattened check mark is a drawing, not text: never treat it as certain.
                state = FieldValue(widget_name, page_no, rect, 'not_found',
                                   reason='A check box on a flattened form cannot be read reliably.')
            out.fields[widget_name] = state
        out.text_pages = _page_texts(data, range(FORM_PAGES, len(doc)))
        return out
    note = ('This looks like the SCC variance form, but its layout does not match a known field map version, '
            'or the blank form for that version is not available on this deployment.')
    fmap = fmaps[-1] if fmaps else None
    out = ReadFile(name, '', len(data), len(doc), 'scc_form_flattened', None, note=note, data=data)
    if fmap:
        for widget_name in sorted(mapped_widgets(fmap)):
            out.fields[widget_name] = FieldValue(widget_name, 0, None, 'not_found', reason=note)
    out.text_pages = _page_texts(data, range(FORM_PAGES, len(doc)))
    return out


def _added_marks(page, rect, template: frozenset) -> bool:
    x0, y0, x1, y1 = rect
    for box in _object_boxes(page) - template:
        bx0, by0, bx1, by1 = box
        if bx0 < x1 and bx1 > x0 and by0 < y1 and by1 > y0:
            return True
    return False


def read_pdf(data: bytes, name: str) -> ReadFile:
    """Classify and read one uploaded file. Never raises for bad input; reports it as unreadable."""
    digest = hashlib.sha256(data).hexdigest()
    base = dict(sha256=digest, size=len(data))
    if not data.startswith(b'%PDF'):
        return ReadFile(name, digest, len(data), 0, 'unreadable', note='Not a PDF file.')
    try:
        from pypdf import PdfReader
        reader = PdfReader(io.BytesIO(data))
        if reader.is_encrypted:
            return ReadFile(name, digest, len(data), 0, 'unreadable', note='The PDF is encrypted.')
        page_count = len(reader.pages)
    except Exception:  # noqa: BLE001 - a malformed upload is reported, not raised
        return ReadFile(name, digest, len(data), 0, 'unreadable', note='The PDF could not be opened.')
    fmaps = field_maps()
    try:
        found = _fillable(reader, data, name, fmaps)
    except Exception:  # noqa: BLE001 - pypdf parses pages lazily; a broken widget falls through to flattened
        found = None
    if found is None:
        try:
            found = _flattened(data, name, form_versions(), fmaps)
        except Exception:  # noqa: BLE001
            found = None
    if found is not None:
        found.sha256, found.size = base['sha256'], base['size']
        return found
    try:
        pages = _page_texts(data, range(page_count))
    except Exception:  # noqa: BLE001
        return ReadFile(name, digest, len(data), page_count, 'unreadable', note='The PDF text could not be read.')
    if not any(page.text.strip() for page in pages):
        return ReadFile(name, digest, len(data), page_count, 'unreadable', data=data,
                        note='No text layer was found (it may be scanned). Its contents were not read.')
    return ReadFile(name, digest, len(data), page_count, 'attachment', text_pages=pages, data=data)
