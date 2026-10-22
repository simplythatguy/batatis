"""Visible annotation appearances and wrapped next-field labels never prove rationale presence."""
import pytest

from engine.review import information_request as ir
from engine.review.package import review_uploads
from engine.tests.package_review_fixtures import annotated_rationale_pdf, text_pdf


def assert_officer_check(parts):
    reading = next(f for f in parts.fields if f.field == 'rationale')
    finding = next(f for f in parts.findings if f.field == 'rationale')
    assert reading.status == finding.status == 'not_found' and reading.value is None
    request = ir.build(parts.findings)
    item = next(i for i in request.items if i.field == 'rationale')
    assert item.officer_check and not item.included and item.text not in request.text
    assert finding.key not in ir.open_gaps(parts.findings)
    return finding


@pytest.mark.parametrize('options', [
    {}, {'kind': 'vector'}, {'appearance': 'state'}, {'subtype': '/FreeText'}, {'flags': 0}, {'flags': 5}, {'rotation': 90}],
    ids=['text', 'vector', 'selected-state', 'free-text', 'screen-visible', 'supported-invisible-flag', 'rotated'])
def test_visible_annotation_in_rationale_is_an_excluded_officer_check(options):
    finding = assert_officer_check(review_uploads([
        ('annotated.pdf', annotated_rationale_pdf(**options))], None))
    assert [(p.file, p.page, p.quote) for p in finding.pointers] == [('annotated.pdf', 1, 'Rationale')]


@pytest.mark.parametrize('layout,page', [('cover', 1), ('cover-page', 2)])
@pytest.mark.parametrize('kind', ['text', 'vector'])
def test_visible_unlabelled_annotation_retains_the_actual_page_pointer(layout, page, kind):
    uploads = [('blank.pdf', text_pdf(['Rationale', 'Risk assessment'])),
               ('supplement.pdf', annotated_rationale_pdf(kind, layout=layout))]
    before = None
    for ordered in (uploads, list(reversed(uploads))):
        finding = assert_officer_check(review_uploads(ordered, None))
        assert [(p.file, p.page, p.quote) for p in finding.pointers] == [
            ('blank.pdf', 1, 'Rationale'), ('supplement.pdf', page, None)]
        if before:
            assert finding.model_dump() == before
        before = finding.model_dump()


@pytest.mark.parametrize('options', [
    {'flags': 6}, {'flags': 36}, {'appearance': 'empty'}, {'appearance': 'missing'},
    {'appearance': 'unselected-state'}, {'appearance': 'invisible-text'}, {'layout': 'outside'}, {'layout': 'page-rect-outside'}],
    ids=['hidden', 'no-view', 'empty-appearance', 'missing-appearance', 'unselected-state', 'invisible-text', 'outside', 'wide-rect-footer'])
def test_non_rendered_or_unrelated_annotations_do_not_invalidate_a_certain_blank(options):
    parts = review_uploads([('annotated.pdf', annotated_rationale_pdf(**options))], None)
    reading = next(f for f in parts.fields if f.field == 'rationale')
    finding = next(f for f in parts.findings if f.field == 'rationale')
    assert reading.status == finding.status == 'blank' and reading.value is None
    item = ir.build([finding]).items[0]
    assert item.included and not item.officer_check


def test_readable_rationale_remains_verbatim_beside_an_unrelated_annotation():
    passage = 'SYNTHETIC readable applicant passage.'
    parts = review_uploads([('annotated.pdf', annotated_rationale_pdf(layout='outside', passage=passage))], None)
    reading = next(f for f in parts.fields if f.field == 'rationale')
    assert reading.status == 'present' and reading.value == reading.pointer.quote == passage
    assert not any(f.field == 'rationale' for f in parts.findings)


@pytest.mark.parametrize('heading', [
    'Risk\nassessment:', 'P-2 Risk\nassessment:', 'Mitigating\nmeasures:', 'Assumptions\nand limits:',
    'Responsible\nprofessional:', 'Qualifications of\nresponsible professional:',
    'Description of the proposed\nalternative solution:', 'Code\nanalysis:', 'Applicant\nsource: SYNTHETIC applicant'])
@pytest.mark.parametrize('body', ['', 'SYNTHETIC neighboring field body.'], ids=['label-only', 'with-body'])
def test_wrapped_next_field_does_not_become_the_rationale(heading, body):
    finding = assert_officer_check(review_uploads([('wrapped.pdf', text_pdf([
        'Rationale', *heading.split('\n'), body, 'Commissioning']))], None))
    assert [(p.file, p.page, p.quote) for p in finding.pointers] == [('wrapped.pdf', 1, 'Rationale')]


def test_rationale_prose_with_wrapped_words_remains_the_applicants_words():
    lines = ['SYNTHETIC applicant introduction.', 'Risk', 'assessment informs the proposed departure.']
    parts = review_uploads([('prose.pdf', text_pdf(['Rationale', *lines, 'Mitigating measures']))], None)
    reading = next(f for f in parts.fields if f.field == 'rationale')
    assert reading.status == 'present' and reading.value == ' '.join(lines)
    assert not any(f.field == 'rationale' for f in parts.findings)
