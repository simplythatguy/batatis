"""Build one package review from a Batatis case or from uploaded PDFs.

Administrative completeness only. The review reads values and points to them;
it never fills a missing item, never states compliance, and never writes risk,
mitigation or the officer's decision.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from ..completeness_variants import ElementVerdict, run_variant
from ..models import INTENT_LABEL
from ..models_review import (CitationCheck, DocumentRow, FieldReading, Finding, InputFile, Pointer,
                             SectionCCheck)
from . import citations as cite
from . import div_c
from .documents import attachment_row, case_rows, merge_section_d, unreadable_row
from .ingest import Ingested, StoredValue
from .pdf_reader import FieldValue, ReadFile, field_maps, read_pdf

CITATION_PROBLEMS = {'nonexistent_provision', 'superseded_edition', 'page_mismatch', 'attribution_not_in_table'}
_PRESENCE = {'blank', 'not_found', 'placeholder', None, 'unconfirmed'}
# Variant elements replaced by per-row or per-file checks below, or that are officer duties.
_REPLACED = {'section_c.pair_match', 'section_c.provision_found', 'section_c.intent', 'signature',
             'owner_rep_signature_date', 'representative', 'division_c_2_3_1'}

# Headings that start an applicant-written passage in an appendix or attachment.
TEXT_FIELDS = {
    'alternative_description': ('description of the proposed alternative', re.compile(
        r'^\s*(?:[A-Z]-\d+\s+)?(?:proposed alternative(?: solution)?|description of (?:the )?proposed alternative'
        r'(?: solution)?)\s*(?::|$)', re.I | re.M)),
    'rationale': ('rationale', re.compile(
        r'^\s*(?:[A-Z]-\d+\s+)?rationale(?: for (?:the )?(?:proposed )?(?:alternative(?: solution)?|variance))?'
        r'\s*(?::|$)', re.I | re.M)),
    'risk_assessment': ('risk assessment', re.compile(r'^\s*(?:[A-Z]-\d+\s+)?risk assessment\s*(?::|$)', re.I | re.M)),
    'mitigating_measures': ('mitigating measures', re.compile(
        r'^\s*(?:[A-Z]-\d+\s+)?mitigating measures\s*(?::|$)', re.I | re.M)),
    'assumptions_and_limits': ('assumptions and limits', re.compile(
        r'^\s*(?:[A-Z]-\d+\s+)?assumptions(?:,)?(?: and)? limit(?:s|ing factors|ations)?\s*(?::|$)', re.I | re.M)),
    'professional_name': ('responsible professional', re.compile(
        r'^\s*(?:responsible professional|registered professional)\s*(?::|$)', re.I | re.M)),
    'professional_qualifications': ('qualifications of the responsible professional', re.compile(
        r'^\s*(?:[A-Z]-\d+\s+)?qualifications(?: of (?:the )?responsible (?:people|professional|persons?))?\s*(?::|$)',
        re.I | re.M)),
}
_STOP_LINE = re.compile(r'^\s*(?:[A-Z]-\d+\s|Applicant source:|NBC\(AE\)|[A-Z]\.\s+[A-Z]|Appendix page|'
                        r'(?:rationale|code analysis|testing procedures?|qualifications(?: of [a-z ]+)?|'
                        r'maintenance(?: and (?:operation|commissioning))?|operation and maintenance|commissioning)'
                        r'\s*(?::|$))', re.M | re.I)
_ENGINEERING = re.compile(r'\b(?:engineering|registered professional|professional involvement)\s+(?:is\s+)?required'
                          r'\s*[:\-]?\s*(yes|no)\b', re.I)


@dataclass
class Parts:
    files: list[InputFile] = field(default_factory=list)
    fields: list[FieldReading] = field(default_factory=list)
    findings: list[Finding] = field(default_factory=list)
    documents: list[DocumentRow] = field(default_factory=list)
    citations: list[CitationCheck] = field(default_factory=list)
    section_c: list[SectionCCheck] = field(default_factory=list)
    lookup_skipped: bool = False
    case_version: int | None = None


@dataclass
class TextValue:
    status: str
    value: str
    file: str
    page: int | None
    quote: str | None


def _norm(text: str) -> str:
    return re.sub(r'\s+', ' ', text or '').strip()


def text_value(pages: list[tuple[str, int, str]], pattern) -> TextValue:
    """Passage after a heading, up to the next heading or source line. Absent heading: not_found."""
    for file, page, text in pages:
        match = pattern.search(text)
        if not match:
            continue
        rest = text[match.end():]
        stop = _STOP_LINE.search(rest)
        for other in TEXT_FIELDS.values():
            hit = other[1].search(rest)
            if hit and (stop is None or hit.start() < stop.start()):
                stop = hit
        body = rest[:stop.start()] if stop else rest
        body = body.split('\n\n', 1)[0]
        value = _norm(body)
        return TextValue('present' if value else 'blank', value, file, page, value or _norm(match.group(0)))
    return TextValue('not_found', '', '', None, None)


def _finding_status(element: ElementVerdict) -> str:
    if element.verdict == 'missing':
        if element.problem == 'blank':
            return 'blank'
        if element.problem == 'not_found':
            return 'not_found'
        return 'missing'
    return 'unclear'


def _family(problem: str | None) -> str:
    return 'presence' if problem in _PRESENCE else problem


def _pointer_from_source(source: dict, fallback: str) -> Pointer:
    bbox = source.get('bbox')
    return Pointer(file=source.get('ref') or fallback, page=source.get('page'),
                   bbox=tuple(bbox) if bbox else None, quote=source.get('quote'))


def element_finding(element: ElementVerdict, pointers: list[Pointer]) -> Finding | None:
    if element.verdict == 'present':
        return None
    if element.verdict == 'unclear' and not element.problem:
        return None   # a skipped screen is not a gap the applicant can answer
    section = 'process' if element.export_section == 'process' else element.template_section
    status = _finding_status(element)
    return Finding(key=f'{element.field}:{_family(element.problem)}', section=section, field=element.field,
                   label=element.label, status=status, problem=element.problem, defect_class=element.defect_class,
                   message=element.reason, severity='blocking' if element.verdict == 'missing' else 'warning',
                   routed_to=element.routed_to or 'applicant', pointers=pointers, citations=list(element.citations))


# ---------------------------------------------------------------- uploaded PDFs

def _label(fmap: dict, name: str) -> tuple[str, str]:
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
    return name, 'A'


def _pointer(read: ReadFile, value: FieldValue) -> Pointer:
    return Pointer(file=read.name, page=value.page + 1, form_field=value.name,
                   bbox=tuple(round(v, 1) for v in value.rect) if value.rect else None,
                   quote=value.value or None)


def _stored(logical: str, value: FieldValue, read: ReadFile) -> StoredValue | None:
    if value.status == 'not_found':
        return None
    source = {'type': 'file', 'ref': read.name, 'page': value.page + 1,
              'bbox': list(value.rect) if value.rect else None, 'quote': value.value or None}
    return StoredValue(logical, value.value, 'exact', value.value or None, form_field=value.name,
                       explicit_blank=value.status == 'blank', source=source, input_field=value.name)


def _legal(read: ReadFile) -> tuple[StoredValue | None, list[str]]:
    fields = read.fields
    lbp, ats = ('Lot', 'Block', 'Plan'), ('QTR', 'SEC', 'TWP', 'RGE', 'MER')
    for group in (lbp, ats):
        if all(fields.get(name) and fields[name].status == 'present' for name in group):
            value = ', '.join(f'{name} {fields[name].value}' for name in group)
            return StoredValue('legal_description', value, 'exact', fields[group[0]].value,
                               form_field=group[0], source={'type': 'file', 'ref': read.name, 'page': 1,
                                                            'quote': fields[group[0]].value},
                               input_field=group[0]), []
    states = [fields[name].status for name in lbp + ats if name in fields]
    if any(state == 'not_found' for state in states) and not any(state == 'present' for state in states):
        return None, []
    blank = [name for name in lbp + ats if name in fields and fields[name].status != 'present']
    return StoredValue('legal_description', '', 'exact', None, form_field='Lot', explicit_blank=True,
                       source={'type': 'file', 'ref': read.name, 'page': 1}, input_field='Lot'), blank


def _intent_ok(text: str) -> bool:
    folded = text.casefold()
    return ('explanatory' in folded or INTENT_LABEL.casefold() in folded or 'no row' in folded
            or 'no nbc 2020' in folded or bool(cite._APPENDIX.search(text)) and len(text) < 40)


def review_uploads(uploads: list[tuple[str, bytes]], codes) -> Parts:
    parts = Parts(lookup_skipped=codes is None)
    reads = [read_pdf(data, name) for name, data in uploads]
    for read in reads:
        parts.files.append(InputFile(name=read.name, sha256=read.sha256, size=read.size, pages=read.pages,
                                     role=read.role, form_version=read.form_version, note=read.note))
    forms = [read for read in reads if read.role.startswith('scc_form')]
    form = forms[0] if forms else None
    for extra in forms[1:]:
        parts.files[reads.index(extra)].note = 'A second SCC form was uploaded; only the first form was reviewed.'
    attachments = [read for read in reads if read.role == 'attachment']
    pages = [(read.name, page.page + 1, page.text) for read in ([form] if form else []) + attachments
             for page in read.text_pages]

    if form is None:
        parts.findings.append(Finding(
            key='form:presence', section='A', field='scc_form', label='SCC variance form', status='not_found',
            message='No SCC variance form was recognised among the uploaded files. Check whether it was included.',
            severity='blocking', pointers=[Pointer(file=read.name) for read in reads]))
    for read in reads:
        if read.role == 'unreadable':
            parts.findings.append(Finding(
                key=f'file:{read.name}:unreadable', section='D', field=f'file.{read.name}', label=f'file "{read.name}"',
                status='not_found', problem='unreadable', message=f'{read.note} Check this file by eye.',
                routed_to='officer', pointers=[Pointer(file=read.name)]))
    fmap = next((m for m in field_maps() if form and m['version'] == form.form_version), None)

    # ---- field readings
    if form is not None:
        if fmap is None and form.fields:
            fmap = field_maps()[-1]
        for name, value in sorted(form.fields.items()):
            label, section = _label(fmap, name) if fmap else (name, 'A')
            parts.fields.append(FieldReading(field=name, label=label, section=section, status=value.status,
                                             value=value.value or None, reason=value.reason,
                                             pointer=_pointer(form, value)))
        for name, value in sorted(form.signatures.items()):
            parts.fields.append(FieldReading(field=name, label='Owner signature' if name == 'Signature1'
                                             else "Owner's representative signature", section='A',
                                             status=value.status, value=value.value or None, reason=value.reason,
                                             pointer=_pointer(form, value)))
    texts = {key: text_value(pages, pattern) for key, (_label_text, pattern) in TEXT_FIELDS.items()}
    # A draft export explicitly says no answer was supplied. Its notice is not applicant rationale.
    rationale = texts['rationale']
    if rationale.value == '(Not provided or not confirmed. No answer has been supplied by Batatis.)':
        rationale.status, rationale.value = 'blank', ''
    for key, found in texts.items():
        label = TEXT_FIELDS[key][0]
        section = 'process' if key in ('rationale', 'risk_assessment', 'mitigating_measures', 'assumptions_and_limits') else (
            'B' if key == 'alternative_description' else 'D')
        parts.fields.append(FieldReading(
            field=key, label=label, section=section, status=found.status, value=found.value or None,
            reason={'not_found': 'No heading for this passage was found in the form appendix or attachments.',
                    'blank': 'The heading is present with no text under it.'}.get(found.status, ''),
            pointer=Pointer(file=found.file or (form.name if form else '(no file)'), page=found.page,
                            quote=found.quote)))

    # ---- deterministic element screens (ported variant B) over the form reading
    by_widget = form.fields if form else {}
    values: dict[str, StoredValue] = {}
    widget_for = {'owner_name': 'Owner', 'application_date': 'Date of Reqeuest', 'representative': 'Owner Rep',
                  'mailing_address': 'Mailing Address', 'civic_address': 'Municipal Address',
                  'code_or_standard': 'Code or Standard', 'objective': 'Objective', 'function': 'Function',
                  'section_c.intent': 'Intent statement', 'supporting_doc': 'Supporting Doc',
                  'responsible_party': 'Name Responsible'}
    if form is not None:
        for logical, widget in widget_for.items():
            if widget in by_widget:
                stored = _stored(logical, by_widget[widget], form)
                if stored is not None:
                    values[logical] = stored
        article_cells = [by_widget[row['article']] for row in (fmap or {}).get('section_c_rows', [])
                         if row['article'] in by_widget]
        if article_cells and not any(cell.status == 'not_found' for cell in article_cells[:1]):
            joined = '; '.join(cell.value for cell in article_cells if cell.status == 'present')
            values['section_c.article'] = StoredValue(
                'section_c.article', joined, 'exact', joined or None, form_field=article_cells[0].name,
                explicit_blank=not joined, input_field=article_cells[0].name,
                source={'type': 'file', 'ref': form.name, 'page': article_cells[0].page + 1, 'quote': joined or None})
        legal, legal_blank = _legal(form)
        if legal is not None:
            values['legal_description'] = legal
    for key, found in texts.items():
        if found.status == 'not_found':
            continue
        values[key] = StoredValue(key, found.value, 'pointed', found.value or None, explicit_blank=found.status == 'blank',
                                  source={'type': 'file', 'ref': found.file, 'page': found.page, 'quote': found.quote},
                                  input_field=key)
    blob = '\n'.join(text for _f, _p, text in pages)
    engineering = _ENGINEERING.search(blob)
    engineering_at = None
    for file, page, text in pages:
        hit = _ENGINEERING.search(text)
        if hit:
            engineering_at = Pointer(file=file, page=page, quote=hit.group(0))
            break
    if engineering:
        values['engineering_required'] = StoredValue('engineering_required', engineering.group(1), 'pointed',
                                                     engineering.group(0))
    doc = Ingested(ref=form.name if form else 'upload', data=blob.encode('utf-8'), text=blob, kind='form',
                   values=values, form_fields={name: value.value for name, value in by_widget.items() if value.value})
    # Files that carry the application's own passages are not evidence to compare Section B with.
    narrative_files = {found.file for found in texts.values() if found.file}
    doc.section_text = {'A': '', 'B': texts['alternative_description'].value, 'C': values.get(
        'section_c.article', StoredValue('', '', '', None)).value, 'D': '', 'process': '',
        'attachment': '\n'.join(page.text for read in attachments if read.name not in narrative_files
                                for page in read.text_pages)}
    result = run_variant('B', doc, codes)
    widgets_by_logical = {**widget_for, 'section_c.article': 'Article(s)', 'legal_description': 'Lot'}
    for element in result.elements:
        if element.field in _REPLACED:
            continue
        if form is None and element.field not in TEXT_FIELDS:
            continue   # one "form not found" finding instead of a row per form field
        pointers = []
        widget = widgets_by_logical.get(element.field)
        if form is not None and widget in by_widget:
            pointers.append(_pointer(form, by_widget[widget]))
        found = texts.get(element.field)
        if found is not None and found.file:
            pointers.append(Pointer(file=found.file, page=found.page, quote=found.quote))
        for quote in element.quotes:
            if quote.source:
                pointer = _pointer_from_source(quote.source, form.name if form else 'upload')
                if pointer not in pointers:
                    pointers.append(pointer)
        if element.field in ('responsible_professional', 'professional_qualifications') and engineering_at:
            pointers.append(engineering_at)
        if not pointers:
            pointers.append(Pointer(file=form.name if form else (reads[0].name if reads else 'upload')))
        finding = element_finding(element, pointers)
        if finding is None:
            continue
        if element.field == 'legal_description' and form is not None and legal_blank and finding.status == 'blank':
            finding.message += ' Blank components: ' + ', '.join(legal_blank) + '.'
        if element.field in TEXT_FIELDS and texts[element.field].status == 'not_found':
            finding.status = 'not_found'
            finding.message = (f'No {element.label} was found in the form appendix or the attachments. '
                               'Check the attachments; if it is not there, ask the applicant for it.')
        parts.findings.append(finding)

    if form is not None:
        _signatures(form, parts)
        _rows(form, fmap, codes, parts, texts['alternative_description'])
        _section_d(form, fmap, parts)
    _attachment_citations(attachments, codes, parts)

    # ---- documents panel
    rows = []
    for index, read in enumerate(reads, start=1):
        if read.role == 'attachment':
            rows.append(attachment_row(read, index))
        elif read.role == 'unreadable':
            rows.append(unreadable_row(read, index))
    listed = []
    if form is not None and fmap:
        for number, row in enumerate(fmap['section_d_rows'], start=1):
            name, who = by_widget.get(row['document']), by_widget.get(row['responsible'])
            if name and name.status == 'present':
                listed.append((number, name.value, who.value if who and who.status == 'present' else '',
                               _pointer(form, name), _pointer(form, who) if who else _pointer(form, name)))
    parts.documents = merge_section_d(rows, listed)
    _div_c_upload(form, by_widget, pages, engineering, parts, codes, reads)
    for row in parts.documents:
        looks_like_evidence = row.listed_in_section_d or row.type.known or row.evidence_rung.known
        if row.file and looks_like_evidence and not row.issuer.known and not row.responsible.known:
            parts.findings.append(Finding(
                key=f'document:{row.file}:responsible', section='D', field=f'document.{row.id}',
                label=f'supporting document "{row.title.value}"', status='unclear', problem='no_responsible',
                defect_class='D13', message='No issuer or responsible person was read in this document.',
                pointers=[row.title.source] if row.title.source else [Pointer(file=row.file)]))
    return parts


def _div_c_upload(form, by_widget, pages, engineering, parts: Parts, codes, reads) -> None:
    where = Pointer(file=form.name if form else (reads[0].name if reads else 'upload'))
    corpus: div_c.Corpus = [(form.name, value.page + 1, f'{value.name}: {value.value}')
                            for value in by_widget.values() if value.status == 'present'] if form else []
    corpus += pages
    responsible = [row.responsible.value for row in parts.documents if row.responsible.known]
    readable = any(text.strip() for _f, _p, text in corpus)
    if readable:
        uncertain = any(read.role == 'unreadable' for read in reads)
        parts.findings.extend(div_c.file_findings(corpus, where, codes, responsible=responsible,
                                                  uncertain=uncertain))
    signal = div_c.peer_review_finding(
        professional_required=bool(engineering and engineering.group(1).casefold() == 'yes'),
        provisions=[check.provision_id for check in parts.citations if check.provision_id],
        rungs=[row.evidence_rung.value for row in parts.documents],
        novel_product=any(div_c.NOVEL.search(text) for _f, _p, text in corpus)
        or any(row.evidence_rung.value == "manufacturer's literature" for row in parts.documents),
        where=where)
    if signal:
        parts.findings.append(signal)


def _signatures(form: ReadFile, parts: Parts) -> None:
    signs = list(form.signatures.values())
    if signs and not any(sign.status == 'present' for sign in signs):
        parts.findings.append(Finding(
            key='signature:presence', section='A', field='signature', label='applicant signature', status='not_found',
            problem='signature_unread', defect_class='D02',
            message='No signature could be read. A wet or image signature cannot be read; check the signature boxes.',
            pointers=[_pointer(form, sign) for sign in signs]))
    dates = [form.fields[name] for name in ('Date1', 'Date2') if name in form.fields]
    if dates and not any(date.status == 'present' for date in dates):
        status = 'not_found' if any(date.status == 'not_found' for date in dates) else 'blank'
        parts.findings.append(Finding(
            key='signature_date:presence', section='A', field='signature_date', label='signature date',
            status=status, problem=status, defect_class='D02', severity='blocking',
            message='No date is next to either signature.' if status == 'blank' else
            'The signature dates could not be read.', pointers=[_pointer(form, date) for date in dates]))


def _rows(form: ReadFile, fmap: dict | None, codes, parts: Parts, description: TextValue) -> None:
    if not fmap:
        return
    fields = form.fields
    code_std = fields.get('Code or Standard')
    edition = code_std.value if code_std and code_std.status == 'present' else ''
    row_ids: list[str] = []
    for number, row in enumerate(fmap['section_c_rows'], start=1):
        cells = {key: fields.get(widget) for key, widget in row.items()}
        article = cells['article']
        if article is None or article.status != 'present':
            continue
        pointer = _pointer(form, article)
        ids = cite.provision_ids(article.value)
        row_ids.extend(ids)
        text = f'{edition} Div B {article.value}' if edition else f'Div B {article.value}'
        for check in cite.verify_citation(text, pointer, codes):
            check.text = article.value
            parts.citations.append(check)
            for issue in check.issues:
                if issue.code not in CITATION_PROBLEMS:
                    continue
                if issue.code == 'superseded_edition':
                    continue   # the edition screen (variant B, section_c.edition) owns this finding
                parts.findings.append(Finding(
                    key=f'section_c.row{number}:{issue.code}', section='C', field=f'section_c.row{number}.article',
                    label=f'Section C row {number} provision {check.provision_id}',
                    status='missing' if issue.code == 'nonexistent_provision' else 'unclear', problem=issue.code,
                    defect_class='D05' if issue.code == 'nonexistent_provision' else None,
                    message=issue.message, severity='blocking', pointers=[pointer]))
        objective = cells['objective'].value if cells.get('objective') and cells['objective'].status == 'present' else ''
        function = cells['function'].value if cells.get('function') and cells['function'].status == 'present' else ''
        comparison = cite.compare_row(number, article.value, objective, function, pointer, codes)
        parts.section_c.append(comparison)
        if comparison.status == 'mismatch':
            parts.findings.append(Finding(
                key=f'section_c.row{number}:pair', section='C', field=f'section_c.row{number}.pair',
                label=f'Section C row {number} objective and function', status='unclear', problem='pair_mismatch',
                defect_class='D07', message=comparison.message, severity='blocking',
                pointers=[p for p in (pointer, cells['objective'] and _pointer(form, cells['objective']),
                                      cells['function'] and _pointer(form, cells['function'])) if p]))
        intent = cells.get('intent')
        if intent is not None and intent.status == 'present' and not _intent_ok(intent.value):
            parts.findings.append(Finding(
                key=f'section_c.row{number}:intent_label', section='C', field=f'section_c.row{number}.intent',
                label=f'Section C row {number} intent statement', status='unclear', problem='intent_label',
                defect_class='D08', message='The intent statement is presented without the national explanatory '
                f'label. It is NBC 2020 explanatory material, not Alberta law. Label: {INTENT_LABEL}.',
                pointers=[_pointer(form, intent)]))
    if description.status == 'present':
        cited = set(row_ids)

        def covered(pid: str) -> bool:
            article = pid.split('(')[0]
            if '(' in pid:   # a sentence: its own row, or a row citing the whole article
                return pid in cited or article in cited
            return any(row.startswith(article) for row in cited)

        for pid in cite.provision_ids(description.value):
            if not covered(pid):
                parts.findings.append(Finding(
                    key=f'section_c.missing_row:{pid}', section='C', field=f'section_c.missing_row.{pid}',
                    label=f'benchmark {pid}', status='missing', problem='missing_row', defect_class='D16',
                    message=f'Section B names {pid}, but no Section C row cites it.', severity='blocking',
                    pointers=[Pointer(file=description.file, page=description.page, quote=pid)]))


def _section_d(form: ReadFile, fmap: dict | None, parts: Parts) -> None:
    if not fmap:
        return
    for number, row in enumerate(fmap['section_d_rows'], start=1):
        if number == 1:
            continue   # row 1 is screened by the supporting-document element
        name, who = form.fields.get(row['document']), form.fields.get(row['responsible'])
        if name and name.status == 'present' and who and who.status == 'blank':
            parts.findings.append(Finding(
                key=f'section_d.row{number}:responsible', section='D', field=f'section_d.row{number}.responsible',
                label=f'Section D row {number} responsible person', status='blank', problem='no_responsible',
                defect_class='D13', message=f'"{name.value}" is listed with no responsible person.',
                severity='blocking', pointers=[_pointer(form, who), _pointer(form, name)]))
        if who and who.status == 'present' and name and name.status == 'blank':
            parts.findings.append(Finding(
                key=f'section_d.row{number}:document', section='D', field=f'section_d.row{number}.document',
                label=f'Section D row {number} document', status='blank', problem='blank',
                message=f'A responsible person ("{who.value}") is listed with no document.',
                pointers=[_pointer(form, name)]))


def _attachment_citations(attachments: list[ReadFile], codes, parts: Parts) -> None:
    for read in attachments:
        for page in read.text_pages:
            for line in page.text.split('\n'):
                if not cite.provision_ids(line):
                    continue
                pointer = Pointer(file=read.name, page=page.page + 1, quote=_norm(line)[:300],
                                  bbox=read.locate(page.page, _norm(line)[:120]))
                for check in cite.verify_citation(line, pointer, codes):
                    parts.citations.append(check)
                    for issue in check.issues:
                        if issue.code in CITATION_PROBLEMS:
                            parts.findings.append(Finding(
                                key=f'citation:{read.name}:{check.provision_id}:{issue.code}', section='D',
                                field=f'citation.{check.provision_id}', label=f'citation of {check.provision_id} in '
                                f'"{read.name}"', status='unclear', problem=issue.code,
                                defect_class={'nonexistent_provision': 'D05', 'superseded_edition': 'D06'}.get(issue.code),
                                message=issue.message, pointers=[pointer]))


# ---------------------------------------------------------------- Batatis case

def review_case(case, codes, store=None) -> Parts:
    from ..completeness_report import saved_case_response
    from ..section_c import section_c_rows
    parts = Parts(case_version=case.version)
    record = f'case:{case.id}'
    parts.files.append(InputFile(name=record, role='case_record', note='The saved Batatis case was reviewed.'))
    report = saved_case_response(case, codes, 'B')
    for review in report.reviews:
        for section in review.sections:
            for element in section.elements:
                pointers = [_pointer_from_source(source.model_dump() if hasattr(source, 'model_dump') else source,
                                                 record) for source in element.sources]
                quote = element.quotes[0].text if element.quotes else None
                if not pointers:
                    pointers = [Pointer(file=record, form_field=element.form_fields[0] if element.form_fields else None,
                                        quote=quote)]
                status = 'present'
                if element.verdict == 'missing' and element.problem in ('blank', 'not_found', None):
                    status = 'blank'   # the saved record has no value: certain
                parts.fields.append(FieldReading(
                    field=element.field, label=element.label, section='process' if element.export_section == 'process'
                    else element.template_section, status=status, value=quote if status == 'present' else None,
                    reason=element.reason if status != 'present' else '', pointer=pointers[0]))
                verdict = ElementVerdict(**{k: getattr(element, k) for k in (
                    'field', 'template_section', 'export_section', 'export_field', 'form_fields', 'label', 'group',
                    'verdict', 'reason', 'defect_class', 'problem', 'source', 'severity', 'related_fields',
                    'citations', 'routed_to')})
                finding = element_finding(verdict, pointers)
                if finding is None:
                    continue
                if finding.status == 'not_found':
                    finding.status = 'blank'
                finding.severity = element.severity
                parts.findings.append(finding)
    for number, row in enumerate(case.section_c, start=1):
        pointer = Pointer(file=record, form_field=f'section_c[{number - 1}]', quote=row.citation)
        parts.citations.extend(cite.verify_citation(row.citation, pointer, codes))
        try:
            fresh = section_c_rows([row.provision_id], codes)
        except (KeyError, ValueError):
            fresh = []
        stored = sorted({f'{p.function}-{p.objective}' for p in row.pairs})
        table = sorted({f'{p.function}-{p.objective}' for r in fresh for p in r.pairs})
        status = 'match' if stored == table else ('no_table_row' if not table and not stored else 'mismatch')
        message = (f'The saved row for {row.provision_id} matches the Division B table.' if status == 'match' else
                   f'The Division B table has no row for {row.provision_id}.' if status == 'no_table_row' else
                   f'The saved row gives {", ".join(stored) or "(no pair)"} for {row.provision_id}; the Division B '
                   f'table gives {", ".join(table) or "(no row)"}.')
        parts.section_c.append(SectionCCheck(row=number, provision_id=row.provision_id,
                                             form_objective=', '.join(p.objective for p in row.pairs) or None,
                                             form_function=', '.join(p.function for p in row.pairs) or None,
                                             table_pairs=table, status=status, message=message, pointer=pointer))
        if status == 'mismatch':
            parts.findings.append(Finding(
                key=f'section_c.{row.provision_id}:pair', section='C', field=f'section_c.{row.provision_id}',
                label=f'Section C row for {row.provision_id}', status='unclear', problem='pair_mismatch',
                defect_class='D07', message=message, severity='blocking', pointers=[pointer]))
    parts.documents = case_rows(case, store)
    _div_c_case(case, codes, parts, record)
    return parts


def _div_c_case(case, codes, parts: Parts, record: str) -> None:
    from ..process_fields import alternative_path, confirmed_value
    from ..professional import professional_involvement
    corpus: div_c.Corpus = [(record, None, f'{fact.field}: {fact.value}') for fact in case.facts
                            if isinstance(fact.value, str) and fact.value.strip()]
    corpus += [(record, None, f'{row.provision_id} {" ".join(p.bracket or "" for p in row.pairs)}')
               for row in case.section_c]
    corpus += [(record, None, item.description) for item in case.evidence]
    responsible = [row.responsible.value for row in parts.documents if row.responsible.known]
    name = confirmed_value(case, 'professional_name')
    if isinstance(name, str):
        responsible.append(name)
    where = Pointer(file=record)
    # Qualifications and maintenance are process fields the saved-case policy already names.
    parts.findings.extend(div_c.file_findings(corpus, where, codes, responsible=responsible,
                                              skip={'div_c.qualifications', 'div_c.maintenance'},
                                              on_alternative_path=alternative_path(case)))
    try:
        required = professional_involvement(case, codes).required == 'yes'
    except Exception:  # noqa: BLE001 - the signal is advisory; a screen failure must not block the review
        required = False
    signal = div_c.peer_review_finding(
        professional_required=required, provisions=list(case.provisions),
        rungs=[row.evidence_rung.value for row in parts.documents],
        novel_product=any(div_c.NOVEL.search(text) for _f, _p, text in corpus), where=where)
    if signal:
        parts.findings.append(signal)
