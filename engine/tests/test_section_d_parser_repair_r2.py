"""K26-6/7/8 regressions over synthetic text; never load evaluation targets."""
import pytest

from engine.codes import Codes
from engine.section_d_flag_eval import evaluate, observe, prepare


HOUSE = 'two-storey house, 210 m², wood frame, 6 m clear span'
UNITS = 'two-storey wood frame building, 210 m2, 6 m clear span, six principal dwelling units'


def case(text):
    return {'id': 'synthetic-parser-repair', 'description': text, 'known_facts': []}


@pytest.fixture(scope='module')
def codes():
    return Codes()


@pytest.mark.parametrize('cue', [
    '5200 mm floor joists',
    'q50 = 1.25 kPa',
    'floor joist span to be confirmed',
    'wind pressure to be confirmed',
    'specified live load to be confirmed',
    'seismic demand to be confirmed',
    'Sa(0.2) to be confirmed',
    'roof member span to be confirmed',
    'beam span of 5200 mm',
    '1.25 kPa wind pressure',
    '4.9 m floor joists; other floor joists have an unstated span',
    'wind pressure of 1.1 kPa; extension wind pressure to be confirmed',
    'Sa(0.2) of 1.0; extension seismic demand to be confirmed',
])
def test_unparsed_relevant_cue_keeps_part4_unknown_and_asks(codes, cue):
    row = case(f'{HOUSE}, {cue}')
    facts, signals = observe(row)
    assert facts.part4_design is None
    assert prepare(facts, signals, 'rules_plus_unknown').part4_design is None
    label, question = evaluate(row, codes, 'rules_plus_unknown')
    assert label == 'unknown'
    assert question and 'Part 4' in question


@pytest.mark.parametrize(('cue', 'part4', 'label'), [
    ('', False, 'no'),
    ('5.2 m floor joists', True, 'yes'),
    ('joists spanning 5.2 m', True, 'yes'),
    ('4.9 m joist span', False, 'no'),
    ('specified live load of 2.4 kPa', False, 'no'),
    ('specified live load of 2.4001 kPa', True, 'yes'),
    ('1-in-50 hourly wind pressure = 1.2 kPa', True, 'yes'),
    ('1-in-50 hourly wind pressure = 1.25 kPa', True, 'yes'),
    ('1-in-50 hourly wind pressure of 1.1 kPa', False, 'no'),
    ('Sa(0.2) of 1.8', False, 'no'),
    ('Sa(0.2) of 1.81', True, 'yes'),
    ('lumber roof sheathing and Sa(0.2) of 1.2', False, 'no'),
    ('lumber roof sheathing and Sa(0.2) of 1.21', True, 'yes'),
    ('soil bearing pressure of 80 kPa', False, 'no'),
    ('not on permafrost', False, 'no'),
])
def test_understood_values_preserve_source_thresholds(codes, cue, part4, label):
    row = case(f'{HOUSE}, {cue}')
    facts, _signals = observe(row)
    assert facts.part4_design is part4
    assert evaluate(row, codes, 'rules_plus_unknown') == (label, None)


@pytest.mark.parametrize('separator', ['; ', ', ', '. ', '\n', ' and '])
@pytest.mark.parametrize('reverse', [False, True])
def test_kpa_value_stays_with_its_own_preceding_cue(codes, separator, reverse):
    clauses = ['specified live load of 1.9 kPa', '1-in-50 hourly wind pressure is 0.45 kPa']
    if reverse:
        clauses.reverse()
    row = case(f'{HOUSE}, {separator.join(clauses)}')
    facts, _signals = observe(row)
    assert facts.part4_design is False
    assert evaluate(row, codes, 'rules_plus_unknown') == ('no', None)


@pytest.mark.parametrize(('pressures', 'label'), [
    ('specified live load 2.4 kPa; wind pressure 1.19 kPa', 'no'),
    ('wind pressure 1.19 kPa; specified live load 2.4 kPa', 'no'),
    ('specified live load 2.4 kPa; wind pressure 1.2 kPa', 'yes'),
    ('wind pressure 1.2 kPa; specified live load 2.4 kPa', 'yes'),
    ('specified live load 2.41 kPa; wind pressure 0.45 kPa', 'yes'),
    ('wind pressure 0.45 kPa; specified live load 2.41 kPa', 'yes'),
    ('wind pressure 0.45 kPa; soil bearing pressure 80 kPa', 'no'),
])
def test_mixed_pressure_thresholds_and_unrelated_values(codes, pressures, label):
    assert evaluate(case(f'{HOUSE}, {pressures}'), codes, 'rules_plus_unknown') == (label, None)


@pytest.mark.parametrize('supplier', ['shop', 'supplier', 'retail shop'])
def test_supplier_is_not_the_building_occupancy(codes, supplier):
    row = case(f'{UNITS}; materials supplied by a {supplier}')
    facts, _signals = observe(row)
    assert facts.occupancy == 'multi_family'
    # This principal-count wording is not supported: preserve the question, not a forced yes.
    assert facts.principal_dwelling_units is None
    label, question = evaluate(row, codes, 'rules_plus_unknown')
    assert label == 'unknown'
    assert question and 'dwelling units' in question


@pytest.mark.parametrize(('use', 'occupancy'), [
    ('single-storey retail shop', 'mercantile'),
    ('single-storey shop building', 'mercantile'),
    ('single-storey office', 'business'),
])
def test_actual_nonresidential_occupancy_is_preserved(codes, use, occupancy):
    row = case(f'{use}, 180 m2 building area, wood frame, 6 m clear span')
    facts, _signals = observe(row)
    assert facts.occupancy == occupancy
    assert evaluate(row, codes, 'rules_plus_unknown') == ('no', None)


def test_conflicting_retail_and_residential_uses_ask(codes):
    row = case(f'{UNITS}; the ground floor is a retail shop')
    label, question = evaluate(row, codes, 'rules_plus_unknown')
    assert label == 'unknown'
    assert question


def test_an_independent_positive_trigger_still_resolves_yes(codes):
    row = case(f'{HOUSE}, reinforced concrete wall; wind pressure to be confirmed')
    facts, _signals = observe(row)
    assert facts.part4_design is True
    assert evaluate(row, codes, 'rules_plus_unknown') == ('yes', None)
