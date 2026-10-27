"""One administrative evaluator. Adapters read evidence; projections never add rules.

The field registry owns presence and semantic screens once. Native saved-row payload
checks and visible-PDF row checks are evidence-specific validation inside that policy,
not competing definitions of completeness. Technical adequacy remains human-owned.
"""
from __future__ import annotations

import re
import sqlite3
import hashlib
from dataclasses import dataclass, field
from types import SimpleNamespace

from .completeness import Gap, _case_constraints
from .completeness_elements import BY_FIELD, ELEMENTS, ElementSpec
from .completeness_snapshot import Snapshot
from .completeness_snapshot import _label, _pointer
from .completeness_rules import (ElementVerdict, QuoteSpan, VariantResult, _one, _presence_class,
                                    format_export_reason)
from .fact_aliases import FIELD_KEYS, LOGICAL_KEYS, latest
from .models_completeness import AdministrativeItem, AdministrativeReport, PolicyPointer
from .models import INTENT_LABEL
from .models_review import CitationCheck, Finding, Pointer, SectionCCheck
from .process_fields import _FIELDS, alternative_path
from .review import citations as cite, div_c
from .review.ingest import StoredValue
from .review.passages import located_quote
from .review.pdf_reader import FieldValue


@dataclass
class PolicyResult:
    elements: list[ElementVerdict]
    gaps: list[Gap]
    report: AdministrativeReport
    citations: list[CitationCheck] = field(default_factory=list)
    section_c: list[SectionCCheck] = field(default_factory=list)

    def variant_result(self, variant, document_id):
        return VariantResult(variant, document_id, self.elements)


def _source_pointer(source, fallback):
    return {'file': source.get('ref') or fallback, 'page': source.get('page'),
            'bbox': source.get('bbox'), 'quote': source.get('quote')}


def _finding_element(finding: Finding) -> ElementVerdict:
    return ElementVerdict(
        field=finding.field, template_section='B' if finding.section == 'process' else finding.section,
        export_section=finding.section, export_field=finding.field, form_fields=[], label=finding.label, group='',
        verdict='unclear' if finding.status in ('not_found', 'unclear') else 'missing', reason=finding.message,
        problem=finding.problem or finding.status, defect_class=finding.defect_class, key=finding.key,
        severity=finding.severity, routed_to=finding.routed_to,
        in_export_preflight=finding.severity == 'blocking', citations=finding.citations,
        certainty='not_found' if finding.status == 'not_found' else 'blank',
        finding_status=finding.status,
        pointers=[pointer.model_dump() for pointer in finding.pointers],
        fix_hint='Check the indicated sources.' if finding.status == 'not_found' else 'Ask the applicant to supply or clarify this item.')


def _gap_element(gap: Gap) -> ElementVerdict:
    return ElementVerdict(
        field=gap.field, template_section='B' if gap.section == 'process' else gap.section,
        export_section=gap.section, export_field=gap.field, form_fields=[], label=gap.field.replace('_', ' '), group='',
        verdict='unclear' if gap.routed_to == 'officer' else 'missing', reason=gap.message, problem='policy_gap',
        defect_class=gap.id.split(':')[0] if gap.id.startswith('D') else None, key=gap.id,
        severity=gap.severity, routed_to=gap.routed_to, in_export_preflight=gap.severity == 'blocking',
        citations=[gap.citation] if gap.citation else [], fix_hint=gap.fix_hint,
        submission_blocking=gap.submission_blocking)


def _specs():
    # The field registry is the sole owner of core and process presence.
    for spec in ELEMENTS:
        if spec.field not in {'signature', 'owner_rep_signature_date', 'division_c_2_3_1',
                              'section_c.pair_match', 'section_c.provision_found', 'responsible_professional',
                              'professional_qualifications'}:
            yield spec


def signature_date_gaps(doc):
    gaps = []
    from .completeness import _missing
    for signature, date in (('signature', 'signature_date'), ('owner_signature', 'owner_signature_date'),
                            ('owner_rep_signature', 'owner_rep_signature_date')):
        signed, dated = doc.values.get(signature), doc.values.get(date)
        if signed and signed.confirmed and signed.status != 'not_found' and signed.value.strip():
            if not dated or not dated.confirmed or _missing(dated.value):
                gaps.append(Gap(id=f'D02:{date}', section='A', field=date,
                    message=f'Your application appears to be missing the {date.replace("_", " ")}.',
                    fix_hint='Ask the signatory to supply the signature date.'))
    return gaps


