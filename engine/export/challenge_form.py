"""Mechanical layout of the supplied challenge's pages 5-11.

The source is hash-pinned. Only the blank attribution rows on its second page
are removed/repeated; the original Section D and disclosures move together.
All drawing/text operators, resources and page boxes come from the source.
No source Appendix text is interpreted as code-database authority.
"""
from __future__ import annotations

import copy
import hashlib
import io
from dataclasses import dataclass

from pypdf import PageObject, PdfWriter
from pypdf.generic import (ArrayObject, BooleanObject, ContentStream, DictionaryObject,
                           FloatObject, NameObject, NumberObject, RectangleObject, TextStringObject)

VERSION = 'challenge_2026-09-15'
SOURCE_SHA256 = '761bf8d9d8e93445a49ce58c443a1a8928fa08a45a031a0adc371d45fd5a7d55'
ROW_NAMES = ('Article(s)', 'Objective', 'Function', 'Intent statement')
ROW_KEYS = ('article', 'objective', 'function', 'intent')

# Coordinates of the actual blue table's vector rectangles (PDF points).
PAGE_TOP = 755.995
PAGE_BOTTOM = 69.775
FIRST_BOTTOM = 692.72
REPEAT_BOTTOM = 630.7
ROW_HEIGHT = 62.025
FOLLOWING_TOP = 506.65
FOLLOWING_BOTTOM = 81.275
# The printed Section B row "Legal description of property that this variance will apply to:" has no source
# widget. Export draws a typed legal description after its label (ending at x 303.3), inset in the row
# (y 333.6 to 351.1) as the source insets its Permit widget. Export only: the editable blank and the
# re-upload reader keep the source's own widgets.
LEGAL_ROW = 'Legal description'
LEGAL_PAGE = 0
LEGAL_RECT = (305.5, 334.5, 571.8, 349.5)


def row_fields(index: int) -> dict[str, str]:
    suffix = str(index) if index else ''
    return dict(zip(ROW_KEYS, (name + suffix for name in ROW_NAMES)))


def independent_fields(writer: PdfWriter) -> None:
    """Make every source widget its own canonical terminal field, using its real parent.

    In the supplied PDF the four attribution parents each own five Kids. They
    must be split, never reattached as duplicate parents with the same name.
    """
    counts: dict[str, int] = {}
    fields = ArrayObject()
    for page in writer.pages:
        for ref in page.get('/Annots', []):
            widget = ref.get_object()
            if widget.get('/Subtype') != '/Widget':
                continue
            parent = widget.get('/Parent')
            owner = parent.get_object() if parent else widget
            name = str(owner['/T'])
            if name in ROW_NAMES:
                index = counts.get(name, 0)
                counts[name] = index + 1
                name += str(index) if index else ''
            for key, value in owner.items():
                if key not in ('/Kids', '/Parent') and key not in widget:
                    widget[key] = value
            widget.pop(NameObject('/Parent'), None)
            widget.pop(NameObject('/Kids'), None)
            widget[NameObject('/T')] = TextStringObject(name)
            widget[NameObject('/P')] = page.indirect_reference
            # Preserve source help text/flags but do not carry executable actions.
            widget.pop(NameObject('/A'), None)
            widget.pop(NameObject('/AA'), None)
            fields.append(ref)
    acro = writer.root_object['/AcroForm']
    acro[NameObject('/Fields')] = fields
    acro[NameObject('/NeedAppearances')] = BooleanObject(False)
    font = DictionaryObject({NameObject('/Type'): NameObject('/Font'),
                             NameObject('/Subtype'): NameObject('/Type1'),
                             NameObject('/BaseFont'): NameObject('/Helvetica'),
                             NameObject('/Encoding'): NameObject('/WinAnsiEncoding')})
    acro[NameObject('/DR')] = DictionaryObject({NameObject('/Font'): DictionaryObject({
        NameObject('/Helv'): writer._add_object(font)})})
    # Blank editable fields have real, deterministic appearances as well as /V.
    blank = {name: '' for name, item in writer.get_fields().items()
             if item.get('/FT') == '/Tx' and not item.get('/V')}
    writer.update_page_form_field_values(None, blank, auto_regenerate=False)


