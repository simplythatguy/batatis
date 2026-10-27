"""Supporting-documents panel: type, issuer, date, evidence rung, seal, responsible person.

Every cell is read from a labelled line in the attachment (or from Section D of
the form, or from applicant-entered metadata on a Batatis case) and points to
its source. Anything not read is "unknown". The rung is what the document says
it is, not an assessment of it. A seal mention is reported as "stated", never
as verified: authenticity cannot be read from text.
"""
from __future__ import annotations

import re

from ..models_review import Attribute, DocumentRow, Pointer
from .pdf_reader import ReadFile

# (rung, pattern) in priority order. Rung names are engine.section_d evidence types.
_RUNGS = (
    ('CCMC evaluation', re.compile(r'\bCCMC\b.*\b(?:evaluation|listing)\b|\bCanadian Construction Materials Centre\b', re.I)),
    ('ICC-ES evaluation', re.compile(r'\bICC-ES\b', re.I)),
    ('ISO 17065 certification', re.compile(r'\bISO(?:/IEC)?\s*17065\b', re.I)),
    ('ISO 17025 test report', re.compile(r'\bISO(?:/IEC)?\s*17025\b', re.I)),
    ('existing STANDATA variance', re.compile(r'\bSTANDATA\b', re.I)),
    ('registered professional opinion', re.compile(r'\b(?:professional opinion|letter of assurance|P\.\s?Eng\.?|'
                                                   r'Professional Engineer|Architect)\b', re.I)),
    ('engineering review', re.compile(r'\bengineering (?:review|analysis|assessment)\b', re.I)),
    ("manufacturer's literature", re.compile(r"\b(?:brochure|product literature|data ?sheet|manufacturer'?s? literature|"
                                             r'installation guide)\b', re.I)),
)
_TYPES = (
    ('test report', re.compile(r'\btest report\b|\breport of tests?\b', re.I)),
    ('evaluation report', re.compile(r'\bevaluation report\b|\bevaluation listing\b', re.I)),
    ('engineering analysis', re.compile(r'\b(?:engineering analysis|calculations?|engineering assessment)\b', re.I)),
    ('professional letter', re.compile(r'\b(?:letter of assurance|professional opinion|engineer\'?s letter)\b', re.I)),
    ('drawing', re.compile(r'\b(?:drawing|sheet [A-Z]?\d|site plan|elevation)\b', re.I)),
    ('manufacturer literature', re.compile(r'\b(?:brochure|product literature|data ?sheet|installation guide)\b', re.I)),
)
_LABELLED = {
    'issuer': re.compile(r'^\s*(?:issued by|issuer|prepared by|laboratory|author|authored by|company)\s*[:\-]\s*(.+?)\s*$',
                         re.I | re.M),
    'date': re.compile(r'^\s*(?:date(?: of issue)?|issued|dated|issue date|revision date)\s*[:\-]\s*(.+?)\s*$', re.I | re.M),
    'responsible': re.compile(r'^\s*(?:responsible(?: person| professional)?|signed by|engineer of record|'
                              r'prepared and sealed by)\s*[:\-]\s*(.+?)\s*$', re.I | re.M),
    'title': re.compile(r'^\s*(?:title|document|report title)\s*[:\-]\s*(.+?)\s*$', re.I | re.M),
}
_DATE_VALUE = re.compile(r'\b(?:\d{4}-\d{2}-\d{2}|\d{1,2}\s+[A-Z][a-z]+\s+\d{4}|[A-Z][a-z]+\s+\d{1,2},\s+\d{4})\b')
_SEAL = re.compile(r'\b(?:seal(?:ed)?|stamp(?:ed)?|permit to practi[cs]e|APEGA|AAA)\b', re.I)
_PLACEHOLDER = re.compile(r'^(?:tbd|n/?a|unknown|none|-+|to follow|pending)\.?$', re.I)


def _attr(value: str | None, file: str, page: int | None, quote: str | None, read: ReadFile | None = None,
          form_field: str | None = None, bbox=None) -> Attribute:
    if not value or _PLACEHOLDER.match(value.strip()):
        return Attribute()
    if bbox is None and read is not None and page is not None and quote:
        bbox = read.locate(page - 1, quote)
    return Attribute(value=value.strip(), known=True,
                     source=Pointer(file=file, page=page, form_field=form_field, bbox=bbox, quote=quote))


def _first_line(pattern, pages):
    for page in pages:
        match = pattern.search(page.text)
        if match:
            line = page.text[page.text.rfind('\n', 0, match.start()) + 1:].split('\n', 1)[0].strip()
            return match, page.page + 1, line or match.group(0)
    return None, None, None


