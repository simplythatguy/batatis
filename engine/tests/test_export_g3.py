"""Gate G3 (WP-33, AC9.1): the three demo cases and the BTRboard sample export complete and clean.

For each case: all runtime applicant fields are filled or N/A from an applicant fact; `codedb validate` over the
exported text reports 0 errors; every filled field renders inside its box; Section C rows (provision, lookup
objectives and functions, quoted sentence, how identified) and the six process rows with their provenance are in
the appendix; Batatis-authored text never says complies, safe, approved or adequate.
"""
import subprocess
import sys
from pathlib import Path

import pytest

from engine.codes import Codes
from engine.export import ExportBlocked, export_case, form_path, load_field_map
from engine.export.demo_cases import CASES, demo_case
from engine.export.g3 import (appendix_text, applicant_fields, check_case, coverage, wording_problems)
from engine.export.sample import sample_case

pytestmark = pytest.mark.skipif(not form_path().exists(), reason='SCC form not present (git-excluded)')
ROOT = Path(__file__).resolve().parents[2]
NAMES = [*CASES, 'sample-btrboard']


@pytest.fixture(scope='module')
def codes():
    return Codes()


@pytest.fixture(scope='module')
def exported(codes):
    cases = {name: demo_case(name, codes) for name in CASES}
    cases['sample-btrboard'] = sample_case(codes)
    return {name: (case, export_case(case, codes=codes)) for name, case in cases.items()}


@pytest.mark.parametrize('version,count', [('challenge_2026-09-15', 37), ('scc_2026-10', 50)])
def test_each_source_map_has_all_applicant_fields(version, count):
    fields = applicant_fields(load_field_map(version))
    assert len(fields) == len(set(fields)) == count


def test_homebuilder_fixture_needs_a_current_officer_determination(exported, codes):
    case, _ = exported['c-homebuilder-infill-house']
    resolution = case.professional_resolutions[0]
    assert resolution.required is False and 'window W-07' in resolution.scope
    assert resolution.by_name == 'EXAMPLE DATA fictional officer'
    unresolved = case.model_copy(deep=True)
    unresolved.professional_resolutions = []
    with pytest.raises(ExportBlocked, match='professional_requirement'):
        export_case(unresolved, codes=codes)
    changed = case.model_copy(deep=True)
    next(f for f in changed.facts if f.field == 'alternative_description').value = 'EXAMPLE DATA changed applicant scope'
    with pytest.raises(ExportBlocked, match='professional_requirement'):
        export_case(changed, codes=codes)


@pytest.mark.parametrize('name', NAMES)
def test_gate_g3_passes(exported, codes, name):
    case, result = exported[name]
    problems = check_case(case, result, codes)
    assert problems == {k: [] for k in problems}, problems
    cov = coverage(case, result)
    assert len(cov['filled']) + len(cov['na']) == 17 + 4 * max(1, len(case.section_c))
    assert not cov['missing']


def test_demo_cases_are_the_three_personas_and_exercise_na(exported):
    titles = [exported[name][0].title for name in CASES]
    assert any('manufacturer' in t for t in titles) and any('general contractor' in t for t in titles) \
        and any('homebuilder' in t for t in titles)
    for name in CASES:
        assert exported[name][1].not_applicable, f'{name} has no N/A field'


@pytest.mark.parametrize('name', CASES)
def test_codedb_validate_cli_reports_zero_errors(exported, tmp_path, name):
    _, result = exported[name]
    path = tmp_path / f'{name}.md'
    path.write_text('\n\n'.join(result.text) + '\n', encoding='utf-8')
    run = subprocess.run([sys.executable, '-m', 'codedb', 'validate', str(path)], cwd=ROOT,
                         capture_output=True, text=True)
    assert run.returncode == 0, run.stdout + run.stderr
    assert '; 0 errors;' in run.stdout


def test_section_c_rows_carry_identification_lookup_and_quoted_sentence(exported):
    case, result = exported['a-manufacturer-nailbase-sheathing']
    text = appendix_text(result)
    assert 'Committed by code identification; confirmed by the applicant.' in text
    assert 'Benchmark acceptable solution' in text and 'Quoted sentence:' in text
    assert '(confirmed by the applicant)' in text
    for row in case.section_c:
        assert row.provision_id in text and all(p.objective in text and p.function in text for p in row.pairs)
    b_text = appendix_text(exported['b-contractor-firestop-nonconformance'][1])
    assert 'Listed by code identification; confirmed by the applicant.' in b_text


