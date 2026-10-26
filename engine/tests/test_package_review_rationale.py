"""Applicant rationale is a presence check, never a review of the applicant's analysis."""
import io

import pytest

from engine.codes import Codes
from engine.export import export_case
from engine.export.sample import sample_case
from engine.review import information_request as ir
from engine.review.package import review_case, review_uploads
from engine.tests.case_builder_fixtures import complete_case, fact
from engine.tests.package_review_fixtures import (CLEAN_NARRATIVE, covered_scan_pdf, narrative_pdf, package,
                                                repeated_rationale_pdf, scanned, text_pdf)


@pytest.fixture(scope='module')
def codes():
    return Codes()


@pytest.mark.parametrize('flat', [False, True], ids=['fillable', 'flattened'])
def test_blank_rationale_is_an_applicant_gap_and_information_request(flat):
    narrative = dict(CLEAN_NARRATIVE, Rationale='')
    parts = review_uploads(package(narrative=narrative, flat=flat), None)

    finding = next((f for f in parts.findings if f.field == 'rationale'), None)
    assert finding is not None, 'A blank applicant rationale must be named in the package review.'
    assert finding.status == 'blank' and finding.severity == 'blocking'
    assert finding.section == 'process' and finding.routed_to == 'applicant'
    assert finding.pointers[0].file == 'section-b-narrative.pdf'
    assert finding.pointers[0].page and finding.pointers[0].quote == 'Rationale'
    request = ir.build(parts.findings)
    item = next(i for i in request.items if i.finding_key == finding.key)
    assert item.included and not item.officer_check
    assert item.text.startswith('Please provide the rationale')
    assert item.text in request.text
    assert finding.key in ir.open_gaps(parts.findings)


@pytest.mark.parametrize('missing', ['heading', 'scanned'])
def test_uncertain_rationale_waits_for_officer_and_is_not_an_applicant_gap(missing):
    uploads = package(drop=('Rationale',))
    if missing == 'scanned':
        uploads.append(('rationale-scan.pdf', scanned(narrative_pdf({'Rationale': 'SYNTHETIC applicant passage.'}))))
    parts = review_uploads(uploads, None)
    reading = next(f for f in parts.fields if f.field == 'rationale')
    finding = next(f for f in parts.findings if f.field == 'rationale')
    assert reading.status == finding.status == 'not_found'
    assert reading.value is None and finding.pointers
    request = ir.build(parts.findings)
    item = next(i for i in request.items if i.finding_key == finding.key)
    assert item.officer_check and not item.included
    assert item.text not in request.text
    assert finding.key not in ir.open_gaps(parts.findings)


@pytest.mark.parametrize('heading', ['Rationale', 'Rationale for proposed variance', 'P-1 Rationale'])
def test_present_rationale_is_read_verbatim_without_assessing_adequacy(heading):
    # Even a short passage counts as present; adequacy belongs to the human reviewer.
    narrative = {k: v for k, v in CLEAN_NARRATIVE.items() if k != 'Rationale'}
    narrative[heading] = 'SYNTHETIC reason.'
    parts = review_uploads(package(narrative=narrative), None)
    reading = next(f for f in parts.fields if f.field == 'rationale')
    assert reading.status == 'present' and reading.value == 'SYNTHETIC reason.'
    assert reading.pointer.file == 'section-b-narrative.pdf'
    assert reading.pointer.page and reading.pointer.quote == reading.value
    assert not any(f.field == 'rationale' for f in parts.findings)


@pytest.mark.parametrize('alias', ['rationale', 'process.rationale'])
@pytest.mark.parametrize('state', ['present', 'absent', 'blank', 'unconfirmed'])
def test_saved_case_rationale_uses_the_latest_applicant_passage(codes, alias, state):
    case = complete_case()
    case.facts = [f for f in case.facts if f.field != 'rationale']
    if state != 'absent':
        case.facts.append(fact('rationale', 'SYNTHETIC earlier reason.'))
        case.facts.append(fact(alias, '' if state == 'blank' else 'SYNTHETIC latest reason.',
                               status='unconfirmed' if state == 'unconfirmed' else 'confirmed'))
    before = case.model_dump(mode='json')
    parts = review_case(case, codes)
    assert case.model_dump(mode='json') == before, 'The review must not fill or rewrite the case.'
    reading = next(f for f in parts.fields if f.field == 'rationale')
    finding = next((f for f in parts.findings if f.field == 'rationale'), None)
    if state == 'present':
        assert reading.status == 'present' and reading.value == 'SYNTHETIC latest reason.'
        assert reading.pointer.file == 'synthetic-applicant-fixture'
        assert finding is None
    else:
        assert finding is not None and finding.severity == 'blocking'
        assert finding.status == ('unclear' if state == 'unconfirmed' else 'blank')
        assert finding.key in ir.open_gaps(parts.findings)
        assert ir.build([finding]).items[0].included
        if state == 'unconfirmed':
            assert finding.problem == 'unconfirmed'
            assert reading.status == 'not_found' and reading.value is None and reading.pointer.quote is None
        else:
            assert reading.status == 'blank' and reading.value is None


