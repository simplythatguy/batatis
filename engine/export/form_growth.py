"""The supplied form's own boxes, grown or continued so every cell holds its whole text at normal size.

The supplied challenge form is drawn row by row: each row is one or more clipped text groups and one group of
border rectangles. A `Layout` says how many lines each growable cell needs (10 pt; 9 pt in the attribution
table). This module turns the hash-checked template into a blank with exactly that room, using only the
source's own drawing:

- a row moves as a unit, or grows at a cut just above its bottom border: every rectangle crossing the cut gets
  taller and everything below it moves down, so printed labels stay where they are;
- a row or the Section D box too tall for the rest of a page continues on the next page in the same style,
  with repeated source labels or a continuation heading, and continuation widgets `name~2`, `name~3`...;
- headings stay with the row after them, Section D starts on a continuation page as in the source, and each
  page that does not end with the signatures block is closed with the source's own bottom rule.

Page 1 is rebuilt only when one of its own cells grows; the officer, appeal and printed appendix pages are
never touched. The default layout never comes here: `challenge_form.prepare_form` keeps today's blank byte for
byte, so earlier exports still re-verify. The `/BatatisLayout` hint the export writes is parsed strictly and
bounded; the reader rebuilds the blank from it and still verifies every glyph and rectangle on the page.
"""
from __future__ import annotations

import copy
import io
import math
import re
from dataclasses import dataclass
from functools import lru_cache

from pypdf import PageObject, PdfReader, PdfWriter
from pypdf.generic import (ArrayObject, ContentStream, DictionaryObject, FloatObject, NameObject, NumberObject,
                           RectangleObject, TextStringObject)

from .challenge_form import (LEGAL_RECT, LEGAL_ROW, PAGE_BOTTOM, PAGE_TOP, VERSION, _cut, _translated,
                             row_fields)
from .text import LINE, V_PAD

TABLE_SIZE = 9.0            # attribution table text
CELL_SIZE = 10.0            # every other applicant cell
ROW_LINES = 5               # an attribution row's own room at 9 pt
DOC_LINES = 6               # the Section D box's own room at 10 pt
MIN_SPLIT = 3               # fewer lines than this at a page's foot: the row starts on the next page instead

# Growable cells on page 1, in the order the layout hint numbers them, with their own lines at 10 pt.
CELLS = ('Owner', 'Owner Rep', 'Mailing Address', 'Date of Reqeuest', 'Permit', LEGAL_ROW, 'Municipal Address',
         'Lot', 'Block', 'Plan', 'QTR', 'SEC', 'TWP', 'RGE', 'MER', 'Code or Standard')
CAPACITY = {**dict.fromkeys(CELLS, 1), 'Mailing Address': 2, 'Municipal Address': 2}
ATS = ('Lot', 'Block', 'Plan', 'QTR', 'SEC', 'TWP', 'RGE', 'MER')
CELL_MAX = dict.fromkeys(CELLS, 2000)
ROW_MAX = 2000              # lines in one attribution row
DOC_MAX = 5000              # lines in the Section D listing
TOTAL_MAX = 60000           # all lines together: bounds the work of rebuilding an uploaded layout

PREFIX = [([FloatObject(.129), FloatObject(.369), FloatObject(.6)], b'rg')]   # the source's blue rules


def height_for(lines: int, size: float) -> float:
    """A text box's height for `lines` at `size`, as `text.fit` and pypdf lay them out."""
    return lines * LINE * size + V_PAD


def lines_in(height: float, size: float) -> int:
    """Whole lines a box holds; the small tolerance absorbs coordinates rounded when the PDF is written."""
    return max(0, int((height - V_PAD) / (LINE * size) + 1e-3))


