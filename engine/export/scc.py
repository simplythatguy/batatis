"""Export a case to the Safety Codes Council variance form (Part 1, applicant fields only).

Steps: check the blank form's SHA-256 against the version-keyed field map, decide what goes in each applicant
field (short values in the cell, long ones moved to the appendix with a reference), fill with pypdf, flatten
(appearance streams merged into the page, every widget removed, so the help pop-ups and buttons disappear and
every viewer shows the same thing), and append the generated appendix. Draft status stays in metadata;
the website displays it without adding visible markings to the supplied form or generated appendix.

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
from .challenge_form import LEGAL_PAGE, LEGAL_RECT, LEGAL_ROW, VERSION as CHALLENGE_VERSION, prepare_form
from .text import fit, fit_start, pdf_safe

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
    appendix carries under `ref` when the form shows only a reference."""
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
    return json.loads((MAP_DIR / f'{version}.json').read_text())


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

_ALIASES = {
    'owner_name': ('owner_name', 'owner', 'section_a.owner_name'),
    'owner_rep_name': ('owner_rep_name', 'representative', 'applicant_name'),
    'request_date': ('request_date', 'application_date', 'date', 'section_a.date'),
    'mailing_address': ('mailing_address', 'mailingAddress'),
    'municipal_address': ('municipal_address', 'municipalAddress', 'civic_address', 'address'),
    'legal_description': ('legal_description', 'legalDescription', 'section_b.legal_description'),
    'permit_number': ('permit_number', 'permit', 'section_b.permit_number'),
    'alternative_description': ('alternative_description', 'alternative'),
}
_FIELD_KEYS = {alias: key for key, aliases in _ALIASES.items() for alias in aliases}
_FIELD_KEYS.update({alias: 'process.' + key for key, names in PROCESS_ALIASES.items()
                    for name in names for alias in (name, 'process.' + name)})


def _latest(case: Case):
    out = {}
    for fact in case.facts:
        out[_FIELD_KEYS.get(fact.field, fact.field)] = fact
    return out


def confirmed_values(case: Case) -> dict[str, object]:
    """Latest logical field wins, even when its revision is blank, proposed or unconfirmed."""
    return {key: f.value for key, f in _latest(case).items() if f.export()['status'] == 'confirmed'
            and f.value is not None and str(f.value).strip() != ''}


def package_notes(case: Case, codes: Codes | None = None) -> list[str]:
    """Non-blocking items that still belong in an official package."""
    codes = codes or Codes()
    return [gap.message for gap in check_completeness(case, codes)
            if gap.severity == 'warning' and gap.message == NOT_ENGAGED_ITEM]


def blockers(case: Case, fmap: dict, codes: Codes | None = None) -> list[str]:
    codes = codes or Codes()
    values = confirmed_values(case)
    reasons = [f'unconfirmed {f.kind} fact "{f.field}" ({f.id})' for f in _latest(case).values()
               if f.export()['status'] != 'confirmed']
    reasons += [f'blocking gap in section {g.section}, {g.field}: {g.message} Fix: {g.fix_hint}'
                for g in check_completeness(case, codes) if g.severity == 'blocking']
    reasons += [f'blocking gap in section {g.section}, {g.field}: {g.message}' for g in case.gaps
                if g.severity == 'blocking']
    reasons += [f'required field "{k}" is empty' for k in fmap['required_facts'] if k not in values]
    if not case.section_c:
        reasons.append('Section C has no provisions')
    return list(dict.fromkeys(reasons))


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


