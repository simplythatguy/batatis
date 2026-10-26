"""Officer projections of the shared administrative policy; no officer-only rule ownership."""
from __future__ import annotations

from dataclasses import dataclass, field

from ..completeness_policy import evaluate
from ..completeness_snapshot import from_case, from_uploads
from ..models_completeness import AdministrativeReport
from ..models_review import CitationCheck, DocumentRow, FieldReading, Finding, InputFile, Pointer, SectionCCheck
from .passages import TEXT_FIELDS, TextValue, rationale_value, text_value


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
    policy: AdministrativeReport | None = None


def _parts(snapshot, codes, result=None):
    result = result or evaluate(snapshot, codes)
    parts = Parts(files=snapshot.files, fields=list(snapshot.fields), documents=snapshot.documents,
                  citations=result.citations, section_c=result.section_c, lookup_skipped=codes is None,
                  case_version=snapshot.document.case.version if snapshot.document.case else None,
                  policy=result.report)
    for item in result.report.items:
        pointers = [Pointer(**pointer.model_dump()) for pointer in item.pointers]
        if snapshot.document.case is not None:
            parts.fields.append(FieldReading(field=item.field, label=item.label, section=item.section,
                status=item.certainty if item.certainty in ('present', 'blank') else 'not_found',
                value=item.value if item.certainty == 'present' else None,
                reason=item.reason, pointer=pointers[0]))
        if item.verdict == 'present' or (not item.export_blocking and item.reason_code == 'supplied'):
            continue
        if item.severity == 'info':
            continue  # informational notices remain available in policy.items, never applicant gaps
        status = item.finding_status or ('not_found' if item.certainty == 'not_found' and item.reason_code in
                  ('not_found', 'source_unresolved', 'signature_unread', 'lookup_skipped') else
                  'unclear' if item.verdict == 'unclear' else
                  'blank' if item.reason_code == 'blank' else 'missing')
        # The existing request projection represents unread content as an excluded
        # not_found row (officer_check=True). Preserve that transport convention;
        # policy.items carries the explicit officer route for both workspaces.
        route = ('applicant' if status == 'not_found' and item.field != 'attachment_source'
                 and item.reason_code != 'requirement_unresolved' else item.routed_to)
        parts.findings.append(Finding(key=item.key, section=item.section, field=item.field, label=item.label,
            status=status, problem=item.reason_code, message=item.reason, severity=item.severity,
            routed_to=route, pointers=pointers, citations=item.citations,
            defect_class=next((element.defect_class for element in result.elements if element.key == item.key), None)))
    return parts


def review_uploads(uploads, codes) -> Parts:
    return _parts(from_uploads(uploads), codes)


def review_case(case, codes, store=None) -> Parts:
    from ..export.package import prepare_package
    prepared = prepare_package(case, codes, store=store)
    parts = _parts(prepared.snapshot, codes, prepared.policy)
    parts.case_version = case.version
    parts.fields = from_case(case, store).fields + parts.fields
    from .documents import case_rows
    parts.documents = case_rows(case, store)
    return parts
