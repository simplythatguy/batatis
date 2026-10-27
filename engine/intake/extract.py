"""Intake extraction: rules first, then the model, then ledger facts with pointers.

A rule hit becomes a `pointed` fact quoting the words that state it (a unit conversion adds a
`computed` fact over the value as written). A fillable-form value becomes an `exact` fact. A model
fact is `pointed` only when the rules re-derive it from the quoted sentence, otherwise `proposed`.
Extraction returns unconfirmed facts; settlement requires verified project context to confirm them.
Article numbers the applicant typed are kept
only when they resolve in NBC(AE) 2023, 2nd printing; the rest are listed as unresolved text.
"""
from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Callable

from ..models import Fact, Source
from ..redact import scrub
from ..models_intake import DocumentReview, FactPointer, FieldConflict, FileReport, ModelPass, UnresolvedCitation
from . import model as model_pass
from .context import project_pages, reference_widget
from .images import InvalidImage, image_format, image_type, picture_url
from .pdf import (FORM_ONLY, MAX_PAGES, NO_TEXT, NOT_A_PDF, SCC_MAP, TOO_LONG, NotAPdf, Page, PdfContent,
                  is_pdf, picture_page, read_pdf)
from .review import personal_values
from .rules import FIELDS, LEGAL_PARTS, PERSONAL, Hit, canonical_citation, read
from .text import find_quote

DESCRIPTION = 'description'
DESCRIPTION_REF = 'intake:description'
IMAGES_PER_FILE = 4
READER_VERSION = 'reader-1'                       # what a client reads instead of the private model pin
PICTURES_NOT_ALLOWED = 'waiting for your OK'
# (text, personal values the rules just read) -> the copy a provider may see.
Outbound = Callable[[str, list[str]], str]


def scrubbed(text: str, personal: list[str]) -> str:
    return scrub(text, sorted(set(personal), key=len, reverse=True))


@dataclass
class Extraction:
    facts: list[Fact] = field(default_factory=list)
    pointers: list[FactPointer] = field(default_factory=list)
    conflicts: list[FieldConflict] = field(default_factory=list)
    unresolved: list[UnresolvedCitation] = field(default_factory=list)
    model: ModelPass = field(default_factory=lambda: ModelPass(status='off'))
    files: list[FileReport] = field(default_factory=list)
    review: DocumentReview | None = None
    personal: list[str] = field(default_factory=list)  # scrub candidates even when not project answers

    def merge(self, other: Extraction) -> None:
        self.facts += other.facts
        self.pointers += other.pointers
        self.conflicts += other.conflicts
        self.unresolved += other.unresolved
        self.files += other.files
        self.personal += other.personal
        self.merge_model(other.model)

    def merge_model(self, other: ModelPass) -> None:
        mine, theirs = self.model, other
        if theirs.status != 'off':
            mine.status = theirs.status if mine.status in ('off', 'not_needed') else mine.status
            mine.model = theirs.model or mine.model
            mine.reason = mine.reason or theirs.reason
        for name in ('pointed', 'proposed', 'dropped'):
            setattr(mine, name, getattr(mine, name) + getattr(theirs, name))
        for name in ('input_tokens', 'output_tokens'):
            a, b = getattr(mine, name), getattr(theirs, name)
            setattr(mine, name, None if a is None or b is None else a + b)


def deduplicate(out: Extraction) -> None:
    """One metric field/value, many pointers. Computed inputs keep their stable ledger ids."""
    kept, ids, same = [], {}, {}
    for fact in out.facts:
        value = fact.value
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            key = (fact.field, 'number', round(value, 6))
        else:
            key = (fact.field, type(value).__name__, ' '.join(value.split()).casefold() if isinstance(value, str) else value)
        first = same.get(key)
        if first is None:
            same[key] = fact
            kept.append(fact)
            ids[fact.id] = fact.id
        elif first.kind == 'proposed' and fact.kind != 'proposed':
            # A verified text reading outranks a picture proposal of the same value.
            kept[kept.index(first)] = fact
            same[key] = fact
            ids[first.id] = fact.id
            ids[fact.id] = fact.id
        else:
            ids[fact.id] = first.id
    def canonical(id):
        while id != ids.get(id, id):
            id = ids[id]
        return id
    for fact in kept:
        fact.inputs = list(dict.fromkeys(canonical(id) for id in fact.inputs))
    seen, pointers = set(), []
    for pointer in out.pointers:
        pointer.fact_id = canonical(pointer.fact_id)
        key = (pointer.fact_id, pointer.source_ref, pointer.page, pointer.method, pointer.start, pointer.end)
        if key not in seen:
            seen.add(key)
            pointers.append(pointer)
    out.facts, out.pointers = kept, pointers


