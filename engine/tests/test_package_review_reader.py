"""Blank (certain) versus not found (ask the officer) on SYNTHETIC fillable, flattened and scanned forms."""
from __future__ import annotations

import io

from pypdf import PdfReader, PdfWriter

from engine.review.package import review_uploads
from engine.review.pdf_reader import read_pdf
from engine.tests.package_review_fixtures import CLEAN_FORM, blank_form, fillable, flattened, scanned, text_pdf

OWNER_RECT = (113, 481, 571, 496)


def _overlay(pdf: bytes, draw) -> bytes:
    from reportlab.pdfgen import canvas
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=(612, 792))
    draw(c)
    c.save()
    stamp = PdfReader(io.BytesIO(buf.getvalue())).pages[0]
    writer = PdfWriter(clone_from=io.BytesIO(pdf))
    writer.pages[0].merge_page(stamp)
    out = io.BytesIO()
    writer.write(out)
    return out.getvalue()


def test_fillable_empty_field_is_blank_and_filled_is_present_with_pointer():
    read = read_pdf(fillable(dict(CLEAN_FORM, Owner='')), 'form.pdf')
    assert read.role == 'scc_form_fillable' and read.form_version == 'scc_2026-10'
    assert read.fields['Owner'].status == 'blank'
    rep = read.fields['Owner Rep']
    assert rep.status == 'present' and rep.value == CLEAN_FORM['Owner Rep'] and rep.page == 0 and rep.rect


def test_untouched_blank_form_reads_every_applicant_field_blank():
    read = read_pdf(blank_form(), 'blank.pdf')
    assert {value.status for name, value in read.fields.items() if name != 'Check Box'} == {'blank'}


def test_flattened_empty_box_is_blank_and_text_is_present():
    read = read_pdf(flattened(dict(CLEAN_FORM, Owner='')), 'flat.pdf')
    assert read.role == 'scc_form_flattened' and read.form_version == 'scc_2026-10'
    assert read.fields['Owner'].status == 'blank'
    assert read.fields['Mailing Address'].status == 'present'
    assert read.fields['Mailing Address'].value == CLEAN_FORM['Mailing Address']


def test_flattened_box_with_handwriting_or_image_is_not_found():
    flat = flattened(dict(CLEAN_FORM, Owner=''))

    def ink(c):
        c.setLineWidth(1)
        c.bezier(130, 485, 200, 495, 260, 480, 320, 490)

    marked = read_pdf(_overlay(flat, ink), 'ink.pdf')
    assert marked.fields['Owner'].status == 'not_found'
    assert 'drawn' in marked.fields['Owner'].reason

    def stamp(c):
        from PIL import Image
        from reportlab.lib.utils import ImageReader
        c.drawImage(ImageReader(Image.new('RGB', (20, 10), 'black')), 140, 483, 60, 10)

    stamped = read_pdf(_overlay(flat, stamp), 'stamp.pdf')
    assert stamped.fields['Owner'].status == 'not_found'
    # Other empty boxes on the page stay certain.
    assert stamped.fields['QTR'].status == 'blank'


def test_scanned_form_without_text_is_never_reported_blank():
    read = read_pdf(scanned(flattened(dict(CLEAN_FORM, Owner=''))), 'scan.pdf')
    assert read.role == 'unreadable'
    parts = review_uploads([('scan.pdf', scanned(flattened(CLEAN_FORM)))], None)
    assert {f.status for f in parts.findings} == {'not_found'}
    assert {'form:presence', 'file:scan.pdf:unreadable'} <= {f.key for f in parts.findings}


def test_a_page_without_text_layer_inside_a_recognised_form_is_not_found():
    flat = flattened(CLEAN_FORM)
    page2 = PdfReader(io.BytesIO(scanned(flat))).pages[1]
    writer = PdfWriter(clone_from=io.BytesIO(flat))
    writer.insert_page(page2, 1)
    writer.remove_page(2)
    buf = io.BytesIO()
    writer.write(buf)
    read = read_pdf(buf.getvalue(), 'mixed.pdf')
    assert read.role == 'scc_form_flattened'
    assert read.fields['Owner'].status == 'present'
    assert read.fields['Supporting Doc'].status == 'not_found'
    assert read.fields['Supporting Doc2'].status == 'not_found'   # empty, but unreadable page: not certain


def test_text_fields_in_attachments_blank_versus_not_found():
    with_heading = text_pdf(['Risk assessment', 'Mitigating measures', 'SYNTHETIC measures text.'])
    parts = review_uploads([('form.pdf', fillable(CLEAN_FORM)), ('narrative.pdf', with_heading)], None)
    by_field = {f.field: f for f in parts.fields}
    assert by_field['risk_assessment'].status == 'blank'
    assert by_field['mitigating_measures'].status == 'present'
    assert by_field['assumptions_and_limits'].status == 'not_found'
    findings = {f.field: f for f in parts.findings}
    assert findings['risk_assessment'].status == 'blank'
    assert findings['assumptions_and_limits'].status == 'not_found'


def test_signatures_are_never_certain_from_text():
    for pdf in (fillable(CLEAN_FORM), flattened(CLEAN_FORM)):
        read = read_pdf(pdf, 'form.pdf')
        assert {value.status for value in read.signatures.values()} == {'not_found'}


def test_non_form_pdf_is_an_attachment_and_bad_bytes_are_unreadable():
    assert read_pdf(text_pdf(['SYNTHETIC test report', 'Issued by: Lab']), 'r.pdf').role == 'attachment'
    assert read_pdf(b'not a pdf', 'x.pdf').role == 'unreadable'
    assert read_pdf(b'%PDF-1.4 truncated', 'y.pdf').role == 'unreadable'