@dataclass(frozen=True)
class FormLayout:
    """Locations needed by export and the separately owned re-upload reader."""
    rows: tuple[tuple[int, float, bool], ...]  # page, y translation, first source row vs repeating row
    following_page: int
    following_dy: float
    form_pages: int


def layout(row_count: int) -> FormLayout:
    """One initial row, no filler, followed by as many source-styled rows as needed."""
    count = max(1, row_count)
    rows = [(0, 0.0, True)]
    page, bottom = 1, PAGE_TOP
    for _ in range(1, count):
        first = bottom == PAGE_TOP
        height = PAGE_TOP - FIRST_BOTTOM if first else ROW_HEIGHT
        if bottom - height < PAGE_BOTTOM - 0.01:
            page += 1
            bottom, first = PAGE_TOP, True
            height = PAGE_TOP - FIRST_BOTTOM
        source_top = PAGE_TOP if first else REPEAT_BOTTOM + ROW_HEIGHT
        rows.append((page, bottom - source_top, first))
        bottom -= height
    following_height = FOLLOWING_TOP - FOLLOWING_BOTTOM
    if bottom - following_height < PAGE_BOTTOM - 0.01:
        page += 1
        bottom = PAGE_TOP
    return FormLayout(tuple(rows), page, bottom - FOLLOWING_TOP, page + 6)


def _cut(operations: list, rect: tuple[float, ...]) -> int:
    """Find a source's balanced top-level text block by its exact clipping rectangle."""
    depth = marked = 0
    for i, (values, op) in enumerate(operations):
        if depth == marked == 0 and op == b'q' and operations[i + 1][1] == b're':
            found = tuple(float(v) for v in operations[i + 1][0])
            if found == rect:
                return i
        depth += (op == b'q') - (op == b'Q')
        marked += (op in (b'BDC', b'BMC')) - (op == b'EMC')
    raise ValueError('The pinned challenge form content does not match its layout')


def _translated(operations: list, dy: float) -> list:
    return [([], b'q'), ([NumberObject(1), NumberObject(0), NumberObject(0), NumberObject(1),
                          NumberObject(0), FloatObject(dy)], b'cm'),
            *copy.deepcopy(operations), ([], b'Q')]


