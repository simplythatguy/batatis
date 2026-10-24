"""Saved applicant uncertainty and officer requests survive the actual review route."""
import pytest

from engine.account_models import Decision, DecisionItem
from engine.intake.plan import build_plan
from engine.models import Source
from engine.models_identify import OpenQuestion
from engine.models_intake import IntakeRecord
from engine.tests.case_builder_fixtures import fact
from engine.tests.test_intake_plan import _identify
from engine.tests.test_review import owned, scene  # noqa: F401 - isolated authenticated adapters


def questions(clients, case_id):
    response = clients['reviewer'].get(f'/cases/{case_id}/identify/information-request')
    assert response.status_code == 200, response.text
    return response.json()


def test_saved_uncertainty_has_context_current_answers_and_a_read_only_revision(scene):
    store, clients, _ = scene
    case = owned(scene, status='submitted')
    case.facts = [
        fact('codecheck.desc-storeys', 'not_sure', source=Source(
            type='user_click', ref='Applicant code check', quote='How many storeys is the building?')),
        fact('building.storeys', 3),
        fact('municipalAddress', 'SYNTHETIC saved project address'),
    ]
    plan = build_plan(case)
    plan.not_sure = ['intake.occupancy', 'intake.storeys']
    case.intake = IntakeRecord(plan=plan)
    _identify(case, ['9.27.2.1.'], {'9.27.2.1.': 'not_sure'})
    case.identify.open_questions = [OpenQuestion(id='saved-location', field='municipal_address',
        text='Which project address is being reviewed?', why='Identify the location under review.')]
    case = store.put(case, expected_version=case.version)
    before = case.model_dump()

    data = questions(clients, case.id)
    by_id = {question['id']: question for question in data['questions']}
    assert data['case_version'] == case.version and data['case_id'] == case.id
    assert len(data['items']) == 1 and data['items'][0]['provision_id'] == '9.27.2.1.'
    assert by_id['codecheck.desc-storeys']['text'] == 'How many storeys is the building?'
    assert by_id['codecheck.desc-storeys']['state'] == 'not_sure'
    assert by_id['intake.storeys']['answer'] == '3' and by_id['intake.storeys']['state'] == 'answered'
    assert by_id['intake.occupancy']['state'] == 'not_sure' and by_id['intake.occupancy']['text']
    assert by_id['saved-location']['answer'] == 'SYNTHETIC saved project address'
    for actor in ('other', 'foreign', 'anonymous'):
        assert clients[actor].get(f'/cases/{case.id}/identify/information-request').status_code == 404
    assert store.get(case.id).model_dump() == before


def test_dropped_candidate_keeps_officer_question_and_applicant_clarification_separate(scene):
    store, clients, users = scene
    case = owned(scene, status='returned')
    case.decision_history = [Decision(outcome='return', by_id=users['reviewer']['id'], by_name='Reviewer',
        message='SYNTHETIC request for context.', items=[DecisionItem(
            field='clarification.old-question', note='Which opening does the proposed change cover?')])]
    case.facts = [fact('clarification.old-question', 'SYNTHETIC bedroom opening W-07')]
    case = store.put(case, expected_version=case.version)
    before = case.model_dump()
    data = questions(clients, case.id)
    question = next(item for item in data['questions'] if item['id'] == 'old-question')
    assert question['text'] == 'Which opening does the proposed change cover?'
    assert question['origin'] == 'officer_request' and question['state'] == 'unanswered'
    assert question['clarification']['state'] == 'answered'
    assert question['clarification']['answer'] == 'SYNTHETIC bedroom opening W-07'
    assert data['items'] == []
    assert store.get(case.id).model_dump() == before


def test_latest_withdrawn_alias_does_not_revive_an_earlier_officer_answer(scene):
    store, clients, _ = scene
    case = owned(scene, status='returned')
    plan = build_plan(case)
    plan.not_sure = ['intake.storeys']
    case.intake = IntakeRecord(plan=plan)
    case.facts = [fact('storeys', 3), fact('building.storeys', '', source=Source(
        type='user_click', ref='Answer withdrawn by applicant'))]
    case = store.put(case, expected_version=case.version)
    question = next(item for item in questions(clients, case.id)['questions'] if item['id'] == 'intake.storeys')
    assert question['answer'] is None and question['state'] == 'withdrawn'


@pytest.mark.parametrize('old,new', [('storeys', 'building.storeys'), ('building.storeys', 'storeys')])
def test_returned_journey_planner_uses_the_same_saved_storey_aliases(scene, old, new):
    store, clients, _ = scene
    case = owned(scene, status='returned')
    case.facts = [fact('project.description', 'SYNTHETIC proposed alternative staircase in a building.'),
                  fact(old, 3), fact(new, 4)]
    case = store.put(case, expected_version=case.version)
    response = clients['owner'].post(f'/cases/{case.id}/intake/plan', json={})
    assert response.status_code == 200, response.text
    assert 'storeys' not in {question['field'] for question in response.json()['record']['plan']['questions']}
    case = store.get(case.id)
    case.facts.append(fact(new, '', source=Source(type='user_click', ref='Answer withdrawn by applicant')))
    store.put(case, expected_version=case.version)
    response = clients['owner'].post(f'/cases/{case.id}/intake/plan', json={})
    assert response.status_code == 200, response.text
    assert 'storeys' in {question['field'] for question in response.json()['record']['plan']['questions']}
