"""Export a case to the Safety Codes Council variance form (Part 1, applicant fields only).

Steps: check the blank form's SHA-256 against the version-keyed field map, decide what goes in each applicant
field (short values in the cell, long ones moved to the appendix with a reference), fill with pypdf, flatten
(appearance streams merged into the page, every widget removed, so the help pop-ups and buttons disappear and
every viewer shows the same thing), append the generated appendix, and stamp DRAFT on every page when asked.

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
from pypdf.generic import ArrayObject, NameObject, NumberObject, RectangleObject, TextStringObject

from ..models import INTENT_LABEL, Case, SectionCRow
from ..codes import Codes
from ..completeness import check_completeness
from ..process_fields import PROCESS_ALIASES
from ..section_c import section_c_rows
from ..section_d import supporting_documents
from .text import fit, pdf_safe

DEFAULT_FORM = Path(__file__).resolve().parents[2] / 'reference' / 'guides' / 'SCC-Variance-Form.pdf'
BUNDLE_FORM = Path(__file__).resolve().parents[2] / 'codedb' / 'build' / 'SCC-Variance-Form.pdf'
FORM_NOT_FOUND_DETAIL = 'SCC variance form not found'
EXPORT_FAILED_DETAIL = 'The SCC variance form could not be exported.'
MAP_DIR = Path(__file__).parent / 'field_maps'
CURRENT_MAP = 'scc_2026-10'
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


def form_path() -> Path:
    """Explicit path, then a local guide copy, then the file the engine build downloads."""
    override = (os.environ.get('BATATIS_SCC_FORM') or '').strip()
    if override:
        return Path(override)
    if DEFAULT_FORM.is_file():
        return DEFAULT_FORM
    return BUNDLE_FORM


def load_field_map(version: str = CURRENT_MAP) -> dict:
    return json.loads((MAP_DIR / f'{version}.json').read_text())


def load_form(path: Path | str | None, fmap: dict) -> bytes:
    path = Path(path) if path else form_path()
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


def _plan(case: Case, values: dict, fmap: dict, rects: dict) -> _Plan:
    plan = _Plan(rects=rects)
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
        if value is None:
            continue
        value = pdf_safe(value)
        if fit(value, rects[name]) is not None:
            put(name, value)
        else:
            ref = f'X-{len(plan.overflow) + 1}'
            put(name, f'See Appendix {ref}', ref, value)
            plan.overflow.append((ref, spec['label'], value))
    for name, spec in fmap['checkboxes'].items():
        plan.checks[name] = spec['on'] if values.get(spec['fact']) is True else '/Off'

    # The form provides structured legal-description boxes. A free-text legal description
    # continues in the appendix; it is never split into invented lot/block/plan components.
    if values.get('legal_description') and not all(values.get(k) for k in ('lot', 'block', 'plan')):
        ref = f'X-{len(plan.overflow) + 1}'
        value = pdf_safe(values['legal_description'])
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

    dslots = fmap['section_d_rows']
    docs = [(pdf_safe(d.title), pdf_safe(d.responsible_party)) for d in supporting_documents(case)]
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


def _fill_and_flatten(form: bytes, plan: _Plan) -> tuple[bytes, list[Placement]]:
    """Fill each planned field at its fitted size, merge appearances into the page, then drop every widget."""
    writer = PdfWriter(clone_from=io.BytesIO(form))
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
    from .appendix import build_appendix, stamp_draft

    fmap = load_field_map(version)
    codes = codes or Codes()
    reasons = blockers(case, fmap, codes)
    if reasons and not draft:
        raise ExportBlocked(reasons)
    case = _canonical_case(case, codes)
    blank_form = load_form(form, fmap)
    values = confirmed_values(case)
    plan = _plan(case, values, fmap, _rects(blank_form, fmap))
    filled, placements = _fill_and_flatten(blank_form, plan)
    appendix = build_appendix(case, plan, values, fmap, codes=codes, open_items=reasons if draft else [])

    out = PdfWriter(clone_from=io.BytesIO(filled))
    form_pages = len(out.pages)
    app_reader = PdfReader(io.BytesIO(appendix))
    for page in app_reader.pages:
        out.add_page(page)
    if draft:
        stamp_draft(out)
    out.add_metadata({'/Title': 'Variance Form for Proposed Alternative Solution' + (' (DRAFT)' if draft else ''),
                      '/Producer': f'Batatis export, field map {fmap["version"]}'})
    buf = io.BytesIO()
    out.write(buf)
    filled_names = set(plan.text) | {k for k, v in plan.checks.items() if v != '/Off'}
    blank = [n for n in [*fmap['text_fields'], *[f for r in fmap['section_c_rows'] for f in r.values()],
                         *[f for r in fmap['section_d_rows'] for f in r.values()]] if n not in filled_names]
    return ExportResult(pdf=buf.getvalue(), field_map=fmap['version'], form_pages=form_pages,
                        appendix_pages=len(app_reader.pages), draft=draft, placements=placements,
                        blank_fields=blank, open_items=reasons if draft else [])
