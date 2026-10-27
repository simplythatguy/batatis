"""Prepare once: render actual outgoing bytes, then evaluate exactly those bytes."""
from __future__ import annotations

import io
import sqlite3
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import TYPE_CHECKING

from pypdf import PdfReader, PdfWriter
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.pdfgen import canvas

from ..completeness import Gap, _case_constraints
from ..fact_aliases import LOGICAL_KEYS, latest
from ..process_fields import confirmed_value
from ..professional import professional_confirmed, professional_involvement
from ..section_d import supporting_documents
from ..package_format import CONTEXT, ATTACHMENT
from .scc import CURRENT_MAP, ExportResult, _render_case, confirmed_values

if TYPE_CHECKING:
    from ..completeness_policy import PolicyResult
    from ..completeness_snapshot import Snapshot


@dataclass
class PreparedPackage:
    export: ExportResult
    policy: PolicyResult
    snapshot: Snapshot


class _CodeSnapshot:
    """One operation reads each code record once; nothing survives the request."""
    def __init__(self, codes):
        self._codes = codes
        self._provision = lru_cache(maxsize=None)(lambda pid, division: codes.provision(pid, division))

    def provision(self, provision_id, division='B'):
        return self._provision(provision_id, division)

    def citation(self, provision_id, division='B'):
        record = self.provision(provision_id, division)
        return record['citation'] if record else None

    def __getattr__(self, name):
        return getattr(self._codes, name)


_FONT, _SIZE, _LEFT, _WIDTH = 'Helvetica', 10, 40, 612 - 2 * 40


def _wrap(line: str) -> list[str]:
    """Lines measured to fit the page: break between words, and inside a word only when it alone is too wide."""
    lines, current, width = [], '', 0.0
    space = stringWidth(' ', _FONT, _SIZE)
    for word in line.split(' '):
        size = stringWidth(word, _FONT, _SIZE)
        if current and width + space + size <= _WIDTH:
            current, width = f'{current} {word}', width + space + size
            continue
        if current and size <= _WIDTH:
            lines.append(current)
            current, width = word, size
            continue
        if current:                 # a word wider than the page starts on this line, like textwrap
            current, width = current + ' ', width + space
        for char in word:
            step = stringWidth(char, _FONT, _SIZE)
            if current.strip() and width + step > _WIDTH:
                lines.append(current.rstrip())
                current, width = '', 0.0
            current, width = current + char, width + step
    lines.append(current)
    return lines


def _page(lines):
    """Visible records only. No embedded JSON or metadata carries policy authority."""
    output = io.BytesIO()
    c = canvas.Canvas(output, pagesize=(612, 792), invariant=1)
    c.setFont(_FONT, _SIZE)
    y = 752
    for line in lines:
        for part in _wrap(str(line).expandtabs(4)):
            if y < 44:
                c.showPage()
                c.setFont(_FONT, _SIZE)
                y = 752
            c.drawString(_LEFT, y, part)
            y -= 13
    c.save()
    return output.getvalue()


def _source(case, document, store):
    if store is not None:
        saved = store.get_file(case.id, document.file.ref)
        return (saved.get('name') or document.file.ref, saved['data']) if saved and saved.get('data') else None
    root = Path(__file__).resolve().parents[2]
    path = (root / document.file.ref).resolve()
    if path.is_relative_to(root) and path.is_file():
        return document.file.ref, path.read_bytes()
    return None


