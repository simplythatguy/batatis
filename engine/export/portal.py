"""Package prepared for the safety codes officer to register on the Orders and Variances Portal.

IB-2026-10-01: from 2026-12-01 the portal is the sole method; only a safety codes
officer registers; registration is not Council approval; the filled form and
supporting documentation go together; one variance is for one location;
unnecessary personal information in supporting documents is flagged so it can be
removed or redacted. This module does not edit files and does not decide that a
file is safe.

The 10-day copy in IB-2025-11-18 is a copy of the issued variance, attached as a
reminder, not as a pre-flight failure. Pre-flight reuses the completeness gates.

The checks below are the unofficial OVP rules that would reject an upload.
They were read from the public front end at https://ovp.safetycodes.ab.ca/
before login on 2026-10-20. That list is not SCC documentation and may change.
A JSON sidecar, derived discipline and AHJ, civic-address splitting, and the
lists that load after login are post-submission. See docs/ovp-portal-fields.md.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from ..bulletin_gates import applicant_reminder, bulletin_gaps
from ..models import Case
from ..process_fields import confirmed_value

_EMAIL = re.compile(r'[A-Z0-9._%+\-]+@[A-Z0-9.\-]+\.[A-Z]{2,}', re.I)
_PHONE = re.compile(r'(?<!\d)(?:\+?1[\s.\-]?)?(?:\(?\d{3}\)?[\s.\-]\d{3}[\s.\-]\d{4})(?!\d)')
# Sentence-level or finer, as the public bundle requires: 3.5.2.1.(2), plus an optional clause.
_SENTENCE = re.compile(r'^\d+\.\d+\.\d+\.\d+\.\(\d+\)(\([a-z]\)(\([ivxlcdm]+\))?)?$', re.I)
_SPECIAL = re.compile(r'[\\/:*?"<>|]')
_PLAIN_NAME = re.compile(r'^[A-Za-z0-9._ -]{1,100}$')
_ALLOWED_SUFFIXES = {'.pdf', '.txt', '.jpg', '.jpeg', '.png', '.tif', '.tiff', '.csv'}
_MAX_BYTES = 25 * 1024 * 1024
_MAX_NAME = 100
_SENTENCE_FLAG = 'needs sentence-level reference'

# Left blank. The registering officer fills these. Never copy them from the case.
SCO_FIELDS = (
    'Issuing SCO',
    'Designation of Power',
    'Employer',
    'Discipline',
    'AHJ',
    'Variance status',
    'Issue Date',
)
NOT_OVP_FIELDS = ('owner', 'signature', 'objectives')
SCO_ROLE = 'filled by the registering SCO'


@dataclass
class PortalAttachment:
    name: str
    text: str
    needs_personal_information: bool = False
    size_bytes: int | None = None
    document_type: str = 'Supporting Document'


@dataclass
class ManifestEntry:
    name: str
    role: str
    needs_personal_information: bool
    included: bool
    note: str
    value: str = ''


@dataclass
class RedactionFlag:
    attachment: str
    kind: str
    match: str
    bulletin_id: str
    message: str


@dataclass
class PortalLocation:
    """Civic address, lot/block/plan, or ATS. Any one is enough. municipal_address is not required."""

    ready: bool
    civic_address: str
    lot: str
    block: str
    plan: str
    ats_qtr: str
    ats_sec: str
    ats_twp: str
    ats_rge: str
    ats_mer: str
    note: str


@dataclass
class CodeItem:
    code_set: str
    reference: str
    sentence_level: bool
    flag: str | None = None


@dataclass
class AttachmentCheck:
    name: str
    document_type: str
    format_ok: bool
    size_ok: bool | None
    name_ok: bool
    suggested_name: str
    problems: list[str] = field(default_factory=list)
    present: bool = True


@dataclass
class PortalPackage:
    bulletin_ids: tuple[str, ...]
    form_pdf: bytes | None
    form_included: bool
    form_note: str
    manifest: list[ManifestEntry] = field(default_factory=list)
    redaction_flags: list[RedactionFlag] = field(default_factory=list)
    preflight_reasons: list[str] = field(default_factory=list)
    reminder_verdict: str = 'reminder'
    reminder: str = ''
    reminder_links: list[str] = field(default_factory=list)
    location: PortalLocation | None = None
    code_items: list[CodeItem] = field(default_factory=list)
    attachment_checks: list[AttachmentCheck] = field(default_factory=list)
    documents_ready: bool = False
    not_ovp_fields: tuple[str, ...] = NOT_OVP_FIELDS

    def text(self) -> str:
        lines = [
            'Portal registration package prepared for the safety codes officer to register',
            'Registration is not Council approval.',
            'OVP field list: unofficial, from the public front end before login, and it may change.',
            'Bulletins: ' + ', '.join(self.bulletin_ids),
            self.form_note,
            'Owner, signature and objectives stay in the variance form PDF. They are not OVP fields.',
            'Pre-flight:',
        ]
        lines += [f'- {reason}' for reason in self.preflight_reasons] or ['- none']
        lines.append('Manifest:')
        for item in self.manifest:
            value = ' value=(blank);' if item.role == SCO_ROLE else f' value={item.value!r};'
            lines.append(
                f'- {item.role}: {item.name}; included={item.included};{value} '
                f'needs_personal_information={item.needs_personal_information}; {item.note}')
        if self.location is not None:
            lines.append(f'Location: ready={self.location.ready}; {self.location.note}')
        lines.append('Code items:')
        lines += [
            f'- {item.code_set or "(no code set)"} {item.reference}'
            + (f' [{item.flag}]' if item.flag else '')
            for item in self.code_items] or ['- none']
        lines.append('Attachment checks:')
        lines += [
            f'- {item.document_type}: {item.name}; format_ok={item.format_ok}; '
            f'size_ok={item.size_ok}; name_ok={item.name_ok}; suggested={item.suggested_name}'
            for item in self.attachment_checks] or ['- none']
        lines.append(f'Documents ready (Variance Form and Supporting Document)={self.documents_ready}')
        lines.append('Redaction flags (not edited, not a safety finding):')
        lines += [f'- {flag.attachment}: {flag.kind} ({flag.bulletin_id})' for flag in self.redaction_flags] or ['- none']
        lines.append(self.reminder)
        return '\n'.join(lines) + '\n'


def _text(value) -> str:
    return '' if value is None else str(value).strip()


def portal_location(case: Case) -> PortalLocation:
    """Any one of a civic address, lot/block/plan, or ATS. municipal_address is not required.

    The civic string is not split. Splitting suite, house, street, municipality, and
    postal code is post-submission.
    """
    civic = _text(confirmed_value(case, 'civic_address', 'municipal_address', 'municipalAddress', 'address'))
    lot = _text(confirmed_value(case, 'lot'))
    block = _text(confirmed_value(case, 'block'))
    plan = _text(confirmed_value(case, 'plan'))
    ats = {key: _text(confirmed_value(case, key))
           for key in ('ats_qtr', 'ats_sec', 'ats_twp', 'ats_rge', 'ats_mer')}
    legal_ok = bool(lot and block and plan)
    ats_ok = all(ats.values())
    ready = bool(civic) or legal_ok or ats_ok
    if ready:
        note = ('One of civic address, lot/block/plan, or ATS is present. '
                'municipal_address is not required.')
    else:
        note = ('Location is not ready for OVP. Provide a civic address, or lot, block and plan, '
                'or an ATS description. Do not invent the missing parts.')
    return PortalLocation(
        ready, civic, lot, block, plan,
        ats['ats_qtr'], ats['ats_sec'], ats['ats_twp'], ats['ats_rge'], ats['ats_mer'], note)


def _references(case: Case) -> list[str]:
    found: list[str] = []
    for provision in list(case.provisions) + [row.provision_id for row in case.section_c]:
        token = _text(provision)
        if token and token not in found:
            found.append(token)
    article = confirmed_value(case, 'section_c.article', 'article')
    token = _text(article)
    if token and token not in found:
        found.append(token)
    return found


def code_items_for(case: Case) -> list[CodeItem]:
    """Flag an id that is not already sentence-level. Never choose or invent a sentence."""
    code_set = _text(confirmed_value(case, 'code_or_standard', 'code_set'))
    items = []
    for reference in _references(case):
        compact = re.sub(r'\s+', '', reference)
        sentence_level = bool(_SENTENCE.match(compact))
        items.append(CodeItem(
            code_set, reference, sentence_level, None if sentence_level else _SENTENCE_FLAG))
    return items


def suggest_filename(name: str) -> str:
    """A file name within 100 characters and without special characters. The original is not renamed."""
    cleaned = _SPECIAL.sub('-', name or '')
    cleaned = re.sub(r'[^A-Za-z0-9._ -]', '-', cleaned)
    cleaned = re.sub(r'-{2,}', '-', cleaned).strip(' .-')
    if not cleaned:
        cleaned = 'attachment'
    suffix = ''
    if '.' in cleaned:
        base, ext = cleaned.rsplit('.', 1)
        if 1 <= len(ext) <= 5:
            suffix = '.' + ext
            cleaned = base
    room = _MAX_NAME - len(suffix)
    cleaned = cleaned[:room].rstrip(' .-')
    if not cleaned:
        cleaned = 'attachment'
    return (cleaned + suffix)[:_MAX_NAME]


def check_attachment(name: str, document_type: str, size_bytes: int | None) -> AttachmentCheck:
    suffix = ''
    if '.' in (name or ''):
        suffix = name[name.rfind('.'):].casefold()
    format_ok = suffix in _ALLOWED_SUFFIXES
    if size_bytes is None:
        size_ok = None
    else:
        size_ok = 0 <= size_bytes <= _MAX_BYTES
    name_ok = bool(_PLAIN_NAME.match(name or ''))
    problems = []
    if document_type not in ('Variance Form', 'Supporting Document'):
        problems.append('Tag the file Variance Form or Supporting Document.')
    if not format_ok:
        problems.append('Allowed formats are PDF, TXT, JPG, PNG, TIF, and CSV.')
    if size_ok is False:
        problems.append('The file is over the 25 MB limit.')
    elif size_ok is None:
        problems.append('File size was not supplied, so the 25 MB limit was not checked.')
    if not name_ok:
        problems.append('The file name must be 100 characters or fewer and have no special characters.')
    return AttachmentCheck(
        name or '', document_type, format_ok, size_ok, name_ok, suggest_filename(name or ''), problems)


def _sco_entries() -> list[ManifestEntry]:
    return [ManifestEntry(
        label, SCO_ROLE, False, False,
        'Left blank. The registering safety codes officer fills this. It is never auto-filled. '
        'Unofficial OVP field; the list may change.',
        value='') for label in SCO_FIELDS]


def _permit_entry(case: Case) -> ManifestEntry:
    permit = _text(confirmed_value(case, 'permit_number', 'permitNumber'))
    return ManifestEntry(
        'Permit #', 'optional', False, bool(permit),
        'Optional. Not invented.' if permit else 'Optional. Not supplied.',
        value=permit)


def _preflight_reasons(case: Case, codes) -> list[str]:
    from ..completeness_variants import format_export_reason

    if codes is not None:
        from ..completeness import check_completeness
        gaps = check_completeness(case, codes)
    else:
        gaps = bulletin_gaps(case)
    return [format_export_reason(gap.section, gap.field, gap.message, gap.fix_hint)
            for gap in gaps if gap.severity == 'blocking']


def _flags(attachments: list[PortalAttachment]) -> list[RedactionFlag]:
    found = []
    for attachment in attachments:
        if attachment.needs_personal_information or attachment.document_type == 'Variance Form':
            continue
        for kind, pattern in (('email', _EMAIL), ('phone', _PHONE)):
            for match in pattern.findall(attachment.text or ''):
                found.append(RedactionFlag(
                    attachment=attachment.name, kind=kind, match=match, bulletin_id='IB-2026-10-01',
                    message=(f'IB-2026-10-01: supporting attachment "{attachment.name}" includes a {kind}. '
                             'Unnecessary personal information should be removed or redacted before the safety '
                             'codes officer registers the variance. Registration is not Council approval. '
                             'This check does not edit the file and does not decide that the file is safe.')))
    return found


def portal_package(case: Case, *, codes=None, attachments: list[PortalAttachment] | None = None,
                   form=None) -> PortalPackage:
    """Filled form, upload checks, and the shared completeness pre-flight.

    SCO-side fields are manifest lines marked filled by the registering safety codes
    officer. They stay blank. Owner, signature and objectives are not OVP fields.
    """
    from .scc import ExportBlocked, FormNotFound, export_case

    attachments = list(attachments or [])
    reminder = applicant_reminder()
    reasons = _preflight_reasons(case, codes)
    form_pdf = None
    if reasons:
        form_note = (
            'The filled form was not produced because the completeness pre-flight has open items. '
            'This package is prepared for the safety codes officer to register. Registration is not '
            'Council approval. IB-2026-10-01.')
    else:
        try:
            result = export_case(case, codes=codes, form=form)
        except ExportBlocked as exc:
            form_note = (
                'The filled form was not produced because export pre-flight refused the case. '
                'This package is prepared for the safety codes officer to register. Registration is not '
                'Council approval. IB-2026-10-01.')
            if not reasons:
                reasons = list(exc.reasons)
        except FormNotFound:
            form_note = (
                'The SCC variance form file is not on this machine, so the filled form was not produced. '
                'This package is prepared for the safety codes officer to register. Registration is not '
                'Council approval. IB-2026-10-01.')
        except FileNotFoundError:
            form_note = (
                'The code database is not on this machine, so the filled form was not produced. '
                'This package is prepared for the safety codes officer to register. Registration is not '
                'Council approval. IB-2026-10-01.')
        else:
            form_pdf = result.pdf
            form_note = (
                'Filled variance form included in the package prepared for the safety codes officer to register. '
                'IB-2026-10-01. Registration is not Council approval. '
                'The form does not replace the supporting documentation.')
    attachment_checks: list[AttachmentCheck] = []
    if form_pdf is not None:
        attachment_checks.append(check_attachment('Variance-form.pdf', 'Variance Form', len(form_pdf)))
    manifest = [ManifestEntry(
        'Variance form', 'form', True, form_pdf is not None,
        'Variance Form. Personal information belongs on the form. Prepared for the safety codes officer '
        'to register. Registration is not Council approval. IB-2026-10-01. '
        'Owner, signature and objectives stay in this PDF and are not separate OVP fields.')]
    saw_supporting = False
    for attachment in attachments:
        document_type = attachment.document_type or 'Supporting Document'
        if document_type == 'Supporting Document':
            saw_supporting = True
        check = check_attachment(attachment.name, document_type, attachment.size_bytes)
        attachment_checks.append(check)
        manifest.append(ManifestEntry(
            attachment.name, 'supporting' if document_type == 'Supporting Document' else 'form',
            attachment.needs_personal_information, True,
            f'{document_type}. Suggested file name: {check.suggested_name}. '
            'Registration is not Council approval. IB-2026-10-01.'))
    has_variance_form = form_pdf is not None or any(
        item.document_type == 'Variance Form' for item in attachments)
    if not has_variance_form:
        missing_form = check_attachment('Variance-form.pdf', 'Variance Form', None)
        missing_form.present = False
        missing_form.problems.append('A Variance Form file is required.')
        attachment_checks.append(missing_form)
    if not saw_supporting:
        attachment_checks.append(AttachmentCheck(
            '', 'Supporting Document', False, None, False, 'supporting-document.pdf',
            ['A Supporting Document is required.'], present=False))
    manifest.extend(_sco_entries())
    manifest.append(_permit_entry(case))
    present = [item for item in attachment_checks if item.present]
    present_types = {item.document_type for item in present}
    documents_ready = (
        'Variance Form' in present_types and 'Supporting Document' in present_types
        and all(item.format_ok and item.name_ok and item.size_ok is True and not item.problems
                for item in present))
    return PortalPackage(
        bulletin_ids=('IB-2026-10-01', 'IB-2025-11-18', 'IB-2026-10-16'),
        form_pdf=form_pdf, form_included=form_pdf is not None, form_note=form_note, manifest=manifest,
        redaction_flags=_flags(attachments), preflight_reasons=reasons,
        reminder_verdict=reminder['verdict'], reminder=reminder['text'], reminder_links=list(reminder['links']),
        location=portal_location(case), code_items=code_items_for(case),
        attachment_checks=attachment_checks, documents_ready=documents_ready)
