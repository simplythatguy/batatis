"""SYNTHETIC passage certainty at the upload seam, independent of form layout."""
import io

import pytest
from PIL import Image, ImageDraw
from pypdf import PdfReader, PdfWriter
from pypdf.annotations import FreeText
from pypdf.generic import (ArrayObject, DecodedStreamObject, DictionaryObject, NameObject,
                           NumberObject, RectangleObject, TextStringObject)
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas

from engine.review import information_request as ir
from engine.review.package import review_uploads
from engine.tests.package_review_fixtures import CLEAN_FORM, fillable, flattened

ANSWER = 'SYNTHETIC supplied applicant answer'
READABLE = 'SYNTHETIC risk: see the attached fire-spread study by the engineering group.'
NEARBY = 'SYNTHETIC illuminated exit signs and self-closing doors; fire-rated lintel.'
HEADINGS = [('rationale', 'Rationale'), ('risk_assessment', 'Risk assessment'),
            ('mitigating_measures', 'Mitigating measures'), ('assumptions_and_limits', 'Assumptions and limits'),
            ('alternative_description', 'Description of the proposed alternative')]


def written(writer):
    output = io.BytesIO()
    writer.write(output)
    return output.getvalue()


def passage(kind, heading='Risk assessment', *, prefix=False, nearby=False):
    """Saved U1 graphics fixture plus invisible/covered text and a nearby readable answer."""
    output = io.BytesIO()
    c = canvas.Canvas(output, pagesize=(612, 792))
    c.setFont('Helvetica', 11)
    c.drawString(50, 740, heading)
    if prefix:
        c.drawString(50, 724, 'SYNTHETIC explanation with a pasted answer below.')
    if kind == 'image':
        image = Image.new('RGB', (1000, 60), 'white')
        ImageDraw.Draw(image).text((6, 10), ANSWER, fill='black', font_size=30)
        c.drawImage(ImageReader(image), 50, 685, 500, 30)
    elif kind == 'path':
        c.setLineWidth(2)
        c.bezier(50, 685, 140, 735, 300, 675, 500, 715)
    elif kind in ('invisible', 'clip-only', 'white', 'covered', 'visible'):
        c.saveState()
        text = c.beginText(50, 700)
        text.setFont('Helvetica', 11)
        if kind in ('invisible', 'clip-only'):
            text.setTextRenderMode(3 if kind == 'invisible' else 7)
        if kind == 'white':
            text.setFillColorRGB(1, 1, 1)
        text.textOut(ANSWER)
        c.drawText(text)
        c.restoreState()
        if kind == 'covered':
            c.setFillColorRGB(1, 1, 1)
            c.rect(45, 695, 510, 22, stroke=0, fill=1)
            c.setFillColorRGB(0, 0, 0)
    c.drawString(50, 650, 'Mitigating measures' if nearby else 'Code analysis')
    if nearby:
        c.drawString(50, 634, NEARBY)
        c.drawString(50, 600, 'Code analysis')
    c.save()
    writer = PdfWriter(clone_from=io.BytesIO(output.getvalue()))
    if kind == 'annotation':
        writer.add_annotation(0, FreeText(text=ANSWER, rect=(50, 685, 560, 715), font_size='11pt'))
    elif kind == 'annotation-ap':
        appearance = DecodedStreamObject()
        appearance.update({NameObject('/Type'): NameObject('/XObject'), NameObject('/Subtype'): NameObject('/Form'),
                           NameObject('/BBox'): RectangleObject((0, 0, 510, 30)),
                           NameObject('/Resources'): DictionaryObject({NameObject('/Font'): DictionaryObject({
                               NameObject('/Helv'): DictionaryObject({NameObject('/Type'): NameObject('/Font'),
                               NameObject('/Subtype'): NameObject('/Type1'), NameObject('/BaseFont'): NameObject('/Helvetica')})})})})
        appearance.set_data(f'BT /Helv 11 Tf 0 g 2 6 Td ({ANSWER}) Tj ET'.encode())
        writer.pages[0][NameObject('/Annots')] = ArrayObject([writer._add_object(DictionaryObject({
            NameObject('/Type'): NameObject('/Annot'), NameObject('/Subtype'): NameObject('/FreeText'),
            NameObject('/Rect'): RectangleObject((50, 685, 560, 715)), NameObject('/F'): NumberObject(4),
            NameObject('/Contents'): TextStringObject(ANSWER),
            NameObject('/AP'): DictionaryObject({NameObject('/N'): writer._add_object(appearance)})}))])
    return written(writer)


def officer_check(parts, field, file='answer.pdf', page=1):
    reading = next(x for x in parts.fields if x.field == field)
    finding = next(x for x in parts.findings if x.field == field)
    assert reading.status == finding.status == 'not_found' and reading.value is None
    assert (reading.pointer.file, reading.pointer.page) == (file, page)
    assert all(ANSWER not in (p.quote or '') for p in finding.pointers)
    request = ir.build(parts.findings)
    item = next(x for x in request.items if x.finding_key == finding.key)
    assert item.officer_check and not item.included and item.text not in request.text
    assert finding.key not in ir.open_gaps(parts.findings)
    return reading


@pytest.mark.parametrize('field,heading', HEADINGS)
@pytest.mark.parametrize('kind', ['image', 'path', 'annotation', 'annotation-ap'])
@pytest.mark.parametrize('prefix', [False, True], ids=['non-text', 'mixed-text'])
def test_nontext_answer_never_establishes_blank_or_partial_presence(field, heading, kind, prefix):
    parts = review_uploads([('form.pdf', fillable(CLEAN_FORM)),
                            ('answer.pdf', passage(kind, heading, prefix=prefix))], None)
    officer_check(parts, field)


