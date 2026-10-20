"""Dana's live Section D session: truthful alternative-case answers, and two evidence saves."""
import io
from types import SimpleNamespace

from fastapi.testclient import TestClient
from pypdf import PdfReader

from engine.api import create_app
from engine.completeness import professional_involvement_gaps
from engine.export.appendix import build_appendix
from engine.models import Case
from engine.professional import ProfessionalFacts, professional_involvement
from engine.store import CaseStore
from engine.tests.case_builder_fixtures import fact
from engine.tests.test_section_d_issues import codes_with_rules

# The 13 questions a single-family alternative case is asked. Farm use and principal
# dwelling units are not among them. Prescriptive route is no. Judgement is yes.
DANA_ANSWERS = {
    'occupancy': 'single_family',
    'storeys': 2,
    'building_area_m2': 210.0,
    'part4_design': False,
    'ahj_requires_professional': False,
    'special_safety_concerns': False,
    'roof_trusses': False,
    'preserved_wood_foundation_part4': False,
    'prescriptive_route_confirmed': False,
    'professional_judgement_required': True,
    'professional_scope_resolved': True,
    'fire_suppression': False,
    'fire_alarm': False,
}
ENGINEER = (
    fact('professional.role', 'R. Singh, P.Eng.'),
    fact('professional.registration_number', 'A123456'),
)
ENGINEER_EMAIL = 'Engineer email from R. Singh, P.Eng.'
SUPPLIER_NOTE = 'Window supplier note'


def _case(answers: dict, *, engineer: bool) -> Case:
    facts = [fact(field, value) for field, value in answers.items()]
    if engineer:
        facts.extend(ENGINEER)
    return Case(facts=facts)


def _gaps(case: Case):
    return professional_involvement_gaps(case, codes_with_rules(), [])


def _pdf_text(case: Case) -> str:
    pdf = build_appendix(case, SimpleNamespace(overflow=[], rows_in_form=0, docs_in_form=4),
                         {}, {'version': 'test'}, codes=None, open_items=[])
    text = ' '.join(page.extract_text() or '' for page in PdfReader(io.BytesIO(pdf)).pages)
    return ' '.join(text.split())


def test_dana_truthful_answers_resolve_to_professional_involved():
    assert len(DANA_ANSWERS) == 13
    assert DANA_ANSWERS['prescriptive_route_confirmed'] is False
    assert DANA_ANSWERS['professional_judgement_required'] is True
    case = _case(DANA_ANSWERS, engineer=True)
    result = professional_involvement(case, codes_with_rules())
    assert result.involvement == 'professional_involved'
    assert result.involvement != 'not_required'
    assert result.required != 'no'
    assert _gaps(case) == []


def test_false_prescriptive_answers_are_not_cleaner_than_the_truthful_ones():
    truthful = _case(DANA_ANSWERS, engineer=True)
    false_answers = dict(DANA_ANSWERS, prescriptive_route_confirmed=True, professional_judgement_required=False)
    false_case = _case(false_answers, engineer=True)
    truthful_result = professional_involvement(truthful, codes_with_rules())
    false_result = professional_involvement(false_case, codes_with_rules())
    truthful_gaps = [gap for gap in _gaps(truthful) if gap.severity == 'blocking']
    false_gaps = [gap for gap in _gaps(false_case) if gap.severity == 'blocking']
    assert truthful_result.involvement == 'professional_involved'
    assert false_result.involvement != 'not_required'
    assert false_result.involvement != 'professional_involved'
    assert false_result.required != 'no'
    assert len(false_gaps) > len(truthful_gaps)
    assert any(gap.field == 'professional_requirement' for gap in false_gaps)
    assert 'professional_judgement_required' in false_gaps[0].message
    assert 'prescriptive_route_confirmed' not in false_gaps[0].message


def test_open_professional_gap_names_the_missing_facts():
    unanswered = _case(DANA_ANSWERS, engineer=False)
    gaps = _gaps(unanswered)
    message = next(gap.message for gap in gaps if gap.field == 'professional_requirement')
    assert 'professional.role' in message
    assert 'professional.registration_number or professional.seal' in message
    assert 'facts needed to resolve professional involvement' not in message
    assert 'prescriptive_route_confirmed' not in message

    missing_part4 = dict(DANA_ANSWERS)
    del missing_part4['part4_design']
    part4_message = next(gap.message for gap in _gaps(_case(missing_part4, engineer=True))
                         if gap.field == 'professional_requirement')
    assert 'part4_design' in part4_message
    assert 'facts needed to resolve professional involvement' not in part4_message


def test_fact_screen_can_still_answer_not_required():
    facts = ProfessionalFacts(
        occupancy='single_family', part4_design=False, preserved_wood_foundation_part4=False,
        roof_trusses=False, prescriptive_route_confirmed=True, ahj_requires_professional=False,
        special_safety_concerns=False, professional_judgement_required=False, professional_scope_resolved=True,
        fire_suppression=False, fire_alarm=False)
    result = professional_involvement(facts, codes_with_rules())
    assert result.required == 'no' and result.involvement == 'not_required'


def test_two_evidence_saves_stay_in_the_api_and_the_pdf(tmp_path):
    client, store = _client(tmp_path)
    case_id = client.post('/cases', json={'title': 'Dana'}).json()['id']
    first = client.post(f'/cases/{case_id}/evidence', json={
        'description': ENGINEER_EMAIL, 'responsible_party': 'R. Singh, P.Eng.'})
    second = client.post(f'/cases/{case_id}/evidence', json={
        'description': SUPPLIER_NOTE, 'responsible_party': 'Example Fenestration Co.'})
    assert first.status_code == second.status_code == 201
    saved = client.get(f'/cases/{case_id}').json()['evidence']
    assert [item['description'] for item in saved] == [ENGINEER_EMAIL, SUPPLIER_NOTE]
    assert saved[0]['id'] == first.json()['id']
    assert saved[1]['id'] == second.json()['id']
    assert saved[0]['id'] != saved[1]['id']
    text = _pdf_text(store.get(case_id))
    assert ENGINEER_EMAIL in text and SUPPLIER_NOTE in text


def test_delete_evidence_removes_only_that_item(tmp_path):
    client, store = _client(tmp_path)
    case_id = client.post('/cases', json={'title': 'Dana'}).json()['id']
    first = client.post(f'/cases/{case_id}/evidence', json={'description': ENGINEER_EMAIL}).json()
    second = client.post(f'/cases/{case_id}/evidence', json={'description': SUPPLIER_NOTE}).json()
    assert client.delete(f'/cases/{case_id}/evidence/{first["id"]}').status_code == 204
    assert client.delete(f'/cases/{case_id}/evidence/{first["id"]}').status_code == 404
    saved = client.get(f'/cases/{case_id}').json()['evidence']
    assert [item['id'] for item in saved] == [second['id']]
    assert saved[0]['description'] == SUPPLIER_NOTE
    text = _pdf_text(store.get(case_id))
    assert SUPPLIER_NOTE in text and ENGINEER_EMAIL not in text


def _client(tmp_path):
    store = CaseStore(tmp_path / 'cases.sqlite')
    return TestClient(create_app(store, codes=object())), store
