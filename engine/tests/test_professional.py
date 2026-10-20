import pytest

from engine.codes import Codes
from engine.models import Case, Fact, Source
from engine.professional import ProfessionalFacts, professional_confirmed, professional_involvement, role_confirmed


def ordinary_house(**overrides):
    return ProfessionalFacts(**(dict(occupancy='single_family', part4_design=False,
        preserved_wood_foundation_part4=False, roof_trusses=False, prescriptive_route_confirmed=True,
        ahj_requires_professional=False, special_safety_concerns=False, professional_judgement_required=False,
        professional_scope_resolved=True, fire_suppression=False, fire_alarm=False) | overrides))


def test_role_confirmation_matches_an_engineer_or_architect_not_a_commercial_role():
    assert role_confirmed('structural engineer')
    assert role_confirmed('P.Eng.')
    assert role_confirmed('P Eng')
    assert role_confirmed('registered architect')
    assert not role_confirmed('sales rep')
    assert not role_confirmed('supplier')


def _text(field, value, source_type='user_text'):
    return Fact(field=field, value=value, kind='pointed', status='confirmed',
                source=Source(type=source_type, ref='applicant', quote=value))


def test_prescriptive_answers_do_not_confirm_a_professional():
    case = Case(facts=[
        _text('prescriptive_route_confirmed', 'true'),
        _text('professional_judgement_required', 'false'),
        _text('professional.seal', 'copied stamp', 'file'),
    ])
    assert professional_confirmed(case) is False
    case.facts += [_text('professional.role', 'P.Eng.'), _text('professional.registration_number', 'APEGA-1000')]
    assert professional_confirmed(case) is True


def test_missing_facts_never_return_no():
    result = professional_involvement(ProfessionalFacts(), Codes())
    assert result.required == result.general_required == 'depends' and result.questions
    assert professional_involvement(ProfessionalFacts(occupancy='single_family'), Codes()).required == 'depends'


def test_under_flagging_guard_every_missing_house_scope_fact():
    facts = ordinary_house()
    assert professional_involvement(facts, Codes()).required == 'no'
    for field in ('part4_design', 'preserved_wood_foundation_part4', 'roof_trusses', 'prescriptive_route_confirmed',
                  'ahj_requires_professional', 'special_safety_concerns', 'professional_judgement_required',
                  'professional_scope_resolved', 'fire_suppression', 'fire_alarm'):
        result = professional_involvement(facts.model_copy(update={field: None}), Codes())
        assert result.required == 'depends', field


@pytest.mark.parametrize('occupancy,storeys,area,expected', [
    ('assembly', 1, 300, 'no'), ('assembly', 1, 301, 'yes'),
    ('care', 2, 150, 'no'), ('treatment', 2, 151, 'yes'),
    ('detention', 3, 100, 'no'), ('assembly', 3, 101, 'yes'),
    ('hotel', 1, 400, 'no'), ('hotel', 2, 201, 'yes'), ('hotel', 3, 130, 'no'),
    ('business', 1, 500, 'no'), ('mercantile', 2, 251, 'yes'),
    ('industrial', 3, 165, 'no'), ('industrial', 4, 100, 'yes'),
])
def test_general_area_thresholds(occupancy, storeys, area, expected):
    result = professional_involvement(ordinary_house(occupancy=occupancy, storeys=storeys, building_area_m2=area), Codes())
    assert result.required == result.general_required == expected


def test_part9_six_units_still_requires_professionals():
    result = professional_involvement(ordinary_house(occupancy='multi_family', storeys=3,
                                     building_area_m2=400, principal_dwelling_units=6), Codes())
    assert result.required == 'yes'
    assert next(r for r in result.reasons if r.code == 'general_building').citation == Codes().citation('2.4.1.1.(3)', 'C')
    assert professional_involvement(ordinary_house(occupancy='multi_family', principal_dwelling_units=4), Codes()).required == 'no'
    assert professional_involvement(ordinary_house(occupancy='multi_family'), Codes()).required == 'depends'


@pytest.mark.parametrize('flag', ['part4_design', 'preserved_wood_foundation_part4', 'roof_trusses', 'ahj_requires_professional'])
def test_component_triggers_override_house_exception(flag):
    result = professional_involvement(ordinary_house(**{flag: True}), Codes())
    assert result.required == 'yes' and result.general_required == 'no'
    assert any('Div C' in r.citation and r.required == 'yes' for r in result.reasons)


def test_general_building_system_retention_and_citations():
    result = professional_involvement(ordinary_house(occupancy='multi_family', principal_dwelling_units=8,
                                      fire_alarm=True, fire_suppression=True), Codes())
    cited = {r.citation for r in result.reasons}
    assert {Codes().citation(pid, 'C') for pid in ('2.4.1.3.(1)', '2.4.1.4.(1)')} <= cited


def test_case_uses_only_confirmed_well_typed_facts():
    src = Source(type='user_text', ref='m')
    facts = [Fact(field='occupancy', value='single_family', kind='pointed', source=src, status='confirmed'),
             Fact(field='part4_design', value='false', kind='pointed', source=src, status='confirmed'),
             Fact(field='professional_scope_resolved', value=True, kind='proposed', source=src)]
    data = ProfessionalFacts.from_case(Case(facts=facts))
    assert data.occupancy == 'single_family' and data.part4_design is None and data.professional_scope_resolved is None
    assert professional_involvement(Case(facts=facts), Codes()).required == 'depends'


def test_farm_and_camp_exceptions_do_not_erase_component_duties():
    assert professional_involvement(ordinary_house(occupancy='farm', farm_public_use=False), Codes()).required == 'no'
    assert professional_involvement(ordinary_house(occupancy='farm', farm_public_use=True), Codes()).required == 'depends'
    assert professional_involvement(ordinary_house(occupancy='relocatable_industrial_camp', part4_design=True), Codes()).required == 'yes'
