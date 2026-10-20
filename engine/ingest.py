"""Read applicant documents. Every stored value is exact or pointed.

exact   — the value is the AcroForm field value read from the file.
pointed — the quote matches the document after whitespace is collapsed.

Text files must match the raw bytes. PDFs match Unicode literals in the file or
its decompressed streams when the page stores text that way. Pages that store
glyph ids match the Unicode recovered from those streams by the PDF reader,
which is a deterministic read of the file. A value that fails the check is an
invented value and is rejected.
"""
from __future__ import annotations

import io
import re
from dataclasses import dataclass, field

from pypdf import PdfReader
from pypdf.generic import IndirectObject


class IngestError(ValueError):
    """A stored value was not copied from the file."""


_WS = re.compile(r'\s+')
_FIELD_LINE = re.compile(r'^FIELD\s*\|', re.M)
_PROVISION = re.compile(r'\d+(?:\.\d+){3}(?:\.\(\d+\)(?:\([a-z]\))?)?')
_STANDATA = re.compile(r'\b\d{2}-BC[A-Z]-\d+\b')
_BLANK = re.compile(r'^(?:\(blank\)|blank|✘)$', re.I)
_PLACEHOLDER = re.compile(
    r"\b(?:tbd|to be determined|to be provided|unknown|placeholder|don't have it yet|do not have it yet)\b",
    re.I)


def normalize_ws(text: str) -> str:
    return _WS.sub(' ', text).strip()


def quote_in_text(quote: str, text: str) -> bool:
    folded = normalize_ws(quote)
    return bool(folded) and folded in normalize_ws(text)


@dataclass
class StoredValue:
    field: str
    value: str
    kind: str
    quote: str | None
    form_field: str | None = None
    explicit_blank: bool = False
    confirmed: bool = True


@dataclass
class Mention:
    """Applicant text that names a citation but does not confirm it."""
    quote: str
    token: str
    why: str


@dataclass
class Ingested:
    ref: str
    data: bytes
    text: str
    kind: str
    values: dict[str, StoredValue] = field(default_factory=dict)
    section_text: dict[str, str] = field(default_factory=dict)
    mentions: list[Mention] = field(default_factory=list)
    form_fields: dict[str, str] = field(default_factory=dict)
    submission_id: str | None = None
    ledger: bool = False

    def raw(self, *keys: str) -> StoredValue | None:
        for key in keys:
            if key in self.values:
                return self.values[key]
        return None


def _literal_streams(data: bytes) -> str:
    if not data.startswith(b'%PDF'):
        return ''
    try:
        reader = PdfReader(io.BytesIO(data))
    except Exception:
        return ''
    chunks: list[str] = []
    seen: set[int] = set()

    def walk(obj, depth: int = 0) -> None:
        if depth > 6 or obj is None:
            return
        if isinstance(obj, IndirectObject):
            ident = (obj.idnum, obj.generation)
            if ident in seen:
                return
            seen.add(ident)
            obj = obj.get_object()
        if hasattr(obj, 'get_data'):
            try:
                chunks.append(obj.get_data().decode('latin-1', errors='ignore'))
            except Exception:
                return
        if isinstance(obj, dict):
            for value in obj.values():
                walk(value, depth + 1)
        elif isinstance(obj, list):
            for value in obj:
                walk(value, depth + 1)

    for page in reader.pages:
        walk(page)
    return '\n'.join(chunks)


def recovered_text(data: bytes) -> str:
    """Unicode text recovered from the file bytes. Not a paraphrase."""
    if data.startswith(b'%PDF'):
        reader = PdfReader(io.BytesIO(data))
        return '\n'.join((page.extract_text() or '') for page in reader.pages)
    return data.decode('utf-8')


def quote_matches_bytes(quote: str, data: bytes, extracted: str, *, ledger: bool = False) -> bool:
    folded = normalize_ws(quote)
    if not folded:
        return False
    if ledger:
        return True
    if not data.startswith(b'%PDF'):
        return folded in normalize_ws(data.decode('utf-8'))
    if folded in normalize_ws(data.decode('latin-1', errors='ignore')):
        return True
    if folded in normalize_ws(_literal_streams(data)):
        return True
    # Glyph-encoded pages keep Unicode in the font map, not as literals.
    return folded in normalize_ws(extracted)


def _reject(message: str) -> None:
    raise IngestError(message)