def prepare_form(form: bytes, fmap: dict, row_count: int) -> tuple[bytes, dict]:
    """Return a correctly editable dynamic blank and its complete runtime field map.

    Both export and review can reconstruct geometry with this public seam. It
    accepts only the already hash-checked packaged template, not upload metadata.
    """
    if fmap['version'] != VERSION:
        return form, copy.deepcopy(fmap)
    if hashlib.sha256(form).hexdigest() != fmap['sha256']:
        raise ValueError('The challenge template hash does not match its field map')
    count = max(1, row_count)
    geometry = layout(count)
    if count == 5:
        # The supplied layout already has exactly these five independent rows.
        runtime_map = copy.deepcopy(fmap)
        runtime_map['attribution_row_count'] = count
        return form, runtime_map
    writer = PdfWriter(clone_from=io.BytesIO(form))
    donor = writer.pages[1]
    operations = donor.get_contents().operations
    first = _cut(operations, (38.275, 692.72, 102.03, 61.0))
    repeat = _cut(operations, (38.275, 630.7, 102.03, 61.025))
    third = _cut(operations, (38.275, 568.67, 102.03, 61.025))
    following = _cut(operations, (38.275, 485.9, 534.22, 19.75))
    row_ops, repeat_ops = operations[first:repeat], operations[repeat:third]
    # Source black text operators inherit black; blue borders inherit its blue.
    prefix = [([FloatObject(.129), FloatObject(.369), FloatObject(.6)], b'rg')]
    following_ops = [*prefix, *operations[following:]]
    repeat_ops = [*prefix, *repeat_ops]
    donor_widgets = {str(a.get_object().get('/T')): a.get_object()
                     for a in donor.get('/Annots', []) if a.get_object().get('/Subtype') == '/Widget'}
    # Keep the first applicant page and all five subsequent source pages verbatim.
    # The second page is the sole mutable source page; additional pages are clones
    # of its resources/page boxes with only the required source fragments.
    original_pages = list(writer.pages)
    middle = [donor]
    for _ in range(geometry.following_page - 1):
        page = PageObject()
        page.update({k: v for k, v in donor.items() if k not in ('/Annots', '/Parent', '/Contents')})
        middle.append(writer.add_page(page))
    # Reorder using page references; no annotation /P can point to a removed page.
    final_pages = [original_pages[0], *middle, *original_pages[2:]]
    writer.root_object['/Pages'][NameObject('/Kids')] = ArrayObject([p.indirect_reference for p in final_pages])
    writer.root_object['/Pages'][NameObject('/Count')] = NumberObject(len(final_pages))
    writer.flattened_pages = final_pages
    for page in middle:
        page[NameObject('/Annots')] = ArrayObject()
    contents = {i: [] for i in range(1, geometry.following_page + 1)}
    for index, (page_no, dy, is_first) in enumerate(geometry.rows[1:], start=1):
        contents[page_no].extend(_translated(row_ops if is_first else repeat_ops, dy))
        old_slot = row_fields(1 if is_first else 2)
        for key, name in row_fields(index).items():
            _add_widget(writer, final_pages[page_no], donor_widgets[old_slot[key]], name, dy)
    contents[geometry.following_page].extend(_translated(following_ops, geometry.following_dy))
    for name, widget in donor_widgets.items():
        if name not in {value for i in range(1, 5) for value in row_fields(i).values()}:
            _add_widget(writer, final_pages[geometry.following_page], widget, name, geometry.following_dy)
    for page_no, ops in contents.items():
        if page_no != geometry.following_page:
            # A continuation ending before Section D still needs the source's
            # outer bottom border; never leave open-ended column rules.
            last = next(row for row in reversed(geometry.rows) if row[0] == page_no)
            bottom = (FIRST_BOTTOM if last[2] else REPEAT_BOTTOM) + last[1]
            close = []
            original = writer.pages[0].get_contents().operations
            for i, (values, op) in enumerate(original):
                if op == b're' and float(values[1]) == 69.775 and float(values[3]) == 2.25:
                    close.extend(original[i:i + 2])
            ops.extend(_translated([*prefix, *close], bottom - 72.025))
        stream = ContentStream(None, writer)
        stream.operations = ops
        final_pages[page_no].replace_contents(stream)
    writer.root_object['/AcroForm'][NameObject('/Fields')] = ArrayObject([
        a for page in final_pages for a in page.get('/Annots', [])
        if a.get_object().get('/Subtype') == '/Widget'])
    writer.update_page_form_field_values(None, {
        name: str(item.get('/V') or '') for name, item in writer.get_fields().items()
        if item.get('/FT') == '/Tx' and not item.get('/V')}, auto_regenerate=False)
    runtime_map = copy.deepcopy(fmap)
    runtime_map['section_c_rows'] = [row_fields(i) for i in range(count)]
    runtime_map['field_count'] = len(writer.get_fields())
    runtime_map['form_pages'] = geometry.form_pages
    runtime_map['attribution_row_count'] = count
    writer.add_metadata({'/BatatisFormVersion': VERSION, '/BatatisAttributionRows': str(count),
                         '/BatatisFormPages': str(geometry.form_pages)})
    buf = io.BytesIO()
    writer.write(buf)
    return buf.getvalue(), runtime_map


def _add_widget(writer, page, source, name: str, dy: float) -> None:
    widget = DictionaryObject({key: value for key, value in source.items()
                               if key not in ('/P', '/Parent', '/Kids')})
    if widget.get('/FT') == '/Tx' and not widget.get('/V'):
        widget.pop(NameObject('/AP'), None)  # every new row needs its own appearance stream
    widget[NameObject('/T')] = TextStringObject(name)
    widget[NameObject('/P')] = page.indirect_reference
    x0, y0, x1, y1 = source['/Rect']
    widget[NameObject('/Rect')] = RectangleObject((float(x0), float(y0) + dy, float(x1), float(y1) + dy))
    page['/Annots'].append(writer._add_object(widget))
