"""Export a case to the Safety Codes Council variance form (Part 1, applicant fields only).

Steps: check the blank form's SHA-256 against the version-keyed field map, measure applicant values at normal
size and grow or continue their supplied-form cells (legacy forms use appendix references), fill with pypdf, flatten
(appearance streams merged into the page, every widget removed, so the help pop-ups and buttons disappear and
every viewer shows the same thing), and append the generated appendix when it has real content. Draft
status and the draft's open items stay in metadata and the result; the website shows them, and nothing
adds visible markings, a to-do list or unanswered placeholders to the supplied form or the appendix.

Export refuses while a fact is unconfirmed, a blocking gap is open or a required field is empty, unless
draft=True. Only confirmed facts are ever written to the form, draft or not.
"""
from __future__ import annotations

import hashlib
import io
import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import NamedTuple

from pypdf import PdfReader, PdfWriter
from pypdf.generic import ArrayObject, DictionaryObject, NameObject, NumberObject, RectangleObject, TextStringObject

from ..models import INTENT_LABEL, Case, SectionCRow
from ..not_applicable import LABEL as NA_LABEL, ROWS as NA_ROWS, NotApplicable, not_applicable
from ..codes import Codes
from ..completeness import check_completeness
from ..professional import NOT_ENGAGED_ITEM
from ..process_fields import PROCESS_ALIASES
from ..section_c import section_c_rows
from ..section_d import supporting_documents, text_evidence
from .edition import code_or_standard_value
from .challenge_form import LEGAL_ROW, ROW_KEYS, prepare_form, row_fields
from .form_growth import CAPACITY, CELL_SIZE, CELLS, DOC_LINES, TABLE_SIZE, Layout, lines_in, text_widths
from .text import fit, lines_at, pdf_safe

DEFAULT_FORM = Path(__file__).resolve().parents[2] / 'reference' / 'guides' / 'SCC-Variance-Form.pdf'
BUNDLE_FORM = Path(__file__).resolve().parents[2] / 'codedb' / 'build' / 'SCC-Variance-Form.pdf'
FORM_NOT_FOUND_DETAIL = 'SCC variance form not found'
EXPORT_FAILED_DETAIL = 'The SCC variance form could not be exported.'
MAP_DIR = Path(__file__).parent / 'field_maps'
CURRENT_MAP = 'challenge_2026-09-15'
MULTILINE = 1 << 12
SECTION_C_SIZES = (9.0, 7.0)          # one size band for the attribution table so the rows read evenly


class ExportError(Exception):
    pass


class FormNotFound(ExportError):
    pass


class FormMismatch(ExportError):
    pass


class ExportBlocked(ExportError):
    def __init__(self, reasons: list[str]):
        self.reasons = reasons
        super().__init__('export blocked: ' + '; '.join(reasons))


@dataclass
class Placement:
    """One applicant field as drawn: `lines` are what the form shows; `value` is the full value, which the
    appendix carries under `ref` when the form shows only a reference. A field the supplied form continues in
    more boxes has one placement per box, in reading order, each with the field's full value."""
    field: str
    page: int
    rect: tuple[float, float, float, float]
    lines: list[str]
    size: float
    value: str
    ref: str | None = None


@dataclass
class ExportResult:
    pdf: bytes
    field_map: str
    form_pages: int
    appendix_pages: int
    draft: bool
    placements: list[Placement] = field(default_factory=list)
    blank_fields: list[str] = field(default_factory=list)
    open_items: list[str] = field(default_factory=list)
    not_applicable: list[str] = field(default_factory=list)   # form fields showing N/A from an applicant fact
    form_text: list[str] = field(default_factory=list)        # 'field: full value' for every filled form field
    appendix_text: list[str] = field(default_factory=list)    # appendix paragraphs and '| a | b |' table rows

    @property
    def text(self) -> list[str]:
        """The exported narrative the citation validator checks: form values, then the appendix."""
        return [*self.form_text, *self.appendix_text]