def evaluate(snapshot: Snapshot, codes, *, professional=None, documents=None) -> PolicyResult:
    """Compute once per operation; callers project this exact result without rechecking."""
    doc = snapshot.document
    case = doc.case
    out = []
    citation_checks = []
    row_checks = []
    engineering = bool(doc.values.get('engineering_required') and
                       doc.values['engineering_required'].confirmed and
                       doc.values['engineering_required'].value.casefold() in ('yes', 'true'))
    for spec in _specs():
        if spec.field == 'representative':
            stored = doc.values.get('representative')
            # Owner-only applications are valid. A pending answer still needs confirmation.
            if stored is None or (stored.confirmed and stored.value.strip().casefold() in
                                  ('', 'none', 'no representative', 'n/a', 'na')):
                out.append(ElementVerdict(spec.field, 'A', 'A', spec.field, list(spec.form_fields), spec.label, '',
                                          'present', 'The owner may apply without a representative.',
                                          certainty='not_applicable'))
                continue
        element = _one(doc, spec, codes, engineering, heuristics=True)
        if element.problem == 'contradiction':
            for quote in element.quotes:
                located = [(file, page) for file, page, text in snapshot.corpus if _norm(quote.text) in _norm(text)]
                if located:
                    file, page = located[0]
                    quote.source = {'type': 'file', 'ref': file, 'page': page, 'quote': quote.text}
        if (element.field == 'section_b.consistency' and not element.problem
                and (snapshot.unreadable or not doc.section_text.get('attachment', '').strip())):
            element.verdict, element.problem, element.lookup_skipped = 'unclear', 'source_unresolved', True
            element.reason = ('Attachment contents are absent or could not all be read. Compare the indicated sources with Section B; '
                              'consistency is unresolved.')
            element.routed_to = 'officer'
            element.pointers = [pointer.model_dump() for pointer in snapshot.unreadable]
        # Suspected semantic defects are shared administrative tasks, never an adequacy verdict.
        if element.problem in {'generic', 'thin', 'unrelated', 'stated_as_fact', 'contradiction',
                               'multiple_locations', 'superseded_edition', 'brochure_only', 'no_evidence'}:
            element.severity, element.in_export_preflight = 'blocking', True
        if element.problem in {'not_found', 'unconfirmed'}:
            element.verdict = 'unclear' if element.problem == 'unconfirmed' or (doc.values.get(spec.field)
                                and doc.values[spec.field].status == 'not_found') else element.verdict
        if element.problem == 'topic_mismatch':
            # A keyword screen cannot decide relevance; the officer reviews the benchmarks.
            element.severity, element.in_export_preflight, element.routed_to = 'warning', False, 'officer'
        elif element.verdict != 'present' and not element.lookup_skipped:
            element.in_export_preflight = True
            element.severity = 'blocking'
        out.append(element)

    scope = doc.values.get('scope')
    if scope is not None and scope.explicit_blank:
        out.append(ElementVerdict('scope', 'B', 'B', 'scope', ['Check Box'], 'site or jurisdiction-wide scope', '',
            'missing', 'Your application appears to be missing the site or jurisdiction-wide scope.',
            problem='blank', key='scope:presence', severity='blocking', in_export_preflight=True,
            certainty='blank', fix_hint='Ask whether this variance is for one site or the whole jurisdiction.'))

    # Preparation is the shared stage: Batatis produces applicant pages for external signing.
    # Starting a signature makes its date required; a date alone does not establish signing.
    out.extend(_gap_element(gap) for gap in signature_date_gaps(doc))
    signs = [doc.values[key] for key in ('owner_signature', 'owner_rep_signature') if key in doc.values]
    if signs and not any(sign.confirmed and sign.status != 'not_found' and sign.value.strip() for sign in signs):
        out.append(_finding_element(Finding(
            key='signature:presence', field='signature', section='A', label='applicant signature', status='not_found',
            problem='signature_unread', message='Preparation stage: sign externally before submission. '
                'A wet or image signature cannot be established by this reading; check the signature boxes.',
            routed_to='officer', pointers=[Pointer(**pointer) for sign in signs for pointer in sign.pointers])))

    if snapshot.form is None:
        out.append(_finding_element(Finding(key='form:presence', field='scc_form', section='A',
            label='SCC variance form', status='not_found', severity='blocking', routed_to='officer',
            message='No SCC variance form was recognised. Check whether it was included.',
            pointers=[Pointer(file=file.name) for file in snapshot.files])))
    _pdf_rows(snapshot, codes, out, citation_checks, row_checks)
    for key in ('responsible_professional', 'professional_qualifications'):
        if engineering:
            out.append(_one(doc, BY_FIELD[key], codes, engineering, heuristics=True))
    declarations = snapshot.professional_declarations
    declaration = declarations[0] if len(declarations) == 1 else None
    involvement = declaration.involvement if declaration else 'unresolved'
    if len(declarations) > 1:
        out.append(_finding_element(Finding(key='professional:declaration_sources', section='D',
            field='professional_source', label='professional declaration sources', status='not_found',
            problem='source_unresolved', severity='blocking', routed_to='officer',
            message='Multiple professional declarations were supplied; the controlling source is unresolved.',
            pointers=[Pointer(**entry.pointer.model_dump()) for entry in declarations])))
    if declaration and involvement != 'unresolved':
        if not declaration.bound_to_application:
            involvement = 'unresolved'
            out.append(_finding_element(Finding(key='professional:declaration_scope', section='D',
                field='professional_source', label='professional declaration scope', status='not_found',
                problem='source_unresolved', severity='blocking', routed_to='officer',
                message='The visible professional declaration could not be bound to the owner and location read from this application.',
                pointers=[Pointer(**declaration.pointer.model_dump())])))
    resolved = involvement in ('professional_involved', 'not_required')
    known_required = bool(declaration and declaration.bound_to_application and declaration.requirement == 'yes')
    out.append(ElementVerdict('professional_requirement', 'D', 'D', 'professional_requirement', [],
        'professional involvement', '', 'present' if resolved else 'unclear',
        'The visible administrative declaration records ' + involvement.replace('_', ' ') +
        '. Credentials, authority and technical scope remain for human review.' if resolved else
        'A registered engineer or architect is recorded as required for this scope. Their responsibility and authentication need human review.' if known_required else
        'Whether a registered professional is required is unresolved. The officer must determine it from the scope and sources.',
        problem=None if resolved else 'requirement_unresolved', severity='warning', in_export_preflight=False,
        routed_to='professional' if engineering or known_required else 'officer'))

    for item in snapshot.context_items:
        element = ElementVerdict(item.field, 'B' if item.section == 'process' else item.section,
            item.section, item.field, [], item.label, 'Visible administrative input context', item.verdict, item.reason,
            key=item.key, problem=item.reason_code, severity=item.severity, routed_to=item.routed_to,
            certainty=item.certainty, in_export_preflight=item.export_blocking, fix_hint=item.fix_hint,
            citations=item.citations, pointers=[pointer.model_dump() for pointer in item.pointers],
            submission_blocking=item.submission_blocking, finding_status=item.finding_status,
            defect_class=item.key.split(':')[0] if re.match(r'^D\d+:', item.key) else None)
        if item.key.startswith('export:unconfirmed:'):
            element.export_reason = item.reason   # 'unconfirmed <kind> fact "<field>" (<id>)'
        out.append(element)

    from .completeness_rules import _on_variance
    on_alternative = _on_variance(doc)
    responsible = [row.responsible.value for row in snapshot.documents if row.responsible.known]
    person = doc.values.get('professional_name')
    if person and person.confirmed and person.value.strip():
        responsible.append(person.value)
    where = Pointer(file=doc.ref)
    uncertain_pages = {(pointer.file, pointer.page) for pointer in snapshot.unreadable}
    readable_corpus = [(file, page, text) for file, page, text in snapshot.applicant_corpus
                       if (file, page) not in uncertain_pages and (file, None) not in uncertain_pages]
    # The code analysis can span the applicant's rationale and its verified attribution table.
    # Quoted code requirements alone cannot supply the applicant's testing procedures.
    analysis_parts_present = (doc.values.get('rationale') and doc.values['rationale'].status == 'present'
                              and row_checks and all(row.status in ('match', 'no_table_row') for row in row_checks))
    skip = {'div_c.code_analysis'} if analysis_parts_present else set()
    # An answered, labelled passage supplies its own Division C item; no keyword is needed inside it.
    for passage, item in (('qualifications', 'div_c.qualifications'), ('maintenance_operation', 'div_c.maintenance')):
        if doc.values.get(passage) and doc.values[passage].status == 'present':
            skip.add(item)
    # An unread Section C or D cell can hold a file item (for example the co-ordinator), so it is a location too.
    locations = list(snapshot.unreadable)
    if snapshot.form and snapshot.field_map:
        locations += [_pointer(snapshot.form, value) for name, value in sorted(snapshot.form.fields.items())
                      if value.status == 'not_found' and _label(snapshot.field_map, name)[1] in ('C', 'D')]
    for finding in div_c.file_findings(readable_corpus, where, codes, responsible=responsible, skip=skip,
                                     on_alternative_path=on_alternative, uncertain=bool(locations)):
        if finding.status == 'not_found':
            finding.pointers = locations
            finding.routed_to = 'officer'
        out.append(_finding_element(finding))
    signal = div_c.peer_review_finding(professional_required=engineering,
        provisions=list(case.provisions) if case else [check.provision_id for check in citation_checks if check.provision_id],
        rungs=[row.evidence_rung.value for row in snapshot.documents],
        novel_product=any(div_c.NOVEL.search(text) for _file, _page, text in snapshot.corpus), where=where)
    if signal:
        out.append(_finding_element(signal))
    for row in snapshot.documents:
        if row.listed_in_section_d and not row.file:
            uncertain_identity = bool(snapshot.unreadable)
            out.append(_finding_element(Finding(key=f'attachment:{_title_key(row.title.value)}:presence', section='D',
                field=f'evidence.{row.id}.file_ref' if case else f'attachment.{_title_key(row.title.value)}',
                label=f'attachment “{row.title.value}”',
                status='not_found' if uncertain_identity else 'missing',
                problem='attachment_unresolved' if uncertain_identity else 'missing_attachment', severity='blocking',
                routed_to='officer' if uncertain_identity else 'applicant',
                message=(f'The named attachment “{row.title.value}” could not be identified among the readable sources.'
                         if uncertain_identity else f'The named supporting document “{row.title.value}” has no matching attachment.'),
                pointers=([row.title.source] if row.title.source else [where]) + snapshot.unreadable)))
        if row.listed_in_section_d and not row.responsible.known:
            out.append(_finding_element(Finding(key=f'document:{_title_key(row.title.value)}:responsible',
                section='D', field=f'evidence.{row.id}.responsible_party' if case else f'document.{row.id}',
                label=f'responsible person for “{row.title.value}”', status='missing', problem='no_responsible',
                defect_class='D13', severity='blocking', message='Your application appears to be missing a responsible person or organisation for this supporting document.',
                pointers=[row.title.source] if row.title.source else [where])))
    # One upload is identified by its pages; several uploads also need their names, or one would hide another.
    unreadable_files = [file for file in snapshot.files if file.role == 'unreadable']
    named = len(snapshot.files) > 1 or len({pointer.file for pointer in snapshot.unreadable}) > 1
    for file in unreadable_files:
        out.append(_finding_element(Finding(key=f'file:{file.name}:unreadable', section='D', field=f'file.{file.name}',
            label=f'file "{file.name}"', status='not_found', problem='unreadable', severity='blocking',
            routed_to='officer', message=f'{file.note} Check this file by eye.'.strip(),
            pointers=[Pointer(file=file.name)])))
    for pointer in snapshot.unreadable:
        if any(pointer.file == file.name for file in unreadable_files):
            continue
        out.append(_finding_element(Finding(
            key=f'source:{pointer.file}:page:{pointer.page or 0}' if named else f'source:page:{pointer.page or 0}',
            section='D', field='attachment_source', label='readable attachment contents', status='not_found',
            problem='source_unresolved', severity='blocking', routed_to='officer',
            message='The supplied source could not be fully read. Check the indicated file or page before treating its contents as supplied or absent.',
            pointers=[pointer])))
    _citation_findings(snapshot, codes, out, citation_checks)
    for field_name, failed in (
            ('section_c.provision_found', any(element.defect_class == 'D05' for element in out)),
            ('section_c.pair_match', any(row.status == 'mismatch' for row in row_checks))):
        if field_name == 'section_c.provision_found':
            known = bool(row_checks) and all(check.exists is True for check in citation_checks)
        else:
            known = bool(row_checks) and all(row.status in ('match', 'no_table_row') for row in row_checks)
        spec = BY_FIELD[field_name]
        out.append(ElementVerdict(field_name, 'C', 'C', field_name, list(spec.form_fields), spec.label, '',
            'missing' if failed else 'present' if known else 'unclear',
            ' '.join(element.reason for element in out if element.defect_class == 'D05') if failed and field_name == 'section_c.provision_found' else
            'See the located deterministic Section C checks.' if failed else
            'All supplied rows passed this deterministic check.' if known else
            'This check could not be completed from the supplied sources; review the located rows.',
            problem='row_check_failed' if failed else None, lookup_skipped=not known and not failed))
    return _finish(snapshot, out, citation_checks, row_checks)