@pytest.mark.parametrize('path', ['acceptable', 'acceptable_solution'])
def test_saved_acceptable_path_does_not_require_a_rationale(codes, path):
    case = complete_case()
    case.facts = [f for f in case.facts if f.field != 'rationale'] + [fact('pathway', path)]
    assert not any(f.field == 'rationale' for f in review_case(case, codes).findings)


@pytest.mark.parametrize('present', [True, False], ids=['applicant-passage', 'missing-draft-passage'])
def test_official_export_rationale_round_trip(codes, present):
    case = sample_case(codes)
    if not present:
        case.facts = [f for f in case.facts if f.field != 'rationale']
    result = export_case(case, codes=codes, draft=not present)
    parts = review_uploads([('official-export.pdf', result.pdf)], codes)
    reading = next(f for f in parts.fields if f.field == 'rationale')
    if present:
        assert reading.status == 'present'
        assert reading.value == next(f.value for f in case.facts if f.field == 'rationale')
        assert reading.pointer.file == 'official-export.pdf' and reading.pointer.page > result.form_pages
        assert not any(f.field == 'rationale' for f in parts.findings)
    else:
        # A draft prints no placeholder passage, but its visible administrative record marks the rationale
        # unanswered, so the same file reads as a certain applicant gap on both sides.
        assert not any('Rationale' in line for line in result.appendix_text)
        _assert_blank_applicant_gap(parts)


def _assert_blank_applicant_gap(parts):
    reading = next(f for f in parts.fields if f.field == 'rationale')
    finding = next(f for f in parts.findings if f.field == 'rationale')
    assert reading.status == finding.status == 'blank'
    assert finding.severity == 'blocking' and finding.routed_to == 'applicant'


def _assert_officer_check(parts):
    reading = next(f for f in parts.fields if f.field == 'rationale')
    finding = next(f for f in parts.findings if f.field == 'rationale')
    assert reading.status == finding.status == 'not_found'
    assert reading.value is None
    assert reading.pointer.quote is None and all(pointer.quote is None for pointer in finding.pointers)
    request = ir.build(parts.findings)
    item = next(i for i in request.items if i.finding_key == finding.key)
    assert item.officer_check and not item.included and item.text not in request.text
    assert finding.key not in ir.open_gaps(parts.findings)
    return finding


def test_long_official_rationale_is_complete_or_an_officer_check(codes):
    ending = ' SYNTHETIC ending.'
    rationale = ('SYNTHETIC applicant detail. ' * 400)[:8269 - len(ending)] + ending
    case = sample_case(codes)
    case.facts = [f for f in case.facts if f.field != 'rationale'] + [fact('rationale', rationale)]
    pdf = export_case(case, codes=codes).pdf
    parts = review_uploads([('long-official-export.pdf', pdf)], codes)
    reading = next(f for f in parts.fields if f.field == 'rationale')
    if reading.status == 'present':
        assert reading.value == rationale, 'A rationale must never be silently truncated at a page boundary.'
    else:
        finding = _assert_officer_check(parts)
        assert len({p.page for p in finding.pointers}) >= 2
        assert all(p.quote is None for p in finding.pointers)


def split_rationale_pdf(*, footer=False):
    from reportlab.pdfgen import canvas
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=(612, 792))
    c.drawString(50, 50, 'Rationale')
    if footer:
        c.drawString(400, 20, 'Appendix page 1')
    c.showPage()
    c.drawString(50, 740, 'SYNTHETIC applicant passage on the next page.')
    c.drawString(50, 700, 'Applicant source: SYNTHETIC applicant')
    c.save()
    return buf.getvalue()


