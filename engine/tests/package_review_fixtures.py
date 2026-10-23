"""SYNTHETIC package-review fixtures: fillable, flattened and scanned SCC forms plus attachments.

Every name, address and document is fictional. Forms are built from the blank SCC
form (BATATIS_SCC_FORM); attachments are drawn with reportlab. Nothing is committed
as a PDF file.
"""
from __future__ import annotations

import copy
import io

import pytest
from pypdf import PdfReader, PdfWriter
from pypdf.generic import ArrayObject, NameObject

from engine.export.scc import FormMismatch, FormNotFound, form_path, load_field_map, load_form

LABEL = 'NBC 2020 Intent Statements, explanatory only'

CLEAN_FORM = {
    'Owner': 'SYNTHETIC Example Homes Ltd.',
    'Owner Rep': 'SYNTHETIC J. Example',
    'Mailing Address': '000 Example Avenue NW, Edmonton AB',
    'Date of Reqeuest': '2026-10-20',
    'Municipal Address': '000 Example Crescent SW, Calgary AB',
    'Lot': '12', 'Block': '3', 'Plan': '0000000',
    'Code or Standard': 'National Building Code - 2023 Alberta Edition (2nd printing), Division B',
    'Article(s)': '9.10.15.5.(8)', 'Objective': 'OP3.1', 'Function': 'F03',
    'Intent statement': f'{LABEL}: limit fire spread through roof soffits.',
    'Supporting Doc': 'SYNTHETIC soffit fire test report',
    'Name Responsible': 'SYNTHETIC Example Labs Inc.',
    'Owner Print': 'SYNTHETIC Example Homes Ltd.',
    'Date1': '2026-10-20',
}

CLEAN_NARRATIVE = {
    'Description of the proposed alternative': 'SYNTHETIC: a protected roof soffit on the east exposing building '
                                               'face, where the limiting distance is 0.40 m. limiting distance: 0.40 m',
    'Rationale': 'SYNTHETIC applicant rationale; no technical conclusion.',
    'Risk assessment': 'SYNTHETIC applicant passage: fire spread from the soffit to the neighbouring house during '
                       'the time emergency responders need to arrive.',
    'Mitigating measures': 'SYNTHETIC applicant passage: noncombustible soffit with the fire spread limited at the '
                           'exposing building face and the neighbouring house.',
    'Assumptions and limits': 'SYNTHETIC applicant passage: assumes a single-family house; limited to the east face. '
                              'Assumes a fire department response within the municipal standard.',
    'Code analysis': 'SYNTHETIC applicant passage: objectives and functional statements F03-OP3.1 from the '
                     'Division B table.',
    'Testing procedures': 'SYNTHETIC: soffit assembly tested to CAN/ULC-S134 (no test performed).',
    'Qualifications': 'SYNTHETIC: design by a fictional registered professional; no licence is claimed.',
    'Maintenance and commissioning': 'SYNTHETIC: annual inspection of the soffit; if maintenance lapses or the '
                                     'protection fails, the owner restores it before occupancy continues.',
}

CLEAN_REPORT = [
    'SYNTHETIC soffit fire test report',
    'Issued by: SYNTHETIC Example Labs Inc.',
    'Date: 2026-09-30',
    'Accredited under ISO/IEC 17025 (synthetic statement, no test performed).',
    'Test report on a protected soffit assembly. limiting distance: 0.40 m',
    'Sealed by: SYNTHETIC P.Eng. (no real seal)',
]


def blank_form() -> bytes:
    fmap = load_field_map()
    try:
        return load_form(form_path(), fmap)
    except (FormNotFound, FormMismatch):
        pytest.skip('SCC variance form not available (set BATATIS_SCC_FORM)')


def _filled_writer(values: dict) -> PdfWriter:
    writer = PdfWriter(clone_from=io.BytesIO(blank_form()))
    writer.set_need_appearances_writer(True)
    texts = {k: v for k, v in values.items() if v is not None}
    writer.update_page_form_field_values(None, texts, auto_regenerate=False)
    return writer


