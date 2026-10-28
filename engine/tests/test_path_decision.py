"""W2 path: a firm check chooses the package. An unknown fork does not open one."""
import pytest

from engine.codes import Codes
from engine.models import Case, Fact, Source
from engine.path_decision import decide_path
from engine.process_fields import process_fields
from engine.section_c import section_c_rows
from engine.section_d import ALTERNATIVE_EVIDENCE_TYPES, CONFIDENCE_LADDER, section_d_plan


def fact(field, value):
    return Fact(field=field, value=value, kind='pointed', status='confirmed',
                source=Source(type='user_text', ref='test', quote=str(value)))


def soffit(**overrides):
    values = dict(storeys=2, building_area_m2=150, occupancy='single_family', soffit_projects=True,
                  soffit_to_property_line_m=0.1, faces_public_way=False, limiting_distance_m=0.3)
    values.update(overrides)
    facts = [fact('project.description', 'Aluminum soffit along the north wall.')]
    facts += [fact(field, value) for field, value in values.items() if value is not None]
    return Case(facts=facts)


def test_explicit_variance_request_opens_the_alternative_package():
    case = Case(facts=[fact('variance_requested', True)])
    decision = decide_path(case)
    assert decision.path == 'alternative' and decision.source == 'recorded' and not decision.firm
    assert len(process_fields(case, Codes())) == 6


def test_unknown_path_opens_no_process_fields():
    decision = decide_path(Case())
    assert decision.path == 'unresolved' and not decision.firm
    assert process_fields(Case(), Codes()) == []


def test_firm_follows_is_acceptable_without_process_fields():
    case = soffit(limiting_distance_m=1.2, soffit_to_property_line_m=0.8)
    decision = decide_path(case)
    assert decision.path == 'acceptable' and decision.firm and decision.source == 'coded_check'
    assert decision.article == '9.10.15.5.(9)'
    assert process_fields(case, Codes()) == []
    case.provisions = ['9.10.15.5.(9)']
    plan = section_d_plan(case, Codes())
    assert plan.items and all(item.recommended_types == CONFIDENCE_LADDER for item in plan.items)
    assert all(ALTERNATIVE_EVIDENCE_TYPES[0] not in item.recommended_types for item in plan.items)


def test_firm_departs_opens_the_six_process_fields():
    case = soffit()
    decision = decide_path(case)
    assert decision.path == 'alternative' and decision.firm
    assert decision.rule_id == 'soffits-houses' and decision.article == '9.10.15.5.(8)'
    assert [field.id for field in process_fields(case, Codes())] == [
        'rationale', 'risk_assessment', 'mitigating_measures', 'assumptions_and_limits',
        'maintenance_operation', 'qualifications']
    case.provisions = [decision.article]
    plan = section_d_plan(case, Codes())
    assert plan.items and all(
        item.recommended_types == CONFIDENCE_LADDER + ALTERNATIVE_EVIDENCE_TYPES for item in plan.items)


def test_firm_follows_wins_over_a_recorded_variance():
    case = soffit(limiting_distance_m=1.2, soffit_to_property_line_m=0.8)
    case.facts.append(fact('pathway', 'alternative'))
    assert decide_path(case).path == 'acceptable'
    assert process_fields(case, Codes()) == []


def test_labeled_assumption_is_not_a_firm_departure():
    case = soffit(storeys=None, building_area_m2=None)
    decision = decide_path(case)
    assert not decision.firm and decision.path == 'unresolved'
    assert decision.asks_rule_inputs and 'storeys' in decision.missing
    assert process_fields(case, Codes()) == []


def test_not_applicable_opens_no_package():
    case = soffit(storeys=5, building_area_m2=100)
    decision = decide_path(case)
    assert decision.path == 'not_applicable' and decision.firm
    assert decision.article == '1.3.3.3.(1)'
    assert process_fields(case, Codes()) == []
    assert section_d_plan(case, Codes()).items == []


def test_wording_that_follows_is_acceptable_without_process_fields():
    case = Case(facts=[fact('project.description', 'A standard house built to the Part 9 tables.')])
    decision = decide_path(case)
    assert decision.path == 'acceptable' and decision.source == 'wording' and not decision.firm
    assert decision.article is None
    assert process_fields(case, Codes()) == []


def test_stated_departure_opens_alternative_when_the_check_is_not_firm():
    case = Case(facts=[fact('project.description', 'We will omit the sheathing on this wall.')])
    decision = decide_path(case)
    assert decision.path == 'alternative' and decision.source == 'wording' and not decision.firm
    assert len(process_fields(case, Codes())) == 6


def test_recorded_acceptable_wins_over_departure_wording_when_the_check_is_not_firm():
    case = Case(facts=[
        fact('project.description', 'We will omit the sheathing on this wall.'),
        fact('pathway', 'acceptable'),
    ])
    assert decide_path(case).path == 'acceptable'
    assert process_fields(case, Codes()) == []


def test_other_regime_redirects_and_opens_no_package():
    case = Case(facts=[fact('project.description', 'The air admittance valve is the thing we want to change.')])
    assert decide_path(case).path == 'redirect'
    assert process_fields(case, Codes()) == []


def test_section_c_for_the_firm_article_matches_the_database_codes():
    case = soffit()
    article = decide_path(case).article
    [row] = section_c_rows([article], Codes())
    assert row.provision_id == '9.10.15.5.(8)'
    assert row.attribution_status == 'direct'
    assert [(pair.function, pair.objective) for pair in row.pairs] == [('F03', 'OP3.1')]
    assert [(block.objective, len(block.intents)) for block in row.intents] == [('OP3', 1)]


def test_section_c_lookup_miss_names_the_id():
    with pytest.raises(KeyError, match=r'Section C lookup missed 1\.3\.3\.3\.\(1\)'):
        section_c_rows(['1.3.3.3.(1)'], Codes())
    with pytest.raises(KeyError, match=r'Section C lookup missed 9\.99\.99\.99\.\(1\)'):
        section_c_rows(['9.99.99.99.(1)'], Codes())