@pytest.mark.parametrize('field,heading', HEADINGS)
@pytest.mark.parametrize('kind', ['invisible', 'clip-only', 'white', 'covered'])
def test_nonvisible_passage_is_not_an_answer(field, heading, kind):
    parts = review_uploads([('form.pdf', fillable(CLEAN_FORM)), ('answer.pdf', passage(kind, heading))], None)
    officer_check(parts, field)


@pytest.mark.parametrize('kind', ['image', 'invisible'])
def test_uncertainty_is_confined_to_its_own_answer_region(kind):
    parts = review_uploads([('form.pdf', fillable(CLEAN_FORM)),
                            ('answer.pdf', passage(kind, nearby=True))], None)
    officer_check(parts, 'risk_assessment')
    measures = next(x for x in parts.fields if x.field == 'mitigating_measures')
    assert measures.status == 'present' and measures.value == NEARBY
    assert (measures.pointer.file, measures.pointer.page) == ('answer.pdf', 1)


@pytest.mark.parametrize('make_form', [fillable, flattened])
@pytest.mark.parametrize('kind', ['image', 'invisible'])
def test_same_certainty_rules_apply_to_the_existing_forms_appendix(make_form, kind):
    writer = PdfWriter(clone_from=io.BytesIO(make_form(CLEAN_FORM)))
    writer.add_page(PdfReader(io.BytesIO(passage(kind))).pages[0])
    parts = review_uploads([('form-plus-appendix.pdf', written(writer))], None)
    officer_check(parts, 'risk_assessment', 'form-plus-appendix.pdf', 6)


def test_uncertainty_keeps_its_file_when_another_attachment_has_hidden_text():
    parts = review_uploads([('form.pdf', fillable(CLEAN_FORM)),
                            ('a-cover.pdf', passage('invisible', 'SYNTHETIC cover letter')),
                            ('b-risk.pdf', passage('invisible'))], None)
    officer_check(parts, 'risk_assessment', 'b-risk.pdf')


def test_text_outside_the_page_cannot_supply_an_unseen_answer_suffix():
    from engine.tests.package_review_fixtures import CLEAN_NARRATIVE

    output = io.BytesIO()
    c = canvas.Canvas(output, pagesize=(612, 792))
    c.drawString(50, 740, 'Description of the proposed alternative')
    c.drawString(50, 704, CLEAN_NARRATIVE['Description of the proposed alternative'])
    c.drawString(50, 668, 'Risk assessment')
    c.save()
    parts = review_uploads([('answer.pdf', output.getvalue())], None)
    officer_check(parts, 'alternative_description')


def readable_layout(kind):
    """The six saved U1 layout controls, without their obsolete implementation assertions."""
    output = io.BytesIO()
    c = canvas.Canvas(output, pagesize=(612, 792))
    landscape = kind.startswith('landscape')
    if landscape:
        c.translate(612, 0)
        c.rotate(90)
    y = 560 if landscape else 740
    c.setFont('Helvetica', 11)
    c.drawString(50, y, 'Risk assessment')
    c.drawString(50, y - 16, READABLE)
    if kind == 'underline':
        x = 50 + c.stringWidth('SYNTHETIC risk: ', 'Helvetica', 11)
        width = c.stringWidth('see the attached fire-spread study', 'Helvetica', 11)
        c.rect(x, y - 17.6, width, .6, stroke=0, fill=1)
    c.drawString(50, y - 46, 'Mitigating measures')
    c.drawString(50, y - 62, NEARBY)
    if kind == 'dense':
        c.setFont('Helvetica', 7)
        for row in range(77):
            line = ('SYNTHETIC product data: gypsum board type X 15.9 mm, density 680 kg/m3, edge tapered; ' * 2)[:140]
            c.drawString(36, 650 - row * 8, line)
    if kind == 'landscape-table':
        c.setFont('Helvetica', 8)
        for row in range(24):
            for col in range(6):
                c.drawString(40 + col * 115, 430 - row * 13, f'SYNTHETIC {row} {col}')
    c.save()
    data = output.getvalue()
    if landscape or kind == 'crop':
        writer = PdfWriter(clone_from=io.BytesIO(data))
        if landscape:
            writer.pages[0].rotate(90)
        else:
            writer.pages[0].cropbox = RectangleObject((10, 10, 602, 782))
        data = written(writer)
    return data


@pytest.mark.parametrize('kind', ['plain', 'underline', 'crop', 'landscape', 'landscape-table', 'dense'])
def test_readable_layout_controls_preserve_the_exact_answer(kind):
    parts = review_uploads([('form.pdf', fillable(CLEAN_FORM)), ('narrative.pdf', readable_layout(kind))], None)
    row = next(x for x in parts.fields if x.field == 'risk_assessment')
    assert row.status == 'present' and row.value == READABLE
    assert (row.pointer.file, row.pointer.page) == ('narrative.pdf', 1)


def test_readable_narrative_fixture_does_not_clip_its_declared_source_words():
    import pypdfium2 as pdfium
    from engine.tests.package_review_fixtures import CLEAN_NARRATIVE, narrative_pdf

    with pdfium.PdfDocument(narrative_pdf(CLEAN_NARRATIVE)) as doc:
        text = []
        for index in range(len(doc)):
            page = doc[index]
            left, bottom, right, top = page.get_bbox()
            textpage = page.get_textpage()
            text.append(textpage.get_text_range())
            for i in range(textpage.count_chars()):
                if textpage.get_text_range(i, 1).strip():
                    x0, y0, x1, y1 = textpage.get_charbox(i)
                    assert left <= x0 < x1 <= right and bottom <= y0 < y1 <= top
            textpage.close()
        actual = ' '.join(' '.join(text).split())
        assert all(' '.join(value.split()) in actual for value in CLEAN_NARRATIVE.values())