def fillable(values: dict) -> bytes:
    buf = io.BytesIO()
    _filled_writer(values).write(buf)
    return buf.getvalue()


def flattened(values: dict) -> bytes:
    """Fill, merge the appearances into the page and drop every widget, as the official export does."""
    writer = PdfWriter(clone_from=io.BytesIO(blank_form()))
    texts = {k: v for k, v in values.items() if v}
    writer.update_page_form_field_values(None, texts, auto_regenerate=False, flatten=True)
    for page in writer.pages:
        if '/Annots' in page:
            keep = [a for a in page['/Annots'] if a.get_object().get('/Subtype') != '/Widget']
            if keep:
                page[NameObject('/Annots')] = ArrayObject(keep)
            else:
                del page['/Annots']
    del writer._root_object['/AcroForm']
    buf = io.BytesIO()
    writer.write(buf)
    return buf.getvalue()


def scanned(pdf: bytes) -> bytes:
    """Image-only copy: no text layer, as a scanner would produce."""
    import pypdfium2 as pdfium
    from reportlab.lib.utils import ImageReader
    from reportlab.pdfgen import canvas
    doc = pdfium.PdfDocument(pdf)
    buf = io.BytesIO()
    page0 = doc[0]
    width, height = page0.get_size()
    c = canvas.Canvas(buf, pagesize=(width, height))
    for page in doc:
        image = page.render(scale=1).to_pil()
        c.drawImage(ImageReader(image), 0, 0, width, height)
        c.showPage()
    c.save()
    return buf.getvalue()


def text_pdf(lines: list[str]) -> bytes:
    from reportlab.lib.pagesizes import letter
    from reportlab.pdfgen import canvas
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=letter)
    y = 740
    for line in lines:
        if y < 60:
            c.showPage()
            y = 740
        c.drawString(50, y, line)
        y -= 18
    c.save()
    return buf.getvalue()


def narrative_pdf(sections: dict) -> bytes:
    lines = ['SYNTHETIC Section B narrative and process fields']
    for heading, body in sections.items():
        lines += ['', heading, body if body is not None else '', '']
    return text_pdf(lines)


def repeated_rationale_pdf(body='raster', *, unique_heading=False, reversed_stop=False) -> bytes:
    """Two labelled candidates; the second body is not necessarily in the text layer."""
    import pypdfium2 as pdfium
    from reportlab.lib.utils import ImageReader
    from reportlab.pdfgen import canvas
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=(612, 792))
    c.drawString(48, 748, 'Rationale')
    c.drawString(48, 708, 'Risk assessment')
    c.drawString(48, 600, 'Rationale for variance' if unique_heading else 'Rationale')
    if body in ('raster', 'outside'):
        source = io.BytesIO()
        text = canvas.Canvas(source, pagesize=(480, 80))
        text.drawString(12, 40, 'SYNTHETIC supplied rationale raster body.')
        text.save()
        doc = pdfium.PdfDocument(source.getvalue())
        raster = doc[0].render(scale=1.5).to_pil()
        c.drawImage(ImageReader(raster), 48, 20 if body == 'outside' else 465, width=480, height=80)
    elif body == 'vector':
        c.line(48, 520, 480, 480)
    c.drawString(48, 640 if reversed_stop else 420, 'Risk assessment')
    c.save()
    return buf.getvalue()


def covered_scan_pdf(cover='separate') -> bytes:
    """A scanned applicant passage, optionally behind or below a readable cover."""
    import pypdfium2 as pdfium
    from reportlab.lib.utils import ImageReader
    from reportlab.pdfgen import canvas
    source = pdfium.PdfDocument(text_pdf([
        'Rationale', 'SYNTHETIC supplied applicant rationale.', 'Risk assessment',
        'SYNTHETIC following process field.']))
    raster = source[0].render(scale=1).to_pil()
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=(612, 792))
    if cover != 'none':
        c.drawString(48, 748, 'SYNTHETIC supplement - applicant passage follows.')
        if cover == 'separate':
            c.showPage()
    c.drawImage(ImageReader(raster), 0, 0, width=612, height=700 if cover == 'same-page' else 792)
    c.save()
    return buf.getvalue()