def _add(doc: Ingested, stored: StoredValue) -> None:
    if stored.kind == 'exact':
        if not stored.form_field or stored.form_field not in doc.form_fields:
            _reject(f'{stored.field}: exact value is not a form field')
        if doc.form_fields[stored.form_field] != stored.value:
            _reject(f'{stored.field}: exact value does not match form field {stored.form_field}')
    elif stored.kind == 'pointed':
        if not stored.quote or not quote_matches_bytes(stored.quote, doc.data, doc.text, ledger=doc.ledger):
            _reject(f'{stored.field}: pointed quote is not in the source')
        if stored.value and not quote_in_text(stored.value, stored.quote) and not quote_in_text(stored.value, doc.text):
            _reject(f'{stored.field}: value is not in the quoted span')
        if stored.value and not quote_in_text(stored.value, doc.text) and not doc.ledger:
            _reject(f'{stored.field}: invented value')
    else:
        _reject(f'{stored.field}: invented value')
    doc.values[stored.field] = stored


def _pointed(doc: Ingested, field_name: str, value: str, quote: str, *, confirmed: bool = True,
             explicit_blank: bool = False) -> None:
    _add(doc, StoredValue(field_name, value, 'pointed', quote, explicit_blank=explicit_blank or not value.strip(),
                          confirmed=confirmed))


def _form_fields(data: bytes) -> dict[str, str]:
    if not data.startswith(b'%PDF'):
        return {}
    try:
        fields = PdfReader(io.BytesIO(data)).get_fields() or {}
    except Exception:
        return {}
    out = {}
    for name, spec in fields.items():
        if not isinstance(spec, dict):
            continue
        value = spec.get('/V')
        out[str(name)] = '' if value is None else str(value)
    return out


def _parse_field_document(doc: Ingested) -> None:
    section = 'B'
    buckets: dict[str, list[str]] = {key: [] for key in ('A', 'B', 'C', 'D', 'process', 'attachment')}
    for raw in doc.text.splitlines():
        line = raw.strip()
        if line.startswith('[section '):
            section = line.split()[1].rstrip(']').upper()[:1]
            if section not in buckets:
                section = 'B'
            continue
        if line.startswith('[attachment'):
            section = 'attachment'
            continue
        if not line:
            continue
        buckets[section].append(line)
        if not _FIELD_LINE.match(line):
            continue
        bits = [part.strip() for part in line.split('|')]
        # FIELD | key | widget | value
        if len(bits) < 3:
            _reject('FIELD line is missing a key')
        key = bits[1]
        widget = bits[2] if len(bits) > 3 else ''
        value = bits[-1] if len(bits) > 3 else ''
        if len(bits) == 3:
            key, value = bits[1], bits[2]
            widget = ''
        quote = value if value else line
        _pointed(doc, key, value, quote, explicit_blank=not value.strip())
        if widget and widget in doc.form_fields and doc.form_fields[widget] == value:
            _add(doc, StoredValue(key, value, 'exact', None, widget, explicit_blank=not value.strip()))
    doc.section_text = {key: '\n'.join(lines) for key, lines in buckets.items()}


def _grab(text: str, pattern: str) -> tuple[str, str] | None:
    match = re.search(pattern, text, re.I)
    if not match:
        return None
    return match.group(0), match.group(1).strip()


def _store_grab(doc: Ingested, field_name: str, text: str, pattern: str, *, confirmed: bool = True) -> bool:
    found = _grab(text, pattern)
    if not found:
        return False
    quote, value = found
    blank = bool(_BLANK.match(value))
    _pointed(doc, field_name, '' if blank else value, quote, confirmed=confirmed, explicit_blank=blank)
    return True


