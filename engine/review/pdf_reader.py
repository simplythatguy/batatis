"""Read uploaded PDFs for the package review. Reads only; never writes a value.

An uploaded PDF is one of: the SCC variance form with live AcroForm fields
(fillable), the SCC form flattened (text drawn on the page, no fields), an
attachment, or unreadable (no text layer, encrypted, not a PDF).

Field states:
- present: extracted text contributes visible pixels in the field. A fillable
  value must also agree with its stored normal appearance.
- blank: certain. Fillable: the field and its appearance are empty, with no
  added page content in the box. Flattened: the
  page has a text layer that matches the blank form, the rectangle holds no
  text and nothing else (image, drawing) was added inside it.
- not_found: Batatis could not tell. Ask the officer to look at the pointer.

Flattened reading uses the widget rectangles of the hash-checked blank form for
the field map's version (engine/export field maps). A supplied form grown for long
content is rebuilt from its strictly parsed `/BatatisLayout` hint and verified like
any other blank; a field continued in more boxes reads as one value.
"""
from __future__ import annotations

import hashlib
import io
import re
from dataclasses import dataclass, field
from functools import lru_cache

from ..export import scc
from ..export.form_growth import Layout
from ..pdfium import open_pdf
from ..pdfium_lock import pdfium_locked

FORM_TITLE = 'Variance Form for Proposed Alternative Solution'
MAX_ATTRIBUTION_ROWS = 256  # bound untrusted reconstruction hints independently of upload byte limits


@dataclass
class FieldValue:
    name: str                       # the form's own /T value
    page: int | None                # 0-based; unknown layout has only a file pointer
    rect: tuple[float, float, float, float] | None
    status: str                     # present | blank | not_found
    value: str = ''
    reason: str = ''


@dataclass
class PageText:
    page: int                       # 0-based
    text: str
    uncertain_boxes: tuple[tuple[float, float, float, float], ...] = ()


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
    field_map: dict | None = None    # verified runtime map for this form layout

    def locate(self, page: int, quote: str) -> tuple[float, float, float, float] | None:
        return locate(self.data, page, quote)

    @pdfium_locked
    def passage_has_marks(self, page: int, heading: tuple[str, int] | None,
                          stop: tuple[str, int] | None) -> bool:
        """Non-text objects between passage boundaries make text-only presence uncertain.

        Boundaries carry their offsets in the newline-normalized extracted page text.
        Unmatched or reversed boundaries cannot establish a readable, empty region.
        Unsafe text and visible graphics are regional. Compare their device coordinates
        so a rotated or cropped passage uses the same reading direction as its headings.
        """
        try:
            with open_pdf(self.data) as doc:
                pdf_page = doc[page]
                textpage = pdf_page.get_textpage()
                try:
                    after = _boundary_box(textpage, heading) if heading else None
                    before = _boundary_box(textpage, stop) if stop else None
                finally:
                    textpage.close()
                if (heading and after is None) or (stop and before is None):
                    return True
                after = _device_box(pdf_page, after, 2) if after else None
                before = _device_box(pdf_page, before, 2) if before else None
                if after and before and after[3] >= before[1]:
                    return True
                top = after[1] if after else float('-inf')
                bottom = before[1] if before else float('inf')
                boxes = frozenset(box for source in self.text_pages if source.page == page
                                  for box in source.uncertain_boxes)
                boxes |= _passage_object_boxes(pdf_page) | _annotation_boxes(pdf_page)
                return any(box[1] < bottom and box[3] > top
                           for box in (_device_box(pdf_page, rect, 2) for rect in boxes))
        except Exception:  # noqa: BLE001 - unreadable graphics must not establish a blank passage
            return True

    @pdfium_locked
    def unreadable_pages(self) -> list[int]:
        """Textless drawn pages, raster regions or annotation appearances in attachment/appendix pages.

        Paths on otherwise readable pages can be table borders/backgrounds, including in
        the official export. Paths inside a labelled passage are checked by passage_has_marks.
        """
        import pypdfium2.raw as raw
        try:
            with open_pdf(self.data) as doc:
                unreadable = []
                for page in self.text_pages:
                    pdf_page = doc[page.page]
                    if (page.uncertain_boxes or _annotation_boxes(pdf_page)
                            or (not page.text.strip() and _object_boxes(pdf_page)) or any(
                                obj.type == raw.FPDF_PAGEOBJ_IMAGE for obj in pdf_page.get_objects(max_depth=4))):
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
    template_glyphs: tuple[frozenset, ...]
    page_boxes: tuple[tuple, ...]
    widget_rects: dict[str, tuple]


