"""Paint explicit current signatures, retaining blank signature widgets for other tools."""
from __future__ import annotations

import base64
import io

from pypdf import PdfReader
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas

from ..workspace import content_hash, signers
from .text import fit, pdf_safe

SIGNATURE_FIELDS = {'owner': ('Signature1', 'Date1'), 'owner_rep': ('Signature2', 'Date2')}
OFFICER_FIELDS = {'Signature3', 'SCO Date', 'Signature4', 'SCO Date1'}
CONSENT_FIELD = 'Check Box14'


def current_signatures(case):
    digest = content_hash(case)
    roles = {signer.role for signer in signers(case)}
    return {signature.role: signature for signature in case.workspace.signatures
            if signature.content_hash == digest and signature.role in roles}


def live_fields(case) -> set[str]:
    current = current_signatures(case)
    keep = set(OFFICER_FIELDS)
    for role, names in SIGNATURE_FIELDS.items():
        if role not in current:
            keep.update(names)
    if not (case.workspace.consent and case.workspace.consent.agreed):
        keep.add(CONSENT_FIELD)
    return keep


def paint_signatures(writer, case, widgets) -> None:
    current = current_signatures(case)
    by_page = {}
    for page_no, name, widget in widgets:
        for role, (signature_field, date_field) in SIGNATURE_FIELDS.items():
            if role in current and name == signature_field:
                by_page.setdefault(page_no, []).append((role, widget['/Rect'], current[role]))
    dates = {name: widget['/Rect'] for _page, name, widget in widgets}
    for page_no, signatures in by_page.items():
        page = writer.pages[page_no]
        buf = io.BytesIO()
        draw = canvas.Canvas(buf, pagesize=(float(page.mediabox.width), float(page.mediabox.height)))
        for role, rect, signature in signatures:
            x0, y0, x1, y1 = map(float, rect)
            image = ImageReader(io.BytesIO(base64.b64decode(signature.image.split(',', 1)[1])))
            draw.drawImage(image, x0 + 2, y0 + 2, width=x1 - x0 - 4, height=y1 - y0 - 4,
                           preserveAspectRatio=True, anchor='c', mask='auto')
            date_rect = dates.get(SIGNATURE_FIELDS[role][1])
            if date_rect:
                draw.setFont('Helvetica', 10)
                draw.drawString(float(date_rect[0]) + 3, float(date_rect[1]) + 4, signature.signed_on)
            # The supplied form has a printed-name row, but no widget. Share its
            # baseline with the printed label, leaving the source wording intact.
            left = 190 if role == 'owner' else 290
            printed_rect = (left, y0 - 20, 566, y0 - 3)
            fitted = fit(pdf_safe(signature.name), printed_rect, 9, 6)
            if fitted is None or len(fitted[0]) != 1:
                raise ValueError('The printed signer name is too long for the supplied form.')
            draw.setFont('Helvetica', fitted[1])
            draw.drawString(left, y0 - 11, fitted[0][0])
        draw.save()
        page.merge_page(PdfReader(buf).pages[0])


def stamp_draft(writer) -> None:
    for page in writer.pages:
        width, height = float(page.mediabox.width), float(page.mediabox.height)
        buf = io.BytesIO()
        draw = canvas.Canvas(buf, pagesize=(width, height))
        draw.setFillGray(0.58)
        draw.setFont('Helvetica', 8)
        draw.drawRightString(width - 24, height - 13, 'Draft · not for submission')
        draw.save()
        page.merge_page(PdfReader(buf).pages[0])