@dataclass(frozen=True)
class Layout:
    """Lines each growable cell needs at its normal size; never less than the supplied form's own room."""
    rows: tuple[int, ...]                     # one entry per attribution row
    cells: tuple[tuple[str, int], ...] = ()   # page-1 cells needing more than their own lines, in CELLS order
    docs: int = DOC_LINES                     # the Section D listing

    @classmethod
    def of(cls, rows, cells: dict[str, int] | None = None, docs: int = DOC_LINES) -> Layout:
        rows = tuple(max(ROW_LINES, int(n)) for n in rows) or (ROW_LINES,)
        grown = tuple((name, int(cells[name])) for name in CELLS
                      if cells and int(cells.get(name, 0)) > CAPACITY[name])
        return cls(rows, grown, max(DOC_LINES, int(docs)))

    @property
    def default(self) -> bool:
        return not self.cells and self.docs == DOC_LINES and all(n == ROW_LINES for n in self.rows)

    def lines(self, cell: str) -> int:
        return dict(self.cells).get(cell, CAPACITY[cell])

    def pages(self) -> int:
        """Fewest form pages this layout can make: each line of the table and the Section D listing takes its own
        height above the five printed officer pages, and no page offers more than its frame. Checked against an
        upload's page count before rebuilding, so a small file cannot ask for a huge blank."""
        extra = sum(n - CAPACITY[name] for name, n in self.cells if name not in ATS)
        extra += sum(max(self.lines(a), self.lines(b)) - 1 for a, b in zip(ATS[::2], ATS[1::2]))
        text = sum(self.rows) * LINE * TABLE_SIZE + (self.docs + extra) * LINE * CELL_SIZE
        return 5 + math.ceil(text / (PAGE_TOP - PAGE_BOTTOM))

    def bounded(self) -> bool:
        return (1 <= len(self.rows) <= 1024 and all(ROW_LINES <= n <= ROW_MAX for n in self.rows)
                and all(name in CELL_MAX and CAPACITY[name] < n <= CELL_MAX[name] for name, n in self.cells)
                and DOC_LINES <= self.docs <= DOC_MAX
                and sum(self.rows) + self.docs + sum(n for _, n in self.cells) <= TOTAL_MAX)

    def hint(self) -> str:
        """The canonical `/BatatisLayout` value: `r5,13;c2:4,5:3;d9` (rows; grown cells by number; docs)."""
        text = 'r' + ','.join(map(str, self.rows))
        if self.cells:
            text += ';c' + ','.join(f'{CELLS.index(name)}:{n}' for name, n in self.cells)
        if self.docs != DOC_LINES:
            text += f';d{self.docs}'
        return text

    @classmethod
    def parse(cls, text: str, rows: int) -> Layout | None:
        """A hint from an uploaded file: exact canonical form within bounds, or None (the form stays unverified).
        The default layout never carries a hint."""
        match = re.fullmatch(r'r(\d{1,4}(?:,\d{1,4}){0,1023})(?:;c(\d{1,2}:\d{1,4}(?:,\d{1,2}:\d{1,4}){0,15}))?'
                             r'(?:;d(\d{1,5}))?', text or '')
        if not match:
            return None
        counts = [int(n) for n in match.group(1).split(',')]
        cells = {}
        for item in (match.group(2) or '').split(',') if match.group(2) else []:
            index, n = (int(v) for v in item.split(':'))
            if index >= len(CELLS) or CELLS[index] in cells:
                return None
            cells[CELLS[index]] = n
        docs = int(match.group(3)) if match.group(3) else DOC_LINES
        if len(counts) != rows:
            return None
        layout = cls.of(counts, cells, docs)
        return layout if layout.bounded() and layout.hint() == text and not layout.default else None


@lru_cache(maxsize=4)
def text_widths(form: bytes) -> dict[str, float]:
    """Usable text width of each growable box: page-1 cells, the four attribution columns (narrowest of the
    source's row variants, so a line measured once fits every segment) and the Section D box."""
    from .text import H_PAD
    reader = PdfReader(io.BytesIO(form))
    rects = {}
    for page in reader.pages[:2]:
        for ref in page.get('/Annots', []):
            widget = ref.get_object()
            if widget.get('/Subtype') == '/Widget':
                rects[str(widget['/T'])] = tuple(float(v) for v in widget['/Rect'])
    rects[LEGAL_ROW] = LEGAL_RECT
    width = {name: rects[name][2] - rects[name][0] - H_PAD for name in CELLS}
    for key in ('article', 'objective', 'function', 'intent'):
        width[key] = min(rects[row_fields(i)[key]][2] - rects[row_fields(i)[key]][0] for i in range(5)) - H_PAD
    width['docs'] = rects['Supporting Doc'][2] - rects['Supporting Doc'][0] - H_PAD
    return width