@pytest.mark.parametrize('footer', [False, True])
def test_rationale_heading_at_page_end_does_not_request_the_supplied_body(footer):
    parts = review_uploads([('split-rationale.pdf', split_rationale_pdf(footer=footer))], None)
    reading = next(f for f in parts.fields if f.field == 'rationale')
    if reading.status == 'present':
        assert reading.value == 'SYNTHETIC applicant passage on the next page.'
    else:
        finding = _assert_officer_check(parts)
        assert {p.page for p in finding.pointers} >= {1, 2}
        assert any(p.page == 2 and p.quote is None for p in finding.pointers)


def raster_rationale_pdf():
    import pypdfium2 as pdfium
    from reportlab.lib.utils import ImageReader
    from reportlab.pdfgen import canvas
    body = pdfium.PdfDocument(narrative_pdf({'SYNTHETIC applicant passage': 'No technical conclusion.'}))
    raster = body[0].render(scale=1).to_pil()
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=(612, 792))
    c.drawString(50, 750, 'Rationale')
    c.drawImage(ImageReader(raster), 0, 0, width=612, height=720)
    c.save()
    return buf.getvalue()


def test_readable_heading_over_raster_rationale_is_an_officer_check():
    parts = review_uploads([('raster-rationale.pdf', raster_rationale_pdf())], None)
    finding = _assert_officer_check(parts)
    assert finding.pointers[0].file == 'raster-rationale.pdf' and finding.pointers[0].page == 1


@pytest.mark.parametrize('body,unique_heading,reversed_stop', [
    ('raster', False, False), ('raster', True, False), ('vector', False, False), ('raster', True, True)],
    ids=['repeated-raster', 'unique-heading-repeated-stop', 'repeated-vector', 'reversed-boundaries'])
def test_each_rationale_occurrence_checks_its_own_graphical_body(body, unique_heading, reversed_stop):
    pdf = repeated_rationale_pdf(body, unique_heading=unique_heading, reversed_stop=reversed_stop)
    finding = _assert_officer_check(review_uploads([('repeated.pdf', pdf)], None))
    assert [(p.file, p.page, p.quote) for p in finding.pointers] == [
        ('repeated.pdf', 1, None), ('repeated.pdf', 1, None)]


@pytest.mark.parametrize('body', ['blank', 'outside'])
def test_repeated_readable_blank_rationales_do_not_include_graphics_outside_the_passages(body):
    parts = review_uploads([('repeated.pdf', repeated_rationale_pdf(body))], None)
    finding = next(f for f in parts.findings if f.field == 'rationale')
    assert finding.status == 'blank' and finding.severity == 'blocking'
    assert len(finding.pointers) == 2
    item = ir.build([finding]).items[0]
    assert item.included and not item.officer_check


@pytest.mark.parametrize('cover,page', [('none', 1), ('separate', 2), ('same-page', 1)])
def test_readable_cover_cannot_make_a_scanned_rationale_certainly_absent(cover, page):
    uploads = [('blank.pdf', text_pdf(['Rationale', 'Risk assessment'])),
               ('supplement.pdf', covered_scan_pdf(cover))]
    for ordered in (uploads, list(reversed(uploads))):
        finding = _assert_officer_check(review_uploads(ordered, None))
        assert [(p.file, p.page, p.quote) for p in finding.pointers] == [
            ('blank.pdf', 1, None), ('supplement.pdf', page, None)]


def test_readable_cover_and_truly_empty_page_do_not_imply_an_unreadable_passage():
    from reportlab.pdfgen import canvas
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=(612, 792))
    c.drawString(48, 748, 'SYNTHETIC readable cover.')
    c.showPage()
    c.showPage()
    c.save()
    parts = review_uploads([('blank.pdf', text_pdf(['Rationale', 'Risk assessment'])),
                            ('empty-page.pdf', buf.getvalue())], None)
    finding = next(f for f in parts.findings if f.field == 'rationale')
    assert finding.status == 'blank' and ir.build([finding]).items[0].included


@pytest.mark.parametrize('cover', ['separate', 'same-page'])
@pytest.mark.parametrize('layout', ['files', 'same-file'])
def test_single_readable_rationale_stays_present_beside_unrelated_covered_scan(cover, layout):
    passage = 'SYNTHETIC supplied readable rationale.'
    uploads = [('rationale.pdf', text_pdf(['Rationale', passage, 'Risk assessment'])),
               ('other-material.pdf', covered_scan_pdf(cover))]
    if layout == 'same-file':
        from pypdf import PdfWriter
        writer = PdfWriter()
        for _name, data in uploads:
            writer.append(io.BytesIO(data))
        buf = io.BytesIO()
        writer.write(buf)
        uploads = [('combined.pdf', buf.getvalue())]
    parts = review_uploads(uploads, None)
    reading = next(f for f in parts.fields if f.field == 'rationale')
    assert reading.status == 'present' and reading.value == passage
    assert not any(f.field == 'rationale' for f in parts.findings)


