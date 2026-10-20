"""Human-review rows name a person and a pinpoint. They do not grant a variance."""
from engine.models import Case
from engine.professional import ProfessionalFacts, professional_involvement
from engine.section_d_issues import section_d_issues
from engine.tests.test_section_d_issues import BENCHMARK, codes_with_rules, fact


def _ids(issue):
    return [row.trigger_id for row in issue.human_review]


def test_every_issue_names_someone_and_labels_the_source():
    from engine.human_review import CODEDB_ONLY_TRIGGERS
    issue = section_d_issues(Case(provisions=[BENCHMARK]), codes_with_rules())[0]
    assert issue.human_review
    assert all(row.who and row.why and row.cite for row in issue.human_review)
    assert all(row.source == 'statute' or row.trigger_id in CODEDB_ONLY_TRIGGERS for row in issue.human_review)
    assert all(row.source == 'codedb' and row.act is None and row.quote is None
               for row in issue.human_review if row.source == 'codedb')
    variance = next(row for row in issue.human_review if row.trigger_id == 'HR-30')
    assert variance.source == 'statute'
    assert variance.cite == 'Safety Codes Act s.38(1)'
    assert variance.act == 'Safety Codes Act, RSA 2000 c S-1 (current as of Dec 1, 2025)'
    assert variance.quote.startswith('An Administrator or a safety codes officer may issue a written variance')
    assert 'approximately equivalent or greater safety performance' in variance.quote
    blob = issue.model_dump_json()
    assert 'Table 2.4.2' not in blob


def test_acceptable_path_has_no_variance_row():
    issue = section_d_issues(
        Case(provisions=[BENCHMARK], facts=[fact('pathway', 'acceptable')]), codes_with_rules())[0]
    assert 'HR-30' not in _ids(issue)


def test_general_yes_names_schedules_without_the_missing_tables():
    facts = [
        fact('occupancy', 'multi_family'), fact('principal_dwelling_units', 6),
        fact('part4_design', False), fact('prescriptive_route_confirmed', True),
        fact('ahj_requires_professional', False), fact('special_safety_concerns', False),
        fact('professional_judgement_required', False), fact('professional_scope_resolved', True),
        fact('fire_suppression', False), fact('fire_alarm', False),
        fact('preserved_wood_foundation_part4', False), fact('roof_trusses', False),
    ]
    issue = section_d_issues(Case(provisions=[BENCHMARK], facts=facts), codes_with_rules())[0]
    assert 'HR-02' not in _ids(issue)
    assert 'HR-01' in _ids(issue)
    assert 'Table 2.4.2' not in issue.model_dump_json()


def test_code_exception_can_still_name_the_acts():
    facts = [
        fact('occupancy', 'multi_family'), fact('principal_dwelling_units', 4),
        fact('total_unit_count', 5), fact('building_area_m2', 200.0),
        fact('gross_area_per_floor_m2', 260.0),
        fact('part4_design', False), fact('prescriptive_route_confirmed', True),
        fact('ahj_requires_professional', False), fact('special_safety_concerns', False),
        fact('professional_judgement_required', False), fact('professional_scope_resolved', True),
        fact('fire_suppression', False), fact('fire_alarm', False),
        fact('preserved_wood_foundation_part4', False), fact('roof_trusses', False),
    ]
    issue = section_d_issues(Case(provisions=[BENCHMARK], facts=facts), codes_with_rules())[0]
    assert issue.practice_of_engineering.value is True
    units = [row for row in issue.human_review if row.cite in (
        'Architects Act s.2(6)(b)(ii)', 'EGPA s.2(7)(b)(ii)')]
    assert {row.cite for row in units} == {'Architects Act s.2(6)(b)(ii)', 'EGPA s.2(7)(b)(ii)'}
    assert all(row.source == 'statute' and row.why ==
               'counts dwelling units (4 or less); whether a suite counts is for the officer' for row in units)
    assert all(row.act and row.quote for row in units)
    assert 'EGPA s.2(7)(a)' not in _ids(issue) and all(row.cite != 'EGPA s.2(7)(a)' for row in issue.human_review)
    assert 'Architects Act s.2(6)(a)' not in issue.model_dump_json()
    assert 'does not exclude suites' not in issue.model_dump_json()