def form_path(version: str = CURRENT_MAP) -> Path:
    """The tracked supplied asset, or the legacy-only override/guide/build copy."""
    override = (os.environ.get('BATATIS_SCC_FORM') or '').strip()
    fmap = load_field_map(version)
    if fmap.get('asset'):
        return Path(__file__).parent / fmap['asset']
    if override:
        return Path(override)
    if DEFAULT_FORM.is_file():
        return DEFAULT_FORM
    return BUNDLE_FORM


def load_field_map(version: str = CURRENT_MAP) -> dict:
    return json.loads((MAP_DIR / f'{version}.json').read_text(encoding='utf-8'))


def load_form(path: Path | str | None, fmap: dict) -> bytes:
    path = Path(path) if path else form_path(fmap['version'])
    if not path.is_file():
        raise FormNotFound(FORM_NOT_FOUND_DETAIL)
    data = path.read_bytes()
    digest = hashlib.sha256(data).hexdigest()
    if digest != fmap['sha256']:
        raise FormMismatch(f'{path} has SHA-256 {digest}, but field map {fmap["version"]} was made for '
                           f'{fmap["sha256"]}. The form has changed: map its fields again before exporting.')
    return data


# ---------------------------------------------------------------- case values

from ..fact_aliases import ALIASES as _ALIASES, FIELD_KEYS as _FIELD_KEYS, latest as _latest


def confirmed_values(case: Case) -> dict[str, object]:
    """Latest logical field wins, even when its revision is blank, proposed or unconfirmed."""
    from ..review.ingest import _stored
    return {key: f.value for key, f in _latest(case).items() if _stored(f, key).confirmed
            and f.value is not None and str(f.value).strip() != ''}


def package_notes(case: Case, codes: Codes | None = None, *, policy=None) -> list[str]:
    """Non-blocking items that still belong in an official package."""
    codes = codes or Codes()
    from ..completeness_policy import evaluate
    from ..completeness_snapshot import from_case
    policy = policy or evaluate(from_case(case), codes)
    return [gap.message for gap in policy.gaps
            if gap.severity == 'warning' and gap.message == NOT_ENGAGED_ITEM]


def blockers(case: Case, fmap: dict, codes: Codes | None = None, *, store=None) -> list[str]:
    from .package import prepare_package
    return prepare_package(case, codes or Codes(), store=store, version=fmap['version']).policy.report.export_reasons


def _canonical_case(case: Case, codes: Codes) -> Case:
    """Drafts show verified confirmed rows, excluding supplied forged/stale material."""
    rows = {}
    for pid in dict.fromkeys(case.provisions):
        try:
            rows.update((row.provision_id, row) for row in section_c_rows([pid], codes))
        except (KeyError, ValueError):
            continue  # The authoritative findings retain the invalid reference as an open item.
    return case.model_copy(deep=True, update={'provisions': list(rows), 'section_c': list(rows.values())})


def _codes(row: SectionCRow, attr: str) -> list[str]:
    return list(dict.fromkeys(getattr(p, attr) for p in row.pairs))


def _intent_note(row: SectionCRow) -> str:
    """How a row's 2020 intent was attributed, said before the intent itself."""
    notes = {'direct': '', 'inherited from parent': f'Attribution inherited from {row.attributed_via}. ',
             'no row in the attribution table': 'No row in the NBC(AE) attribution table. '}
    differs = 'The 2020 intent is attributed differently from NBC(AE) 2023. ' if row.differs else ''
    return notes[row.attribution_status] + differs


def _checks(fmap: dict, values: dict) -> dict[str, str]:
    out = {}
    for name, spec in fmap['checkboxes'].items():
        answer = values.get(spec['fact'])
        checked = answer == spec['equals'] if 'equals' in spec else answer is True
        out[name] = spec['on'] if checked else '/Off'
    return out


# ---------------------------------------------------------------- layout