def _title_key(title):
    return re.sub(r'[^a-z0-9]+', '-', title.casefold()).strip('-')


def _finish(snapshot, elements, citations, rows):
    doc = snapshot.document
    unique = {}
    gaps = []
    public = []
    for element in elements:
        stored = doc.values.get({'responsible_professional': 'professional_name'}.get(element.field, element.field))
        if (stored is None and doc.case is not None and element.verdict == 'missing'
                and element.field in BY_FIELD):
            element.certainty, element.finding_status = 'blank', 'blank'
        if stored is None and doc.case and element.field == 'professional_requirement':
            from .professional import _STATUS_FIELDS
            from .process_fields import latest_fact
            status = latest_fact(doc.case, *_STATUS_FIELDS)
            if status:
                source = status.source.model_dump()
                element.sources.append(source)
                element.pointers.append(_source_pointer(source, doc.ref))
        for quote in element.quotes:
            if quote.source and quote.source not in element.sources:
                element.sources.append(quote.source)
                element.pointers.append(_source_pointer(quote.source, doc.ref))
        if stored:
            element.value = stored.value if stored.confirmed and stored.status != 'not_found' and stored.value.strip() else None
            if element.certainty == 'not_applicable':
                element.value = None
            else:
                element.certainty = ('not_found' if not stored.confirmed or stored.status == 'not_found' else
                                     'present' if element.value is not None else 'blank')
            if stored.source and stored.source not in element.sources:
                element.sources.append(stored.source)
            if stored.pointers:
                element.pointers = list(stored.pointers)
            elif not element.pointers:
                element.pointers = [_source_pointer(stored.source or {}, doc.ref)]
            if element.certainty == 'not_found' and element.problem in ('not_found', 'unconfirmed'):
                element.routed_to = 'officer' if stored.status == 'not_found' else 'applicant'
                if stored.reason:
                    element.reason = stored.reason
        if not element.key:
            problem = 'presence' if element.problem in (None, 'blank', 'placeholder', 'not_found', 'unconfirmed') else element.problem
            element.key = f'{element.field}:{problem}'
        if element.certainty == 'not_found':
            element.pointers = [{**pointer, 'quote': located_quote(pointer.get('quote'))} for pointer in element.pointers]
        if not element.pointers:
            element.pointers = [{'file': doc.ref}]
        if element.prompt is None and element.verdict != 'present':
            element.prompt = {'question': element.fix_hint or element.reason, 'field': element.export_field,
                              'form_fields': element.form_fields, 'source': element.source}
        if not element.fix_hint and element.prompt:
            element.fix_hint = element.prompt['question']
        if element.verdict == 'present':
            element.in_export_preflight = False
            element.export_reason = None
            element.prompt = None
        if element.in_export_preflight and element.export_reason is None:
            element.export_reason = format_export_reason(element.export_section, element.export_field,
                                                         element.reason, element.fix_hint)
        if element.verdict == 'present' and stored is None and element.certainty == 'not_found':
            element.certainty = 'not_applicable'  # a passed check, not a value that went unread
        if element.key in unique:
            continue
        unique[element.key] = element
        if element.verdict != 'present' and (element.problem or element.in_export_preflight) and element.field != 'peer_review':
            gap_id = f'{element.defect_class}:{element.field}' if element.defect_class else element.key
            gaps.append(Gap(id=gap_id, section=element.export_section, field=element.field, message=element.reason,
                            severity=element.severity, routed_to=element.routed_to,
                            submission_blocking=element.submission_blocking, fix_hint=element.fix_hint,
                            citation=element.citations[0] if element.citations else None))
        public.append(AdministrativeItem(key=element.key, field=element.field, section=element.export_section,
            label=element.label, verdict=element.verdict, reason_code=element.problem or ('supplied' if element.verdict == 'present' else
                                             'lookup_skipped' if element.lookup_skipped else 'unresolved'), reason=element.reason,
            value=element.value, certainty=element.certainty, severity=element.severity,
            finding_status=element.finding_status,
            routed_to=element.routed_to or 'applicant', export_blocking=element.in_export_preflight,
            submission_blocking=element.submission_blocking, fix_hint=element.fix_hint,
            citations=element.citations, sources=element.sources,
            pointers=[PolicyPointer(**pointer) for pointer in element.pointers]))
    reasons = list(dict.fromkeys(element.export_reason for element in sorted(
        unique.values(), key=lambda element: not element.key.startswith('export:unconfirmed:'))
        if element.export_reason))
    return PolicyResult(list(unique.values()), gaps, AdministrativeReport(items=public, export_reasons=reasons,
                         ready_for_export=not reasons), citations, rows)


