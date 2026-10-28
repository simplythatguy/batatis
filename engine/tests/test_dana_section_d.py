"""Dana's live Section D session: truthful alternative-case answers, and two evidence saves."""
import io
from types import SimpleNamespace

from fastapi.testclient import TestClient
from pypdf import PdfReader

from engine.api import create_app
from engine.completeness import professional_involvement_gaps
from engine.export.appendix import build_appendix
from engine.models import Case, EvidenceItem, Source
from engine.professional import OFFICER_PROFESSIONAL_GAP, ProfessionalFacts, professional_involvement
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
    facts = [fact('pathway', 'alternative')]
    facts += [fact(field, value) for field, value in answers.items()]
    if engineer:
        facts.extend(ENGINEER)
    return Case(facts=facts)


def _gaps(case: Case):
    return professional_involvement_gaps(case, codes_with_rules(), [])


def _pdf_text(case: Case) -> str:
    pdf = build_appendix(case, SimpleNamespace(overflow=[], rows_in_form=0, docs_in_form=4),
                         {}, {'version': 'test'}, codes=None)
    if pdf is None:                         # nothing real to print: no appendix
        return ''
    text = ' '.join(page.extract_text() or '' for page in PdfReader(io.BytesIO(pdf)).pages)
    return ' '.join(text.split())


def test_dana_truthful_answers_do_not_clear_the_professional_gap():
    assert len(DANA_ANSWERS) == 13
    assert DANA_ANSWERS['prescriptive_route_confirmed'] is False
    assert DANA_ANSWERS['professional_judgement_required'] is True
    case = _case(DANA_ANSWERS, engineer=True)
    result = professional_involvement(case, codes_with_rules())
    assert result.involvement != 'professional_involved'
    assert result.involvement != 'not_required'
    assert result.required != 'no'
    assert result.applicant_sourced
    gaps = [gap for gap in _gaps(case) if gap.severity == 'blocking']
    assert gaps and all(gap.message == OFFICER_PROFESSIONAL_GAP and gap.routed_to == 'officer' for gap in gaps)


def test_false_prescriptive_answers_are_not_cleaner_than_the_truthful_ones():
    truthful = _case(DANA_ANSWERS, engineer=True)
    false_answers = dict(DANA_ANSWERS, prescriptive_route_confirmed=True, professional_judgement_required=False)
    false_case = _case(false_answers, engineer=True)
    truthful_result = professional_involvement(truthful, codes_with_rules())
    false_result = professional_involvement(false_case, codes_with_rules())
    truthful_gaps = [gap for gap in _gaps(truthful) if gap.severity == 'blocking']
    false_gaps = [gap for gap in _gaps(false_case) if gap.severity == 'blocking']
    assert truthful_result.required != 'no' and false_result.required != 'no'
    assert truthful_result.involvement != 'professional_involved'
    assert false_result.involvement != 'not_required'
    assert false_result.involvement != 'professional_involved'
    assert truthful_gaps and false_gaps
    assert all(gap.message == OFFICER_PROFESSIONAL_GAP for gap in truthful_gaps + false_gaps)
    assert false_result.prescriptive_contradiction
    assert truthful_result.prescriptive_contradiction is None
    assert 'prescriptive_route_confirmed' not in false_gaps[0].message


def test_applicant_answers_route_the_professional_gap_to_the_officer():
    unanswered = _case(DANA_ANSWERS, engineer=False)
    gaps = _gaps(unanswered)
    message = next(gap.message for gap in gaps if gap.field == 'professional_requirement')
    assert message == OFFICER_PROFESSIONAL_GAP
    assert next(gap.routed_to for gap in gaps if gap.field == 'professional_requirement') == 'officer'

    missing_part4 = dict(DANA_ANSWERS)
    del missing_part4['part4_design']
    part4_message = next(gap.message for gap in _gaps(_case(missing_part4, engineer=True))
                         if gap.field == 'professional_requirement')
    assert part4_message == OFFICER_PROFESSIONAL_GAP


def test_fact_screen_can_still_answer_not_required():
    facts = ProfessionalFacts(
        occupancy='single_family', part4_design=False, preserved_wood_foundation_part4=False,
        roof_trusses=False, prescriptive_route_confirmed=True, ahj_requires_professional=False,
        special_safety_concerns=False, professional_judgement_required=False, professional_scope_resolved=True,
        fire_suppression=False, fire_alarm=False)
    result = professional_involvement(facts, codes_with_rules())
    assert result.required == 'no' and result.involvement == 'not_required'


TEXT_LABEL = 'listed by applicant, no file attached, not reviewed'


def _text_listing(description: str, *, status: str = 'evidence_listed') -> tuple[EvidenceItem, list]:
    """A typed listing. Facts are applicant text. There is no file_ref."""
    item = EvidenceItem.model_validate({'id': f'ev_{description[:8]}', 'description': description, 'status': status})
    prefix = f'evidence.{item.id}.'
    facts = [
        fact(prefix + 'title', description),
        fact(prefix + 'responsible_party', 'R. Singh, P.Eng.'),
        fact(prefix + 'date', '2026-10-20'),
    ]
    return item, facts


def test_text_evidence_has_no_file_ref_and_the_pdf_lists_it():
    first, first_facts = _text_listing(ENGINEER_EMAIL, status='provided')
    second, second_facts = _text_listing(SUPPLIER_NOTE)
    assert first.status == second.status == 'evidence_listed'
    assert first.kind == second.kind == 'text'
    case = Case(evidence=[first, second], facts=first_facts + second_facts)
    assert all(item.kind == 'text' for item in case.evidence)
    assert all('file_ref' not in entry.field for entry in case.facts)
    text = _pdf_text(case)
    assert ENGINEER_EMAIL in text and SUPPLIER_NOTE in text
    assert TEXT_LABEL in text


def test_typed_evidence_cannot_create_a_file_and_withdrawal_is_idempotent(tmp_path):
    client, store = _client(tmp_path)
    case_id = client.post('/cases', json={'title': 'Dana'}).json()['id']
    # The text listing route exists now; a body without its required fields is refused unwritten.
    posted = client.post(f'/cases/{case_id}/evidence', json={'description': ENGINEER_EMAIL})
    assert posted.status_code == 422
    version = client.get(f'/cases/{case_id}').json()['version']
    absent = client.request('DELETE', f'/cases/{case_id}/evidence/ev_missing', json={'expected_version': version})
    assert absent.status_code == 404 and absent.json()['detail'] == 'evidence not found'
    assert client.get(f'/cases/{case_id}').json()['version'] == version  # no write for an absent slot
    assert client.request('DELETE', '/cases/missing/evidence/ev_missing', json={'expected_version': 1}).status_code == 404
    saved = store.get(case_id)
    assert saved.evidence == []
    assert all('file_ref' not in entry.field for entry in saved.facts)


def test_a_file_document_is_not_labelled_as_an_unattached_listing():
    item = EvidenceItem(id='ev_file', description='Sealed report', kind='text')
    file = Source(type='file', ref='report.pdf', quote='report.pdf')
    case = Case(evidence=[item], facts=[
        fact('evidence.ev_file.file_ref', 'report.pdf', source=file),
        fact('evidence.ev_file.title', 'Sealed report'),
    ])
    assert case.evidence[0].kind == 'file'
    text = _pdf_text(case)
    assert 'Sealed report' in text
    assert TEXT_LABEL not in text


def _client(tmp_path):
    store = CaseStore(tmp_path / 'cases.sqlite')
    return TestClient(create_app(store, codes=object())), store