@dataclass(frozen=True)
class Origin:
    """Where a text came from: the description, or one page of a file."""
    ref: str                                     # 'description' or the file id
    page: int | None = None
    box: Callable[[int, int], tuple[float, float, float, float] | None] | None = None
    project_context: bool = False

    def source(self, quote: str, start: int, end: int) -> Source:
        if self.ref == DESCRIPTION:
            return Source(type='user_text', ref=DESCRIPTION_REF, quote=quote)
        return Source(type='file', ref=self.ref, page=self.page, quote=quote,
                      bbox=self.box(start, end) if self.box else None)


def _add(out: Extraction, origin: Origin, name: str, value, kind: str, start: int | None, end: int | None,
         quote: str | None, confidence: float, method: str, *, verified: bool = True,
         source: Source | None = None, formula: str | None = None, inputs: list[str] | None = None) -> Fact:
    fact = Fact(field=name, value=value, kind=kind, confidence=round(confidence, 2), status='unconfirmed',
                source=source or origin.source(quote, start, end), formula=formula, inputs=inputs or [])
    out.facts.append(fact)
    out.pointers.append(FactPointer(fact_id=fact.id, field=name, method=method, source_ref=origin.ref,
                                    page=origin.page, start=start, end=end, verified=verified,
                                    quote=fact.source.quote,
                                    project_context=origin.ref == DESCRIPTION or origin.project_context))
    return fact


def _hit_facts(out: Extraction, origin: Origin, text: str, hit: Hit) -> None:
    quote = text[hit.start:hit.end]
    if hit.raw is None:
        _add(out, origin, hit.field, hit.value, 'pointed', hit.start, hit.end, quote, hit.confidence, 'rules')
        return
    raw_field, written, formula = hit.raw
    pointed = _add(out, origin, raw_field, written, 'pointed', hit.start, hit.end, quote, hit.confidence, 'rules')
    _add(out, origin, hit.field, hit.value, 'computed', hit.start, hit.end, quote, hit.confidence, 'rules',
         formula=formula, inputs=[pointed.id])


def _citations(out: Extraction, origin: Origin, text: str, citations, codes) -> None:
    seen = set()
    for entered, start, end in citations:
        canonical = canonical_citation(entered)
        if canonical is None or canonical in seen:
            continue
        seen.add(canonical)
        found = None
        if codes is not None:
            try:
                found = codes.provision(canonical, 'B')
            except Exception:
                found = None
        if found:
            _add(out, origin, 'claimed_provision', canonical, 'pointed', start, end, text[start:end], 0.9, 'rules')
        else:
            out.unresolved.append(UnresolvedCitation(entered=entered, source_ref=origin.ref, page=origin.page))


def read_text(text: str, origin: Origin, *, codes=None, outbound: Outbound = scrubbed,
              transport: model_pass.Transport | None = None, status: str = 'off',
              budget: model_pass.Budget | None = None, citation_text: str | None = None) -> Extraction:
    """Rules over `text`, then the model over its scrubbed copy for the fields still empty."""
    out = Extraction()
    reading = read(text)
    for hit in reading.hits:
        _hit_facts(out, origin, text, hit)
    for name, hits in reading.conflicts.items():
        values = list(dict.fromkeys(json.dumps(h.value) for h in hits if h.value != -1))
        out.conflicts.append(FieldConflict(field=name, values=[json.loads(v) for v in values],
                                           quotes=[text[h.start:h.end] for h in hits], source_ref=origin.ref,
                                           page=origin.page, source_refs=[origin.ref] * len(values)))
    citation_text = text if citation_text is None else citation_text
    _citations(out, origin, citation_text, read(citation_text).citations, codes)
    found = {hit.field for hit in reading.hits} | set(reading.conflicts)
    if transport is None:
        return out
    personal = [str(hit.value) for hit in reading.hits if hit.field in PERSONAL and len(str(hit.value)) >= 3]
    run = model_pass.run(text, outbound(text, personal), transport, skip=found, status=status, budget=budget)
    out.model = ModelPass(status=run.status, model=READER_VERSION if run.status == 'live' else None,
                          reason=run.reason, dropped=run.dropped, input_tokens=run.input_tokens,
                          output_tokens=run.output_tokens)
    for item in run.facts:
        quote = text[item.start:item.end]
        name = item.field if item.field != model_pass.STATEMENT else \
            'statement.' + hashlib.sha256(' '.join(quote.split()).encode()).hexdigest()[:10]
        kind = 'pointed' if item.verified else 'proposed'
        _add(out, origin, name, item.value, kind, item.start, item.end, quote, 0.6 if item.verified else 0.4,
             'model', verified=item.verified)
        if item.verified:
            out.model.pointed += 1
        else:
            out.model.proposed += 1
    return out