# ---------------------------------------------------------------- the source's own drawing, as groups

def _groups(operations: list) -> list[list]:
    """Top-level balanced groups (q..Q, BDC/BMC..EMC, BT..ET) in drawing order."""
    out, start, depth = [], 0, 0
    for i, (_values, op) in enumerate(operations):
        depth += (op in (b'q', b'BDC', b'BMC', b'BT')) - (op in (b'Q', b'EMC', b'ET'))
        if depth == 0:
            out.append(operations[start:i + 1])
            start = i + 1
    if start != len(operations):
        raise ValueError('The pinned challenge form content does not match its layout')
    return out


def _extent(group: list) -> tuple[float, float] | None:
    ys = [y for values, op in group if op == b're'
          for y in (float(values[1]), float(values[1]) + float(values[3]))]
    return (min(ys), max(ys)) if ys else None


def _rect_moved(values, cut: float, extra: float):
    x, y, w, h = (float(v) for v in values)
    if y + h <= cut:
        y -= extra
    elif y < cut:
        y, h = y - extra, h + extra
    else:
        return values
    return [FloatObject(x), FloatObject(y), FloatObject(w), FloatObject(h)]


def _stretched(groups: list[list], cut: float, extra: float) -> list[list]:
    """Grow the drawing by `extra` points at y = `cut`; a group wholly below moves as a unit, one crossing the
    cut keeps its text and grows its rectangles, one above stays."""
    if not extra:
        return groups
    out = []
    for group in groups:
        extent = _extent(group)
        if extent is None or extent[0] >= cut:
            out.append(group)
        elif extent[1] <= cut:
            out.append(_translated(group, -extra))
        else:
            out.append([(_rect_moved(values, cut, extra), op) if op == b're' else (values, op)
                        for values, op in group])
    return out


def _rect_after(rect, cuts, name: str):
    """A widget's rectangle after the stretches (lowest cut first): its own cell grows down, lower ones move."""
    x0, y0, x1, y1 = rect
    for (cells, cut), extra in cuts:
        if name in cells:
            y0 -= extra
        elif y1 <= cut:
            y0, y1 = y0 - extra, y1 - extra
        elif y0 < cut:
            y0 -= extra
    return x0, y0, x1, y1


def _fonts_renamed(groups: list[list], names: dict[str, str]) -> list[list]:
    return [[([NameObject(names[str(values[0])]), *values[1:]], op)
             if op == b'Tf' and str(values[0]) in names else (values, op) for values, op in group]
            for group in groups]


@dataclass(frozen=True)
class _Row:
    """A page-1 row: its source top and bottom (top border included) and its growing cells with their cuts."""
    name: str
    top: float
    bottom: float
    grows: tuple[tuple[tuple[str, ...], float], ...] = ()     # lowest cut first
    heading: bool = False


