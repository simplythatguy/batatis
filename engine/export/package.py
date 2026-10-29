"""Prepare once: render actual outgoing bytes, then evaluate exactly those bytes."""
from __future__ import annotations

import io
import re
import sqlite3
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import TYPE_CHECKING

from pypdf import PdfReader, PdfWriter
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.pdfgen import canvas

from ..completeness import Gap, _case_constraints
from ..fact_aliases import LOGICAL_KEYS, is_withdrawal, latest
from ..path_decision import decide_path
from ..process_fields import confirmed_value
from ..professional import professional_confirmed, professional_involvement
from ..section_d import supporting_documents
from ..package_format import CONTEXT, ATTACHMENT, PHOTO
from .scc import CURRENT_MAP, ExportResult, _render_case, confirmed_values
from .signatures import stamp_draft
from .text import pdf_safe

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


def _image_pdf(data: bytes, title: str) -> bytes | None:
    """A photo (JPEG, PNG, WebP) as one captioned letter page, so the package carries what was attached."""
    from PIL import Image, ImageOps, UnidentifiedImageError
    from reportlab.lib.pagesizes import letter
    from reportlab.lib.utils import ImageReader
    try:
        with Image.open(io.BytesIO(data)) as opened:
            if opened.format not in ('JPEG', 'PNG', 'WEBP'):
                return None
            image = ImageOps.exif_transpose(opened).convert('RGB')
    except (UnidentifiedImageError, OSError, ValueError):
        return None
    width, height = letter
    margin, caption = 36, 28
    scale = min((width - 2 * margin) / image.width, (height - 2 * margin - caption) / image.height)
    drawn = (image.width * scale, image.height * scale)
    output = io.BytesIO()
    page = canvas.Canvas(output, pagesize=letter, invariant=1)
    page.drawImage(ImageReader(image), (width - drawn[0]) / 2, margin + caption + (height - 2 * margin - caption - drawn[1]) / 2, *drawn)
    # The marker has its own short line so no title, however long, can push it off the page.
    page.setFont('Helvetica', 8)
    page.drawString(margin, margin, PHOTO)
    label = pdf_safe(f'Photo supplied by the applicant: {title}')
    while label and stringWidth(label, 'Helvetica', 8) > width - 2 * margin:
        label = label[:-2].rstrip() + '…'
    page.drawString(margin, margin + 11, label)
    page.save()
    return output.getvalue()


ANSWER_LABELS = {'permit_number': 'permit number', 'pathway': 'solution path', 'storeys': 'number of storeys',
                 'lot': 'lot number', 'block': 'block number', 'plan': 'plan number'}


def answer_label(canonical: str) -> str:
    """What the applicant calls an answer; never a fact id."""
    from ..completeness_elements import BY_FIELD

    field = LOGICAL_KEYS.get(canonical, canonical)
    if field in BY_FIELD:
        return BY_FIELD[field].label
    if canonical.startswith('evidence.'):
        return 'a supporting document'
    if canonical.startswith('citation.'):
        return f'the code reference {canonical.removeprefix("citation.").rstrip(".")}'
    return ANSWER_LABELS.get(canonical) or f'the answer for {field.split(".")[-1].replace("_", " ")}'