def _semantic_pages(out: Extraction, pages: list[Page], report: FileReport, *, transport, outbound, status, budget):
    if not pages:
        return
    if transport is None:
        report.semantic_reason = 'AI is off'
        return
    chunks, ends, length = [], [], 0
    for page in pages:
        personal = [str(h.value) for h in read(page.text).hits if h.field in PERSONAL]
        chunk = outbound(page.text, personal)
        chunks.append(chunk)
        begin = length
        length += len(chunk)
        ends.append((page.number, begin, length))
        length += 2                            # page separator in the outbound text
    source = '\n\n'.join(p.text for p in pages)
    run = model_pass.run(source, '\n\n'.join(chunks), transport, skip=set(), status=status, budget=budget)
    report.semantic_pages_read = [number for number, _, end in ends if end <= run.covered_chars]
    report.semantic_pages_sent = [number for number, begin, _ in ends if begin < run.sent_chars]
    if len(report.semantic_pages_read) != len(pages):
        report.semantic_reason = (model_pass.LIMIT if run.reason == model_pass.LIMIT else
                                  'AI is paused' if run.status == 'gate_closed' else 'AI could not finish reading')
    counts = ModelPass(status=run.status, model=READER_VERSION if run.status == 'live' else None,
                       reason=run.reason, dropped=run.dropped, input_tokens=run.input_tokens,
                       output_tokens=run.output_tokens)
    for item in run.facts:
        quote = source[item.start:item.end]
        # Keep each occurrence's real page and box, including an identical fact on several pages.
        for page in pages:
            if page.number not in report.semantic_pages_read:
                continue
            span = find_quote(page.text, quote)
            if span is None:
                continue
            name = item.field if item.field != model_pass.STATEMENT else \
                'statement.' + hashlib.sha256(' '.join(quote.split()).encode()).hexdigest()[:10]
            _add(out, Origin(report.file_id, page.number, page.box, project_context=True), name, item.value,
                 'pointed' if item.verified else 'proposed', *span, quote, .6 if item.verified else .4,
                 'model', verified=item.verified)
            if item.verified:
                counts.pointed += 1
            else:
                counts.proposed += 1
    out.merge_model(counts)


def _pictures(out: Extraction, report: FileReport, pages: list[int], url, *, transport, status, budget, outbound,
              allowed: bool):
    if not pages:
        return
    if transport is None:
        report.pictures_not_read_reason = 'AI is off'
        return
    if not getattr(transport, 'supports_images', False):
        report.pictures_not_read_reason = 'this AI connection reads text only'
        return
    if not allowed:
        # Pixels cannot be scrubbed like text: a picture leaves the machine only after the applicant allows it.
        report.pictures_not_read_reason = PICTURES_NOT_ALLOWED
        return
    for page in pages:
        if len(report.image_pages_read) >= IMAGES_PER_FILE or budget.images <= 0 or budget.expired():
            report.pictures_not_read_reason = model_pass.LIMIT
            break
        budget.images -= 1
        try:
            image = url(page)
        except Exception:
            report.pictures_not_read_reason = 'it could not be opened'
            continue
        run = model_pass.vision(image, transport, status=status, outbound=lambda text: outbound(text, []))
        counts = ModelPass(status=run.status, model=READER_VERSION if run.status == 'live' else None,
                           reason=run.reason, dropped=run.dropped, input_tokens=run.input_tokens,
                           output_tokens=run.output_tokens)
        if run.status in ('failed', 'gate_closed'):
            report.pictures_not_read_reason = run.reason
            out.merge_model(counts)
            budget.images = 0
            break
        report.image_pages_read.append(page)
        for item in run.facts:
            name, value, quote = item.field, item.value, item.quote
            if name == model_pass.STATEMENT:
                name = 'statement.' + hashlib.sha256(' '.join(quote.split()).encode()).hexdigest()[:10]
            _add(out, Origin(report.file_id, page, project_context=True), name, value, 'proposed', None, None, quote, .4, 'vision',
                 verified=False, source=Source(type='file', ref=report.file_id, page=page, quote=quote))
            out.pointers[-1].source_name = report.name
            counts.proposed += 1
        out.merge_model(counts)


