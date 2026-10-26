import pytest

from engine.codes import Codes
from engine.identify.case_input import active_facts
from engine.identify.scope import assess
from engine.models import Case, Fact, Source


def fact(field, value, status='confirmed'):
    return Fact(field=field, value=value, status=status, kind='pointed',
                source=Source(type='user_text', ref='applicant'))


@pytest.fixture(scope='module')
def codes():
    return Codes()


def test_storey_value_changes_source_backed_scope_without_keyword_routing(codes):
    case = Case(facts=[fact('storeys', 2)])
    first = assess(codes, active_facts(case))[0]
    case.facts.append(fact('storeys', 8))
    second = assess(codes, active_facts(case))[0]
    assert first.status == 'not_determined'
    assert first.conditions[0].status == 'met'
    assert second.status == 'boundary_not_met'
    assert second.conditions[0].status == 'not_met'
    source = codes.provision(second.basis[0].provision_id, 'A')
    assert second.basis[0].quote == source['text'] and second.basis[0].citation == source['citation']


def test_even_all_three_gates_do_not_certify_part9_applicability(codes):
    result = assess(codes, [fact('storeys', 2), fact('building_area_m2', 500), fact('occupancy', 'Group C')])[0]
    assert result.status == 'conditions_met_scope_unresolved'
    assert all(c.status == 'met' for c in result.conditions)


def test_conflicting_and_unconfirmed_numbers_are_not_scope_decisions(codes):
    case = Case(facts=[fact('storeys', 2), fact('storeys', 8, 'unconfirmed')])
    result = assess(codes, active_facts(case))[0]
    assert result.conditions[0].status == 'conflict' and result.status == 'not_determined'
    result = assess(codes, [fact('storeys', 8, 'unconfirmed')])[0]
    assert result.conditions[0].status == 'unknown'


def test_house_keyword_does_not_supply_a_major_occupancy_classification(codes):
    result = assess(codes, [fact('storeys', 2), fact('building_area_m2', 500), fact('occupancy', 'house')])[0]
    assert result.conditions[-1].status == 'unknown'
    assert result.status == 'not_determined'
