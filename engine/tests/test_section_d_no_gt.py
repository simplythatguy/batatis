"""No-ground-truth hazards. Labels are model-constructed, model-checked, not human-verified."""
from pathlib import Path

from engine.section_d_flag_eval import (
    NGT_LABEL, evaluate, load_codes, load_ngt, ngt_report, observe, score,
)


def _case(text: str) -> dict:
    return {'id': 'probe', 'description': text, 'known_facts': []}


def test_part4_phrase_inside_a_negation_is_not_a_positive_trigger():
    assert observe(_case('structural design under Part 4')).__getitem__(0).part4_design is True
    negated = 'two-storey house, 210 m², wood frame, not designed under Part 4'
    assert observe(_case(negated))[0].part4_design is False
    assert observe(_case('foundations on permafrost'))[0].part4_design is True
    assert observe(_case('two-storey house, 210 m², wood frame, not on permafrost'))[0].part4_design is False


def test_no_engineer_is_an_explicit_negative_fact():
    codes, _codedb = load_codes()
    house = 'two-storey house, 210 m², wood frame, 6 m clear span, no engineer engaged'
    facts, signals = observe(_case(house))
    assert facts.engineer_engaged is False
    assert 'unresolved_design' not in signals.flags
    assert evaluate(_case(house), codes, 'rules_plus_unknown')[0] == 'no'
    panels = 'custom single-family home built from structural insulated panels, no engineer is on the project'
    _facts, panel_signals = observe(_case(panels))
    assert _facts.engineer_engaged is False
    assert 'unresolved_design' in panel_signals.flags


def test_stick_framed_part9_building_sets_part4_false():
    text = ('single-storey detached house, building area of 150 m2, stick-framed lumber '
            'from the Part 9 span tables, 4.0 m clear span')
    assert observe(_case(text))[0].part4_design is False


def test_retail_shop_is_mercantile_and_answers_no():
    codes, _codedb = load_codes()
    case = next(item for item in load_ngt() if item['id'] == 'ngt-007')
    facts, _signals = observe(case)
    assert facts.occupancy == 'mercantile'
    assert facts.part4_design is False
    assert evaluate(case, codes, 'rules_plus_unknown')[0] == 'no'
    assert evaluate(case, codes, 'rules_only')[0] == 'no'


def test_suites_over_four_answer_yes_without_double_counting_a_stated_total():
    codes, _codedb = load_codes()
    cases = {item['id']: item for item in load_ngt()}
    townhouses = observe(cases['ngt-101'])[0]
    assert townhouses.principal_dwelling_units == 3
    assert townhouses.total_unit_count == 6
    assert evaluate(cases['ngt-101'], codes, 'rules_plus_unknown')[0] == 'yes'
    assert observe(cases['ngt-102'])[0].total_unit_count == 8
    assert evaluate(cases['ngt-102'], codes, 'rules_plus_unknown')[0] == 'yes'
    stated = observe(cases['ngt-004'])[0]
    assert stated.total_unit_count == 4
    assert evaluate(cases['ngt-004'], codes, 'rules_plus_unknown')[0] == 'no'
    assert evaluate(cases['ngt-003'], codes, 'rules_plus_unknown')[0] == 'no'


def test_ambiguous_gross_area_asks_and_does_not_answer_no():
    codes, _codedb = load_codes()
    case = next(item for item in load_ngt() if item['id'] == 'ngt-103')
    facts, _signals = observe(case)
    assert facts.gross_area_unsettled is True
    assert facts.occupancy == 'hotel'
    label, question = evaluate(case, codes, 'rules_plus_unknown')
    assert label == 'unknown'
    assert question and 'gross area' in question.casefold()
    assert evaluate(case, codes, 'rules_only')[0] == 'depends'
    named = _case('single-storey motel, building area of 200 m2, gross area of the main floor')
    assert observe(named)[0].gross_area_unsettled is True


def test_ngt_report_labels_every_line_and_the_shipped_screen_does_not_under_flag():
    codes, _codedb = load_codes()
    cases = load_ngt()
    assert [item['id'] for item in cases] == [
        'ngt-001', 'ngt-002', 'ngt-003', 'ngt-004', 'ngt-005', 'ngt-006', 'ngt-007', 'ngt-008',
        'ngt-101', 'ngt-102', 'ngt-103']
    readme = Path('evals/fixtures/section_d_no_gt/README.md').read_text()
    assert NGT_LABEL in readme
    for case in cases:
        assert case['authoring']['label'] == NGT_LABEL
        assert case['evidence']['label'] == NGT_LABEL
        assert 'quote' not in case['evidence']
    totals = score(codes, cases)
    text = ngt_report(totals)
    assert text.splitlines()
    assert all(NGT_LABEL in line for line in text.splitlines())
    assert 'in-sample once tuned against these cases' in text
    shipped = totals['rules_plus_unknown']
    assert shipped.under_flag == 0
    assert shipped.scored == 11
    labels = {case['id']: evaluate(case, codes, 'rules_plus_unknown')[0] for case in cases}
    for name in ('ngt-001', 'ngt-002', 'ngt-003', 'ngt-004', 'ngt-005', 'ngt-006', 'ngt-007', 'ngt-008'):
        assert labels[name] == 'no', name
    assert labels['ngt-101'] == 'yes'
    assert labels['ngt-102'] == 'yes'
    assert labels['ngt-103'] == 'unknown'