class _Box(NamedTuple):
    """What one supplied-form box shows: part of `field`'s text (its own box or a continuation `field~n`)."""
    field: str
    lines: list[str]
    size: float
    top: bool       # top-aligned: several lines, the attribution table, or a box grown for its row neighbour


@dataclass
class _Plan:
    """What each applicant field shows, plus what the appendix must carry."""
    text: dict[str, tuple[str, str | None, str]] = field(default_factory=dict)   # field -> (shown, ref, full)
    rects: dict[str, tuple[float, float, float, float]] = field(default_factory=dict)
    sizes: dict[str, tuple[float, float]] = field(default_factory=dict)          # field -> (max, min) pt
    checks: dict[str, str] = field(default_factory=dict)
    overflow: list[tuple[str, str, str]] = field(default_factory=list)          # (ref, label, full value)
    rows_in_form: int = 0
    docs_in_form: int = 0
    na: dict[str, NotApplicable] = field(default_factory=dict)                  # field -> applicant N/A fact
    printed: dict[str, int] = field(default_factory=dict)       # export-only cell in a printed row -> page
    boxes: dict[str, _Box] = field(default_factory=dict)        # supplied form: widget -> the lines it shows



def _plan(case: Case, values: dict, fmap: dict, rects: dict, codes=None) -> _Plan:
    plan = _Plan(rects=rects)
    na = not_applicable(case)

    def mark_na(name: str, key: str):
        plan.text[name] = (NA_LABEL, None, NA_LABEL)
        plan.na[name] = na[key]
    for slot in fmap['section_c_rows']:
        plan.sizes.update({slot[k]: SECTION_C_SIZES for k in ('article', 'objective', 'function', 'intent')})

    def put(name: str, shown: str, ref: str | None = None, full: str | None = None, fallback: str | None = None):
        shown = pdf_safe(shown)
        full = pdf_safe(full) if full is not None else shown
        if fit(shown, rects[name], *plan.sizes.get(name, ())) is None:
            if fallback is None:
                raise ExportError(f'{name}: reference text does not fit')
            shown = fallback
        plan.text[name] = (shown, ref, full)

    for name, spec in fmap['text_fields'].items():
        value = values.get(spec['fact'], spec.get('default'))
        if spec['fact'] == 'code_or_standard':
            value = code_or_standard_value(value, codes)     # claims the 2nd printing only when codedb proves it
        if value is None:
            if spec['fact'] in na:
                mark_na(name, spec['fact'])
            continue
        value = pdf_safe(value)
        if fit(value, rects[name]) is not None:
            put(name, value)
        else:
            ref = f'X-{len(plan.overflow) + 1}'
            put(name, f'See Appendix {ref}', ref, value)
            plan.overflow.append((ref, spec['label'], value))
    plan.checks = _checks(fmap, values)

    # The older form has no row for a typed legal description: it continues in the appendix, and is never
    # split into invented lot/block/plan components.
    legal = values.get('legal_description')
    if legal and not all(values.get(k) for k in ('lot', 'block', 'plan')):
        ref = f'X-{len(plan.overflow) + 1}'
        value = pdf_safe(values['legal_description'])
        plan.na.pop('Lot', None)
        put('Lot', f'See Appendix {ref}', ref, value)
        plan.overflow.append((ref, 'Legal description', value))

    slots, rows = fmap['section_c_rows'], case.section_c
    shown_rows = rows if len(rows) <= len(slots) else rows[:len(slots) - 1]
    for k, (slot, row) in enumerate(zip(slots, shown_rows), start=1):
        ref = f'C-{k}'
        see = f'See Appendix {ref}'
        objs, fns = _codes(row, 'objective'), _codes(row, 'function')
        put(slot['article'], row.provision_id, ref, row.provision_id, see)
        put(slot['objective'], ', '.join(objs) if objs else 'No table row', ref, None, see)
        put(slot['function'], ', '.join(fns) if fns else 'No table row', ref, None, see)
        intent = _intent_note(row)
        intent += f'{INTENT_LABEL}: Appendix {ref}.' if row.intents else f'No NBC 2020 intent statement; Appendix {ref}.'
        put(slot['intent'], intent, ref, None, see)
    plan.rows_in_form = len(shown_rows)
    if len(rows) > len(slots):
        k0, n = len(slots), len(rows)
        last = slots[-1]
        put(last['article'], f'Rows {k0}-{n}')
        put(last['objective'], 'See Appendix C')
        put(last['function'], 'See Appendix C')
        put(last['intent'], f'Section C rows {k0} to {n} continue in the appendix (C-{k0} to C-{n}).')
    elif NA_ROWS['section_c'] in na:
        for slot in slots[len(rows):]:
            for name in slot.values():
                mark_na(name, NA_ROWS['section_c'])

    dslots = fmap['section_d_rows']
    docs = _documents(case)
    shown_docs = docs if len(docs) <= len(dslots) else docs[:len(dslots) - 1]
    for n, (slot, (doc, who)) in enumerate(zip(dslots, shown_docs), start=1):
        ref = f'D-{n}'
        put(slot['document'], doc, ref, doc, f'See Appendix {ref}')
        if who:
            put(slot['responsible'], who, ref, who, f'See Appendix {ref}')
    plan.docs_in_form = len(shown_docs)
    if len(docs) > len(dslots):
        k0, n = len(dslots), len(docs)
        put(dslots[-1]['document'], f'Documents {k0}-{n}: see Appendix D')
        put(dslots[-1]['responsible'], f'Listed in Appendix D (D-{k0} to D-{n})')
    elif NA_ROWS['section_d'] in na:
        for slot in dslots[len(docs):]:
            for name in slot.values():
                mark_na(name, NA_ROWS['section_d'])
    return plan