def _count_app_signatures(snapshot, case) -> None:
    """A signature made in the app is painted as an image, which reading the package cannot establish.
    The workspace records it against this exact content, so it counts as signed and dated."""
    from ..review.ingest import StoredValue
    from .signatures import current_signatures

    values = snapshot.document.values
    for role, signature in current_signatures(case).items():
        key = f'{role}_signature'
        if key in values:
            values[key] = StoredValue(key, f'Signed in the application by {signature.name}', 'exact', None,
                                      status='present', input_field=key, pointers=values[key].pointers)
            values[f'{key}_date'] = StoredValue(f'{key}_date', signature.signed_on, 'exact', signature.signed_on,
                                                status='present', input_field=f'{key}_date')


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
        # A cleared answer is withdrawn, not pending: a required field is reported missing by its own check.
        if not is_withdrawal(fact) and not _stored(fact, canonical).confirmed:
            label = answer_label(canonical)
            constraints.append(Gap(id=f'export:unconfirmed:{canonical}', section='B',
                field=LOGICAL_KEYS.get(canonical, canonical),
                message=f'{label[:1].upper()}{label[1:]} is not confirmed yet.',
                fix_hint='Confirm it, change it or clear it.'))
    result = _render_case(case, draft=draft, codes=codes, form=form, version=version, signing=original)
    writer = PdfWriter(clone_from=io.BytesIO(result.pdf))

    def append(data):
        for page in PdfReader(io.BytesIO(data)).pages:
            writer.add_page(page)

    def append_gap(gap, reason_code=None):
        missing = 'Your application appears to be missing '
        label = (gap.message[len(missing):].rstrip('.') if gap.message.startswith(missing)
                 else gap.field.replace('_', ' '))
        append(_page([CONTEXT, 'Record type: unresolved input', f'Requirement key: {gap.id}',
            f'Section: {gap.section}', f'Field: {gap.field}', f'Label: {label}',
            f'Reason code: {reason_code or ("unconfirmed" if gap.id.startswith("export:unconfirmed:") else "saved_constraint")}',
            f'Severity: {gap.severity}', f'Route: {gap.routed_to or "applicant"}',
            f'Submission blocking: {"yes" if gap.submission_blocking else "no"}',
            f'Message: {gap.message}', f'Fix: {gap.fix_hint}', f'Citation: {gap.citation or ""}',
            'End administrative source record']))

    involvement = professional.involvement if professional else 'unresolved'
    # A settled screen states its own basis; an unresolved one names the deciding question.
    basis = 'Source unresolved' if professional is None else professional.decision or ' '.join(
        reason.message for reason in professional.reasons if reason.required == professional.required)
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
        f'Name: {name}', f'Role: {role}', f'Basis: {basis}',
        f'Owner: {values.get("owner_name") or ""}', f'Location: {"; ".join(dict.fromkeys(locations))}',
        f'Pathway: {decide_path(case).path}',
        'End administrative source record']
    append(_page(declaration))
    for gap in constraints:
        append_gap(gap)
    # A saved reading marked not found travels visibly, so the reader says not found rather than blank.
    from ..completeness_elements import BY_FIELD
    from ..process_fields import PROCESS_ALIASES, latest_fact
    unread = dict.fromkeys(match.group(1) or match.group(2) for fact in case.facts
                           for match in [re.fullmatch(r'presence\.(.+)|review\.(.+)\.presence', fact.field)] if match)
    for key in unread:
        presence = latest_fact(case, f'presence.{key}', f'review.{key}.presence')
        if presence is not None and presence.value in ('not_found', 'unreadable'):
            spec = BY_FIELD.get(key)
            append_gap(Gap(id=f'presence:{key}', section=spec.export_section if spec else 'B', field=key,
                message=f'The {key.replace("_", " ")} was not found or could not be read. Check its source.',
                fix_hint='Check the indicated source and confirm this answer.', routed_to='officer'), 'not_found')
    # The appendix prints answered passages only. On the alternative path, record each
    # unanswered process field and the site-versus-municipality scope so a reader can call it blank.
    if decide_path(case).path == 'alternative':
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
            data = _image_pdf(data, document.title) or data
        if not data.startswith(b'%PDF-'):
            try:
                data = _page(data.decode('utf-8').splitlines())
            except UnicodeError:
                append_gap(Gap(id=f'source:{document.id}', field='attachment_source', section='D',
                    message=f'The supplied attachment {document.title} could not be decoded.',
                    fix_hint='Supply a readable attachment.', routed_to='officer'), 'source_unresolved')
                continue
        try:
            reader = PdfReader(io.BytesIO(data))
            # Sealed reports often carry only an owner password: they open without one, so they are kept.
            locked = reader.is_encrypted and not reader.decrypt('')
            pages = 0 if locked else len(reader.pages)
        except Exception:
            locked, pages = False, 0
        if not pages:
            append_gap(Gap(id=f'source:{document.id}', field='attachment_source', section='D',
                message=(f'The attached document "{document.title}" could not be opened.'
                         + (' Attach a copy that opens without a password.' if locked else '')),
                fix_hint='Supply a readable PDF.', routed_to='officer'), 'source_unresolved')
            continue
        append(_page([ATTACHMENT,
            'The following pages are the supplied source. Its contents, not a saved extraction quote, own the checks.',
            f'Attachment number: {number}', f'Source name: {source_name}',
            f'Title: {document.title}', f'Responsible: {document.responsible_party}', f'Page count: {pages}',
            'End supporting source header']))
        first = len(writer.pages)
        for page in reader.pages:
            writer.add_page(page)
        writer.add_outline_item(pdf_safe(document.title), first)
    output = io.BytesIO()
    writer.write(output)
    result.pdf = output.getvalue()
    result.record_pages = len(writer.pages) - result.form_pages - result.appendix_pages
    # The policy reads the package content; a draft's quiet page mark is added after, to every page.
    snapshot = from_uploads([('application.pdf', result.pdf)])
    _count_app_signatures(snapshot, original)
    policy = evaluate(snapshot, codes)
    result.open_items = policy.report.export_reasons
    if draft:
        stamp_draft(writer)
        output = io.BytesIO()
        writer.write(output)
        result.pdf = output.getvalue()
    return PreparedPackage(result, policy, snapshot)