@pytest.mark.parametrize('saved', [False, True], ids=['upload', 'saved-case'])
def test_unknown_in_applicant_prose_is_not_a_placeholder(codes, saved):
    rationale = ('SYNTHETIC applicant rationale: the existing assembly rating is unknown, '
                 'so we propose a separately documented alternative.')
    if saved:
        from engine.completeness import check_completeness
        case = complete_case()
        case.facts = [f for f in case.facts if f.field != 'rationale'] + [fact('process.rationale', rationale)]
        assert not any(g.field == 'rationale' for g in check_completeness(case, codes))
        parts = review_case(case, codes)
    else:
        parts = review_uploads(package(narrative=dict(CLEAN_NARRATIVE, Rationale=rationale)), codes)
    reading = next(f for f in parts.fields if f.field == 'rationale')
    assert reading.status == 'present' and reading.value == rationale
    assert not any(f.field == 'rationale' for f in parts.findings)
    assert not any(i.field == 'rationale' for i in ir.build(parts.findings).items)


@pytest.mark.parametrize('saved', [False, True], ids=['upload', 'saved-case'])
@pytest.mark.parametrize('placeholder', ['TBD', 'unknown', 'To be provided.', 'pending', 'N/A', 'Not provided'])
def test_whole_answer_rationale_placeholders_still_need_applicant_input(codes, saved, placeholder):
    if saved:
        case = complete_case()
        case.facts = [f for f in case.facts if f.field != 'rationale'] + [fact('rationale', placeholder)]
        parts = review_case(case, codes)
    else:
        parts = review_uploads(package(narrative=dict(CLEAN_NARRATIVE, Rationale=placeholder)), codes)
    finding = next((f for f in parts.findings if f.field == 'rationale'), None)
    assert finding is not None and finding.severity == 'blocking'
    item = ir.build([finding]).items[0]
    assert item.included and not item.officer_check


@pytest.mark.parametrize('boundary', ['P-2 Risk assessment', 'Applicant source: SYNTHETIC applicant'])
def test_labelled_rationale_boundaries_do_not_absorb_the_next_field(boundary):
    passage = 'NBC(AE) 2023 is the source named by this SYNTHETIC applicant.'
    parts = review_uploads([('labelled.pdf', text_pdf([
        'Rationale', passage, boundary, 'SYNTHETIC following field, outside the rationale.']))], None)
    reading = next(f for f in parts.fields if f.field == 'rationale')
    assert reading.status == 'present' and reading.value == passage
    assert reading.pointer.quote == passage
    assert not any(f.field == 'rationale' for f in parts.findings)


@pytest.mark.parametrize('boundary', ['X-17 Applicant-specific context', 'E. Applicant analysis', 'citation'])
def test_ambiguous_rationale_boundaries_are_officer_checks(codes, boundary):
    if boundary == 'citation':
        boundary = codes.citation('2.3.1.1.(2)(a)', 'C')
    parts = review_uploads([('ambiguous.pdf', text_pdf([
        'Rationale', 'SYNTHETIC applicant introduction.', boundary,
        'SYNTHETIC words that might still belong to the rationale.', 'Risk assessment']))], None)
    finding = _assert_officer_check(parts)
    assert finding.pointers[0].file == 'ambiguous.pdf' and finding.pointers[0].page == 1
    assert 'ambiguous boundary' in finding.message


@pytest.mark.parametrize('layout', ['files', 'pages', 'same-page'])
@pytest.mark.parametrize('values', [('', ''), ('', 'SYNTHETIC supplied rationale.'),
    ('SYNTHETIC first rationale.', 'SYNTHETIC different rationale.'),
    ('SYNTHETIC repeated rationale.', 'SYNTHETIC repeated rationale.')],
    ids=['all-blank', 'blank-and-supplied', 'conflicting', 'matching-text'])