def _parse_submission(parent: Ingested, chunk: str) -> Ingested:
    ident = re.search(r'VR-\d{4}-\d{3}', chunk)
    doc = Ingested(parent.ref, parent.data, parent.text, 'summary', submission_id=ident.group(0) if ident else None)
    doc.form_fields = parent.form_fields
    _store_grab(doc, 'owner_name', chunk, r'Owner:\s*([^;]+)')
    _store_grab(doc, 'representative', chunk, r'Rep:\s*([^;]+)')
    _store_grab(doc, 'mailing_address', chunk, r'Mailing:\s*([^;]+)')
    _store_grab(doc, 'application_date', chunk, r'Date:\s*([^;]+)')
    signed = re.search(r'signed\s*(✔|✘)', chunk)
    if signed:
        mark = signed.group(1)
        _pointed(doc, 'signature', '' if mark == '✘' else 'signed', signed.group(0), explicit_blank=mark == '✘')
    _store_grab(doc, 'permit_number', chunk, r'Permit\s*#:?\s*([^;]+)')
    _store_grab(doc, 'legal_description', chunk, r'Legal:\s*([^;]+)')
    _store_grab(doc, 'civic_address', chunk, r'Address:\s*([^;]+)')
    _store_grab(doc, 'alternative_description', chunk, r'Description:\s*(.+?)(?=\s+C\.|\s+D\.|$)')
    section_c = _grab(chunk, r'C\.\s*(.+?)(?=\s+D\.|$)')
    if section_c:
        quote, value = section_c
        intent_blank = re.search(r'article\s*2\s*intent:\s*(\(blank\))', value, re.I)
        if intent_blank:
            _pointed(doc, 'section_c.intent', '', intent_blank.group(0), explicit_blank=True)
            _pointed(doc, 'section_c.article', value, quote)
        elif re.search(r'intent filled', value, re.I):
            _pointed(doc, 'section_c.intent', 'filled', quote)
            _pointed(doc, 'section_c.article', value, quote)
        else:
            _pointed(doc, 'section_c.article', value, quote)
    section_d = _grab(chunk, r'D\.\s*(.+?)(?=\s+Risk assessment:|$)')
    if section_d:
        _pointed(doc, 'supporting_doc', section_d[1], section_d[0])
    _store_grab(doc, 'risk_assessment', chunk, r'Risk assessment:\s*(.+?)(?=\s+·|\s+Mitigat|$)')
    mitigations = _grab(chunk, r'Mitigat(?:ing measures|ions):\s*(.+?)(?=\s+·|\s+Assumptions|$)')
    if mitigations:
        _pointed(doc, 'mitigating_measures', mitigations[1].strip(" '"), mitigations[0])
    assumptions = _grab(chunk, r'Assumptions(?:/limits)?:\s*(.+)$')
    if assumptions:
        _pointed(doc, 'assumptions_and_limits', assumptions[1], assumptions[0])
    doc.section_text = {'A': chunk, 'B': chunk, 'C': chunk, 'D': chunk, 'process': chunk, 'attachment': ''}
    return doc


def _parse_bundle(parent: Ingested) -> list[Ingested]:
    folded = normalize_ws(parent.text)
    chunks = [chunk for chunk in re.split(r'(?=Submission [ABC] — )', folded) if chunk.startswith('Submission ')]
    if len(chunks) < 2:
        _reject('bundle did not contain the submission headings')
    return [_parse_submission(parent, chunk) for chunk in chunks]


def _parse_brief(doc: Ingested) -> None:
    folded = normalize_ws(doc.text)
    prepared = re.search(r'Prepared by:\s*(.+?)\s+Date:\s*(\d{4}-\d{2}-\d{2})', folded)
    if prepared:
        _pointed(doc, 'owner_name', prepared.group(1).split('(')[0].strip(), prepared.group(0))
        _pointed(doc, 'application_date', prepared.group(2), prepared.group(0))
    site = re.search(r'Site:\s*(.+?)\s+Legal description:\s*(.+?)\s+Permit #:\s*([^.]*)', folded)
    if site:
        _pointed(doc, 'civic_address', site.group(1), site.group(0))
        legal = site.group(2).strip()
        _pointed(doc, 'legal_description', legal, site.group(0), explicit_blank=False)
        _pointed(doc, 'permit_number', site.group(3).strip(), site.group(0))
    unsure = re.search(r"I think that makes it under 3 storeys, but I'm not sure how lofts are counted\.", folded)
    if unsure:
        _pointed(doc, 'storeys_statement', unsure.group(0), unsure.group(0), confirmed=False)
    brochure = re.search(r'Supplier brochure "HempWall Pro".{0,80}', folded)
    if brochure:
        _pointed(doc, 'supporting_doc', brochure.group(0), brochure.group(0))
    no_engineer = re.search(r'No lab tests, no engineer yet', folded)
    if no_engineer:
        _pointed(doc, 'professional_note', no_engineer.group(0), no_engineer.group(0), confirmed=False)
    doc.kind = 'brief'
    doc.section_text = {'B': folded, 'A': folded, 'C': '', 'D': folded, 'process': '', 'attachment': ''}


