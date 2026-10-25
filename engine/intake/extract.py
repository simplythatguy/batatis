"""Intake extraction: rules first, then the model, then ledger facts with pointers.

A rule hit becomes a `pointed` fact quoting the words that state it (a unit conversion adds a
`computed` fact over the value as written). A fillable-form value becomes an `exact` fact. A model
fact is `pointed` only when the rules re-derive it from the quoted sentence, otherwise `proposed`.
Every fact is unconfirmed; the applicant confirms. Article numbers the applicant typed are kept
only when they resolve in NBC(AE) 2023, 2nd printing; the rest are listed as unresolved text.
"""
from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from typing import Callable

from ..models import Fact, Source
from ..redact import scrub
from ..models_intake import DocumentReview, FactPointer, FieldConflict, FileReport, ModelPass, UnresolvedCitation
from . import model as model_pass
from .pdf import FORM_ONLY, MAX_PAGES, NO_TEXT, NOT_A_PDF, SCC_MAP, TOO_LONG, NotAPdf, read_pdf
from .rules import PERSONAL, Hit, canonical_citation, read

DESCRIPTION = 'description'
DESCRIPTION_REF = 'intake:description'
MODEL_PAGES = 5                                  # text pages per file sent to the model
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

    def merge(self, other: Extraction) -> None:
        self.facts += other.facts
        self.pointers += other.pointers
        self.conflicts += other.conflicts
        self.unresolved += other.unresolved
        self.files += other.files
        mine, theirs = self.model, other.model
        if theirs.status != 'off':
            mine.status = theirs.status if mine.status in ('off', 'not_needed') else mine.status
            mine.model = theirs.model or mine.model
            mine.reason = mine.reason or theirs.reason
        for name in ('pointed', 'proposed', 'dropped'):
            setattr(mine, name, getattr(mine, name) + getattr(theirs, name))
        for name in ('input_tokens', 'output_tokens'):
            a, b = getattr(mine, name), getattr(theirs, name)
            setattr(mine, name, None if a is None or b is None else a + b)


@dataclass(frozen=True)
class Origin:
    """Where a text came from: the description, or one page of a file."""
    ref: str                                     # 'description' or the file id
    page: int | None = None
    box: Callable[[int, int], tuple[float, float, float, float] | None] | None = None

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
                                    page=origin.page, start=start, end=end, verified=verified))
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
              transport: model_pass.Transport | None = None, status: str = 'off') -> Extraction:
    """Rules over `text`, then the model over its scrubbed copy for the fields still empty."""
    out = Extraction()
    reading = read(text)
    for hit in reading.hits:
        _hit_facts(out, origin, text, hit)
    for name, hits in reading.conflicts.items():
        values = list(dict.fromkeys(json.dumps(h.value) for h in hits if h.value != -1))
        out.conflicts.append(FieldConflict(field=name, values=[json.loads(v) for v in values],
                                           quotes=[text[h.start:h.end] for h in hits], source_ref=origin.ref,
                                           page=origin.page))
    _citations(out, origin, text, reading.citations, codes)
    found = {hit.field for hit in reading.hits} | set(reading.conflicts)
    if transport is None:
        return out
    personal = [str(hit.value) for hit in reading.hits if hit.field in PERSONAL and len(str(hit.value)) >= 3]
    run = model_pass.run(text, outbound(text, personal), transport, skip=found, status=status)
    out.model = ModelPass(status=run.status, model=model_pass.MODEL if run.status == 'live' else None,
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


# ---------------------------------------------------------------- files

def _scc_map() -> dict[str, str]:
    data = json.loads(SCC_MAP.read_text(encoding='utf-8'))
    mapped = {name: spec['fact'] for name, spec in data['text_fields'].items() if spec['section'] != 'C'}
    mapped.update({name: spec['fact'] for name, spec in data['checkboxes'].items()})
    for index, row in enumerate(data['section_c_rows']):
        mapped[row['article']] = 'claimed_provision'
    return mapped


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
              cache: dict | None = None) -> Extraction:
    out = Extraction()
    report = FileReport(file_id=file_id, name=name, status='not_read')
    out.files.append(report)
    try:
        content = _parsed(cache, file_id, data)
    except NotAPdf:
        report.reason = NOT_A_PDF
        return out
    report.pages = content.pages
    if content.reason:
        report.reason = content.reason
        report.pages_not_read = list(range(1, content.pages + 1))
        return out
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
            origin = Origin(file_id, widget.page)
            _add(out, origin, target, value, 'exact', None, None, None, 1.0, 'form', source=source)
            report.form_fields_read += 1
    if content.form != 'scc_variance':
        # The SCC form's printed text is the template, not the applicant's words.
        for index, page in enumerate(content.text_pages):
            origin = Origin(file_id, page.number, page.box)
            part = read_text(page.text, origin, codes=codes, outbound=outbound,
                             transport=transport if index < MODEL_PAGES else None, status=status)
            out.merge(part)
            report.pages_read.append(page.number)
    else:
        report.pages_read = list(range(1, content.pages + 1))
    report.pages_not_read = sorted(set(content.blank_pages) - set(report.pages_read))
    report.facts = sum(1 for p in out.pointers if p.source_ref == file_id)
    if content.truncated:
        report.pages_not_read += list(range(MAX_PAGES + 1, content.pages + 1))
    if report.form_fields_read and not report.pages_read:
        # A fillable form with no text layer: its fields were read, its printed pages were not.
        report.status = 'partly_read' if report.pages_not_read else 'read'
        report.reason = FORM_ONLY if report.pages_not_read else None
    elif report.pages_read and not report.pages_not_read:
        report.status = 'read'
    elif report.pages_read:
        report.status = 'partly_read'
        report.reason = TOO_LONG if content.truncated else NO_TEXT
    else:
        report.reason = NO_TEXT
    return out