PAGE1_ROWS = (
    _Row('owner', 498.4, 479.9, ((('Owner',), 480.4),)),
    _Row('rep', 479.9, 461.4, ((('Owner Rep',), 461.9),)),
    _Row('mailing', 461.4, 428.38, ((('Mailing Address',), 428.88),)),
    _Row('date', 428.38, 409.88, ((('Date of Reqeuest',), 410.38),)),
    _Row('section_b', 409.88, 389.13, heading=True),
    _Row('scope', 389.13, 370.63),
    _Row('permit', 370.63, 352.1, ((('Permit',), 352.6),)),
    _Row('legal', 352.1, 333.6, (((LEGAL_ROW,), 334.1),)),
    _Row('municipal', 333.6, 300.6, ((('Municipal Address',), 301.1),)),
    _Row('ats', 300.6, 226.58, ((('RGE', 'MER'), 227.08), (('SEC', 'TWP'), 245.58), (('Plan', 'QTR'), 264.08),
                                (('Lot', 'Block'), 282.6))),
    _Row('section_c', 226.58, 191.8, heading=True),
    _Row('code', 191.8, 173.3, ((('Code or Standard',), 173.8),)),
    _Row('attributions', 173.3, 152.55, heading=True),
    _Row('columns', 152.55, 134.05, heading=True),
)
HEAD_BOTTOM = 498.4         # title, address block, Part 1 and the Section A heading never move
ROW0 = (69.775, 134.05)     # page 1's own first attribution row and the frame's bottom rule

# Attribution rows on a continuation page: the page-top row (thick top rule) and the repeating row.
FIRST = ('first', 755.995, 692.72, 693.22)        # name, top, bottom, cut
REPEAT = ('repeat', 692.72, 630.7, 631.2)
INTENT_HEIGHT = 58.995      # the source's intent widget in every row
ROW_DROP = 0.6              # the article, objective and function widgets start up to 0.53 pt below the intent's
SECTION_D = (506.65, 485.9)
BOX = (485.9, 383.38, 383.88)                      # top, bottom, cut
BOX_WIDGET = 74.356         # the source's Supporting Doc widget, under its printed label
SIGNATURES = (383.38, 81.275)


@dataclass
class _Piece:
    page: int
    ops: list
    bottom: float
    closes: bool = False    # draws the frame's own bottom (the signatures block)


@dataclass
class _Widget:
    page: int
    source: DictionaryObject
    name: str
    rect: tuple


class _Flow:
    """Place source pieces top to bottom; a new page starts at the continuation pages' top."""

    def __init__(self, page: int, y: float):
        self.page, self.y = page, y
        self.pieces: list[_Piece] = []
        self.widgets: list[_Widget] = []
        self.continuations: dict[str, list[str]] = {}
        self.printed: dict[str, dict] = {}
        self.page1_rows_on: set[int] = set()     # continuation pages carrying page-1 rows (page 1's fonts)
        self.labels: dict[int, str] = {}

    def room(self) -> float:
        return self.y - PAGE_BOTTOM

    def at_top(self) -> bool:
        return self.page > 0 and self.y == PAGE_TOP

    def new_page(self) -> None:
        self.page, self.y = self.page + 1, PAGE_TOP

    def fits(self, height: float) -> bool:
        return self.y - height >= PAGE_BOTTOM - 0.01

    def place(self, groups: list[list], top: float, height: float, closes: bool = False) -> float:
        dy = self.y - top
        ops = [op for group in groups for op in group]
        self.pieces.append(_Piece(self.page, _translated([*PREFIX, *ops], dy), self.y - height, closes))
        self.y -= height
        return dy


