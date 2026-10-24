"""SYNTHETIC forms: a PDF's stored text is not proof of a readable answer."""
from __future__ import annotations

import io

import pytest
from pypdf import PdfWriter
from pypdf.generic import NameObject, NumberObject, TextStringObject

from engine.export import scc
from engine.review.package import review_uploads
from engine.review.pdf_reader import read_pdf
from engine.tests.package_review_fixtures import CLEAN_FORM, fillable, flattened
from engine.tests.test_package_review_reader import _overlay


def _owner_widget(writer):
    return next(widget for _page, name, widget in scc._widgets(writer.pages) if name == 'Owner')


def _write(writer):
    output = io.BytesIO()
    writer.write(output)
    return output.getvalue()


def test_visible_page_answer_over_empty_fillable_field_is_not_blank():
    def answer(canvas):
        canvas.setFont('Helvetica', 10)
        canvas.drawString(120, 485, 'SYNTHETIC Visible Owner')

    data = _overlay(fillable(dict(CLEAN_FORM, Owner='')), answer)
    field = read_pdf(data, 'visible.pdf').fields['Owner']
    assert field.status != 'blank'
    if field.status == 'present':
        assert field.value == 'SYNTHETIC Visible Owner'
    parts = review_uploads([('visible.pdf', data)], None)
    assert not any(f.field == 'owner_name' and f.status in ('blank', 'missing') for f in parts.findings)


def test_stale_logical_value_does_not_override_visible_appearance():
    writer = PdfWriter(clone_from=io.BytesIO(fillable(dict(CLEAN_FORM, Owner='SYNTHETIC Visible Owner'))))
    _owner_widget(writer)[NameObject('/V')] = TextStringObject('SYNTHETIC Stale Owner')
    field = read_pdf(_write(writer), 'stale.pdf').fields['Owner']
    assert field.status == 'not_found'
    assert not field.value and field.reason


@pytest.mark.parametrize('flags', [1, 2, 32])
def test_hidden_fillable_widget_value_is_not_an_answer(flags):
    writer = PdfWriter(clone_from=io.BytesIO(fillable(CLEAN_FORM)))
    _owner_widget(writer)[NameObject('/F')] = NumberObject(flags)
    field = read_pdf(_write(writer), 'hidden-widget.pdf').fields['Owner']
    assert field.status != 'present'
    assert not field.value


@pytest.mark.parametrize('mode', [3, 7])
def test_invisible_flattened_text_is_not_an_answer(mode):
    def invisible(canvas):
        text = canvas.beginText(120, 485)
        text.setFont('Helvetica', 10)
        text.setTextRenderMode(mode)
        text.textOut('SYNTHETIC Hidden Owner')
        canvas.drawText(text)

    data = _overlay(flattened(dict(CLEAN_FORM, Owner='')), invisible)
    field = read_pdf(data, 'hidden.pdf').fields['Owner']
    assert field.status != 'present'
    assert not field.value


def test_covered_flattened_text_is_uncertain_not_present():
    def cover(canvas):
        canvas.setFillColorRGB(1, 1, 1)
        canvas.rect(113, 481, 458, 15, stroke=0, fill=1)

    data = _overlay(flattened(CLEAN_FORM), cover)
    field = read_pdf(data, 'covered.pdf').fields['Owner']
    assert field.status == 'not_found'
    assert not field.value and field.reason


def test_annotation_answer_on_flattened_form_is_not_reported_blank():
    from pypdf.annotations import FreeText
    writer = PdfWriter(clone_from=io.BytesIO(flattened(dict(CLEAN_FORM, Owner=''))))
    writer.add_annotation(0, FreeText(text='SYNTHETIC Annotated Owner', rect=(120, 482, 350, 495),
                                     font_size='10pt'))
    data = _write(writer)
    field = read_pdf(data, 'annotated.pdf').fields['Owner']
    assert field.status != 'blank'
    parts = review_uploads([('annotated.pdf', data)], None)
    assert not any(f.field == 'owner_name' and f.status in ('blank', 'missing') for f in parts.findings)
