"""Registration package for the Orders and Variances Portal.

IB-2026-10-01: from 2026-12-01 the portal is the sole registration method; the
filled form and supporting documentation are included together; one registration
covers one location; unnecessary personal information in supporting documents is
flagged so it can be removed or redacted. This module does not edit files and
does not decide that a file is safe.

The 10-day copy in IB-2025-11-18 is attached as a reminder, not as a pre-flight
failure. Pre-flight reuses the completeness gates.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from ..bulletin_gates import applicant_reminder, bulletin_gaps
from ..models import Case

_EMAIL = re.compile(r'[A-Z0-9._%+\-]+@[A-Z0-9.\-]+\.[A-Z]{2,}', re.I)
_PHONE = re.compile(r'(?<!\d)(?:\+?1[\s.\-]?)?(?:\(?\d{3}\)?[\s.\-]\d{3}[\s.\-]\d{4})(?!\d)')


@dataclass
class PortalAttachment:
    name: str
    text: str
    needs_personal_information: bool = False


@dataclass
class ManifestEntry:
    name: str
    role: str
    needs_personal_information: bool
    included: bool
    note: str


@dataclass
class RedactionFlag:
    attachment: str
    kind: str
    match: str
    bulletin_id: str
    message: str


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

    def text(self) -> str:
        lines = [
            'Portal registration package',
            'Bulletins: ' + ', '.join(self.bulletin_ids),
            self.form_note,
            'Pre-flight:',
        ]
        lines += [f'- {reason}' for reason in self.preflight_reasons] or ['- none']
        lines.append('Manifest:')
        for item in self.manifest:
            lines.append(
                f'- {item.role}: {item.name}; included={item.included}; '
                f'needs_personal_information={item.needs_personal_information}; {item.note}')
        lines.append('Redaction flags (not edited, not a safety finding):')
        lines += [f'- {flag.attachment}: {flag.kind} ({flag.bulletin_id})' for flag in self.redaction_flags] or ['- none']
        lines.append(self.reminder)
        return '\n'.join(lines) + '\n'


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
        if attachment.needs_personal_information:
            continue
        for kind, pattern in (('email', _EMAIL), ('phone', _PHONE)):
            for match in pattern.findall(attachment.text or ''):
                found.append(RedactionFlag(
                    attachment=attachment.name, kind=kind, match=match, bulletin_id='IB-2026-10-01',
                    message=(f'IB-2026-10-01: supporting attachment "{attachment.name}" includes a {kind}. '
                             'Unnecessary personal information should be removed or redacted before registration. '
                             'This check does not edit the file and does not decide that the file is safe.')))
    return found


def portal_package(case: Case, *, codes=None, attachments: list[PortalAttachment] | None = None,
                   form=None) -> PortalPackage:
    """Filled form, attachment manifest, redaction flags, and the shared completeness pre-flight."""
    from .scc import ExportBlocked, FormNotFound, export_case

    attachments = list(attachments or [])
    reminder = applicant_reminder()
    reasons = _preflight_reasons(case, codes)
    form_pdf = None
    if reasons:
        form_note = 'The filled form was not produced because the completeness pre-flight has open items. IB-2026-10-01.'
    else:
        try:
            # Import stays local so this module does not change scc.py path handling.
            result = export_case(case, codes=codes, form=form)
        except ExportBlocked as exc:
            form_note = 'The filled form was not produced because export pre-flight refused the case. IB-2026-10-01.'
            if not reasons:
                reasons = list(exc.reasons)
        except FormNotFound:
            form_note = 'The SCC variance form file is not on this machine, so the filled form was not produced. IB-2026-10-01.'
        except FileNotFoundError:
            form_note = 'The code database is not on this machine, so the filled form was not produced. IB-2026-10-01.'
        else:
            form_pdf = result.pdf
            form_note = (
                'Filled variance form included. IB-2026-10-01: include it at registration. '
                'The form does not replace the supporting documentation.')
    manifest = [ManifestEntry(
        'Variance form', 'form', True, form_pdf is not None,
        'Personal information belongs on the form. IB-2026-10-01.')]
    for attachment in attachments:
        manifest.append(ManifestEntry(
            attachment.name, 'supporting', attachment.needs_personal_information, True,
            'Supporting documentation included at registration. IB-2026-10-01.'))
    return PortalPackage(
        bulletin_ids=('IB-2026-10-01', 'IB-2025-11-18', 'IB-2026-10-16'),
        form_pdf=form_pdf, form_included=form_pdf is not None, form_note=form_note, manifest=manifest,
        redaction_flags=_flags(attachments), preflight_reasons=reasons,
        reminder_verdict=reminder['verdict'], reminder=reminder['text'], reminder_links=list(reminder['links']))