def grown_blank(form: bytes, fmap: dict, layout: Layout) -> tuple[bytes, dict]:
    """The dynamic blank for a non-default layout and its runtime field map (see the module docstring)."""
    writer = PdfWriter(clone_from=io.BytesIO(form))
    page1, donor = writer.pages[0], writer.pages[1]
    page1_ops, donor_ops = page1.get_contents().operations, donor.get_contents().operations
    marks = [_cut(donor_ops, rect) for rect in ((38.275, 692.72, 102.03, 61.0), (38.275, 630.7, 102.03, 61.025),
                                                (38.275, 568.67, 102.03, 61.025), (38.275, 485.9, 534.22, 19.75),
                                                (38.275, 383.38, 534.22, 101.52),
                                                (38.275, 362.63, 534.22, 19.75))]
    first, repeat, third, heading, box, signatures = marks
    rows = {'first': _groups(donor_ops[first:repeat]), 'repeat': _groups(donor_ops[repeat:third])}
    heading_groups, box_groups = _groups(donor_ops[heading:box]), _groups(donor_ops[box:signatures])
    signature_groups = _groups(donor_ops[signatures:])
    frame_groups = [group for group in box_groups if all(op not in (b'BT', b'Tf') for _, op in group)]
    donor_widgets = _widgets(donor)
    reflow = bool(layout.cells)
    flow = _Flow(0, HEAD_BOTTOM) if reflow else _Flow(1, PAGE_TOP)
    page1_fonts = {}
    if reflow:
        head, bands = _page1_bands(page1_ops)
        page1_widgets = _widgets(page1)
        fonts = page1['/Resources']['/Font']
        page1_fonts = {str(name): '/P1' + str(name)[1:] for name in fonts}
        _place_page1(flow, layout, bands, page1_widgets, page1_fonts)
        for index, lines in enumerate(layout.rows):
            _place_row(flow, rows, donor_widgets, index, lines, 1)
    else:
        if layout.rows[0] > ROW_LINES:       # page 1 keeps its own first row; the rest continues overleaf
            _place_row(flow, rows, donor_widgets, 0, layout.rows[0] - ROW_LINES, 2)
        for index, lines in enumerate(layout.rows[1:], start=1):
            _place_row(flow, rows, donor_widgets, index, lines, 1)
        flow.printed[LEGAL_ROW] = {'page': 0, 'rect': list(LEGAL_RECT)}
    _place_section_d(flow, layout.docs, heading_groups, box_groups, frame_groups, signature_groups, donor_widgets)

    pages = max(piece.page for piece in flow.pieces)
    original = list(writer.pages)
    middle = [donor]
    for _ in range(pages - 1):
        page = PageObject()
        page.update({key: value for key, value in donor.items() if key not in ('/Annots', '/Parent', '/Contents')})
        middle.append(writer.add_page(page))
    final = [page1, *middle, *original[2:]]
    writer.root_object['/Pages'][NameObject('/Kids')] = ArrayObject([p.indirect_reference for p in final])
    writer.root_object['/Pages'][NameObject('/Count')] = NumberObject(len(final))
    writer.flattened_pages = final
    for page in middle:
        page[NameObject('/Annots')] = ArrayObject()
    if reflow:
        # Continuation pages carrying page-1 rows get page 1's fonts under their own names.
        for number in sorted(flow.page1_rows_on):
            resources = DictionaryObject({key: value for key, value in donor['/Resources'].items()})
            fonts = DictionaryObject({key: value for key, value in donor['/Resources']['/Font'].items()})
            for name, renamed in page1_fonts.items():
                fonts[NameObject(renamed)] = page1['/Resources']['/Font'].raw_get(NameObject(name))
            resources[NameObject('/Font')] = fonts
            final[number][NameObject('/Resources')] = resources
        annots = [ref for ref in page1.get('/Annots', []) if ref.get_object().get('/Subtype') != '/Widget'
                  or str(ref.get_object()['/T']) in _HEAD_WIDGETS]
        page1[NameObject('/Annots')] = ArrayObject(annots)

    close = _close_ops(page1_ops)
    by_page: dict[int, list] = {number: [] for number in range(1 if not reflow else 0, pages + 1)}
    if reflow:
        by_page[0] = [op for group in head for op in group]
    for piece in flow.pieces:
        by_page[piece.page].extend(piece.ops)
    for number in by_page:
        on_page = [piece for piece in flow.pieces if piece.page == number]
        last = min(on_page, key=lambda piece: piece.bottom)
        if not last.closes:
            by_page[number].extend(_translated([*PREFIX, *close], last.bottom - 72.025))
        stream = ContentStream(None, writer)
        stream.operations = by_page[number]
        final[number].replace_contents(stream)
    _label_pages(final, flow.labels)
    for widget in flow.widgets:
        _add(writer, final[widget.page], widget.source, widget.name, widget.rect)
    writer.root_object['/AcroForm'][NameObject('/Fields')] = ArrayObject([
        a for page in final for a in page.get('/Annots', []) if a.get_object().get('/Subtype') == '/Widget'])
    writer.update_page_form_field_values(None, {
        name: str(item.get('/V') or '') for name, item in writer.get_fields().items()
        if item.get('/FT') == '/Tx' and not item.get('/V')}, auto_regenerate=False)
    count = len(layout.rows)
    runtime = copy.deepcopy(fmap)
    runtime['section_c_rows'] = [row_fields(i) for i in range(count)]
    runtime['field_count'] = len(writer.get_fields())
    runtime['form_pages'] = len(final)
    runtime['attribution_row_count'] = count
    runtime['continuations'] = flow.continuations
    runtime['printed'] = flow.printed
    runtime['layout'] = layout.hint()
    writer.add_metadata({'/BatatisFormVersion': VERSION, '/BatatisAttributionRows': str(count),
                         '/BatatisFormPages': str(len(final)), '/BatatisLayout': layout.hint()})
    buf = io.BytesIO()
    writer.write(buf)
    return buf.getvalue(), runtime


