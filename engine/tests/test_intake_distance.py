from engine.intake import service
from engine.intake.questions import plan_questions
from engine.models import Case


def test_distance_and_public_way_are_two_questions_filling_the_existing_rule_inputs():
    known = {'alternative_description', 'storeys', 'building_area_m2', 'occupancy', 'sprinklered',
             'dwelling_units', 'part4_design', 'assembly.description'}
    questions = plan_questions(known=known, prose='The soffit is near the property line beside a lane.',
                              candidates=[{'provision': '9.10.15.5.(8)'}], conflicts=[], not_sure=set(),
                              role=None, departure_known=True)
    by_field = {question.field: question for question in questions}
    assert by_field['limiting_distance_m'].text == 'How far is that wall from the property line?'
    assert by_field['faces_public_way'].text == 'What is on the other side of that wall?'
    case = Case()
    service.apply(case, 'The soffit is beside the property line and lane.',
                  service.run('The soffit is beside the property line and lane.', []))
    case.intake.plan.questions = questions
    created = service.answer(case, [
        {'question_id': by_field['limiting_distance_m'].id, 'answer': '1.2192'},
        {'question_id': by_field['faces_public_way'].id, 'answer': 'yes'},
    ])
    assert [(fact.field, fact.value) for fact in created] == [('limiting_distance_m', 1.2192), ('faces_public_way', True)]
    assert not {'limiting_distance_m', 'faces_public_way'} & {question.field for question in case.intake.plan.questions}


def test_a_saved_public_way_input_is_not_a_new_planner_question():
    questions = plan_questions(known={'faces_public_way'}, prose='A soffit beside a lane.',
                              candidates=[{'provision': '9.10.15.5.(8)'}], conflicts=[], not_sure=set(),
                              role=None, departure_known=True)
    assert all(question.field != 'faces_public_way' for question in questions)