def _report(out: Extraction, report: FileReport) -> None:
    deduplicate(out)
    report.pages_read = sorted(set(report.pages_read + report.text_pages_read + report.image_pages_read))
    report.pages_not_read = sorted(set(range(1, (report.pages or 0) + 1)) - set(report.pages_read))
    report.facts = len({p.fact_id for p in out.pointers if p.source_ref == report.file_id})
    if report.pages_read or report.form_fields_read:
        report.status = 'partly_read' if report.pages_not_read else 'read'
    if report.pages_not_read:
        report.reason = ('Pictures not read: ' + report.pictures_not_read_reason
                         if report.pictures_not_read_reason else TOO_LONG)
    if report.semantic_reason and report.semantic_reason != 'AI is off':
        report.status = 'partly_read'
        report.reason = report.semantic_reason


# ---------------------------------------------------------------- files

@lru_cache(maxsize=1)
def _scc_map() -> dict[str, str]:
    data = json.loads(SCC_MAP.read_text(encoding='utf-8'))
    mapped = {name: spec['fact'] for name, spec in data['text_fields'].items() if spec['section'] != 'C'}
    mapped.update({name: spec['fact'] for name, spec in data['checkboxes'].items()})
    for index, row in enumerate(data['section_c_rows']):
        mapped[row['article']] = 'claimed_provision'
    return mapped


def reading_field(name: str) -> bool:
    """Fields intake can write, including legacy readings whose pointers were not retained.

    A file source alone is insufficient: evidence bindings are explicit applicant actions.
    """
    metric = re.sub(r'_ft2$', '_m2', re.sub(r'_ft$', '_m', name))
    return name.startswith('statement.') or metric in FIELDS or name in _scc_map().values()


# Generic fillable forms: a field whose name reads like one of these labels.
_FORM_LABELS = (
    ('owner_rep_name', r"owner'?s?\s*rep(?:resentative)?(?:\s*name)?|applicant(?:'?s)?\s*name|representative"),
    ('owner_name', r"(?:property\s*|registered\s*)?owner'?s?(?:\s*name)?"),
    ('mailing_address', r'mailing\s*address'),
    ('municipal_address', r'(?:municipal|civic|site|project|street|property)\s*address'),
    ('legal_description', r'legal(?:\s*land)?(?:\s*description)?'),
    ('permit_number', r'(?:building\s*)?permit(?:\s*(?:number|no\.?|#))?'),
    ('request_date', r'date\s*of\s*request|request\s*date'),
    ('lot', r'lot'), ('block', r'block'), ('plan', r'plan'),
)


def _form_field(name: str) -> str | None:
    label = re.sub(r'[_\-.:]+', ' ', name).strip().lower()
    return next((key for key, pattern in _FORM_LABELS if re.fullmatch(pattern, label)), None)


def _parsed(cache: dict | None, file_id: str, data: bytes):
    """read_pdf once per file per run: the model pass runs the same files a second time."""
    if cache is None:
        return read_pdf(data)
    if file_id not in cache:
        try:
            cache[file_id] = read_pdf(data)
        except NotAPdf as exc:
            cache[file_id] = exc
    found = cache[file_id]
    if isinstance(found, NotAPdf):
        raise found
    return found