_HEAD_WIDGETS = ('Logo', 'Logo Popup')


def _widgets(page) -> dict[str, DictionaryObject]:
    return {str(ref.get_object()['/T']): ref.get_object() for ref in page.get('/Annots', [])
            if ref.get_object().get('/Subtype') == '/Widget'}


def _add(writer, page, source, name: str, rect) -> None:
    widget = DictionaryObject({key: value for key, value in source.items() if key not in ('/P', '/Parent', '/Kids')})
    if widget.get('/FT') == '/Tx' and not widget.get('/V'):
        widget.pop(NameObject('/AP'), None)  # every placed widget needs its own appearance stream
    widget[NameObject('/T')] = TextStringObject(name)
    widget[NameObject('/P')] = page.indirect_reference
    widget[NameObject('/Rect')] = RectangleObject(rect)
    page['/Annots'].append(writer._add_object(widget))


def _close_ops(page1_ops: list) -> list:
    close = []
    for i, (values, op) in enumerate(page1_ops):
        if op == b're' and float(values[1]) == 69.775 and float(values[3]) == 2.25:
            close.extend(page1_ops[i:i + 2])
    return close


def _page1_bands(operations: list) -> tuple[list[list], dict[str, list[list]]]:
    """Page 1's groups: the fixed head (and page-wide artifacts), each row of PAGE1_ROWS, and its own first
    attribution row with the frame's bottom rule (dropped when page 1 is rebuilt: rows come from the donor)."""
    head, bands = [], {row.name: [] for row in PAGE1_ROWS}
    for group in _groups(operations):
        extent = _extent(group)
        row = next((row for row in PAGE1_ROWS if extent and row.bottom - 0.01 <= extent[0]
                    and extent[1] <= row.top + 0.01), None)
        if row is not None:
            bands[row.name].append(group)
        elif extent and ROW0[0] - 0.01 <= extent[0] and extent[1] <= ROW0[1] + 0.01:
            continue
        else:
            head.append(group)
    if not all(bands.values()):
        raise ValueError('The pinned challenge form content does not match its layout')
    return head, bands


def _cell_extra(counts: dict[str, int], cells: tuple[str, ...], widgets: dict) -> float:
    """How much a row grows at one cut: the most any of its cells needs beyond its own box."""
    extra = 0.0
    for name in cells:
        rect = LEGAL_RECT if name == LEGAL_ROW else tuple(float(v) for v in widgets[name]['/Rect'])
        extra = max(extra, height_for(counts.get(name, CAPACITY[name]), CELL_SIZE) - (rect[3] - rect[1]))
    return extra