def _norm(text: str) -> str:
    return re.sub(r'\s+', ' ', text or '').strip()


def mapped_widgets(fmap: dict) -> set[str]:
    names = set(fmap['text_fields']) | set(fmap['checkboxes'])
    for row in fmap['section_c_rows'] + fmap['section_d_rows']:
        names.update(row.values())
    if fmap.get('supporting_document_field'):
        names.add(fmap['supporting_document_field'])
    return names


def _read_widgets(fmap: dict, *, printed: bool = False) -> list[str]:
    """Mapped widgets, then the continuation boxes (`name~2`...) of a grown supplied form."""
    names = mapped_widgets(fmap)
    if printed:
        names |= {name for name in fmap.get('printed', {}) if '~' not in name}
    names = sorted(names)
    return names + [box for name in names for box in (fmap.get('continuations') or {}).get(name, [])]


def _join_continuations(fields: dict[str, FieldValue], fmap: dict) -> None:
    """Each continued field reads as one value from its boxes in order. Text must fill the boxes from the
    first, and a box that cannot be verified leaves the whole field unverified."""
    for name, boxes in (fmap.get('continuations') or {}).items():
        if name not in fields:
            continue  # the export-only printed legal row has no widget on an editable blank
        parts = [fields[name], *(fields.pop(box) for box in boxes)]
        statuses = [part.status for part in parts]
        own = parts[0]
        if 'not_found' in statuses or statuses != sorted(statuses, key=lambda status: status != 'present'):
            uncertain = next((part for part in parts if part.status == 'not_found'),
                             next(part for part in parts if part.status != 'present'))
            doubt = uncertain.reason if uncertain.status == 'not_found' else (
                'Text continues in a later box after an empty one. Check the boxes on the page.')
            fields[name] = FieldValue(name, uncertain.page, uncertain.rect, 'not_found', reason=doubt)
        elif 'present' in statuses:
            fields[name] = FieldValue(name, own.page, own.rect, 'present',
                                      _norm(' '.join(part.value for part in parts if part.status == 'present')))


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


def _passage_object_boxes(page) -> frozenset:
    """Keep answer graphics, while allowing the saved readable underline control.

    This does not change the native-field object inventory or form recognition.
    """
    import pypdfium2.raw as raw
    boxes = set()
    for obj in page.get_objects(max_depth=4):
        if obj.type in (raw.FPDF_PAGEOBJ_TEXT, raw.FPDF_PAGEOBJ_FORM):
            continue
        bounds = obj.get_bounds() if hasattr(obj, 'get_bounds') else obj.get_pos()
        if obj.type == raw.FPDF_PAGEOBJ_PATH and _passage_underline(page, bounds):
            continue
        boxes.add(tuple(bounds))
    return frozenset(boxes)


def _passage_underline(page, bounds) -> bool:
    """A thin rule immediately below at least two glyph origins is text decoration."""
    import ctypes
    import pypdfium2.raw as raw
    left, top, right, bottom = _device_box(page, bounds, 2)
    if right - left < 4 * max(1, bottom - top):
        return False
    text = page.get_textpage()
    matched = 0
    try:
        for index in range(min(text.count_chars(), 65536)):
            if not text.get_text_range(index, 1).strip():
                continue
            x, y = ctypes.c_double(), ctypes.c_double()
            if not raw.FPDFText_GetCharOrigin(text, index, ctypes.byref(x), ctypes.byref(y)):
                return False
            baseline_x, baseline_y, _right, _bottom = _device_box(page, (x.value, y.value, x.value, y.value), 2)
            size = raw.FPDFText_GetFontSize(text, index) * 2
            if (left <= baseline_x <= right and baseline_y <= top
                    and bottom <= baseline_y + .3 * size + 1 and bottom - top <= .15 * size + 1):
                matched += 1
                if matched >= 2:
                    return True
        return False
    finally:
        text.close()