def test_barrier_free_interpretation_and_tolerance_routes():
    codes = codes_with_rules()
    barrier = section_d_issues(Case(provisions=[BENCHMARK, '3.8.3.1.(1)']), codes)[0]
    row = next(item for item in barrier.human_review if item.trigger_id == 'HR-32')
    assert row.cite == 'fixture:C:2.2.1.4.(1)'
    assert 'Provincial Barrier-Free Administrator' in row.who

    interpretation = section_d_issues(
        Case(provisions=[BENCHMARK], facts=[fact('requests_interpretation', True)]), codes)[0]
    assert next(item.cite for item in interpretation.human_review if item.trigger_id == 'HR-31') == 'fixture:C:2.2.1.3.(1)'

    within = section_d_issues(Case(provisions=[BENCHMARK], facts=[
        fact('dimension_required', 100.0), fact('dimension_proposed', 101.0)]), codes)[0]
    assert next(item.cite for item in within.human_review if item.trigger_id == 'HR-33') == 'fixture:C:2.2.2.3.(1)'
    assert next(item.who for item in within.human_review if item.trigger_id == 'HR-33') == 'Authority having jurisdiction'

    outside = section_d_issues(Case(provisions=[BENCHMARK], facts=[
        fact('dimension_required', 100.0), fact('dimension_proposed', 103.0)]), codes)[0]
    assert 'HR-33' not in _ids(outside)


def test_assembly_gross_area_cites_only_the_confirmed_paragraph():
    facts = [
        fact('occupancy', 'assembly'), fact('storeys', 1), fact('building_area_m2', 200.0),
        fact('gross_area_per_floor_m2', 280.0),
        fact('part4_design', False), fact('prescriptive_route_confirmed', True),
        fact('ahj_requires_professional', False), fact('special_safety_concerns', False),
        fact('professional_judgement_required', False), fact('professional_scope_resolved', True),
        fact('fire_suppression', False), fact('fire_alarm', False),
        fact('preserved_wood_foundation_part4', False), fact('roof_trusses', False),
        fact('pathway', 'acceptable'),
    ]
    issue = section_d_issues(Case(provisions=[BENCHMARK], facts=facts), codes_with_rules())[0]
    gross = [row for row in issue.human_review if row.cite == 'EGPA s.2(7)(a)']
    assert len(gross) == 1 and gross[0].source == 'statute'
    assert gross[0].act == 'Engineering and Geoscience Professions Act, RSA 2000 c E-11 (current as of Dec 7, 2023)'
    assert '300 square metres or less' in gross[0].quote
    assert 'assembly occupancy or institutional occupancy' in gross[0].quote


def test_other_occupancies_emit_no_act_gross_area_row():
    facts = [
        fact('occupancy', 'hotel'), fact('storeys', 1), fact('building_area_m2', 300.0),
        fact('gross_area_per_floor_m2', 450.0), fact('pathway', 'acceptable'),
        fact('part4_design', False), fact('prescriptive_route_confirmed', True),
        fact('professional_judgement_required', False), fact('professional_scope_resolved', True),
        fact('ahj_requires_professional', False), fact('special_safety_concerns', False),
    ]
    issue = section_d_issues(Case(provisions=[BENCHMARK], facts=facts), codes_with_rules())[0]
    assert all(row.cite != 'EGPA s.2(7)(a)' for row in issue.human_review)
    assert all('s.2(7)(c)' not in row.cite and 's.2(6)(a)' not in row.cite for row in issue.human_review)


def test_unanswered_components_ask_only_in_scope():
    codes = codes_with_rules()
    house = ProfessionalFacts(
        occupancy='single_family', part4_design=False, prescriptive_route_confirmed=True,
        ahj_requires_professional=False, special_safety_concerns=False,
        professional_judgement_required=False, professional_scope_resolved=True)
    assert professional_involvement(house, codes).required == 'no'
    assert professional_involvement(house, codes, provisions=('9.23.14.11.(2)',)).required == 'depends'
    assert professional_involvement(house, codes, provisions=('9.15.2.4.(1)',)).required == 'depends'
    part3 = house.model_copy(update={'occupancy': 'mercantile', 'storeys': 5, 'building_area_m2': 800.0})
    asked = professional_involvement(part3, codes)
    assert asked.general_required == 'yes'
    assert any('fire suppression' in question for question in asked.questions)


def test_named_duties_use_looked_up_cites():
    codes = codes_with_rules()
    fields = (
        ('aquatic_facility', 'HR-13', 'fixture:C:2.2.9.2.(1)'),
        ('geotechnical_part4', 'HR-14', 'fixture:B:4.2.2.1.(1)'),
        ('part10_sprinklers', 'HR-12', 'fixture:B:10.4.7.2.(1)'),
        ('guards', 'HR-03', 'fixture:C:2.2.4.4.(1)'),
        ('medical_gas_piping', 'HR-42', 'fixture:C:2.2.11.4.(2)'),
    )
    for field, trigger_id, cite in fields:
        issue = section_d_issues(Case(provisions=[BENCHMARK], facts=[fact(field, True)]), codes)[0]
        match = next(row for row in issue.human_review if row.trigger_id == trigger_id and row.cite == cite)
        assert match.who and match.why
    for field, trigger_id in (('off_site_constructed', 'HR-43'), ('special_structure', 'HR-16')):
        issue = section_d_issues(Case(provisions=[BENCHMARK], facts=[fact(field, True)]), codes)[0]
        assert trigger_id not in _ids(issue)