def test_multiple_rationale_candidates_keep_all_sources_and_stable_outcomes(layout, values):
    def lines(value):
        return ['Rationale', value, 'Risk assessment', 'SYNTHETIC next process field.']

    if layout == 'files':
        uploads = [('a.pdf', text_pdf(lines(values[0]))), ('b.pdf', text_pdf(lines(values[1])))]
    elif layout == 'pages':
        from pypdf import PdfWriter
        writer = PdfWriter()
        for value in values:
            writer.append(io.BytesIO(text_pdf(lines(value))))
        buf = io.BytesIO()
        writer.write(buf)
        uploads = [('both.pdf', buf.getvalue())]
    else:
        uploads = [('both.pdf', text_pdf(lines(values[0]) + lines(values[1])))]
    before = None
    for ordered in (uploads, list(reversed(uploads))):
        parts = review_uploads(ordered, None)
        reading = next(f for f in parts.fields if f.field == 'rationale')
        if any(values):
            finding = _assert_officer_check(parts)
        else:
            finding = next(f for f in parts.findings if f.field == 'rationale')
            assert reading.status == finding.status == 'blank' and finding.severity == 'blocking'
            item = ir.build([finding]).items[0]
            assert item.included and not item.officer_check
        assert len(finding.pointers) == 2, 'Both labelled candidates must retain their actual source pointers.'
        assert [p.quote for p in finding.pointers] == ([None, None] if any(values) else ['Rationale', 'Rationale'])
        projection = (reading.model_dump(), finding.model_dump(), ir.build([finding]).model_dump())
        if before is not None:
            assert projection == before, 'Multipart order must not choose which rationale controls.'
        before = projection


@pytest.mark.parametrize('other', ['', 'SYNTHETIC supplied rationale.'], ids=['blank', 'present'])
def test_uncertain_rationale_sources_are_not_masked_by_other_candidates(other):
    uploads = [('a.pdf', text_pdf(['Rationale', other, 'Risk assessment'])),
               ('b.pdf', raster_rationale_pdf())]
    before = None
    for ordered in (uploads, list(reversed(uploads))):
        finding = _assert_officer_check(review_uploads(ordered, None))
        assert {p.file for p in finding.pointers} == {'a.pdf', 'b.pdf'}
        assert any(p.file == 'a.pdf' and p.quote is None for p in finding.pointers)
        if before is not None:
            assert finding.model_dump() == before
        before = finding.model_dump()


def test_blank_rationale_does_not_assert_absence_when_another_file_is_unreadable():
    uploads = [('blank.pdf', text_pdf(['Rationale', 'Risk assessment'])),
               ('supplied-scan.pdf', scanned(narrative_pdf({'Rationale': 'SYNTHETIC supplied passage.'})))]
    finding = _assert_officer_check(review_uploads(uploads, None))
    assert {p.file for p in finding.pointers} == {'blank.pdf', 'supplied-scan.pdf'}
    assert any(p.file == 'supplied-scan.pdf' and p.quote is None for p in finding.pointers)


def test_single_readable_rationale_stays_present_beside_an_unreadable_other_file():
    passage = 'SYNTHETIC supplied rationale.'
    uploads = [('rationale.pdf', text_pdf(['Rationale', passage, 'Risk assessment'])),
               ('other-scan.pdf', scanned(text_pdf(['SYNTHETIC supporting document.'])))]
    parts = review_uploads(uploads, None)
    reading = next(f for f in parts.fields if f.field == 'rationale')
    assert reading.status == 'present' and reading.value == passage
    assert not any(f.field == 'rationale' for f in parts.findings)


def test_additional_recognized_forms_cannot_hide_a_supplied_rationale(codes):
    supplied = sample_case(codes)
    rationale = next(f.value for f in supplied.facts if f.field == 'rationale')
    blank = supplied.model_copy(deep=True)
    blank.facts = [f for f in blank.facts if f.field != 'rationale']
    uploads = [('blank-draft.pdf', export_case(blank, codes=codes, draft=True).pdf),
               ('supplied-form.pdf', export_case(supplied, codes=codes).pdf)]
    # The draft alone records its rationale as unanswered.
    _assert_blank_applicant_gap(review_uploads(uploads[:1], codes))
    before = None
    for ordered in (uploads, list(reversed(uploads))):
        parts = review_uploads(ordered, codes)
        assert all(file.role == 'scc_form_flattened' for file in parts.files)
        # Whatever the order, the other form's passage is read; the draft has no placeholder to compete with it.
        reading = next(f for f in parts.fields if f.field == 'rationale')
        assert reading.status == 'present' and reading.value == rationale
        assert reading.pointer.file == 'supplied-form.pdf'
        assert not any(f.field == 'rationale' for f in parts.findings)
        if before is not None:
            assert reading.model_dump() == before
        before = reading.model_dump()