def _annotation_boxes(page) -> frozenset:
    """Normal-view annotation appearances are separate from page-content objects.

    Compare normal rendering with annotations on/off: flags, appearance states and invisible
    drawing modes must not be guessed from /Contents or object counts. This detects ink only,
    never OCRs or reads applicant text.
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


def _version(version: str, path: str, layout: int | Layout = 5) -> FormVersion | None:
    fmap = scc.load_field_map(version)
    try:
        source = scc.load_form(path or None, fmap)
    except scc.ExportError:
        return None
    return _prepared_version(version, source, layout)


def _glyphs(page) -> frozenset:
    """Source characters AND their geometry, rather than prose/name-overlap scores."""
    text = page.get_textpage()
    return frozenset((char, *(round(v, 1) for v in text.get_charbox(i)))
                     for i in range(text.count_chars()) if (char := text.get_text_range(i, 1)).strip())


def _page_box(page) -> tuple:
    return (*map(float, page.mediabox), *map(float, page.cropbox), page.rotation)


@lru_cache(maxsize=16)
@pdfium_locked
def _prepared_version(version: str, source: bytes, layout: int | Layout) -> FormVersion:
    from pypdf import PdfReader
    fmap = scc.load_field_map(version)
    blank, fmap = scc.prepare_form(source, fmap, layout)
    rects = scc._rects(blank, fmap)
    reader = PdfReader(io.BytesIO(blank))
    pages = {name: page for page, name, _ in scc._widgets(reader.pages)}
    for name, where in fmap.get('printed', {}).items():
        rects[name], pages[name] = tuple(where['rect']), where['page']
    with open_pdf(blank) as doc:
        fmap['form_pages'] = len(doc)  # legacy stays fixed, irrespective of selected-row metadata
        texts = tuple(_norm(doc[i].get_textpage().get_text_range()) for i in range(len(doc)))
        objects = tuple(_object_boxes(doc[i]) for i in range(len(doc)))
        glyphs = tuple(_glyphs(doc[i]) for i in range(len(doc)))
        return FormVersion(version, fmap, blank, rects, pages, texts, objects, glyphs,
                           tuple(_page_box(page) for page in reader.pages),
                           {name: tuple(round(float(v), 1) for v in widget['/Rect'])
                            for _page, name, widget in scc._widgets(reader.pages)})


def form_versions() -> list[FormVersion]:
    """Every version-keyed field map whose blank form is available on this deployment."""
    out = []
    for path in sorted(scc.MAP_DIR.glob('*.json')):
        found = _version(path.stem, str(scc.form_path(version=path.stem)))
        if found is not None:
            out.append(found)
    return out


def field_maps() -> list[dict]:
    return [scc.load_field_map(path.stem) for path in sorted(scc.MAP_DIR.glob('*.json'))]


def _candidate_versions(reader) -> list[FormVersion]:
    """Metadata can nominate a bounded candidate, never attest the uploaded layout."""
    metadata = reader.metadata or {}
    keys = ('/BatatisFormVersion', '/BatatisAttributionRows', '/BatatisFormPages',
            '/BatatisSourceSHA256', '/BatatisSourcePages', '/BatatisLayout')
    if not any(key in metadata for key in keys):
        # Native legacy forms predate these hints. Missing new-layout hints stay uncertain.
        return [v for v in form_versions() if not v.fmap.get('dynamic_attributions')]
    version = metadata.get('/BatatisFormVersion')
    fmap = next((m for m in field_maps() if m['version'] == version), None)
    if not fmap:
        return []
    rows, pages = str(metadata.get(keys[1], '')), str(metadata.get(keys[2], ''))
    if not re.fullmatch(r'[1-9]\d{0,3}', rows) or not re.fullmatch(r'[1-9]\d{0,3}', pages):
        return []
    if int(rows) > MAX_ATTRIBUTION_ROWS or int(pages) > len(reader.pages):
        return []
    layout: int | Layout | None = int(rows)
    if fmap.get('dynamic_attributions'):
        if metadata.get(keys[3]) != fmap['source']['sha256'] or metadata.get(keys[4]) != '5-11':
            return []
        if keys[5] in metadata:     # grown cells: rebuilt only from a canonical, bounded hint
            layout = Layout.parse(str(metadata[keys[5]]), int(rows))
            if layout is None or layout.pages() > int(pages):
                return []
    elif any(key in metadata for key in keys[3:]):
        return []  # these source-page hints do not describe the five-page legacy form
    found = _version(version, str(scc.form_path(version=version)), layout)
    return [found] if found and found.fmap['form_pages'] == int(pages) else []


def _layout_matches(reader, doc, version: FormVersion) -> bool:
    count = version.fmap['form_pages']
    if len(doc) < count:
        return False
    for i in range(count):
        if _page_box(reader.pages[i]) != version.page_boxes[i]:
            return False
        page = doc[i]
        if page.get_textpage().count_chars() == 0 and i > 0 and not version.fmap.get('dynamic_attributions'):
            continue  # scanned page: its individual fields will be uncertain
        # Dynamic table-only blanks can have no text. Their exact source vectors
        # still need to match; a scanned page or forged hint cannot stand in for them.
        if not version.template_glyphs[i] <= _glyphs(page):
            return False
        if not version.template_objects[i] <= _object_boxes(page):
            return False
    return True


@pdfium_locked
def locate(data: bytes, page: int, quote: str) -> tuple[float, float, float, float] | None:
    """Bounding box of the first occurrence of `quote` on a 0-based page, or None."""
    quote = _norm(quote)[:200]
    if not quote or not data:
        return None
    try:
        with open_pdf(data) as doc:
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


def _device_box(page, rect, scale):
    """Map PDF points through the actual page crop and rotation."""
    import ctypes
    import math
    import pypdfium2.raw as raw
    width, height = (math.ceil(v * scale) for v in page.get_size())
    points = []
    for x in (rect[0], rect[2]):
        for y in (rect[1], rect[3]):
            px, py = ctypes.c_int(), ctypes.c_int()
            if not raw.FPDF_PageToDevice(page, 0, 0, width, height, 0, x, y,
                                         ctypes.byref(px), ctypes.byref(py)):
                raise ValueError('The field render coordinates could not be read.')
            points.append((px.value, py.value))
    xs, ys = zip(*points)
    return min(xs), min(ys), max(xs), max(ys)


def _region_render(page, rect, scale):
    import math
    x0, y0, x1, y1 = page.get_bbox()
    if not (x0 <= rect[0] < rect[2] <= x1 and y0 <= rect[1] < rect[3] <= y1):
        raise ValueError('The field is outside the visible page.')
    width, height = (math.ceil(v * scale) for v in page.get_size())
    left, top, right, bottom = _device_box(page, rect, scale)
    distances = (max(0, left), max(0, height - bottom), max(0, width - right), max(0, top))
    # render() rounds up: avoid a floating-point division moving an edge by one pixel.
    crop = tuple(math.nextafter(v / scale, -math.inf) if v else 0 for v in distances)
    bitmap = page.render(scale=scale, crop=crop, draw_annots=True, may_draw_forms=False)
    try:
        return bitmap.to_pil().convert('RGB')
    finally:
        bitmap.close()


def _text_glyphs(page):
    """Keep page-owned text-object handles with their transformed character boxes."""
    import pypdfium2.raw as raw
    text = page.get_textpage()
    try:
        if text.count_chars() > 65536:
            raise ValueError('Too many characters for bounded field inspection.')
        glyphs = []
        for index in range(text.count_chars()):
            char = text.get_text_range(index, 1)
            if char.strip():
                glyphs.append((char, text.get_charbox(index), raw.FPDFText_GetTextObject(text, index)))
        return glyphs
    finally:
        text.close()


def _text_is_visible(page, rect, value, glyphs=None):
    """Every quoted glyph must affect the rendered field, not just text extraction.

    Suppression is confined to this private inspection document and always restored.
    Per-object differences exclude borders/other answers; per-character boxes prevent
    a visible prefix from attesting an entirely covered suffix. No OCR is performed.
    """
    import ctypes
    import math
    import pypdfium2.raw as raw
    from PIL import ImageChops
    modes = []
    try:
        if len(value) > 8192:
            return False
        left, bottom, right, top = rect
        scale = min(2, math.sqrt(250000 / ((right - left) * (top - bottom))))
        original = _region_render(page, rect, scale)
        objects, chars = {}, []
        for char, box, obj in _text_glyphs(page) if glyphs is None else glyphs:
            x0, y0, x1, y1 = box
            if x0 >= right or x1 <= left or y0 >= top or y1 <= bottom:
                continue
            if (not obj or not all(math.isfinite(v) for v in box)
                    or x0 < left or y0 < bottom or x1 > right or y1 > top or x0 >= x1 or y0 >= y1):
                return False
            key = ctypes.cast(obj, ctypes.c_void_p).value
            objects.setdefault(key, (obj, []))[1].append(box)
            chars.append(char)
        if ''.join(chars) != re.sub(r'\s+', '', value) or len(objects) > 128:
            return False
        if not value:
            # An empty logical value cannot conceal text, handwriting or a raster appearance.
            return original.getextrema() == ((255, 255),) * 3
        if not objects:
            return False
        crop_left, crop_top, _right, _bottom = _device_box(page, rect, scale)
        for obj, boxes in objects.values():
            mode = raw.FPDFTextObj_GetTextRenderMode(obj)
            if mode not in (0, 1, 2):  # invisible and clip-only text do not attest an answer
                return False
            modes.append((obj, mode))
            if not raw.FPDFTextObj_SetTextRenderMode(obj, 3):
                return False
            difference = ImageChops.difference(original, _region_render(page, rect, scale))
            if not raw.FPDFTextObj_SetTextRenderMode(obj, mode):
                return False
            for box in boxes:
                x0, y0, x1, y1 = _device_box(page, box, scale)
                if not difference.crop((x0 - crop_left, y0 - crop_top,
                                        x1 - crop_left + 1, y1 - crop_top + 1)).getbbox():
                    return False
        return True
    except Exception:  # noqa: BLE001 - failed rendering cannot establish a readable answer
        return False
    finally:
        for obj, mode in modes:
            raw.FPDFTextObj_SetTextRenderMode(obj, mode)


def _appearance_pdf(widget, appearance):
    """Inspect the stored AP as an XObject, preserving its resources, matrix and clip."""
    import math
    from pypdf import PdfWriter
    from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject
    left, bottom, right, top = map(float, widget['/Rect'])
    width, height = right - left, top - bottom
    x0, y0, x1, y1 = map(float, appearance['/BBox'])
    a, b, c, d, e, f = map(float, appearance.get('/Matrix', (1, 0, 0, 1, 0, 0)))
    corners = [(a * x + c * y + e, b * x + d * y + f) for x in (x0, x1) for y in (y0, y1)]
    xs, ys = zip(*corners)
    if (not all(math.isfinite(v) for v in (width, height, *xs, *ys))
            or not 0 < width <= 2000 or not 0 < height <= 2000
            or min(xs) >= max(xs) or min(ys) >= max(ys)):
        raise ValueError('The appearance bounds could not be read.')
    sx, sy = width / (max(xs) - min(xs)), height / (max(ys) - min(ys))
    writer = PdfWriter()
    page = writer.add_blank_page(width=width, height=height)
    page[NameObject('/Resources')] = DictionaryObject({NameObject('/XObject'): DictionaryObject({
        NameObject('/Appearance'): writer._add_object(appearance.clone(writer))})})
    content = DecodedStreamObject()
    content.set_data(f'q {sx} 0 0 {sy} {-min(xs) * sx} {-min(ys) * sy} cm /Appearance Do Q'.encode())
    page[NameObject('/Contents')] = writer._add_object(content)
    output = io.BytesIO()
    writer.write(output)
    return output.getvalue()


@pdfium_locked
def _appearance_agrees(widget, value, *, checkbox=False):
    from PIL import ImageChops
    try:
        if int(widget.get('/F', 0)) & (1 | 2 | 32):
            return False
        if '/AP' not in widget or '/N' not in widget['/AP']:
            return not value
        appearance = widget['/AP']['/N']
        if checkbox:
            state = widget.get('/AS', '/Off')
            if state != (value or '/Off') or state not in appearance:
                return False
            selected = appearance[state]
        else:
            selected = appearance
        with open_pdf(_appearance_pdf(widget, selected)) as doc:
            page = doc[0]
            if not checkbox:
                return _text_is_visible(page, page.get_bbox(), value)
            if not value:
                return True
            with open_pdf(_appearance_pdf(widget, appearance['/Off'])) as off:
                return bool(ImageChops.difference(_region_render(page, page.get_bbox(), 2),
                                                  _region_render(off[0], off[0].get_bbox(), 2)).getbbox())
    except Exception:  # noqa: BLE001 - never regenerate a stale or unreadable AP from /V
        return False


def _overlaps(rect, boxes):
    x0, y0, x1, y1 = rect
    return any(bx0 < x1 and bx1 > x0 and by0 < y1 and by1 > y0 for bx0, by0, bx1, by1 in boxes)


@pdfium_locked
def _fillable(reader, data: bytes, name: str, version: FormVersion) -> ReadFile | None:
    try:
        fields = reader.get_fields() or {}
    except Exception:  # noqa: BLE001
        return None
    if not fields:
        return None
    # Canonical fields and actual widget geometry must match the verified blank.
    if set(fields) != set(version.widget_rects):
        return None
    fmap = version.fmap
    pages = {}
    rects = {}
    widgets = {}
    for page_no, widget_name, widget in scc._widgets(reader.pages):
        rect = tuple(round(float(v), 1) for v in widget['/Rect'])
        if (widget_name in pages or page_no != version.pages.get(widget_name)
                or rect != version.widget_rects.get(widget_name)):
            return None
        pages[widget_name] = page_no
        rects[widget_name] = rect
        widgets[widget_name] = widget
    if set(pages) != set(version.widget_rects):
        return None
    out = ReadFile(name, '', len(data), len(reader.pages), 'scc_form_fillable', fmap['version'],
                   data=data, field_map=fmap)
    with open_pdf(data) as doc:
        marks = {}
        for widget_name in _read_widgets(fmap):
            if widget_name not in fields:
                out.fields[widget_name] = FieldValue(widget_name, pages.get(widget_name, 0), None, 'not_found',
                                                     reason='This field is missing from the uploaded form.')
                continue
            raw_value = fields[widget_name].get('/V')
            value = '' if raw_value is None else str(raw_value)
            if widget_name in fmap['checkboxes']:
                value = '' if value in ('', '/Off', 'Off') else value
            value = _norm(value)
            status = 'present' if _norm(value) else 'blank'
            page_no, rect = pages.get(widget_name, 0), rects.get(widget_name)
            try:
                page = doc[page_no]
                if version is None or rect is None or widget_name not in widgets:
                    raise ValueError('The field appearance cannot be verified.')
                if page_no not in marks:
                    marks[page_no] = (_object_boxes(page) - version.template_objects[page_no]) | _annotation_boxes(page)
                text = page.get_textpage()
                try:
                    page_answer = _norm(text.get_text_bounded(*rect))
                finally:
                    text.close()
                widget_value = widgets[widget_name].get('/V', scc._field(widgets[widget_name]).get('/V'))
                widget_value = '' if widget_value is None else _norm(str(widget_value))
                if widget_name in fmap['checkboxes'] and widget_value in ('/Off', 'Off'):
                    widget_value = ''
                if (page_answer or _overlaps(rect, marks[page_no])
                        or widget_value != value
                        or not _appearance_agrees(widgets[widget_name], value, checkbox=widget_name in fmap['checkboxes'])):
                    status = 'not_found'
            except Exception:  # noqa: BLE001 - an unreadable box cannot establish presence or absence
                status = 'not_found'
            out.fields[widget_name] = FieldValue(widget_name, pages.get(widget_name, 0), rects.get(widget_name),
                                                 status, value if status == 'present' else '',
                                                 'The visible field and its stored value could not be verified. '
                                                 'Check the box on the page.' if status == 'not_found' else
                                                 'The fillable field is empty.' if status == 'blank' else '')
    _join_continuations(out.fields, fmap)
    for widget_name in signature_widgets(fmap):
        signed = widget_name in fields and fields[widget_name].get('/V') is not None
        out.signatures[widget_name] = FieldValue(
            widget_name, pages.get(widget_name, 1), rects.get(widget_name), 'present' if signed else 'not_found',
            'digital signature present (not validated)' if signed else '',
            '' if signed else 'No digital signature value. A wet or image signature cannot be read; check the page.')
    out.text_pages = _page_texts(data, range(fmap['form_pages'], len(reader.pages)))
    return out


@pdfium_locked
def _page_texts(data: bytes, pages) -> list[PageText]:
    import pypdfium2.raw as raw
    out = []
    with open_pdf(data) as doc:
        for index in pages:
            page = doc[index]
            textpage = page.get_textpage()
            raw_text = textpage.get_text_range()
            unsafe_boxes = []
            try:
                if textpage.count_chars() > 65536:
                    raise ValueError('Too many characters for bounded passage inspection.')
                units = [textpage.get_text_range(i, 1) for i in range(textpage.count_chars())]
                if ''.join(units) != raw_text:
                    raise ValueError('Text offsets could not be mapped confidently.')
                # Keep PDFium's text-line order, including rotated text. A hidden line
                # does not erase another answer or shift its source-text offsets.
                lines, glyphs = [[]], []
                for i, char in enumerate(units):
                    if '\n' in char or '\r' in char:
                        if lines[-1]:
                            lines.append([])
                        continue
                    if not char.strip():
                        continue
                    box = textpage.get_charbox(i)
                    glyphs.append((char, box, raw.FPDFText_GetTextObject(textpage, i)))
                    lines[-1].append((i, box))
                page_box = page.get_bbox()
                for chars in filter(None, lines):
                    bounds = (min(b[0] for _i, b in chars), min(b[1] for _i, b in chars),
                              max(b[2] for _i, b in chars), max(b[3] for _i, b in chars))
                    rect = (max(page_box[0], bounds[0] - .5), max(page_box[1], bounds[1] - .5),
                            min(page_box[2], bounds[2] + .5), min(page_box[3], bounds[3] + .5))
                    valid = rect[0] < rect[2] and rect[1] < rect[3]
                    # Validate the whole source line, including any clipped suffix;
                    # validating only get_text_bounded(rect) would attest unseen text.
                    value = ''.join(units[i] for i, _box in chars)
                    if not valid or not _text_is_visible(page, rect, value, glyphs):
                        unsafe_boxes.append(bounds)
                        for i, _box in chars:
                            units[i] = ' ' * len(units[i])
                safe_text = ''.join(units)
            except Exception:  # noqa: BLE001 - unverified text cannot establish presence or absence
                safe_text = re.sub(r'\S', ' ', raw_text)
                unsafe_boxes = [tuple(page.get_bbox())]
            finally:
                textpage.close()
            out.append(PageText(index, safe_text.replace('\r\n', '\n').replace('\r', '\n'), tuple(unsafe_boxes)))
    return out


@pdfium_locked
def _flattened(data: bytes, name: str, version: FormVersion) -> ReadFile:
    with open_pdf(data) as doc:
        out = ReadFile(name, '', len(data), len(doc), 'scc_form_flattened', version.version,
                       data=data, field_map=version.fmap)
        annotations, glyphs, pdf_pages = {}, {}, {}
        for widget_name in _read_widgets(version.fmap, printed=True) + signature_widgets(version.fmap):
            page_no = version.pages.get(widget_name, 0)
            rect = version.rects[widget_name]
            if page_no not in pdf_pages:
                pdf_pages[page_no] = doc[page_no]
            page = pdf_pages[page_no]  # retain the owner of cached raw text-object handles
            text = _norm(page.get_textpage().get_text_bounded(*rect))
            if widget_name in signature_widgets(version.fmap):
                out.signatures[widget_name] = FieldValue(
                    widget_name, page_no, rect, 'not_found', '',
                    'A signature on a flattened form cannot be read. Check the signature box on the page.')
                continue
            if page_no not in annotations:
                annotations[page_no] = _annotation_boxes(page)
            if text:
                if page_no not in glyphs:
                    glyphs[page_no] = _text_glyphs(page)
                state = (FieldValue(widget_name, page_no, rect, 'present', text)
                         if not _overlaps(rect, annotations[page_no]) and _text_is_visible(page, rect, text, glyphs[page_no]) else
                         FieldValue(widget_name, page_no, rect, 'not_found',
                                    reason='The extracted text could not be verified as visible. Check the box on the page.'))
            elif page.get_textpage().count_chars() == 0:
                state = FieldValue(widget_name, page_no, rect, 'not_found',
                                   reason='The page has no text layer (it may be scanned). Check the box on the page.')
            elif _added_marks(page, rect, version.template_objects[page_no]) or _overlaps(rect, annotations[page_no]):
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
        _join_continuations(out.fields, version.fmap)
        out.text_pages = _page_texts(data, range(version.fmap['form_pages'], len(doc)))
        return out

def _partially_flattened(reader, data: bytes, name: str, version: FormVersion) -> ReadFile | None:
    """Applicant content is flat; only signature/date/consent widgets remain on the form.

    Attachments may have their own fields. Their pages cannot establish a widget's
    identity or geometry on the verified form prefix.
    """
    from ..export.signatures import CONSENT_FIELD, OFFICER_FIELDS, SIGNATURE_FIELDS
    allowed = {CONSENT_FIELD, *OFFICER_FIELDS,
               *(field for pair in SIGNATURE_FIELDS.values() for field in pair)}
    fields = reader.get_fields() or {}
    prefix, attachment_names = {}, set()
    for page_no, widget_name, widget in scc._widgets(reader.pages):
        if page_no >= version.fmap['form_pages']:
            attachment_names.add(widget_name)
            continue
        rect = tuple(round(float(value), 1) for value in widget['/Rect'])
        if (widget_name not in allowed or widget_name in prefix or widget_name not in fields
                or page_no != version.pages.get(widget_name) or rect != version.widget_rects.get(widget_name)):
            return None
        prefix[widget_name] = widget
    if set(fields) - (set(prefix) | attachment_names):
        return None
    out = _flattened(data, name, version)
    # Applicant answers come from the flattened page; live signature boxes do not make the form fillable.
    out.role = 'scc_form_flattened'
    for widget_name in signature_widgets(version.fmap):
        widget = prefix.get(widget_name)
        value = fields.get(widget_name, {}).get('/V')
        if widget is not None and value is not None and widget.get('/V', scc._field(widget).get('/V')) == value:
            out.signatures[widget_name] = FieldValue(widget_name, version.pages[widget_name],
                version.rects[widget_name], 'present', 'digital signature present (not validated)')
    return out


def _added_marks(page, rect, template: frozenset) -> bool:
    x0, y0, x1, y1 = rect
    for box in _object_boxes(page) - template:
        bx0, by0, bx1, by1 = box
        if bx0 < x1 and bx1 > x0 and by0 < y1 and by1 > y0:
            return True
    return False


@pdfium_locked
def _form_read(reader, data: bytes, name: str) -> ReadFile | None:
    with open_pdf(data) as doc:
        metadata = reader.metadata or {}
        has_fields = bool(reader.get_fields())
        has_hint = any(key.startswith('/Batatis') for key in metadata)
        has_title = len(doc) and FORM_TITLE.casefold() in _norm(doc[0].get_textpage().get_text_range()).casefold()
        form_fields = {'Owner', 'Code or Standard', 'Article(s)'} <= set(reader.get_fields() or {})
        if not (has_title or has_hint or form_fields):
            return None
        candidates = [v for v in _candidate_versions(reader) if _layout_matches(reader, doc, v)]
        if len(candidates) == 1:
            version = candidates[0]
            if not has_fields:
                return _flattened(data, name, version)
            found = _fillable(reader, data, name, version)
            if found is not None:
                return found
            found = _partially_flattened(reader, data, name, version)
            if found is not None:
                return found
        note = ('This looks like the SCC variance form, but its source, layout, widgets or version hints '
                'could not be verified. Check the original file; no field is treated as blank or present.')
        out = ReadFile(name, '', len(data), len(doc),
                       'scc_form_fillable' if has_fields else 'scc_form_flattened', note=note, data=data)
        names = set().union(*(mapped_widgets(fmap) for fmap in field_maps()))
        for widget in names:
            out.fields[widget] = FieldValue(widget, None, None, 'not_found', reason=note)
        # Unknown form boundaries must not turn its printed reviewer/Part 4 pages into applicant evidence.
        return out


@pdfium_locked
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
    try:
        found = _form_read(reader, data, name)
    except Exception:  # noqa: BLE001 - broken form internals cannot establish a readable field
        return ReadFile(name, digest, len(data), page_count, 'unreadable', data=data,
                        note='The PDF layout or fields could not be inspected. Check the original file.')
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
