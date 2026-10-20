"""Human-review rows name a person and a pinpoint. They do not grant a variance."""
from engine.models import Case
from engine.professional import ProfessionalFacts, professional_involvement
from engine.section_d_issues import section_d_issues
from engine.tests.test_section_d_issues import BENCHMARK, codes_with_rules, fact


def _ids(issue):
    return [row.trigger_id for row in issue.human_review]


def test_every_issue_names_someone_and_labels_the_source():
    from engine.human_review import MANDATORY_TRIGGERS
    issue = section_d_issues(Case(provisions=[BENCHMARK]), codes_with_rules())[0]
    assert issue.human_review
    assert all(row.who and row.why and row.cite for row in issue.human_review)
    assert all(row.source == 'statute' or row.trigger_id in MANDATORY_TRIGGERS for row in issue.human_review)
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
    """Discretionary codedb-only triggers route to the officer and do not push yes."""
    codes = codes_with_rules()
    barrier = section_d_issues(Case(provisions=[BENCHMARK, '3.8.3.1.(1)']), codes)[0]
    assert 'HR-32' not in _ids(barrier)
    assert barrier.practice_of_engineering.value is not True
    assert barrier.routed_to == 'officer'

    interpretation = section_d_issues(
        Case(provisions=[BENCHMARK], facts=[fact('requests_interpretation', True)]), codes)[0]
    assert 'HR-31' not in _ids(interpretation)
    assert interpretation.practice_of_engineering.value is not True
    assert interpretation.routed_to == 'officer'

    within = section_d_issues(Case(provisions=[BENCHMARK], facts=[
        fact('dimension_required', 100.0), fact('dimension_proposed', 101.0)]), codes)[0]
    assert 'HR-33' not in _ids(within)
    assert within.practice_of_engineering.value is not True
    assert within.routed_to == 'officer'

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
        ('aquatic_facility', 'HR-13', 'C', '2.2.9.2.(1)'),
        ('geotechnical_part4', 'HR-14', 'B', '4.2.2.1.(1)'),
        ('part10_sprinklers', 'HR-12', 'B', '10.4.7.2.(1)'),
    )
    for field, trigger_id, division, provision_id in fields:
        issue = section_d_issues(Case(provisions=[BENCHMARK], facts=[fact(field, True)]), codes)[0]
        cite = codes.provision(provision_id, division)['citation']
        match = next(row for row in issue.human_review if row.trigger_id == trigger_id and row.cite == cite)
        assert match.who and match.why
        assert issue.practice_of_engineering.value is True
        assert issue.status == 'needs_professional'
    for field, trigger_id in (
        ('guards', 'HR-03'),
        ('medical_gas_piping', 'HR-42'),
        ('off_site_constructed', 'HR-43'),
        ('special_structure', 'HR-16'),
    ):
        issue = section_d_issues(Case(provisions=[BENCHMARK], facts=[fact(field, True)]), codes)[0]
        assert trigger_id not in _ids(issue)
        assert issue.practice_of_engineering.value is not True
    gas = section_d_issues(Case(provisions=[BENCHMARK], facts=[fact('medical_gas_piping', True)]), codes)[0]
    assert gas.routed_to == 'officer'


def _base(**extra):
    """A Part 9 house inside the general exception. None of the mandatory triggers are met."""
    values = dict(
        occupancy='single_family', storeys=2, building_area_m2=150.0,
        part4_design=False, preserved_wood_foundation_part4=False, roof_trusses=False,
        prescriptive_route_confirmed=True, ahj_requires_professional=False,
        special_safety_concerns=False, professional_judgement_required=False,
        professional_scope_resolved=True, fire_suppression=False, fire_alarm=False,
        geotechnical_part4=False, aquatic_facility=False, part10_sprinklers=False,
        part10_building=False, reinforced_concrete=False, framing_exceeds_9_23_1_1=False,
        supported_joist_span_m=4.9, specified_live_load_kPa=2.4,
        hourly_wind_pressure_1in50_kPa=1.1, Sa_0_2=1.8, post_disaster=False,
        minor_alteration_existing_system=False,
    )
    values.update(extra)
    return [fact(key, value) for key, value in values.items()]


def _screen(facts):
    codes = codes_with_rules()
    return codes, section_d_issues(Case(provisions=[BENCHMARK], facts=facts), codes)[0]