def _place_page1(flow: _Flow, layout: Layout, bands: dict, widgets: dict, fonts: dict) -> None:
    def cuts_for(row, counts):
        return [((cells, cut), _cell_extra(counts, cells, widgets)) for cells, cut in row.grows]

    def height(row, counts):
        return row.top - row.bottom + sum(extra for _, extra in cuts_for(row, counts))

    minimum = {row.name: height(row, {name: min(layout.lines(name), MIN_SPLIT)
                                    for cells, _ in row.grows for name in cells}) for row in PAGE1_ROWS}
    keep, after = {}, REPEAT[1] - REPEAT[2]          # the columns heading keeps with a first row's own height
    for row in reversed(PAGE1_ROWS):
        keep[row.name] = minimum[row.name] + (after if row.heading else 0.0)
        after = keep[row.name]
    for row in PAGE1_ROWS:
        if not flow.fits(keep[row.name]) and not flow.at_top():
            flow.new_page()
        remaining = {name: layout.lines(name) for cells, _ in row.grows for name in cells}
        segment = 1
        while True:
            take = dict(remaining)
            if not flow.fits(height(row, take)):
                low, high = 0, max(remaining.values()) + 1
                while high - low > 1:
                    mid = (low + high) // 2
                    if flow.fits(height(row, {name: min(n, mid) for name, n in remaining.items()})):
                        low = mid
                    else:
                        high = mid
                if low < MIN_SPLIT:
                    flow.new_page()
                    continue
                take = {name: min(n, low) for name, n in remaining.items()}
            cuts = cuts_for(row, take)
            groups = bands[row.name]
            for (cells, cut), extra in cuts:
                groups = _stretched(groups, cut, extra)
            if flow.page > 0:
                groups = _fonts_renamed(groups, fonts)
                flow.page1_rows_on.add(flow.page)
                flow.labels.setdefault(flow.page, 'Part 1 (continued)')
            page = flow.page
            dy = flow.place(groups, row.top, height(row, take))

            def label(name):
                if segment == 1:
                    return name
                continued = f'{name}~{segment}'
                flow.continuations.setdefault(name, []).append(continued)
                return continued

            for name, widget in widgets.items():
                x0, y0, x1, y1 = (float(v) for v in widget['/Rect'])
                if name in _HEAD_WIDGETS or not row.bottom < y1 <= row.top + 0.01:
                    continue
                rect = _rect_after((x0, y0, x1, y1), cuts, name)
                flow.widgets.append(_Widget(page, widget, label(name), (rect[0], rect[1] + dy, rect[2], rect[3] + dy)))
            if row.name == 'legal':
                x0, y0, x1, y1 = _rect_after(LEGAL_RECT, cuts, LEGAL_ROW)
                flow.printed[label(LEGAL_ROW)] = {'page': page, 'rect': [x0, y0 + dy, x1, y1 + dy]}
            remaining = {name: n - take[name] for name, n in remaining.items()}
            if not any(remaining.values()):
                break
            segment += 1
            flow.new_page()


def _place_row(flow: _Flow, templates: dict, widgets: dict, index: int, lines: int, segment: int) -> None:
    """One attribution row in the donor's row style, continued on the next pages while it needs more room."""
    remaining = lines
    while remaining > 0:
        name, top, bottom, cut = FIRST if flow.at_top() else REPEAT
        base = top - bottom
        need = base + _row_extra(remaining)
        if flow.fits(need):
            take = remaining
        else:
            take = lines_in(INTENT_HEIGHT + flow.room() - base - ROW_DROP, TABLE_SIZE)
            if flow.room() < base or take < MIN_SPLIT:
                flow.new_page()
                continue
            need = base + _row_extra(take)
        extra = need - base
        page = flow.page
        if page > 0 and flow.at_top():
            flow.labels.setdefault(page, f'Section C - row {index + 1}' + (' (continued)' if segment > 1 else ''))
        dy = flow.place(_stretched(templates[name], cut, extra), top, need)
        slot = row_fields(1 if name == 'first' else 2)
        for key, canonical in row_fields(index).items():
            source = widgets[slot[key]]
            x0, y0, x1, y1 = (float(v) for v in source['/Rect'])
            if key == 'intent':
                y0 -= extra
            label = canonical if segment == 1 else f'{canonical}~{segment}'
            if segment > 1:
                flow.continuations.setdefault(canonical, []).append(label)
            flow.widgets.append(_Widget(page, source, label, (x0, y0 + dy, x1, y1 + dy)))
        remaining -= take
        segment += 1
        if remaining:
            flow.new_page()


