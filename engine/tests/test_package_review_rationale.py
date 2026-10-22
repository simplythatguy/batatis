"""Applicant rationale is a presence check, never a review of the applicant's analysis."""
import pytest

from engine.codes import Codes
from engine.export import export_case
from engine.export.sample import sample_case
from engine.review import information_request as ir
from engine.review.package import review_case, review_uploads
from engine.tests.case_builder_fixtures import complete_case, fact
from engine.tests.package_review_fixtures import CLEAN_NARRATIVE, narrative_pdf, package, scanned


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
            assert reading.value == 'SYNTHETIC latest reason.'
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
        assert reading.status == 'blank' and reading.value is None
        finding = next(f for f in parts.findings if f.field == 'rationale')
        assert finding.status == 'blank' and ir.build([finding]).items[0].included