def _documents(case: Case) -> list[tuple[str, str]]:
    """Section D entries in their D-n order: attached files, then typed listings."""
    attached = supporting_documents(case)
    docs = [(pdf_safe(d.title), pdf_safe(d.responsible_party)) for d in attached]
    typed = [(pdf_safe(title), pdf_safe(who)) for title, who in text_evidence(case)]
    named = {title for title, _who in docs + typed}
    ids = {document.id for document in attached}
    standalone = [(pdf_safe(entry.description), '') for entry in case.evidence
                  if entry.status == 'evidence_listed' and entry.id not in ids
                  and pdf_safe(entry.description) not in named and entry.description.strip()]
    return docs + typed + standalone


def _plan_supplied(case: Case, values: dict, fmap: dict, codes, widths: dict) -> tuple[_Plan, Layout, dict]:
    """The supplied form: every cell's whole text at its normal size, and the room the form must make for it.

    Returns the plan (without places yet), the `Layout` for `prepare_form`, and each field's measured lines.
    """
    plan, na, measured = _Plan(), not_applicable(case), {}

    def put(name: str, text: str, size: float, width: float):
        text = pdf_safe(text)
        plan.text[name] = (text, None, text)
        measured[name] = (lines_at(text, width, size), size)

    def mark_na(name: str, key: str, size: float, width: float):
        put(name, NA_LABEL, size, width)
        plan.na[name] = na[key]

    for name, spec in fmap['text_fields'].items():
        value = values.get(spec['fact'], spec.get('default'))
        if spec['fact'] == 'code_or_standard':
            value = code_or_standard_value(value, codes)     # claims the 2nd printing only when codedb proves it
        if value is None:
            if spec['fact'] in na:
                mark_na(name, spec['fact'], CELL_SIZE, widths[name])
            continue
        put(name, value, CELL_SIZE, widths[name])
    plan.checks = _checks(fmap, values)
    # A typed legal description goes in the form's printed legal-description row, beside any lot, block and
    # plan; it is never split into invented components.
    if values.get('legal_description'):
        put(LEGAL_ROW, values['legal_description'], CELL_SIZE, widths[LEGAL_ROW])
    rows = case.section_c
    slots = [row_fields(i) for i in range(max(1, len(rows)))]
    for k, (slot, row) in enumerate(zip(slots, rows), start=1):
        objs, fns = _codes(row, 'objective'), _codes(row, 'function')
        # The cell carries every deterministic passage; Appendix C-k keeps the full record with its citation and link.
        intent = _intent_note(row) + (
            f'{INTENT_LABEL}: ' + ' '.join(pdf_safe(t) for block in row.intents for t in block.intents)
            if row.intents else f'No NBC 2020 intent statement; Appendix C-{k}.')
        for key, text in (('article', row.provision_id), ('objective', ', '.join(objs) or 'No table row'),
                          ('function', ', '.join(fns) or 'No table row'), ('intent', intent)):
            put(slot[key], text, TABLE_SIZE, widths[key])
    plan.rows_in_form = len(rows)
    if not rows and NA_ROWS['section_c'] in na:
        for key, name in slots[0].items():
            mark_na(name, NA_ROWS['section_c'], TABLE_SIZE, widths[key])

    name, docs = fmap['supporting_document_field'], _documents(case)
    if docs:
        put(name, '\n'.join(f'D-{n}: {title}' + (f' - {who}' if who else '')
                            for n, (title, who) in enumerate(docs, start=1)), CELL_SIZE, widths['docs'])
        plan.docs_in_form = len(docs)
    elif NA_ROWS['section_d'] in na:
        mark_na(name, NA_ROWS['section_d'], CELL_SIZE, widths['docs'])
    layout = Layout.of([max(len(measured[slot[key]][0]) for key in ROW_KEYS) if slot['article'] in measured else 0
                        for slot in slots],
                       {cell: len(measured[cell][0]) for cell in CELLS if cell in measured},
                       len(measured[name][0]) if name in measured else 0)
    if not layout.bounded():
        raise ExportError('The application has too much text for the bounded form layout. Split the application before exporting.')
    return plan, layout, measured


