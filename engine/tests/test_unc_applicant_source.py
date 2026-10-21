"""Applicant Yes/No answers cannot clear the professional gap. Unc's homebuilder case."""
from fastapi.testclient import TestClient

from engine.api import create_app
from engine.completeness import professional_involvement_gaps
from engine.export.scc import ExportBlocked, ExportError, export_case
from engine.models import Case, Source
from engine.professional import NOT_SURE_OPTION, OFFICER_PROFESSIONAL_GAP, professional_involvement
from engine.section_d_issues import section_d_issues
from engine.store import CaseStore
from engine.tests.case_builder_fixtures import fact
from engine.tests.test_section_d_issues import BENCHMARK, codes_with_rules

# Homebuilder. Prescriptive is Yes. Judgement is No. Every other Section D answer is No.
UNC_ANSWERS = {
    'occupancy': 'single_family',
    'part4_design': False,
    'preserved_wood_foundation_part4': False,
    'roof_trusses': False,
    'prescriptive_route_confirmed': True,
    'professional_judgement_required': False,
    'ahj_requires_professional': False,
    'special_safety_concerns': False,
    'professional_scope_resolved': False,
    'fire_suppression': False,
    'fire_alarm': False,
}
# The combination that used to return no: scope answered Yes, everything else as above.
CLEARING_ANSWERS = dict(UNC_ANSWERS, professional_scope_resolved=True)


def _case(answers: dict, *, source_type: str = 'user_text', pathway: str | None = None) -> Case:
    source = Source(type=source_type, ref='applicant-session', quote='applicant answer')
    facts = [fact(field, value, source=source) for field, value in answers.items()]
    if pathway is not None:
        facts.append(fact('pathway', pathway, source=source))
    return Case(provisions=[BENCHMARK], facts=facts)


def _officer_gap(case: Case):
    return next(gap for gap in professional_involvement_gaps(case, codes_with_rules(), [])
                if gap.field == 'professional_requirement')


def test_unc_homebuilder_applicant_answers_stay_unknown():
    """Do not pre-set the practice flag. The screen has to derive it."""
    codes = codes_with_rules()
    case = _case(UNC_ANSWERS)
    issue = section_d_issues(case, codes)[0]
    assert issue.practice_of_engineering.value == 'unknown'
    assert issue.practice_of_engineering.value != 'no'
    assert issue.practice_of_engineering.value is not False
    assert issue.status == 'open' and issue.routed_to == 'officer'
    assert issue.practice_of_engineering.prompts
    assert all(prompt.not_sure == NOT_SURE_OPTION and prompt.help for prompt in issue.practice_of_engineering.prompts)
    gap = _officer_gap(case)
    assert gap.message == OFFICER_PROFESSIONAL_GAP
    assert gap.severity == 'blocking' and gap.routed_to == 'officer'
    # The old clearing combination, still entirely from the applicant, also stays unknown.
    clearing = _case(CLEARING_ANSWERS)
    assert section_d_issues(clearing, codes)[0].practice_of_engineering.value == 'unknown'
    assert professional_involvement(clearing, codes).required != 'no'
    reasons = official_export_reasons(case, codes)
    assert any(OFFICER_PROFESSIONAL_GAP in reason for reason in reasons)
    draft_is_allowed(case, codes)


def test_officer_sourced_screen_can_return_no():
    codes = codes_with_rules()
    case = _case(CLEARING_ANSWERS, source_type='officer', pathway='acceptable')
    result = professional_involvement(case, codes)
    assert result.required == 'no' and result.applicant_sourced is False
    issue = section_d_issues(case, codes)[0]
    assert issue.practice_of_engineering.value is False


def test_posted_confirmed_user_answers_cannot_return_no(tmp_path):
    """BAT-65: status confirmed on a user source is still applicant-sourced. There is no PATCH route."""
    codes = codes_with_rules()
    client = TestClient(create_app(CaseStore(tmp_path / 'cases.sqlite'), codes))
    case_id = client.post('/cases', json={'title': 'Unc homebuilder'}).json()['id']
    for field, value in UNC_ANSWERS.items():
        body = fact(field, value).model_dump()
        assert body['status'] == 'confirmed' and body['source']['type'] == 'user_text'
        assert client.post(f'/cases/{case_id}/facts', json=body).status_code == 200
    assert client.patch(f'/cases/{case_id}/facts', json={'status': 'confirmed'}).status_code == 405
    issue = client.get(f'/cases/{case_id}/section-d/issues').json()['items'][0]
    assert issue['practice_of_engineering']['value'] == 'unknown'
    assert issue['routed_to'] == 'officer'
    gaps = client.get(f'/cases/{case_id}/gaps').json()['items']
    assert any(gap['message'] == OFFICER_PROFESSIONAL_GAP and gap['routed_to'] == 'officer' for gap in gaps)


