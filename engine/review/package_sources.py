"""Read visible source records and source-page envelopes, never embedded JSON.

Unresolved input records can only add findings. They cannot clear a defect read
from the actual form, a narrative, a code lookup, or a supporting source.
"""
from __future__ import annotations

import re
from dataclasses import replace

from ..models_completeness import AdministrativeItem, PolicyPointer, ProfessionalDeclaration
from ..models_review import Attribute, Pointer
from ..package_format import ATTACHMENT, CONTEXT
from ..professional import role_confirmed


def _fields(text, names):
    pattern = re.compile(r'^(' + '|'.join(re.escape(name) for name in names) + r'): *(.*)$', re.M)
    hits = list(pattern.finditer(text))
    values = {}
    for index, hit in enumerate(hits):
        end = hits[index + 1].start() if index + 1 < len(hits) else len(text)
        values[hit.group(1)] = ' '.join(text[hit.start(2):end].split())
    return values


def visible_sources(read):
    records, sources, consumed, declarations = [], [], set(), []
    pages = {page.page: page for page in read.text_pages}
    for page in read.text_pages:
        text = page.text.strip()
        if not text.startswith((CONTEXT, ATTACHMENT)):
            continue
        marker = CONTEXT if text.startswith(CONTEXT) else ATTACHMENT
        end = 'End administrative source record' if marker == CONTEXT else 'End supporting source header'
        pointer = PolicyPointer(file=read.name, page=page.page + 1)
        if end not in text or read.passage_has_marks(page.page, None, None):
            records.append(AdministrativeItem(key=f'package_source:{page.page}:unreadable', field='package_source',
                section='D', label='visible administrative source', verdict='unclear', reason_code='source_unresolved',
                reason='A package source record could not be read completely. Check the indicated page.',
                certainty='not_found', severity='blocking', routed_to='officer', export_blocking=True,
                finding_status='not_found', pointers=[pointer]))
            continue
        body = text[:text.index(end)]
        consumed.add(page.page)
        if marker == ATTACHMENT:
            values = _fields(body, ('Attachment number', 'Source name', 'Title', 'Responsible', 'Page count'))
            try:
                count = int(values['Page count'])
                source_pages = [pages[index] for index in range(page.page + 1, page.page + count + 1)]
                if count < 1 or count > read.pages:
                    raise ValueError('invalid source range')
            except (ValueError, KeyError):
                records.append(AdministrativeItem(key=f'package_source:{page.page}:range', field='attachment_source',
                    section='D', label='supporting source page range', verdict='unclear', reason_code='source_unresolved',
                    reason='The supporting source page range could not be established.', certainty='not_found',
                    severity='blocking', routed_to='officer', export_blocking=True, finding_status='not_found', pointers=[pointer]))
                continue
            consumed.update(source.page for source in source_pages)
            segment = replace(read, role='attachment', fields={}, signatures={}, text_pages=source_pages,
                              field_map=None, form_version=None, note=values.get('Source name', ''), _unreadable_cache=None)
            sources.append((segment, values, pointer))
            continue
        values = _fields(body, ('Record type', 'Requirement key', 'Section', 'Field', 'Reason code', 'Severity',
                               'Route', 'Submission blocking', 'Message', 'Fix', 'Citation', 'Involvement',
                               'Requirement', 'Applicant confirmation', 'Name', 'Role', 'Basis', 'Owner', 'Location', 'Pathway'))
        if values.get('Record type') == 'professional declaration':
            involvement = values.get('Involvement', 'unresolved')
            # Involvement needs the applicant-confirmed engineer or architect role, as the screen does.
            if involvement == 'professional_involved' and not (
                    values.get('Applicant confirmation') == 'yes' and role_confirmed(values.get('Role', ''))):
                involvement = 'unresolved'
            if involvement == 'not_required' and not values.get('Basis'):
                involvement = 'unresolved'
            try:
                declarations.append(ProfessionalDeclaration(involvement=involvement,
                    requirement=values.get('Requirement', 'depends'),
                    applicant_confirmation=values.get('Applicant confirmation') == 'yes',
                    name=values.get('Name', ''), role=values.get('Role', ''), basis=values.get('Basis', ''),
                    owner=values.get('Owner', ''), location=values.get('Location', ''),
                    pathway=values.get('Pathway', 'alternative'), pointer=pointer))
            except ValueError:
                declarations.append(ProfessionalDeclaration(involvement='unresolved', requirement='depends',
                    applicant_confirmation=False, name='', role='', basis='Invalid source declaration',
                    owner='', location='', pointer=pointer))
            continue
        try:
            severity = values['Severity']
            route = values['Route']
            records.append(AdministrativeItem(key=values['Requirement key'], field=values['Field'], section=values['Section'],
                label=values['Field'].replace('_', ' '), verdict='unclear' if route == 'officer' or
                values['Reason code'] == 'unconfirmed' else 'missing', reason_code=values['Reason code'],
                reason=values['Message'], certainty='not_found' if route == 'officer' or values['Reason code'] == 'unconfirmed' else 'blank',
                severity=severity, routed_to=route, export_blocking=severity == 'blocking',
                submission_blocking=values.get('Submission blocking') != 'no', fix_hint=values.get('Fix', ''),
                citations=[values['Citation']] if values.get('Citation') else [], pointers=[pointer]))
        except (KeyError, ValueError):
            records.append(AdministrativeItem(key=f'package_source:{page.page}:invalid', field='package_source',
                section='D', label='administrative input context', verdict='unclear', reason_code='source_unresolved',
                reason='The visible administrative record is incomplete or invalid; it cannot establish a result.',
                certainty='not_found', severity='blocking', routed_to='officer', export_blocking=True,
                finding_status='not_found', pointers=[pointer]))
    main = replace(read, text_pages=[page for page in read.text_pages if page.page not in consumed], _unreadable_cache=None)
    return main, records, sources, declarations