def _place_lines(plan: _Plan, fmap: dict, rects: dict, measured: dict) -> None:
    """Hand each field's lines to its own box, then to its continuations (`name~2`...), in order."""
    plan.rects = rects
    continuations = fmap.get('continuations') or {}
    printed = fmap.get('printed') or {}
    for box, where in printed.items():
        owner = box.split('~', 1)[0]
        if owner in measured:
            rects[box] = tuple(where['rect'])
            plan.printed[box] = where['page']
    for name, (lines, size) in measured.items():
        rest = list(lines)
        for box in [name, *continuations.get(name, [])]:
            if not rest:
                break
            held = lines_in(rects[box][3] - rects[box][1], size)
            shown, rest = rest[:held], rest[held:]
            plan.boxes[box] = _Box(name, shown, size, len(shown) > 1 or size == TABLE_SIZE
                                   or held > CAPACITY.get(name, DOC_LINES))
        if rest:
            raise ExportError(f'{name}: the form has no room for {len(rest)} more lines')


# ---------------------------------------------------------------- PDF

def _annots(page) -> list:
    annots = page.get('/Annots')
    return list(annots.get_object()) if annots is not None else []


def _field(widget):
    """The field dictionary that owns a widget: the widget itself, or its /Parent when the widget is a kid."""
    return widget if '/T' in widget else widget['/Parent'].get_object()


def _widgets(pages):
    for i, page in enumerate(pages):
        for ref in _annots(page):
            a = ref.get_object()
            if a.get('/Subtype') == '/Widget':
                yield i, str(_field(a)['/T']), a


def _printed_cell(writer: PdfWriter, page_no: int, name: str, rect: tuple[float, float, float, float]) -> None:
    """A text widget for a printed row the source gives no widget; flattening removes it like every other."""
    page = writer.pages[page_no]
    ref = writer._add_object(DictionaryObject({
        NameObject('/Type'): NameObject('/Annot'), NameObject('/Subtype'): NameObject('/Widget'),
        NameObject('/FT'): NameObject('/Tx'), NameObject('/F'): NumberObject(4), NameObject('/T'): TextStringObject(name),
        NameObject('/P'): page.indirect_reference, NameObject('/Rect'): RectangleObject(rect),
        NameObject('/DA'): TextStringObject('/Helv 10 Tf 0 g')}))
    page['/Annots'].append(ref)
    writer.root_object['/AcroForm']['/Fields'].append(ref)