def _engagement_stays_unknown(value: str):
    """A cleared screen must not become no when engagement is not_sure or not_engaged_yet."""
    codes = codes_with_rules()
    officer = Source(type='officer', ref='ahj', quote='authority answer')
    for field in ('engineer_engaged', 'architect_engaged', 'registered_professional'):
        for source in (officer, Source(type='user_text', ref='applicant', quote=value)):
            facts = [fact(name, answer, source=officer) for name, answer in CLEARING_ANSWERS.items()]
            facts.append(fact('pathway', 'acceptable', source=officer))
            facts.append(fact(field, value, source=source))
            case = Case(provisions=[BENCHMARK], facts=facts)
            result = professional_involvement(case, codes)
            assert result.required != 'no', field
            issue = section_d_issues(case, codes)[0]
            assert issue.practice_of_engineering.value == 'unknown', field
            assert issue.practice_of_engineering.value is not False, field
            assert issue.routed_to == 'officer', field
            gap = _officer_gap(case)
            assert gap.message == OFFICER_PROFESSIONAL_GAP
            assert gap.severity == 'blocking' and gap.routed_to == 'officer'
        only = Case(provisions=[BENCHMARK], facts=[fact(field, value)])
        assert section_d_issues(only, codes)[0].practice_of_engineering.value == 'unknown'
        assert _officer_gap(only).message == OFFICER_PROFESSIONAL_GAP


def test_not_sure_on_professional_engagement_stays_unknown():
    _engagement_stays_unknown('not_sure')


def test_not_engaged_yet_on_professional_engagement_stays_unknown():
    _engagement_stays_unknown('not_engaged_yet')


def test_acceptable_path_applicant_answers_do_not_clear_special_safety_or_professional_law(tmp_path):
    """Applicant answers stay unknown on an acceptable solution, not only on an alternative."""
    codes = codes_with_rules()
    officer = Source(type='officer', ref='ahj', quote='authority answer')
    applicant = Source(type='user_text', ref='applicant', quote='applicant answer')
    reserved = {'special_safety_concerns', 'professional_scope_resolved'}
    for pathway in ('acceptable', 'acceptable_solution'):
        facts = [fact(name, value, source=applicant if name in reserved else officer)
                 for name, value in CLEARING_ANSWERS.items()]
        facts.append(fact('pathway', pathway, source=officer))
        case = Case(provisions=[BENCHMARK], facts=facts)
        result = professional_involvement(case, codes)
        assert result.required == 'depends', pathway
        assert result.required != 'no', pathway
        by_code = {reason.code: reason.required for reason in result.reasons}
        assert by_code['special_safety'] == 'depends', pathway
        assert by_code['professional_law'] == 'depends', pathway
        issue = section_d_issues(case, codes)[0]
        assert issue.practice_of_engineering.value == 'unknown', pathway
        assert issue.practice_of_engineering.value is not False, pathway
        assert issue.routed_to == 'officer', pathway
        gap = _officer_gap(case)
        assert gap.message == OFFICER_PROFESSIONAL_GAP
        assert gap.severity == 'blocking' and gap.routed_to == 'officer'
        reasons = official_export_reasons(case, codes)
        assert any(OFFICER_PROFESSIONAL_GAP in reason for reason in reasons)
        draft_is_allowed(case, codes)

    store = CaseStore(tmp_path / 'cases.sqlite')
    saved = store.put(case)
    client = TestClient(create_app(store, codes))
    professional = client.get(f'/cases/{saved.id}/professional').json()
    assert professional['required'] == 'depends'
    assert professional['required'] != 'no'
    issued = client.get(f'/cases/{saved.id}/section-d/issues').json()['items'][0]
    assert issued['practice_of_engineering']['value'] == 'unknown'
    assert issued['routed_to'] == 'officer'
    gaps = client.get(f'/cases/{saved.id}/gaps').json()['items']
    assert any(row['message'] == OFFICER_PROFESSIONAL_GAP and row['routed_to'] == 'officer' for row in gaps)


def test_not_sure_is_an_officer_routed_open_item():
    codes = codes_with_rules()
    officer = Source(type='officer', ref='ahj', quote='authority answer')
    facts = [fact(field, value, source=officer) for field, value in CLEARING_ANSWERS.items()]
    facts.append(fact('pathway', 'acceptable', source=officer))
    facts.append(fact('part4_design', NOT_SURE_OPTION, source=Source(
        type='user_text', ref='applicant', quote=NOT_SURE_OPTION)))
    case = Case(provisions=[BENCHMARK], facts=facts)
    issue = section_d_issues(case, codes)[0]
    assert issue.practice_of_engineering.value == 'unknown'
    assert issue.status == 'open' and issue.routed_to == 'officer'
    assert issue.practice_of_engineering.question
    assert any(prompt.not_sure == NOT_SURE_OPTION and 'Yes' in prompt.help and 'No' in prompt.help
               for prompt in issue.practice_of_engineering.prompts)
    assert _officer_gap(case).message == OFFICER_PROFESSIONAL_GAP


def official_export_reasons(case, codes):
    try:
        export_case(case, draft=False, codes=codes)
    except ExportBlocked as blocked:
        return blocked.reasons
    raise AssertionError('official export was allowed')


def draft_is_allowed(case, codes):
    try:
        export_case(case, draft=True, codes=codes)
    except ExportBlocked as blocked:
        raise AssertionError('draft export must stay allowed') from blocked
    except ExportError:
        return