def attachment_row(read: ReadFile, index: int) -> DocumentRow:
    uncertain = set(read.unreadable_pages())
    pages = [page for page in read.text_pages if page.page not in uncertain]
    row = {}
    for key, pattern in _LABELLED.items():
        match, page, line = _first_line(pattern, pages)
        value = match.group(1) if match else None
        if key == 'date' and value and not _DATE_VALUE.search(value):
            value = None
        row[key] = _attr(value, read.name, page, line, read)
    for key, table in (('type', _TYPES), ('evidence_rung', _RUNGS)):
        row[key] = Attribute()
        for label, pattern in table:
            match, page, line = _first_line(pattern, pages)
            if match:
                row[key] = _attr(label, read.name, page, line, read)
                break
    match, page, line = _first_line(_SEAL, pages)
    row['seal'] = (_attr('seal stated in text (not verified)', read.name, page, line, read) if match
                   else Attribute())
    if not row['title'].known:
        first = next((p for p in pages if p.text.strip()), None)
        if first is not None:
            line = first.text.strip().split('\n', 1)[0].strip()[:200]
            row['title'] = _attr(line, read.name, first.page + 1, line, read)
    return DocumentRow(id=f'doc{index}', file=read.name, title=row['title'], type=row['type'], issuer=row['issuer'],
                       date=row['date'], evidence_rung=row['evidence_rung'], seal=row['seal'],
                       responsible=row['responsible'],
                       note='Read from labelled lines in the attachment. Not reviewed for adequacy.')


def unreadable_row(read: ReadFile, index: int) -> DocumentRow:
    return DocumentRow(id=f'doc{index}', file=read.name, title=Attribute(value=read.name, known=True,
                       source=Pointer(file=read.name)), type=Attribute(), issuer=Attribute(), date=Attribute(),
                       evidence_rung=Attribute(), seal=Attribute(), responsible=Attribute(),
                       note=read.note or 'The contents were not read.')


def _matches(listed: str, row: DocumentRow) -> bool:
    def identity(text):
        text = re.sub(r'\.(?:pdf|txt|md)$', '', text or '', flags=re.I)
        return ' '.join(word for word in re.findall(r'[a-z0-9]+', text.casefold())
                        if word not in {'synthetic', 'example', 'data'})
    name = identity(listed)
    return bool(name) and name in {identity(row.title.value), identity(row.file)}


def merge_section_d(rows: list[DocumentRow], listed: list[tuple[int, str, str, Pointer, Pointer]]) -> list[DocumentRow]:
    """Attach Section D rows (document name, responsible) to uploaded attachments when the names match;
    listed documents with no matching upload get their own row with file=None."""
    out = list(rows)
    for number, name, responsible, name_ptr, resp_ptr in listed:
        target = next((row for row in out if row.file and not row.listed_in_section_d and _matches(name, row)), None)
        responsible_attr = (Attribute(value=responsible, known=True, source=resp_ptr)
                            if responsible and not _PLACEHOLDER.match(responsible) else Attribute())
        if target is not None:
            target.listed_in_section_d = True
            if responsible_attr.known:
                target.responsible = responsible_attr
            continue
        out.append(DocumentRow(
            id=f'sectiond{number}', file=None, title=Attribute(value=name, known=True, source=name_ptr),
            type=Attribute(), issuer=Attribute(), date=Attribute(), evidence_rung=Attribute(), seal=Attribute(),
            responsible=responsible_attr, listed_in_section_d=True,
            note='Listed in Section D; no uploaded file with this name was found.'))
    return out


def case_rows(case, store=None) -> list[DocumentRow]:
    """Documents panel for a Batatis case: applicant-entered metadata with its fact sources, then file text."""
    from ..process_fields import latest_fact
    from ..section_d import supporting_documents
    from .pdf_reader import read_pdf
    rows = []
    for index, doc in enumerate(supporting_documents(case), start=1):
        prefix = f'evidence.{doc.id}.'

        def cell(name, value):
            fact = latest_fact(case, prefix + name)
            if not value or fact is None:
                return Attribute()
            from .ingest import _stored
            if not _stored(fact, fact.field).confirmed:
                return Attribute()
            source = fact.source
            return Attribute(value=str(value), known=True,
                             source=Pointer(file=source.ref, page=source.page, bbox=source.bbox,
                                            quote=source.quote if source.quote and str(value) in source.quote else str(value)))

        read_row = None
        if store is not None and hasattr(store, 'get_file'):
            try:
                stored = store.get_file(case.id, doc.file.ref)
            except Exception:  # noqa: BLE001
                stored = None
            if stored and stored.get('data'):
                read = read_pdf(stored['data'], stored.get('name') or doc.file.ref)
                if read.role == 'attachment':
                    read_row = attachment_row(read, index)
        row = DocumentRow(
            id=doc.id, file=doc.file.ref, title=cell('title', doc.title if doc.title and not doc.title.startswith('(') else ''),
            type=read_row.type if read_row else Attribute(),
            issuer=cell('issuer', doc.issuer) if doc.issuer else (read_row.issuer if read_row else Attribute()),
            date=cell('date', doc.date) if doc.date else (read_row.date if read_row else Attribute()),
            evidence_rung=read_row.evidence_rung if read_row else Attribute(),
            seal=(cell('professional_seal', doc.professional_seal) if doc.professional_seal
                  else (read_row.seal if read_row else Attribute())),
            responsible=cell('responsible_party', doc.responsible_party), listed_in_section_d=True,
            note='Applicant-entered metadata; file text read where the file is stored. Not reviewed for adequacy.')
        if not row.title.known and latest_fact(case, prefix + 'title') is None:
            evidence = next((entry for entry in case.evidence if entry.id == doc.id), None)
            if evidence and evidence.description.strip():
                row.title = Attribute(value=evidence.description, known=True, source=Pointer(file=doc.file.ref))
        rows.append(row)
    return rows