def _fill_and_flatten(form: bytes, plan: _Plan) -> tuple[bytes, list[Placement]]:
    """Fill each planned field at its fitted size, merge appearances into the page, then drop every widget."""
    writer = PdfWriter(clone_from=io.BytesIO(form))
    for name, page_no in plan.printed.items():
        _printed_cell(writer, page_no, name, plan.rects[name])
    placements: list[Placement] = []
    values: dict[str, str] = {}
    for page_no, name, widget in _widgets(writer.pages):
        if name in plan.boxes:                      # the supplied form: measured lines at their normal size
            owner, lines, size, top = plan.boxes[name]
            _shown, ref, full = plan.text[owner]
        elif name in plan.text:
            owner, (shown, ref, full) = name, plan.text[name]
            lines, size = fit(shown, plan.rects[name], *plan.sizes.get(name, ()))
            top = len(lines) > 1 or name in plan.sizes
        else:
            continue
        rect = plan.rects[name]
        widget[NameObject('/Rect')] = RectangleObject(rect)
        fdict = _field(widget)
        if top:                                     # top-aligned; other single lines keep pypdf's centring
            fdict[NameObject('/Ff')] = NumberObject(int(fdict.get('/Ff', 0)) | MULTILINE)
        for d in {id(fdict): fdict, id(widget): widget}.values():   # size is read from /DA; field and kid
            d[NameObject('/DA')] = TextStringObject(f'/Helv {size:g} Tf 0 g')
        values[name] = '\n'.join(lines)
        placements.append(Placement(owner, page_no, rect, lines, size, full, ref))
    writer.update_page_form_field_values(None, {**values, **plan.checks}, auto_regenerate=False, flatten=True)
    for page in writer.pages:                       # flattened: drop every widget, keep links
        if '/Annots' in page:
            keep = [a for a in _annots(page) if a.get_object().get('/Subtype') != '/Widget']
            if keep:
                page[NameObject('/Annots')] = ArrayObject(keep)
            else:
                del page['/Annots']
    del writer._root_object['/AcroForm']
    buf = io.BytesIO()
    writer.write(buf)
    return buf.getvalue(), placements


def _rects(form: bytes, fmap: dict) -> dict[str, tuple[float, float, float, float]]:
    """Widget rectangles. The Article/Objective/Function widgets cover only the top 16 pt of their table cell;
    in the flattened copy they extend down to the bottom of the row's Intent widget, which spans the whole cell."""
    rects = {name: tuple(float(x) for x in w['/Rect']) for _, name, w in _widgets(PdfReader(io.BytesIO(form)).pages)}
    continuations = fmap.get('continuations') or {}
    for slot in fmap['section_c_rows']:
        intents = [slot['intent'], *continuations.get(slot['intent'], [])]
        for k in ('article', 'objective', 'function'):
            for name, intent in zip([slot[k], *continuations.get(slot[k], [])], intents):
                x0, _, x1, y1 = rects[name]
                rects[name] = (x0, rects[intent][1], x1, y1)
    return rects