def test_appendix_names_the_variance_and_the_alternative_solution_with_the_equivalence_test(exported):
    text = appendix_text(exported['c-homebuilder-infill-house'][1])
    assert 'request for variance' in text and 'section 38 of the Safety Codes Act' in text
    assert 'alternative solution (NBC(AE) 2023 Division C 2.3.1)' in text
    assert 'at least the level of performance of the acceptable solution' in text
    assert 'P. Alternative solution (Div C 2.3.1): applicant-written documentation' in text
    assert 'B. Request for variance: proposed alternative and scope' in text


def test_wording_check_catches_a_banned_word(exported):
    case, result = exported['c-homebuilder-infill-house']
    result.appendix_text.append('This design is adequate.')
    try:
        assert wording_problems(case, result)
    finally:
        result.appendix_text.pop()


def test_no_local_path_reaches_the_pdf(exported):
    for name in CASES:
        assert str(ROOT) not in appendix_text(exported[name][1])


def test_every_na_cell_traces_to_an_applicant_fact(exported):
    fmap = load_field_map()
    for name in CASES:
        case, result = exported[name]
        ids = {f.id: f for f in case.facts}
        for field in result.not_applicable:
            assert field in applicant_fields(fmap)
        assert all(f.source.type in ('user_text', 'user_click') for f in ids.values()
                   if f.field.startswith('not_applicable.'))


def test_a_600_word_rationale_goes_to_the_appendix_in_full(codes):
    """AC9.3: long applicant text is carried by the appendix by default, never clipped on the form."""
    from engine.models import Fact, Source
    case = demo_case('a-manufacturer-nailbase-sheathing', codes)
    long = ' '.join(f'EXAMPLE rationale word {n}.' for n in range(150))   # 600 words
    assert len(long.split()) == 600
    case.facts += [Fact(field=key, value=long, kind='pointed', status='confirmed',
                        source=Source(type='user_text', ref='test:applicant', quote=long))
                   for key in ('rationale', 'mailing_address')]
    result = export_case(case, codes=codes)
    text = appendix_text(result)
    assert long in text
    mailing = next(p for p in result.placements if p.field == 'Mailing Address')
    assert mailing.ref and mailing.lines == [f'See Appendix {mailing.ref}']
    assert check_case(case, result, codes)['render'] == []


def test_package_note_citations_resolve_and_paraphrase_the_division_a_clause(codes):
    """The fixed appendix note cites Div A 1.2.1.1.(1)(b) and Div C 2.3.1; both resolve in codedb and the wording
    follows the clause text (review on PR #60)."""
    from codedb import validate_text
    from engine.export.appendix import PACKAGE_NOTE
    assert validate_text(PACKAGE_NOTE, db_path=codes.db_path)['errors'] == []
    clause = codes.provision('1.2.1.1.(1)(b)', 'A')
    assert clause and 'at least the minimum level of performance' in ' '.join(clause['text'].split())
    assert 'at least the level of performance of the acceptable solution' in PACKAGE_NOTE
    assert codes.provision('2.3.1.1.', 'C') is not None


def test_story_text_extracts_table_rows_and_grouped_paragraphs(exported):
    """story_text reads ReportLab tables and KeepTogether groups; fail loudly if a ReportLab change empties them."""
    _, result = exported['a-manufacturer-nailbase-sheathing']
    assert any(line.startswith('| C-1 | 9.27.5.1.(1) |') for line in result.appendix_text)
    assert any(line.startswith('P-1 Rationale') for line in result.appendix_text)


def test_appendix_without_a_code_database_claims_no_printing():
    from types import SimpleNamespace
    from engine.export.appendix import build_appendix
    from engine.models import Case
    text: list[str] = []
    build_appendix(Case(), SimpleNamespace(overflow=[], rows_in_form=0, docs_in_form=0), {}, {'version': 't'},
                   codes=None, open_items=[], text=text)
    assert '2nd printing' not in text[1]