CITATION_PROBLEMS = {'nonexistent_provision', 'superseded_edition', 'page_mismatch',
                     'attribution_not_in_table', 'lookup_skipped', 'source_unresolved'}


def _norm(text):
    return re.sub(r'\s+', ' ', text or '').strip()


def _intent_ok(text):
    folded = text.casefold()
    return ('explanatory' in folded or INTENT_LABEL.casefold() in folded or 'no row' in folded
            or 'no nbc 2020' in folded or bool(cite._APPENDIX.search(text)) and len(text) < 40)


def _pdf_rows(snapshot, codes, out, citation_checks, row_checks):
    if not snapshot.form or not snapshot.field_map:
        return
    bucket = SimpleNamespace(findings=[], citations=citation_checks, section_c=row_checks)
    description = snapshot.document.values.get('alternative_description')
    pointer = description.pointers[0] if description and description.pointers else {'file': snapshot.document.ref}
    _rows(snapshot.form, snapshot.field_map, codes, bucket, SimpleNamespace(
        status=description.status if description else 'not_found', value=description.value if description else '',
        file=pointer['file'], page=pointer.get('page')))
    _section_d(snapshot.form, snapshot.field_map, bucket)
    out.extend(_finding_element(finding) for finding in bucket.findings)


def _citation_findings(snapshot, codes, out, checks):
    # A citation can wrap across lines or continuation pages. Keep each source's
    # context together, with a page map for the resulting pointers.
    chunks = []
    for read in snapshot.reads:
        pieces, locations, offset = [], [], 0
        for page in read.text_pages:
            text = re.sub(r'Batatis appendix to SCC variance form - case [^\n]+\n', '', page.text)
            text = re.sub(r'Appendix page \d+\s*', '', text)
            locations.append((offset, offset + len(text), page.page + 1))
            pieces.append(text)
            offset += len(text) + 1
        if pieces:
            chunks.append((read.name, '\n'.join(pieces), locations))
    if not chunks:
        chunks = [(file, text, [(0, len(text), page)]) for file, page, text in snapshot.corpus]
    for file, text, locations in chunks:
        matches = list(cite.PROVISION.finditer(text))
        results = cite.verify_citation(text, Pointer(file=file), codes)
        for match, check in zip(matches, results):
            page = next((page for start, end, page in locations if start <= match.start() <= end), None)
            pointer = Pointer(file=file, page=page)
            check.pointer = pointer
            checks.append(check)
            for issue in check.issues:
                if issue.code not in CITATION_PROBLEMS:
                    continue
                uncertain = issue.code in {'lookup_skipped', 'source_unresolved'}
                out.append(_finding_element(Finding(
                    key=f'citation:{page}:{check.provision_id}:{issue.code}', section='D',
                    field=f'citation.{check.provision_id}', label=f'citation of {check.provision_id}',
                    status='not_found' if uncertain else 'unclear', problem=issue.code,
                    defect_class={'nonexistent_provision': 'D05', 'superseded_edition': 'D06'}.get(issue.code),
                    message=issue.message, severity='blocking',
                    routed_to='officer' if uncertain else 'applicant', pointers=[pointer])))


