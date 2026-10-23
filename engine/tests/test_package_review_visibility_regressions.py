"""SYNTHETIC visibility controls and officer-only uncertainty at the package seam."""
import io

import pytest
from pypdf import PdfWriter
from pypdf.annotations import FreeText
from pypdf.generic import NameObject, NumberObject, TextStringObject

from engine.review import information_request as ir
from engine.review.package import review_uploads
from engine.review.pdf_reader import read_pdf
from engine.tests.package_review_fixtures import CLEAN_FORM, fillable, flattened
from engine.tests.test_package_review_reader import _overlay
from engine.tests.test_package_review_visibility import _owner_widget, _write


def _uncertain_owner(kind):
    if kind == 'covered':
        def cover(canvas):
            # Leave the first part visible; it cannot attest the whole extracted answer.
            canvas.setFillColorRGB(1, 1, 1)
            canvas.rect(210, 481, 360, 15, stroke=0, fill=1)
        return _overlay(flattened(CLEAN_FORM), cover)
    if kind == 'annotation':
        writer = PdfWriter(clone_from=io.BytesIO(flattened(dict(CLEAN_FORM, Owner=''))))
        writer.add_annotation(0, FreeText(text='SYNTHETIC supplied annotation', rect=(120, 482, 350, 495)))
        return _write(writer)
    writer = PdfWriter(clone_from=io.BytesIO(fillable(CLEAN_FORM)))
    widget = _owner_widget(writer)
    if kind == 'empty-value':
        widget[NameObject('/V')] = TextStringObject('')
    elif kind == 'missing-appearance':
        del widget['/AP']
    elif kind == 'invisible-appearance':
        appearance = widget['/AP']['/N']
        appearance.set_data(appearance.get_data().replace(b'BT', b'BT 3 Tr'))
    else:
        widget[NameObject('/F')] = NumberObject(int(kind))
    return _write(writer)


@pytest.mark.parametrize('kind', [
    'covered', 'annotation', 'empty-value', 'missing-appearance', 'invisible-appearance', '1', '2', '32'])
def test_visibility_uncertainty_keeps_an_officer_pointer_and_no_applicant_gap(kind):
    data = _uncertain_owner(kind)
    parts = review_uploads([('synthetic.pdf', data)], None)
    reading = next(field for field in parts.fields if field.field == 'Owner')
    finding = next(finding for finding in parts.findings if finding.field == 'owner_name')
    assert reading.status == finding.status == 'not_found'
    assert reading.value is None and finding.key not in ir.open_gaps(parts.findings)
    pointer = finding.pointers[0]
    assert (pointer.file, pointer.page, pointer.form_field) == ('synthetic.pdf', 1, 'Owner')
    assert pointer.bbox and not pointer.quote
    item = next(item for item in ir.build(parts.findings).items if item.finding_key == finding.key)
    assert item.officer_check and not item.included


@pytest.mark.parametrize('build', [fillable, flattened], ids=['fillable', 'flattened'])
def test_visible_control_keeps_every_supplied_value(build):
    fields = read_pdf(build(CLEAN_FORM), 'visible.pdf').fields
    for name, value in CLEAN_FORM.items():
        assert fields[name].status == 'present' and fields[name].value == value


@pytest.mark.parametrize('state,status', [('/Off', 'blank'), ('/Yes', 'present')])
def test_fillable_checkbox_keeps_its_visible_state(state, status):
    field = read_pdf(fillable(dict(CLEAN_FORM, **{'Check Box': state})), 'checkbox.pdf').fields['Check Box']
    assert field.status == status and field.value == (state if status == 'present' else '')


def test_unrelated_annotation_does_not_invalidate_a_certain_empty_box():
    writer = PdfWriter(clone_from=io.BytesIO(flattened(dict(CLEAN_FORM, Owner=''))))
    writer.add_annotation(0, FreeText(text='SYNTHETIC footer note', rect=(120, 20, 350, 40)))
    assert read_pdf(_write(writer), 'footer.pdf').fields['Owner'].status == 'blank'