def prepare_package(case, codes, *, store=None, draft=False, form=None, version=CURRENT_MAP):
    from ..completeness_policy import evaluate, signature_date_gaps
    from ..completeness_snapshot import from_uploads
    from ..review.ingest import _stored, ingested_from_case, effective_case

    codes = _CodeSnapshot(codes)
    original = case
    case = effective_case(case)

    try:
        professional = professional_involvement(case, codes)
        constraints = _case_constraints(case, codes, professional=professional)
    except (KeyError, ValueError, OSError, RuntimeError, sqlite3.Error):
        professional = None
        constraints = [Gap(id='source:administrative', field='code_source', section='C',
            message='The administrative source could not be resolved; its result remains uncertain.',
            fix_hint='Restore the source and rerun this review.', routed_to='officer')]
    constraints += [Gap(**gap.model_dump(), fix_hint='Resolve this saved administrative finding.') for gap in case.gaps]
    constraints.extend(signature_date_gaps(ingested_from_case(case)))
    for canonical, fact in latest(original).items():
        if not _stored(fact, canonical).confirmed:
            constraints.append(Gap(id=f'export:unconfirmed:{canonical}', section='B',
                field=LOGICAL_KEYS.get(canonical, canonical),
                message=f'unconfirmed {fact.kind} fact "{fact.field}" ({fact.id})',
                fix_hint='Confirm or withdraw the latest answer; do not restore an older answer.'))
    result = _render_case(case, draft=draft, codes=codes, form=form, version=version, store=store)
    writer = PdfWriter(clone_from=io.BytesIO(result.pdf))

    def append(data):
        for page in PdfReader(io.BytesIO(data)).pages:
            writer.add_page(page)

    def append_gap(gap, reason_code=None):
        append(_page([CONTEXT, 'Record type: unresolved input', f'Requirement key: {gap.id}',
            f'Section: {gap.section}', f'Field: {gap.field}',
            f'Reason code: {reason_code or ("unconfirmed" if gap.id.startswith("export:unconfirmed:") else "saved_constraint")}',
            f'Severity: {gap.severity}', f'Route: {gap.routed_to or "applicant"}',
            f'Submission blocking: {"yes" if gap.submission_blocking else "no"}',
            f'Message: {gap.message}', f'Fix: {gap.fix_hint}', f'Citation: {gap.citation or ""}',
            'End administrative source record']))

    involvement = professional.involvement if professional else 'unresolved'
    role = confirmed_value(case, 'professional.role', 'professional_role') or ''
    name = confirmed_value(case, 'professional_name', 'responsible_professional', 'professional.name') or ''
    values = confirmed_values(case)
    from ..review.bulletin_gates import _missing
    locations = [str(values[key]) for key in ('municipal_address', 'additional_location', 'second_location', 'extra_location')
                 if key in values and not _missing(values[key])]
    declaration = [CONTEXT,
        'These are recorded administrative statements. Credentials, authority and technical scope need human review.',
        'Record type: professional declaration',
        f'Involvement: {involvement}', f'Requirement: {professional.required if professional else "depends"}',
        f'Applicant confirmation: {"yes" if professional_confirmed(case) else "no"}',
        f'Name: {name}', f'Role: {role}', f'Basis: {professional.decision if professional else "Source unresolved"}',
        f'Owner: {values.get("owner_name") or ""}', f'Location: {"; ".join(dict.fromkeys(locations))}',
        f'Pathway: {confirmed_value(case, "pathway", "path") or "alternative"}',
        'End administrative source record']
    append(_page(declaration))
    for gap in constraints:
        append_gap(gap)
    # The appendix prints answered passages only; record each unanswered one so a reader can call it blank.
    from ..process_fields import PROCESS_ALIASES, latest_fact
    unanswered = [(key, 'process', f'process.{key}', (*names, *(f'process.{name}' for name in names)))
                  for key, names in PROCESS_ALIASES.items()] + [('scope', 'B', 'scope', ('scope',))]
    for key, section, canonical, names in unanswered:
        fact = latest_fact(case, *names)
        if fact is None or (_stored(fact, canonical).confirmed and not str(fact.value or '').strip()):
            append_gap(Gap(id=f'{key}:unanswered', section=section, field=key, severity='warning',
                message=f'No {key.replace("_", " ")} was supplied.', fix_hint='Supply this answer.'), 'blank')
    # Statements not represented in the template's ordinary A-D/process fields stay visible.
    for key in ('code_analysis', 'testing_procedures', 'coordinator', 'failure_conditions',
                'lapsed_maintenance', 'emergency_response', 'engineering_required'):
        value = confirmed_value(case, key)
        if value is not None:
            append(_page(['Applicant supplemental statement', key.replace('_', ' ').capitalize() + ':', str(value)]))
    for number, document in enumerate(supporting_documents(case), start=1):
        try:
            source = _source(case, document, store)
        except (KeyError, OSError, ValueError):
            source = None
        if source is None:
            append_gap(Gap(id=f'source:{document.id}', field='attachment_source', section='D',
                message=f'The actual bytes for the named attachment {document.title} are unavailable.',
                fix_hint='Supply the readable attachment.', routed_to='officer'), 'source_unresolved')
            continue
        source_name, data = source
        if not data.startswith(b'%PDF-'):
            try:
                data = _page(data.decode('utf-8').splitlines())
            except UnicodeError:
                append_gap(Gap(id=f'source:{document.id}', field='attachment_source', section='D',
                    message=f'The supplied attachment {document.title} could not be decoded.',
                    fix_hint='Supply a readable attachment.', routed_to='officer'), 'source_unresolved')
                continue
        try:
            pages = len(PdfReader(io.BytesIO(data)).pages)
        except Exception:
            append_gap(Gap(id=f'source:{document.id}', field='attachment_source', section='D',
                message=f'The supplied PDF {document.title} could not be read.',
                fix_hint='Supply a readable PDF.', routed_to='officer'), 'source_unresolved')
            continue
        append(_page([ATTACHMENT,
            'The following pages are the supplied source. Its contents, not a saved extraction quote, own the checks.',
            f'Attachment number: {number}', f'Source name: {source_name}',
            f'Title: {document.title}', f'Responsible: {document.responsible_party}', f'Page count: {pages}',
            'End supporting source header']))
        append(data)
    output = io.BytesIO()
    writer.write(output)
    result.pdf = output.getvalue()
    result.record_pages = len(writer.pages) - result.form_pages - result.appendix_pages
    snapshot = from_uploads([('application.pdf', result.pdf)])
    policy = evaluate(snapshot, codes)
    result.open_items = policy.report.export_reasons
    return PreparedPackage(result, policy, snapshot)