def _rows(form, fmap, codes, parts, description) -> None:
    if not fmap:
        return
    fields = form.fields
    code_std = fields.get('Code or Standard')
    edition = code_std.value if code_std and code_std.status == 'present' else ''
    row_ids: list[str] = []
    rows = []
    for number, row in enumerate(fmap['section_c_rows'], start=1):
        cells = {key: fields.get(widget) for key, widget in row.items()}
        article = cells['article']
        if article is None or article.status != 'present':
            continue
        rows.extend(_overflow_rows(form, article) or [(number, cells)])
    for number, cells in rows:
        article = cells['article']
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
        unreadable = [cells[key] for key in ('objective', 'function')
                      if cells.get(key) and cells[key].status == 'not_found']
        if unreadable:
            message = ('The objective or functional statement could not be read confidently. '
                       'Check the indicated cells before comparing the pair.')
            comparison = SectionCCheck(row=number, provision_id=ids[0] if ids else None,
                                       form_objective=objective or None, form_function=function or None,
                                       status='not_checked', message=message, pointer=_pointer(form, unreadable[0]))
            parts.findings.append(Finding(
                key=f'section_c.row{number}:pair', section='C', field=f'section_c.row{number}.pair',
                label=f'Section C row {number} objective and function', status='not_found', problem='unreadable',
                message=message, pointers=[_pointer(form, cell) for cell in unreadable]))
        else:
            comparison = cite.compare_row(number, article.value, objective, function, pointer, codes)
            if (comparison.status == 'not_checked' and comparison.provision_id
                    and cite.complete_visible_attribution(form, number, comparison.provision_id, codes)):
                comparison.status = 'match'
                comparison.message = 'Every attribution pair and condition in the visible appendix matches the deterministic lookup.'
        parts.section_c.append(comparison)
        if comparison.status == 'not_checked' and not unreadable:
            parts.findings.append(Finding(
                key=f'section_c.row{number}:source', section='C', field=f'section_c.row{number}.pair',
                label=f'Section C row {number} attribution scope', status='not_found', problem='source_unresolved',
                message=comparison.message, severity='blocking', routed_to='officer', pointers=[pointer]))
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


