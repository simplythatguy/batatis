"""Normalize saved facts and visible PDF readings without deciding completeness."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import re

from .export.challenge_form import LEGAL_ROW
from .models_review import Attribute, DocumentRow, FieldReading, InputFile, Pointer
from .process_fields import latest_fact
from .review.documents import attachment_row, case_rows, merge_section_d, unreadable_row
from .review.ingest import Ingested, StoredValue, ingested_from_case
from .review.passages import TEXT_FIELDS, _ENGINEERING, passage_value
from .review.pdf_reader import FieldValue, ReadFile, field_maps, read_pdf
from .models_completeness import AdministrativeItem, ProfessionalDeclaration
from .completeness_elements import BY_FIELD


@dataclass
class Snapshot:
    document: Ingested
    files: list[InputFile] = field(default_factory=list)
    fields: list[FieldReading] = field(default_factory=list)
    documents: list[DocumentRow] = field(default_factory=list)
    corpus: list[tuple[str, int | None, str]] = field(default_factory=list)
    applicant_corpus: list[tuple[str, int | None, str]] = field(default_factory=list)
    unreadable: list[Pointer] = field(default_factory=list)
    reads: list[ReadFile] = field(default_factory=list)
    form: ReadFile | None = None
    field_map: dict | None = None
    context_items: list[AdministrativeItem] = field(default_factory=list)
    professional_declarations: list[ProfessionalDeclaration] = field(default_factory=list)


def _label(fmap: dict, name: str) -> tuple[str, str]:
    if name == LEGAL_ROW and name in fmap.get('printed', {}):
        return 'Legal description', 'B'
    spec = fmap['text_fields'].get(name) or fmap['checkboxes'].get(name)
    if spec:
        section = spec['section'] if spec['section'] in 'ABCD' else 'A'
        return spec['label'], section
    for index, row in enumerate(fmap['section_c_rows'], start=1):
        for key, widget in row.items():
            if widget == name:
                return f'Section C row {index} {key}', 'C'
    for index, row in enumerate(fmap['section_d_rows'], start=1):
        for key, widget in row.items():
            if widget == name:
                return f'Section D row {index} {"document" if key == "document" else "responsible person"}', 'D'
    if name == fmap.get('supporting_document_field'):
        return 'Supporting documents and responsible persons', 'D'
    return name, 'A'


def _pointer(read: ReadFile, value: FieldValue) -> Pointer:
    return Pointer(file=read.name, page=value.page + 1 if value.page is not None else None, form_field=value.name,
                   bbox=tuple(round(v, 1) for v in value.rect) if value.rect else None,
                   quote=value.value or None)


def _stored(logical: str, value: FieldValue, read: ReadFile) -> StoredValue | None:
    source = {'type': 'file', 'ref': read.name, 'page': value.page + 1 if value.page is not None else None,
              'bbox': list(value.rect) if value.rect else None, 'quote': value.value or None}
    return StoredValue(logical, value.value, 'exact', value.value or None, form_field=value.name,
                       explicit_blank=value.status == 'blank', source=source, input_field=logical, status=value.status, reason=value.reason,
                       pointers=[_pointer(read, value).model_dump()])


def _legal(read: ReadFile) -> tuple[StoredValue | None, list[str]]:
    fields = read.fields
    printed = fields.get(LEGAL_ROW)
    if printed is not None and printed.status == 'present':
        return _stored('legal_description', printed, read), []
    lbp, ats = ('Lot', 'Block', 'Plan'), ('QTR', 'SEC', 'TWP', 'RGE', 'MER')
    for group in (lbp, ats):
        if all(fields.get(name) and fields[name].status == 'present'
               and fields[name].value.strip().casefold() not in ('n/a', 'na', 'tbd', 'unknown') for name in group):
            value = ', '.join(f'{name} {fields[name].value}' for name in group)
            return StoredValue('legal_description', value, 'exact', fields[group[0]].value,
                               form_field=group[0], source={'type': 'file', 'ref': read.name,
                                                            'page': fields[group[0]].page + 1,
                                                            'quote': fields[group[0]].value},
                               input_field='legal_description'), []
    states = [fields[name].status for name in (LEGAL_ROW, *lbp, *ats) if name in fields]
    if any(state == 'not_found' for state in states):
        return None, []
    blank = [name for name in lbp + ats if name in fields and fields[name].status != 'present']
    return StoredValue('legal_description', '', 'exact', None, form_field='Lot', explicit_blank=True,
                       source={'type': 'file', 'ref': read.name, 'page': 1}, input_field='legal_description'), blank


def _unique_uploads(uploads: list[tuple[str, bytes]]) -> list[tuple[str, bytes]]:
    """Disambiguate source names before any reading or pointer is built; retain every upload."""
    reserved = {name for name, _data in uploads}
    used = set()
    sources = []
    for name, data in uploads:
        source = name
        if source in used:
            stem, extension = (name[:-4], name[-4:]) if name.lower().endswith('.pdf') else (name, '')
            number = 2
            while True:
                suffix = f' ({number})'
                source = f'{stem[:200 - len(suffix) - len(extension)]}{suffix}{extension}'
                if source not in reserved and source not in used:
                    break
                number += 1
        used.add(source)
        sources.append((source, data))
    return sources


def from_uploads(uploads: list[tuple[str, bytes]]) -> Snapshot:
    from .review.package_sources import visible_sources
    originals = [read_pdf(data, name) for name, data in _unique_uploads(uploads)]
    reads, context, segments, declarations = [], [], [], []
    for read in originals:
        main, records, sources, declared = visible_sources(read)
        reads.append(main)
        context.extend(records)
        segments.extend(sources)
        declarations.extend(declared)
    reads.extend(segment for segment, _values, _pointer in segments)
    forms = [read for read in reads if read.role.startswith('scc_form')]
    form = forms[0] if forms else None
    fmap = form.field_map if form else None
    attachments = [read for read in reads if read.role == 'attachment']
    pages = [(read.name, page.page + 1, page.text) for read in reads for page in read.text_pages]
    snapshot = Snapshot(Ingested('upload', b'', '', 'form'), reads=reads, form=form, field_map=fmap,
                        context_items=context, professional_declarations=declarations)
    for read in originals:
        snapshot.files.append(InputFile(name=read.name, sha256=read.sha256, size=read.size, pages=read.pages,
                                        role=read.role, form_version=read.form_version, note=read.note))
    for read in reads:
        snapshot.unreadable += [Pointer(file=read.name, page=page + 1) for page in read.unreadable_pages()]
        if read.role == 'unreadable':
            snapshot.unreadable.append(Pointer(file=read.name, page=1 if read.pages else None))
    values = {}
    widget_for = {'owner_name': 'Owner', 'application_date': 'Date of Reqeuest', 'representative': 'Owner Rep',
                  'mailing_address': 'Mailing Address', 'civic_address': 'Municipal Address',
                  'code_or_standard': 'Code or Standard', 'section_c.intent': 'Intent statement',
                  'supporting_doc': 'Supporting Doc', 'responsible_party': 'Name Responsible',
                  'owner_signature_date': 'Date1', 'owner_rep_signature_date': 'Date2'}
    if form:
        fmap = fmap or next((m for m in field_maps() if m['version'] == form.form_version), field_maps()[-1])
        snapshot.field_map = fmap
        for name, value in sorted(form.fields.items()):
            label, section = _label(fmap, name)
            snapshot.fields.append(FieldReading(field=name, label=label, section=section, status=value.status,
                                                value=value.value if value.status == 'present' else None,
                                                reason=value.reason, pointer=_pointer(form, value)))
        for logical, widget in widget_for.items():
            if widget in form.fields:
                values[logical] = _stored(logical, form.fields[widget], form)
        scope = form.fields.get('Check Box')
        if scope:
            values['scope'] = _stored('scope', scope, form)
            if scope.status != 'not_found':
                values['scope'].value = 'jurisdiction' if scope.status == 'present' and scope.value else 'site'
        legal, _blank = _legal(form)
        if legal is None:
            cells = [value for name, value in form.fields.items()
                     if name in (LEGAL_ROW, 'Lot', 'Block', 'Plan', 'QTR', 'SEC', 'TWP', 'RGE', 'MER')
                     and value.status == 'not_found']
            legal = StoredValue('legal_description', '', 'exact', None, status='not_found',
                                reason='Part of the legal description could not be read confidently.',
                                pointers=[_pointer(form, cell).model_dump() for cell in cells])
        values['legal_description'] = legal
        cells = [form.fields[row['article']] for row in fmap['section_c_rows'] if row['article'] in form.fields]
        if cells:
            uncertain = [cell for cell in cells if cell.status == 'not_found']
            joined = '; '.join(cell.value for cell in cells if cell.status == 'present')
            values['section_c.article'] = StoredValue(
                'section_c.article', '' if uncertain else joined, 'exact', None if uncertain else joined or None,
                explicit_blank=not joined and not uncertain, status='not_found' if uncertain else None,
                pointers=[_pointer(form, cell).model_dump() for cell in uncertain or cells if cell.status != 'blank'])
        for name, sign in form.signatures.items():
            logical = 'owner_signature' if name == 'Signature1' else 'owner_rep_signature'
            values[logical] = _stored(logical, sign, form)
            snapshot.fields.append(FieldReading(field=name, label=logical.replace('_', ' '), section='A',
                                                status=sign.status, value=sign.value if sign.status == 'present' else None,
                                                reason=sign.reason, pointer=_pointer(form, sign)))
        # Multiple supplied forms do not establish precedence, even if the first is readable.
        if len(forms) > 1:
            for logical in list(values):
                values[logical] = StoredValue(logical, '', 'exact', None, status='not_found',
                    reason='Multiple SCC forms were supplied; the controlling form is unresolved.',
                    pointers=[Pointer(file=read.name).model_dump() for read in forms])
    texts = {}
    reads_by_name = {read.name: read for read in reads}
    for key, (label, pattern) in TEXT_FIELDS.items():
        found = passage_value(reads, key)
        texts[key] = found
        pointers = found.pointers or [Pointer(file=found.file or (form.name if form else 'upload'),
                                            page=found.page, quote=found.quote)]
        values[key] = StoredValue(key, found.value if found.status == 'present' else '', 'pointed',
                                 found.quote if found.status != 'not_found' else None,
                                 explicit_blank=found.status == 'blank', status=found.status, reason=found.reason,
                                 source={'type': 'file', 'ref': pointers[0].file, 'page': pointers[0].page,
                                         'quote': pointers[0].quote if found.status != 'not_found' else None},
                                 pointers=[pointer.model_dump() for pointer in pointers])
        section = 'process' if key not in ('alternative_description', 'professional_name',
                                          'professional_qualifications') else ('B' if key == 'alternative_description' else 'D')
        pointer = pointers[0].model_copy(update={'quote': None}) if found.status == 'not_found' else pointers[0]
        snapshot.fields.append(FieldReading(field=key, label=label, section=section, status=found.status,
                                            value=found.value if found.status == 'present' else None,
                                            reason=found.reason, pointer=pointer))
    scope_readings = [(read, page, match) for read in forms for page in read.text_pages
                      for match in re.finditer(r'(?m)^Scope:[ \t]*([^\n]+)', page.text)]
    if len(scope_readings) == 1:
        read, page, match = scope_readings[0]
        if page.page not in read.unreadable_pages():
            scope_text = match.group(1).strip()
            recognized = scope_text.casefold() in {'site', 'site-specific', 'site specific', 'single location',
                                                   'jurisdiction', 'jurisdiction-wide', 'jurisdiction wide', 'all locations'}
            values['scope'] = StoredValue('scope', scope_text if recognized else '', 'pointed',
                match.group(0) if recognized else None, status='present' if recognized else 'not_found',
                reason='' if recognized else 'The site or jurisdiction-wide scope is unresolved; confirm it.',
                source={'type': 'file', 'ref': read.name, 'page': page.page + 1, 'quote': match.group(0)},
                pointers=[Pointer(file=read.name, page=page.page + 1, quote=match.group(0)).model_dump()])
    blob = '\n'.join(text for _f, _p, text in pages)
    engineering = _ENGINEERING.search(blob)
    if engineering:
        values['engineering_required'] = StoredValue('engineering_required', engineering.group(1), 'pointed',
                                                     engineering.group(0))
    narrative_pages = {(pointer.file, pointer.page) for found in texts.values() for pointer in found.pointers}
    narrative_pages.update((found.file, found.page) for found in texts.values() if found.file)
    doc = Ingested(form.name if form else 'upload', blob.encode(), blob, 'form', values=values)
    doc.section_text = {'B': values['alternative_description'].value,
                        'C': values.get('section_c.article', StoredValue('', '', '', None)).value,
                        'attachment': '\n'.join(page.text for read in attachments for page in read.text_pages)}
    remaining_context = []
    for item in snapshot.context_items:
        if item.reason_code == 'unconfirmed' and (item.field in values or item.field in
                ('additional_location', 'second_location', 'extra_location')):
            previous = values.get(item.field)
            values[item.field] = StoredValue(item.field, '', 'pointed', None, confirmed=False,
                reason=item.reason, input_field=item.field,
                pointers=[pointer.model_dump() for pointer in item.pointers]
                    + (previous.pointers if previous else []))
            remaining_context.append(item)   # an unconfirmed latest answer blocks on its own
        elif item.reason_code == 'not_found' and item.field in BY_FIELD:
            # The saved reading was not found: the field's own check reports it as not found, never as blank.
            previous = values.get(item.field)
            values[item.field] = StoredValue(item.field, '', 'pointed', None, status='not_found',
                reason=item.reason, input_field=item.field,
                pointers=[pointer.model_dump() for pointer in item.pointers] + (previous.pointers if previous else []))
        elif item.reason_code == 'blank' and item.field == 'scope':
            # A flattened check box cannot be read; the record says no scope was answered.
            if values.get('scope') is None or values['scope'].status == 'not_found':
                values['scope'] = StoredValue('scope', '', 'exact', None, explicit_blank=True, status='blank',
                    input_field='scope', pointers=[pointer.model_dump() for pointer in item.pointers])
        elif item.reason_code == 'blank' and item.field in texts:
            # Batatis recorded this passage as unanswered. A heading found anywhere else still controls.
            if not texts[item.field].file:
                pointers = [pointer.model_dump() for pointer in item.pointers]
                values[item.field] = StoredValue(item.field, '', 'pointed', None, explicit_blank=True, status='blank',
                    source={'type': 'file', 'ref': pointers[0]['file'], 'page': pointers[0]['page'], 'quote': None},
                    pointers=pointers)
                snapshot.fields = [reading.model_copy(update={'status': 'blank', 'reason': '',
                                                              'pointer': Pointer(**pointers[0])})
                                   if reading.field == item.field else reading for reading in snapshot.fields]
        else:
            remaining_context.append(item)
    snapshot.context_items = remaining_context
    for declaration in snapshot.professional_declarations:
        owner, location = values.get('owner_name'), values.get('civic_address')
        norm = lambda value: ' '.join(value.split())
        declaration.bound_to_application = bool(owner and location and owner.confirmed and location.confirmed
            and owner.status != 'not_found' and location.status != 'not_found'
            and norm(owner.value) == norm(declaration.owner) and norm(location.value) == norm(declaration.location))
    if len(snapshot.professional_declarations) == 1 and snapshot.professional_declarations[0].bound_to_application:
        declaration = snapshot.professional_declarations[0]
        values['pathway'] = StoredValue('pathway', declaration.pathway, 'exact', declaration.pathway,
            source={'type': 'file', 'ref': declaration.pointer.file, 'page': declaration.pointer.page,
                    'quote': declaration.pathway})
    snapshot.document = doc
    snapshot.corpus = [(form.name, value.page + 1, value.value) for value in form.fields.values()
                       if value.status == 'present'] if form else []
    snapshot.corpus += pages
    snapshot.applicant_corpus = [(found.file, found.page, found.value) for found in texts.values()
                                 if found.status == 'present']
    snapshot.applicant_corpus += [(read.name, page.page + 1, page.text)
        for read in attachments for page in read.text_pages]
    snapshot.applicant_corpus += [(read.name, page.page + 1, page.text) for read in reads for page in read.text_pages
                                 if page.text.strip().startswith('Applicant supplemental statement')]
    rows = [attachment_row(read, index) if read.role == 'attachment' else unreadable_row(read, index)
            for index, read in enumerate(reads, start=1) if read.role in ('attachment', 'unreadable')]
    for row, read in zip(rows, [read for read in reads if read.role in ('attachment', 'unreadable')]):
        segment = next(((values, pointer) for source, values, pointer in segments if source is read), None)
        if segment:
            values, pointer = segment
            row.title = Attribute(value=values.get('Title') or row.title.value, known=bool(values.get('Title')),
                                  source=Pointer(**pointer.model_dump()))
            if values.get('Responsible'):
                row.responsible = Attribute(value=values['Responsible'], known=True, source=Pointer(**pointer.model_dump()))
    listed = []
    if form:
        combined = form.fields.get(fmap.get('supporting_document_field'))
        if combined and combined.status == 'present':
            entries = list(re.finditer(r'D-(\d+):\s*(.*?)(?=D-\d+:|$)', combined.value, re.S))
            for entry in entries:
                text = ' '.join(entry.group(2).split())
                title, separator, who = text.rpartition(' - ')
                listed.append((int(entry.group(1)), title if separator else text, who if separator else '',
                               _pointer(form, combined), _pointer(form, combined)))
            if not entries:
                listed.append((1, combined.value, '', _pointer(form, combined), _pointer(form, combined)))
        for number, row in enumerate(fmap['section_d_rows'], start=1):
            name, who = form.fields.get(row['document']), form.fields.get(row['responsible'])
            if name and name.status == 'present':
                listed.append((number, name.value, who.value if who and who.status == 'present' else '',
                               _pointer(form, name), _pointer(form, who) if who else _pointer(form, name)))
    snapshot.documents = merge_section_d(rows, listed)
    return snapshot


def from_case(case, store=None) -> Snapshot:
    doc = ingested_from_case(case)
    record = f'case:{case.id}'
    snapshot = Snapshot(doc, files=[InputFile(name=record, role='case_record',
                                             note='Current saved facts; file content is read only when available.')])
    for key, stored in doc.values.items():
        presence = latest_fact(case, f'presence.{key}', f'review.{key}.presence')
        if presence and presence.value in ('not_found', 'unreadable'):
            stored.status, stored.value, stored.quote = 'not_found', '', None
            stored.reason = f'The {key.replace("_", " ")} was not found or could not be read. Check its source.'
    if latest_fact(case, 'legal_description', 'legalDescription', 'section_b.legal_description') is None:
        from .completeness import _missing
        for group in (('lot', 'block', 'plan'), ('ats_qtr', 'ats_sec', 'ats_twp', 'ats_rge', 'ats_mer')):
            parts = [doc.values.get(key) for key in group]
            if all(part and part.confirmed and not _missing(part.value) for part in parts):
                text = ', '.join(f'{key} {part.value}' for key, part in zip(group, parts))
                doc.values['legal_description'] = StoredValue('legal_description', text, 'pointed', text,
                    pointers=[{'file': part.source_ref or record, 'quote': part.quote} for part in parts])
                break
    # Only the current confirmed readings contribute to searches. Source quotes are provenance,
    # not the field's value and not a way to revive an older or proposed answer.
    from .fact_aliases import FIELD_KEYS, LOGICAL_KEYS, latest
    current = {LOGICAL_KEYS.get(key, key) for key in latest(case)}
    current.update(('section_c.article', 'section_c.intent', 'code_or_standard', 'supporting_doc', 'legal_description'))
    from .completeness_elements import BY_FIELD
    for key in sorted(current):
        stored = doc.values.get(key)
        if not stored:
            continue
        status = ('not_found' if not stored.confirmed or stored.status == 'not_found' else
                  'present' if stored.value.strip() else 'blank')
        source = stored.source or {}
        pointer = Pointer(file=source.get('ref') or stored.source_ref or record, page=source.get('page'),
                          bbox=source.get('bbox'), quote=stored.quote if status == 'present' else None)
        spec = BY_FIELD.get(key)
        section = spec.export_section if spec else ('D' if key.startswith(('professional', 'evidence.')) else 'B')
        snapshot.fields.append(FieldReading(field=key, label=spec.label if spec else key.replace('_', ' '),
            section=section, status=status, value=stored.value if status == 'present' else None,
            reason=stored.reason or ('The current answer has not been established.' if status == 'not_found' else ''),
            pointer=pointer))
    for key, stored in doc.values.items():
        if key not in current:
            continue
        if key.startswith('citation.'):
            continue  # confirmed benchmark selection is verified with the native Section C rows
        if stored.confirmed and stored.status != 'not_found':
            source = stored.source or {}
            snapshot.corpus.append((source.get('ref') or record, source.get('page'), stored.value))
    for row in case.section_c:
        snapshot.corpus.append((record, None, ' '.join(pair.bracket for pair in row.pairs)))
    snapshot.documents = case_rows(case)
    attached = {row.id for row in snapshot.documents}
    for evidence in case.evidence:
        if evidence.status != 'evidence_listed' or evidence.id in attached:
            continue
        title = doc.values.get(f'evidence.{evidence.id}.title')
        who = doc.values.get(f'evidence.{evidence.id}.responsible_party')
        name = title.value if title and title.confirmed and title.value.strip() else evidence.description
        source = title.source if title and title.source else {'ref': record}
        snapshot.documents.append(DocumentRow(id=evidence.id, title=Attribute(value=name, known=True,
            source=Pointer(file=source.get('ref') or record, page=source.get('page'), quote=source.get('quote'))),
            responsible=Attribute(value=who.value, known=True) if who and who.confirmed and who.value.strip() else Attribute(),
            type=Attribute(), issuer=Attribute(), date=Attribute(), evidence_rung=Attribute(), seal=Attribute(),
            listed_in_section_d=True))
    from .section_d import supporting_documents
    attachments = []
    read_refs = set()
    for document in supporting_documents(case):
        if document.file.ref in read_refs:
            continue
        read_refs.add(document.file.ref)
        stored_file = None
        if store is not None:
            try:
                stored_file = store.get_file(case.id, document.file.ref)
            except (KeyError, OSError, ValueError):
                pass
        else:
            # Local CLI/demo callers may explicitly reference repository files. HTTP callers
            # always supply their owned store and never resolve paths on the server filesystem.
            root = Path(__file__).resolve().parents[1]
            path = (root / document.file.ref).resolve()
            if path.is_relative_to(root) and path.is_file():
                stored_file = {'name': document.file.ref, 'data': path.read_bytes()}
        if stored_file and stored_file.get('data'):
            name = stored_file.get('name') or document.file.ref
            data = stored_file['data']
            if data.startswith(b'%PDF-'):
                read = read_pdf(data, name)
                snapshot.reads.append(read)
                snapshot.corpus += [(name, page.page + 1, page.text) for page in read.text_pages]
                snapshot.unreadable += [Pointer(file=name, page=page + 1) for page in read.unreadable_pages()]
                if read.role == 'unreadable':
                    snapshot.unreadable.append(Pointer(file=name))
                attachments.extend(page.text for page in read.text_pages)
            else:
                try:
                    text = data.decode('utf-8')
                    snapshot.corpus.append((name, None, text))
                    attachments.append(text)
                except UnicodeError:
                    snapshot.unreadable.append(Pointer(file=name))
        else:
            # A saved excerpt can expose a defect, but cannot establish the full document's absence/consistency.
            file_fact = latest_fact(case, f'evidence.{document.id}.file_ref')
            if file_fact and file_fact.source.quote:
                snapshot.corpus.append((document.file.ref, file_fact.source.page, file_fact.source.quote))
                attachments.append(file_fact.source.quote)
            snapshot.unreadable.append(Pointer(file=document.file.ref))
    doc.section_text['attachment'] = '\n'.join(attachments)
    description = doc.values.get('alternative_description')
    doc.section_text['B'] = description.value if description and description.confirmed else ''
    # Searching retained excerpts is useful, but never claims all attachment contents were inspected.
    doc.ledger = False
    doc.data = '\n'.join([doc.text, *(text for _file, _page, text in snapshot.corpus)]).encode()
    doc.text = doc.data.decode()
    return snapshot


