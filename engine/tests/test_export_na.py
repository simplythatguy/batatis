"""Explicit "not applicable" facts (WP-33, AC9.1): N/A only from an applicant-confirmed fact, never to fill a blank."""
import pytest

from engine.codes import Codes
from engine.completeness import check_completeness
from engine.export import ExportBlocked, export_case, form_path, load_field_map
from engine.export.demo_cases import demo_case
from engine.export.g3 import appendix_text, coverage
from engine.export.sample import sample_case
from engine.models import Fact, Source
from engine.not_applicable import not_applicable

pytestmark = pytest.mark.skipif(not form_path().exists(), reason='SCC form not present (git-excluded)')

CASE_A = 'a-manufacturer-nailbase-sheathing'


@pytest.fixture(scope='module')
def codes():
    return Codes()


def na_fact(key, value='The applicant says this does not apply.', *, status='confirmed', source='user_click'):
    return Fact(field=f'not_applicable.{key}', value=value, kind='pointed', status=status,
                source=Source(type=source, ref='test:applicant', quote=str(value)))


def without(case, *keys):
    case = case.model_copy(deep=True)
    case.facts = [f for f in case.facts if f.field not in {f'not_applicable.{k}' for k in keys}]
    return case


def shown(result):
    return {p.field: ' '.join(p.lines) for p in result.placements}


def test_confirmed_na_renders_n_a_with_the_applicants_reason_in_the_appendix(codes):
    case = demo_case(CASE_A, codes)
    result = export_case(case, codes=codes)
    cells = shown(result)
    assert cells['Permit'] == 'N/A' and cells['QTR'] == 'N/A' and cells['Owner Rep'] == 'N/A'
    assert cells['Article(s)3'] == 'N/A' and cells['Supporting Doc5'] == 'N/A'
    assert {'Permit', 'Owner Rep', 'Owner Rep Print', 'Date2', 'QTR', 'MER'} <= set(result.not_applicable)
    assert not result.blank_fields
    text = appendix_text(result)
    assert 'N. Fields marked not applicable' in text
    assert 'No building permit has been applied for yet' in text and 'not_applicable.permit_number' in text


def test_without_the_fact_the_field_stays_blank_and_is_never_shown_as_n_a(codes):
    case = without(demo_case(CASE_A, codes), 'permit_number', 'section_c.unused_rows')
    result = export_case(case, codes=codes)
    cells = shown(result)
    assert 'Permit' not in cells and 'Article(s)3' not in cells
    assert {'Permit', 'Article(s)3', 'Intent statement4'} <= set(result.blank_fields)
    assert 'Permit' in coverage(case, result)['missing']
    assert 'N/A' not in cells.values() or all(f in result.not_applicable for f, v in cells.items() if v == 'N/A')


def test_unconfirmed_na_blocks_the_final_export_and_draft_shows_blank(codes):
    case = without(demo_case(CASE_A, codes), 'permit_number')
    case.facts.append(na_fact('permit_number', status='unconfirmed'))
    with pytest.raises(ExportBlocked, match='not_applicable.permit_number'):
        export_case(case, codes=codes)
    draft = export_case(case, codes=codes, draft=True)
    assert 'Permit' not in shown(draft) and 'Permit' in draft.blank_fields


def test_na_on_a_field_that_always_applies_is_a_blocking_finding(codes):
    case = demo_case(CASE_A, codes)
    case.facts.append(na_fact('mailing_address'))
    gaps = [g for g in check_completeness(case, codes) if g.id == 'not_applicable:not_applicable.mailing_address']
    assert gaps and gaps[0].severity == 'blocking'
    assert 'mailing_address' not in not_applicable(case)
    with pytest.raises(ExportBlocked, match='cannot be marked not applicable'):
        export_case(case, codes=codes)


def test_value_and_na_together_are_a_contradiction_batatis_does_not_resolve(codes):
    case = demo_case(CASE_A, codes)
    case.facts.append(Fact(field='permit_number', value='BP-1', kind='pointed', status='confirmed',
                           source=Source(type='user_text', ref='test:applicant', quote='BP-1')))
    with pytest.raises(ExportBlocked, match='both a value and a "not applicable"'):
        export_case(case, codes=codes)


@pytest.mark.parametrize('source', ['file', 'code', 'officer'])
def test_only_the_applicant_can_mark_a_field_not_applicable(codes, source):
    case = without(demo_case(CASE_A, codes), 'permit_number')
    case.facts.append(na_fact('permit_number', source=source))
    assert 'permit_number' not in not_applicable(case)
    assert any(g.id == 'not_applicable:not_applicable.permit_number' for g in check_completeness(case, codes))
    assert 'Permit' not in shown(export_case(case, codes=codes, draft=True))


def test_a_withdrawn_na_is_not_honoured(codes):
    case = demo_case(CASE_A, codes)
    case.facts.append(na_fact('permit_number', value=False))
    assert 'permit_number' not in not_applicable(case)
    assert 'Permit' in export_case(case, codes=codes).blank_fields


def test_owner_rep_na_clears_the_representative_gap_and_pre_flight_does_not_block(codes):
    case = demo_case(CASE_A, codes)
    assert not [g for g in check_completeness(case, codes) if g.severity == 'blocking']
    removed = without(case, 'owner_rep')
    assert any(g.field == 'representative' and g.severity == 'blocking' for g in check_completeness(removed, codes))


def test_a_typed_n_a_value_is_still_a_placeholder_not_a_not_applicable_fact(codes):
    case = without(demo_case(CASE_A, codes), 'owner_rep')
    case.facts.append(Fact(field='owner_rep_name', value='N/A', kind='pointed', status='confirmed',
                           source=Source(type='user_text', ref='test:applicant', quote='N/A')))
    assert any(g.field == 'representative' for g in check_completeness(case, codes))
    assert 'owner_rep_name' not in not_applicable(case)


def test_sample_btrboard_case_marks_ats_not_applicable(codes):
    result = export_case(sample_case(codes), codes=codes)
    fmap = load_field_map()
    ats = [name for name, spec in fmap['text_fields'].items() if spec['fact'].startswith('ats_')]
    assert set(ats) <= set(result.not_applicable) and not result.blank_fields