def test_mandatory_triggers_fire_in_routing_order_with_looked_up_cites():
    from engine.human_review import MANDATORY_ORDER
    codes, issue = _screen(_base(
        occupancy='multi_family', principal_dwelling_units=6, storeys=4,
        part4_design=True, supported_joist_span_m=5.0, reinforced_concrete=True,
        hourly_wind_pressure_1in50_kPa=1.2, fire_suppression=True,
        geotechnical_part4=True, aquatic_facility=True, part10_sprinklers=True,
    ))
    codedb = [row.trigger_id for row in issue.human_review if row.source == 'codedb']
    collapsed = []
    for trigger_id in codedb:
        if not collapsed or collapsed[-1] != trigger_id:
            collapsed.append(trigger_id)
    assert collapsed == list(MANDATORY_ORDER)
    assert all(row.cite in codes.issued for row in issue.human_review if row.source == 'codedb')
    assert issue.practice_of_engineering.value is True
    assert issue.status == 'needs_professional'


def test_each_mandatory_trigger_has_a_positive_and_a_negative_case():
    cases = (
        ('HR-03', 'C', '2.4.1.2.(1)', dict(part4_design=True), dict(part4_design=False)),
        ('HR-01', 'C', '2.4.1.1.(3)',
         dict(occupancy='multi_family', principal_dwelling_units=6),
         dict(occupancy='multi_family', principal_dwelling_units=4)),
        ('HR-06', 'B', '9.15.3.3.(2)', dict(supported_joist_span_m=5.0), dict(supported_joist_span_m=4.9)),
        ('HR-07', 'B', '9.3.1.1.(3)', dict(reinforced_concrete=True), dict(reinforced_concrete=False)),
        ('HR-05', 'B', '9.23.3.5.(4)',
         dict(hourly_wind_pressure_1in50_kPa=1.2), dict(hourly_wind_pressure_1in50_kPa=1.19)),
        ('HR-04', 'A', '1.3.3.2.(1)', dict(storeys=4), dict(storeys=2, building_area_m2=150.0)),
        ('HR-11', 'C', '2.4.1.3.(1)',
         dict(occupancy='multi_family', principal_dwelling_units=6, fire_suppression=True),
         dict(fire_suppression=True)),
        ('HR-14', 'B', '4.2.2.1.(1)', dict(geotechnical_part4=True), dict(geotechnical_part4=False)),
        ('HR-13', 'C', '2.2.9.2.(1)', dict(aquatic_facility=True), dict(aquatic_facility=False)),
        ('HR-12', 'B', '10.4.7.2.(1)',
         dict(part10_sprinklers=True), dict(part10_building=True, fire_suppression=False)),
    )
    for trigger_id, division, provision_id, positive, negative in cases:
        codes, yes_issue = _screen(_base(**positive))
        cite = codes.provision(provision_id, division)['citation']
        match = next(row for row in yes_issue.human_review if row.trigger_id == trigger_id and row.cite == cite)
        assert match.who and match.why and match.cite in codes.issued
        assert yes_issue.practice_of_engineering.value is True
        assert yes_issue.status == 'needs_professional'
        _neg_codes, no_issue = _screen(_base(**negative))
        assert trigger_id not in _ids(no_issue)
        assert no_issue.practice_of_engineering.value is not True
        assert no_issue.status != 'needs_professional'


def test_minor_alteration_does_not_fire_the_suppression_trigger():
    codes, issue = _screen(_base(
        occupancy='multi_family', principal_dwelling_units=6, fire_suppression=True,
        minor_alteration_existing_system=True,
    ))
    assert 'HR-11' not in _ids(issue)
    assert codes.provision('2.4.1.3.(1)', 'C')['citation'] not in [row.cite for row in issue.human_review]


def test_discretionary_trigger_on_a_cleared_screen_stays_no():
    from engine.models import Source
    officer = Source(type='officer', ref='ahj', quote='authority answer')
    facts = _base(medical_gas_piping=True, pathway='acceptable')
    for item in facts:
        item.source = officer
    issue = section_d_issues(Case(provisions=[BENCHMARK], facts=facts), codes_with_rules())[0]
    assert 'HR-42' not in _ids(issue)
    assert issue.practice_of_engineering.value is False
    assert issue.routed_to == 'officer'