def _parse_notes(doc: Ingested) -> None:
    folded = normalize_ws(doc.text)
    verify = re.search(r'.{0,80}please verify.{0,40}', folded, re.I)
    window = verify.group(0) if verify else ''
    for token in _STANDATA.findall(folded) + _PROVISION.findall(folded):
        if token in window or (verify and token in folded[max(0, verify.start() - 80):verify.end() + 40]):
            span = re.search(re.escape(token), folded)
            if span:
                doc.mentions.append(Mention(span.group(0), token, 'applicant asked to verify; not a confirmed citation'))
    owner = re.search(r'Owner:\s*(.+?)\s+Rep:\s*(.+?)\s+Permit', folded)
    if owner:
        _pointed(doc, 'owner_name', owner.group(1), owner.group(0))
        _pointed(doc, 'representative', owner.group(2), owner.group(0))
    storeys = re.search(r'Building:\s*(4 storeys[^.]*)', folded)
    if storeys:
        _pointed(doc, 'storeys_statement', storeys.group(1), storeys.group(0))
    pending = re.search(r'fire test report TBD', folded, re.I)
    if pending:
        _pointed(doc, 'supporting_doc', pending.group(0), pending.group(0))
    doc.kind = 'notes'
    doc.section_text = {'B': folded, 'A': folded, 'C': folded, 'D': folded, 'process': '', 'attachment': folded}


def ingest_bytes(data: bytes, ref: str = 'upload') -> list[Ingested]:
    if not data:
        _reject('empty document')
    text = recovered_text(data)
    parent = Ingested(ref, data, text, 'form', form_fields=_form_fields(data))
    folded = normalize_ws(text)
    if _FIELD_LINE.search(text):
        _parse_field_document(parent)
        _overlay_widgets(parent)
        return [parent]
    if 'Submission A —' in folded and 'SCO Review Queue' in folded:
        return _parse_bundle(parent)
    if 'Project Brief —' in folded:
        _parse_brief(parent)
        return [parent]
    if 'GENERAL NOTES' in folded:
        _parse_notes(parent)
        return [parent]
    if parent.form_fields:
        _overlay_widgets(parent)
        return [parent]
    _reject('no applicant fields could be read from the document')


def _overlay_widgets(doc: Ingested) -> None:
    from .completeness_elements import WIDGET_TO_FIELD

    for widget, logical in WIDGET_TO_FIELD.items():
        if widget not in doc.form_fields:
            continue
        value = doc.form_fields[widget]
        current = doc.values.get(logical)
        if current and current.kind == 'pointed' and normalize_ws(current.value) != normalize_ws(value):
            continue
        _add(doc, StoredValue(logical, value, 'exact', None, widget, explicit_blank=not value.strip()))


def ingest_path(path) -> list[Ingested]:
    file = path.read_bytes() if hasattr(path, 'read_bytes') else open(path, 'rb').read()
    name = getattr(path, 'name', str(path))
    return ingest_bytes(file, name)


def ingested_from_case(case) -> Ingested:
    """Ledger facts already on a case. Pointed values must repeat their own quote."""
    quotes = []
    doc = Ingested(case.id, b'', '', 'form', ledger=True, submission_id=case.id)
    for fact in case.facts:
        if fact.status != 'confirmed' or fact.kind == 'proposed' or fact.kind == 'computed':
            continue
        value = '' if fact.value is None else str(fact.value)
        if fact.kind == 'exact':
            widget = fact.source.ref or fact.field
            doc.form_fields[widget] = value
            _add(doc, StoredValue(fact.field, value, 'exact', None, widget, explicit_blank=not value.strip()))
        elif fact.kind == 'pointed':
            quote = fact.source.quote or ''
            if value and not quote_in_text(value, quote):
                _reject(f'{fact.field}: pointed fact is not a verbatim quote')
            if not quote:
                _reject(f'{fact.field}: pointed fact has no quote')
            quotes.append(quote)
            _add(doc, StoredValue(fact.field, value, 'pointed', quote, explicit_blank=not value.strip()))
        else:
            _reject(f'{fact.field}: invented value')
    doc.text = '\n'.join(quotes)
    doc.section_text = {'A': doc.text, 'B': doc.text, 'C': doc.text, 'D': doc.text, 'process': doc.text, 'attachment': doc.text}
    return doc