# ---------------------------------------------------------------- layout

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
    for name, spec in fmap['checkboxes'].items():
        answer = values.get(spec['fact'])
        checked = answer == spec['equals'] if 'equals' in spec else answer is True
        plan.checks[name] = spec['on'] if checked else '/Off'

    # A typed legal description is never split into invented lot/block/plan components. The supplied form
    # prints a row for it, so it is drawn there, beside any lot, block and plan the applicant gave, and
    # continues in the appendix only when the row cannot hold it. The older form keeps it in the appendix.
    legal = values.get('legal_description')
    if legal and fmap['version'] == CHALLENGE_VERSION:
        value = pdf_safe(legal)
        rects[LEGAL_ROW] = LEGAL_RECT
        plan.printed[LEGAL_ROW] = LEGAL_PAGE
        if fit(value, LEGAL_RECT) is not None:
            put(LEGAL_ROW, value)
        else:
            ref = f'X-{len(plan.overflow) + 1}'
            put(LEGAL_ROW, f'See Appendix {ref}', ref, value)
            plan.overflow.append((ref, 'Legal description', value))
    elif legal and not all(values.get(k) for k in ('lot', 'block', 'plan')):
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
        notes = {'direct': '', 'inherited from parent': f'Attribution inherited from {row.attributed_via}. ',
                 'no row in the attribution table': 'No row in the NBC(AE) attribution table. '}
        intent = notes[row.attribution_status]
        if row.differs:
            intent += 'The 2020 intent is attributed differently from NBC(AE) 2023. '
        head = f'{intent}{INTENT_LABEL}: '
        intent += f'{INTENT_LABEL}: Appendix {ref}.' if row.intents else f'No NBC 2020 intent statement; Appendix {ref}.'
        if fmap.get('dynamic_attributions') and row.intents:
            # The cell shows the deterministic passages, or as much of them as it holds and where the whole
            # entry is. Appendix C-k carries every passage whole, once, with its citation and the NRC link.
            actual = ' '.join(pdf_safe(t) for block in row.intents for t in block.intents)
            rect = rects[slot['intent']]
            shown = head + actual
            if fit(shown, rect, *SECTION_C_SIZES) is None:
                shown = fit_start(head, actual, f' ... (full text: Appendix {ref})', rect, *SECTION_C_SIZES) or intent
            put(slot['intent'], shown, ref, shown, see)
        else:
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
    docs = [(pdf_safe(d.title), pdf_safe(d.responsible_party)) for d in supporting_documents(case)]
    docs += [(pdf_safe(title), pdf_safe(who)) for title, who in text_evidence(case)]
    if fmap.get('supporting_document_field'):
        # The supplied source has one combined full-width field, not the legacy
        # five-row/two-column table. Keep its exact box and use existing D refs:
        # as many whole entries as it holds, then the rest named; Appendix D lists all.
        name = fmap['supporting_document_field']
        if docs:
            entries = [f'D-{n}: {title}' + (f' - {who}' if who else '') for n, (title, who) in enumerate(docs, start=1)]
            for count in range(len(entries), 0, -1):
                rest = [] if count == len(entries) else [
                    f'D-{count + 1}' + (f' to D-{len(entries)}' if count + 1 < len(entries) else '')
                    + ': continued in Appendix D']
                listing = '\n'.join([*entries[:count], *rest])
                if fit(listing, rects[name]) is not None:
                    put(name, listing)
                    plan.docs_in_form = count
                    break
            else:
                put(name, f'See Appendix D (D-1 to D-{len(docs)})')
        elif NA_ROWS['section_d'] in na:
            mark_na(name, NA_ROWS['section_d'])
        return plan
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
        if name not in plan.text:
            continue
        rect = plan.rects[name]
        widget[NameObject('/Rect')] = RectangleObject(rect)
        shown, ref, full = plan.text[name]
        lines, size = fit(shown, rect, *plan.sizes.get(name, ()))
        fdict = _field(widget)
        if len(lines) > 1 or name in plan.sizes:    # top-aligned; other single lines keep pypdf's centring
            fdict[NameObject('/Ff')] = NumberObject(int(fdict.get('/Ff', 0)) | MULTILINE)
        for d in {id(fdict): fdict, id(widget): widget}.values():   # size is read from /DA; field and kid
            d[NameObject('/DA')] = TextStringObject(f'/Helv {size:g} Tf 0 g')
        values[name] = '\n'.join(lines)
        placements.append(Placement(name, page_no, rect, lines, size, full, ref))
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
    for slot in fmap['section_c_rows']:
        bottom = rects[slot['intent']][1]
        for k in ('article', 'objective', 'function'):
            x0, _, x1, y1 = rects[slot[k]]
            rects[slot[k]] = (x0, bottom, x1, y1)
    return rects


def export_case(case: Case, *, draft: bool = False, codes=None, form: Path | str | None = None,
                version: str = CURRENT_MAP) -> ExportResult:
    """Authoritatively check, canonicalize, fill, flatten and append; no prior gap request is needed."""
    from .appendix import build_appendix

    fmap = load_field_map(version)
    codes = codes or Codes()
    reasons = blockers(case, fmap, codes)
    if reasons and not draft:
        raise ExportBlocked(reasons)
    notes = package_notes(case, codes)
    case = _canonical_case(case, codes)
    blank_form = load_form(form, fmap)
    blank_form, fmap = prepare_form(blank_form, fmap, len(case.section_c))
    values = confirmed_values(case)
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
    appendix = build_appendix(case, plan, values, fmap, codes=codes,
                              open_items=reasons if draft else [], package_notes=notes, text=appendix_text)

    out = PdfWriter(clone_from=io.BytesIO(filled))
    form_pages = len(out.pages)
    app_reader = PdfReader(io.BytesIO(appendix))
    for page in app_reader.pages:
        out.add_page(page)
    out.add_metadata({'/Title': 'Variance Form for Proposed Alternative Solution' + (' (DRAFT)' if draft else ''),
                      '/Producer': f'Batatis export, field map {fmap["version"]}',
                      '/BatatisFormVersion': fmap['version'],
                      '/BatatisAttributionRows': str(max(1, len(case.section_c))),
                      '/BatatisFormPages': str(form_pages)})
    buf = io.BytesIO()
    out.write(buf)
    filled_names = set(plan.text) | {k for k, v in plan.checks.items() if v != '/Off'}
    blank = [n for n in [*fmap['text_fields'], *[f for r in fmap['section_c_rows'] for f in r.values()],
                         *[f for r in fmap['section_d_rows'] for f in r.values()],
                         *([fmap['supporting_document_field']] if fmap.get('supporting_document_field') else [])]
             if n not in filled_names]
    visible = list(dict.fromkeys((reasons if draft else []) + notes))
    return ExportResult(pdf=buf.getvalue(), field_map=fmap['version'], form_pages=form_pages,
                        appendix_pages=len(app_reader.pages), draft=draft, placements=placements,
                        blank_fields=blank, open_items=visible, not_applicable=list(plan.na), form_text=form_text,
                        appendix_text=appendix_text)