def _row_extra(lines: int) -> float:
    """How much an attribution row grows so each of its four columns holds `lines` lines at 9 pt."""
    return max(0.0, height_for(lines, TABLE_SIZE) + ROW_DROP - INTENT_HEIGHT)


def _place_section_d(flow: _Flow, docs: int, heading: list, box: list, frame: list, signatures: list,
                     widgets: dict) -> None:
    """Section D starts on a continuation page; its box grows, then continues as the box's bare frame."""
    if flow.page == 0:
        flow.new_page()
    heading_h, box_h = SECTION_D[0] - SECTION_D[1], BOX[0] - BOX[1]
    if not flow.fits(heading_h + box_h) and not flow.at_top():
        flow.new_page()
    flow.labels.setdefault(flow.page, 'Part 1 (continued)')
    dy = flow.place(heading, SECTION_D[0], heading_h)
    flow.widgets.append(_Widget(flow.page, widgets['Supp Doc Button'], 'Supp Doc Button',
                                _moved(widgets['Supp Doc Button'], dy)))
    need = box_h + max(0.0, height_for(docs, CELL_SIZE) - BOX_WIDGET)
    take = docs if flow.fits(need) else lines_in(BOX_WIDGET + flow.room() - box_h, CELL_SIZE)
    extra = max(0.0, height_for(take, CELL_SIZE) - BOX_WIDGET)
    page = flow.page
    dy = flow.place(_stretched(box, BOX[2], extra), BOX[0], box_h + extra)
    for name in ('Supporting Doc', 'Supp Doc Popup'):
        x0, y0, x1, y1 = (float(v) for v in widgets[name]['/Rect'])
        flow.widgets.append(_Widget(page, widgets[name], name, (x0, y0 - extra + dy, x1, y1 + dy)))
    remaining, segment = docs - take, 2
    x0, _, x1, _ = (float(v) for v in widgets['Supporting Doc']['/Rect'])
    while remaining:
        flow.new_page()
        flow.labels[flow.page] = 'Section D - supporting documents (continued)'
        take = min(remaining, lines_in(flow.room() - 3.0, CELL_SIZE))
        height = height_for(take, CELL_SIZE) + 3.0          # border, 1 pt inset above and below the text box
        page, top = flow.page, flow.y
        flow.place(_stretched(frame, BOX[2], height - box_h), BOX[0], height)
        label = f'Supporting Doc~{segment}'
        flow.continuations.setdefault('Supporting Doc', []).append(label)
        flow.widgets.append(_Widget(page, widgets['Supporting Doc'], label, (x0, top - height + 1.0, x1, top - 2.0)))
        remaining -= take
        segment += 1
    sign_h = SIGNATURES[0] - SIGNATURES[1]
    if not flow.fits(sign_h):
        flow.new_page()
        flow.labels[flow.page] = 'Part 1 - declarations and signatures (continued)'
    dy = flow.place(signatures, SIGNATURES[0], sign_h, closes=True)
    for name in ('Check Box14', 'Date1', 'Date2', 'Signature1', 'Signature2'):
        flow.widgets.append(_Widget(flow.page, widgets[name], name, _moved(widgets[name], dy)))


def _moved(widget, dy: float) -> tuple:
    x0, y0, x1, y1 = (float(v) for v in widget['/Rect'])
    return x0, y0 + dy, x1, y1 + dy


def _label_pages(pages, labels: dict[int, str]) -> None:
    """Label generated continuation pages above the source's blue frame, without covering its own drawing."""
    from reportlab.pdfgen.canvas import Canvas
    for number, label in labels.items():
        buf = io.BytesIO()
        canvas = Canvas(buf, pagesize=(612, 792), invariant=1)
        canvas.setFillColorRGB(.129, .369, .6)
        canvas.setFont('Helvetica', 9)
        canvas.drawString(38.275, 765, label)
        canvas.save()
        pages[number].merge_page(PdfReader(buf).pages[0])