_OVERFLOW = re.compile(r'Rows (\d+)-(\d+)')


def _overflow_rows(form, article):
    """Batatis's own marker for rows that continue in its appendix ("Rows 5-24"): check each listed row there.

    A marker whose rows cannot all be found stays a single unresolved row; nothing is assumed to pass.
    """
    marker = _OVERFLOW.fullmatch(article.value.strip())
    if not marker:
        return None
    rows = []
    for number in range(int(marker.group(1)), int(marker.group(2)) + 1):
        found = [(page.page, hit.group(1), re.split(r'(?m)^(?:C-\d+[ \t]|Batatis appendix)', page.text[hit.end():])[0])
                 for page in form.text_pages for hit in re.finditer(rf'(?m)^C-{number}[ \t]+(\S+)', page.text)]
        # The appendix names a row in its table and again in its detail; one provision per row is required.
        if len({pid for _page, pid, _block in found}) != 1 or not cite.provision_ids(found[0][1]):
            return None
        page, pid = found[0][:2]
        # Its table prints "no table row" where it has no pair; otherwise the pairs are compared in its detail.
        shown = 'No table row' if any(re.search(r'\bno table row\b', block, re.I) for *_rest, block in found) \
            else 'See Appendix C'
        appendix = lambda name, value: FieldValue(name, page, None, 'present', value)
        rows.append((number, {'article': appendix(article.name, pid),
                              'objective': appendix(f'C-{number} objective', shown),
                              'function': appendix(f'C-{number} function', shown), 'intent': None}))
    return rows


def _section_d(form, fmap, parts) -> None:
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


def _attachment_citations(attachments, codes, parts) -> None:
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