def _render_case(case: Case, *, draft: bool = False, codes=None, form: Path | str | None = None,
                version: str = CURRENT_MAP, store=None) -> ExportResult:
    """Authoritatively check, canonicalize, fill, flatten and append; no prior gap request is needed."""
    from .appendix import build_appendix

    fmap = load_field_map(version)
    codes = codes or Codes()
    reasons, notes = [], []
    case = _canonical_case(case, codes)
    blank_form = load_form(form, fmap)
    values = confirmed_values(case)
    # Drafts must retain explicit extra sites in their visible source cell. Otherwise
    # officer import would see one address after the shared gate had found several.
    from ..review.bulletin_gates import _missing
    extra_sites = [str(values[key]).strip() for key in ('additional_location', 'second_location', 'extra_location')
                   if key in values and not _missing(values[key])]
    if extra_sites:
        values['municipal_address'] = '; '.join(dict.fromkeys([
            str(values.get('municipal_address') or ''), *extra_sites])).strip('; ')
    if fmap.get('dynamic_attributions'):
        # The supplied form makes room: measure every cell at its normal size, then grow the form to fit.
        plan, layout, measured = _plan_supplied(case, values, fmap, codes, text_widths(blank_form))
        blank_form, fmap = prepare_form(blank_form, fmap, layout)
        _place_lines(plan, fmap, _rects(blank_form, fmap), measured)
    else:
        blank_form, fmap = prepare_form(blank_form, fmap, len(case.section_c))
        plan = _plan(case, values, fmap, _rects(blank_form, fmap), codes)
    filled, placements = _fill_and_flatten(blank_form, plan)
    # Keep a source passage separate from its field label. "Intent statement"
    # is a PDF /T name, not a claim that every cross-reference inside the quoted
    # passage identifies a national intent-table entry.
    intent_fields = {slot['intent'] for slot in fmap['section_c_rows']} if fmap.get('dynamic_attributions') else set()
    form_text = []
    for name, (_shown, _ref, full) in plan.text.items():
        if name in intent_fields:
            full = full.replace(f'{INTENT_LABEL}: ', f'{INTENT_LABEL}:\n\n')
            form_text.append(f'{name}:\n\n{full}')
        else:
            form_text.append(f'{name}: {full}')
    appendix_text: list[str] = []
    # A draft's open items stay in the result, not the document: the questions and Review show them.
    appendix = build_appendix(case, plan, values, fmap, codes=codes, package_notes=notes, text=appendix_text)

    out = PdfWriter(clone_from=io.BytesIO(filled))
    form_pages = len(out.pages)
    appendix_pages = PdfReader(io.BytesIO(appendix)).pages if appendix else []
    for page in appendix_pages:
        out.add_page(page)
    out.add_metadata({'/Title': 'Variance Form for Proposed Alternative Solution' + (' (DRAFT)' if draft else ''),
                      '/Producer': f'Batatis export, field map {fmap["version"]}',
                      '/BatatisFormVersion': fmap['version'],
                      '/BatatisAttributionRows': str(max(1, len(case.section_c))),
                      '/BatatisFormPages': str(form_pages),
                      **({'/BatatisLayout': fmap['layout']} if fmap.get('layout') else {})})
    buf = io.BytesIO()
    out.write(buf)
    filled_names = set(plan.text) | {k for k, v in plan.checks.items() if v != '/Off'}
    blank = [n for n in [*fmap['text_fields'], *[f for r in fmap['section_c_rows'] for f in r.values()],
                         *[f for r in fmap['section_d_rows'] for f in r.values()],
                         *([fmap['supporting_document_field']] if fmap.get('supporting_document_field') else [])]
             if n not in filled_names]
    visible = list(dict.fromkeys((reasons if draft else []) + notes))
    return ExportResult(pdf=buf.getvalue(), field_map=fmap['version'], form_pages=form_pages,
                        appendix_pages=len(appendix_pages), draft=draft, placements=placements,
                        blank_fields=blank, open_items=visible, not_applicable=list(plan.na), form_text=form_text,
                        appendix_text=appendix_text)


def export_case(case: Case, *, draft=False, codes=None, form=None, version=CURRENT_MAP, store=None) -> ExportResult:
    """Gate the exact outgoing, visible package that officer import will read."""
    from .package import prepare_package
    prepared = prepare_package(case, codes or Codes(), store=store, draft=draft, form=form, version=version)
    if prepared.policy.report.export_reasons and not draft:
        raise ExportBlocked(prepared.policy.report.export_reasons)
    prepared.export.open_items = prepared.policy.report.export_reasons
    return prepared.export