def read_file(file_id: str, name: str, data: bytes, *, codes=None, outbound: Outbound = scrubbed,
              transport: model_pass.Transport | None = None, status: str = 'off',
              cache: dict | None = None, budget: model_pass.Budget | None = None,
              media_type: str | None = None, pictures: bool = False) -> Extraction:
    out = Extraction()
    report = FileReport(file_id=file_id, name=name, status='not_read')
    out.files.append(report)
    budget = budget if budget is not None else model_pass.Budget()
    if image_format(data):
        try:
            report.media_type = image_type(data)
        except InvalidImage as error:
            report.reason = str(error)
            return out
        report.pages = 1
        _pictures(out, report, [1], lambda page: picture_url(data), transport=transport, status=status,
                  budget=budget, outbound=outbound, allowed=pictures)
        _report(out, report)
        return out
    try:
        if is_pdf(data) or (media_type != 'text/plain' and not name.lower().endswith('.txt')):
            content = _parsed(cache, file_id, data)
        else:
            text = data.decode('utf-8-sig')
            if not text.strip() or any(ord(c) < 32 and c not in '\r\n\t' for c in text):
                raise NotAPdf()
            report.media_type = 'text/plain'
            content = PdfContent(1, [Page(1, text)], [], [], None)
    except (NotAPdf, UnicodeError):
        report.reason = NOT_A_PDF
        return out
    report.pages = content.pages
    if content.reason:
        report.reason = content.reason
        report.pages_not_read = list(range(1, content.pages + 1))
        return out
    out.personal = personal_values([page.text for page in content.text_pages])
    if content.form:
        report.form = content.form
        mapped = _scc_map() if content.form == 'scc_variance' else {}
        for widget in content.widgets:
            target = mapped.get(widget.name) if content.form == 'scc_variance' else _form_field(widget.name)
            if target is None or widget.kind in ('signature', 'button'):
                report.form_fields_skipped.append(widget.name)
                continue
            if widget.value is None:
                continue
            if target in PERSONAL and not (target in LEGAL_PARTS and str(widget.value).isdigit()
                                           and len(str(widget.value)) < 5):
                out.personal.append(str(widget.value))
            if reference_widget(content.text_pages, widget):
                report.form_fields_skipped.append(widget.name)
                continue
            value = widget.value
            if target == 'claimed_provision':
                canonical = canonical_citation(str(value))
                found = None
                if canonical and codes is not None:
                    try:
                        found = codes.provision(canonical, 'B')
                    except Exception:
                        found = None
                if not found:
                    out.unresolved.append(UnresolvedCitation(entered=str(value), source_ref=file_id, page=widget.page))
                    continue
                value = canonical
            source = Source(type='file', ref=file_id, page=widget.page, bbox=widget.rect,
                            quote=str(widget.value) if widget.kind == 'text' else widget.name)
            origin = Origin(file_id, widget.page, project_context=True)
            _add(out, origin, target, value, 'exact', None, None, None, 1.0, 'form', source=source)
            report.form_fields_read += 1
    if content.form != 'scc_variance':
        # The SCC form's printed text is the template, not the applicant's words.
        # Only project passages give project facts; a reference document's examples never do.
        scoped = {page.number: page.text for page in project_pages(content.text_pages)}
        project = []
        for page in content.text_pages:
            text = scoped[page.number]
            if text.strip():
                report.project_pages.append(page.number)
                project.append(Page(page.number, text, page.boxes))
            origin = Origin(file_id, page.number, page.box, project_context=True)
            part = read_text(text, origin, codes=codes, outbound=outbound, citation_text=page.text)
            out.merge(part)
            report.text_pages_read.append(page.number)
        _semantic_pages(out, project, report, transport=transport, outbound=outbound,
                        status=status, budget=budget)
        _pictures(out, report, content.blank_pages, lambda page: picture_page(data, page),
                  transport=transport, status=status, budget=budget, outbound=outbound, allowed=pictures)
    else:
        report.pages_read = list(range(1, content.pages + 1))
    _report(out, report)
    if report.form_fields_read and not report.pages_read and report.pictures_not_read_reason == 'AI is off':
        report.reason = FORM_ONLY
    if report.pages_read and not report.project_pages and not report.form_fields_read:
        note = ('No current-project passages were identified. This document remains reference context; '
                'type project facts in the description or attach a project brief with explicit project labels.')
        report.reason = f'{report.reason} {note}' if report.reason else note
    return out