def annotated_rationale_pdf(kind='text', *, layout='labelled', flags=4, appearance='stream',
                            subtype='/Stamp', passage='', rotation=0) -> bytes:
    """SYNTHETIC visible or non-rendered annotation appearances, never page text."""
    from reportlab.pdfgen import canvas
    from pypdf.generic import DecodedStreamObject, DictionaryObject, NumberObject, TextStringObject
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=(612, 792))
    if layout in ('cover', 'cover-page'):
        c.drawString(48, 748, 'SYNTHETIC readable supplement cover.')
        if layout == 'cover-page':
            c.showPage()
            c.drawString(48, 748, 'SYNTHETIC continuation page.')
    else:
        c.drawString(48, 748, 'Rationale')
        if passage:
            c.drawString(48, 700, passage)
        c.drawString(48, 500, 'Risk assessment')
    c.save()
    writer = PdfWriter()
    writer.append(io.BytesIO(buf.getvalue()))
    ap = DecodedStreamObject()
    ap.set_data(b'BT /F1 12 Tf 6 36 Td (SYNTHETIC applicant passage supplied as an annotation.) Tj ET'
                if kind == 'text' else b'4 w 10 10 m 470 70 l S')
    if appearance == 'empty':
        ap.set_data(b'q Q')
    elif appearance == 'invisible-text':
        ap.set_data(ap.get_data().replace(b'BT ', b'BT 3 Tr '))
    ap.update({NameObject('/Type'): NameObject('/XObject'), NameObject('/Subtype'): NameObject('/Form'),
               NameObject('/BBox'): ArrayObject([NumberObject(x) for x in (0, 0, 500, 80)]),
               NameObject('/Resources'): DictionaryObject({NameObject('/Font'): DictionaryObject({
                   NameObject('/F1'): DictionaryObject({NameObject('/Type'): NameObject('/Font'),
                       NameObject('/Subtype'): NameObject('/Type1'), NameObject('/BaseFont'): NameObject('/Helvetica')})})})})
    y = 80 if layout == 'outside' else 580
    rect = (48, y, 548, y + 80)
    if layout == 'page-rect-outside':
        rect = (0, 0, 612, 792)
        ap[NameObject('/BBox')] = ArrayObject([NumberObject(x) for x in rect])
    annotation = DictionaryObject({NameObject('/Type'): NameObject('/Annot'), NameObject('/Subtype'): NameObject(subtype),
        NameObject('/Rect'): ArrayObject([NumberObject(x) for x in rect]),
        NameObject('/F'): NumberObject(flags), NameObject('/Contents'): TextStringObject('SYNTHETIC metadata, not page text.')})
    if appearance != 'missing':
        normal = writer._add_object(ap)
        if appearance in ('state', 'unselected-state'):
            normal = DictionaryObject({NameObject('/On'): normal})
            annotation[NameObject('/AS')] = NameObject('/On' if appearance == 'state' else '/Off')
        annotation[NameObject('/AP')] = DictionaryObject({NameObject('/N'): normal})
    writer.add_annotation(page_number=len(writer.pages) - 1, annotation=annotation)
    if rotation:
        writer.pages[-1].rotate(rotation)
    out = io.BytesIO()
    writer.write(out)
    return out.getvalue()


def package(form_values=None, narrative=None, report=None, *, flat=False, drop=()):
    form_values = copy.deepcopy(CLEAN_FORM if form_values is None else form_values)
    narrative = copy.deepcopy(CLEAN_NARRATIVE if narrative is None else narrative)
    report = list(CLEAN_REPORT if report is None else report)
    files = [('scc-form.pdf', (flattened if flat else fillable)(form_values)),
             ('section-b-narrative.pdf', narrative_pdf({k: v for k, v in narrative.items() if k not in drop})),
             ('soffit-test-report.pdf', text_pdf(report))]
    return files


def reader_fields(pdf: bytes) -> dict:
    return PdfReader(io.BytesIO(pdf)).get_fields() or {}
