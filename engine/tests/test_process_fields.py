import pytest
from pydantic import ValidationError

from engine.codes import Codes
from engine.models import Case, Fact, Source
from engine.process_fields import ApplicantText, ProcessField, process_fields


def answer_fact(field='risk_assessment', **changes):
    data = dict(field=field, value='Applicant-written passage.', kind='pointed', status='confirmed',
                source=Source(type='user_text', ref='message-1', quote='Applicant-written passage.'))
    data.update(changes)
    return Fact(**data)


def test_prompts_are_blank_and_separate_from_evidence():
    fields = process_fields(Case(), Codes())
    assert len(fields) == 8 and all(f.answer is None and f.required for f in fields)
    by_id = {field.id: field for field in fields}
    cited = [field for field in fields if field.citation]
    assert all(field.citation.startswith('NBC(AE) 2023 p2, Div C') for field in cited)
    assert {field.id for field in fields if field.citation is None} == {'risk_assessment', 'mitigating_measures'}
    codes = Codes()
    assert by_id['rationale'].citation == codes.citation('2.3.1.1.(2)(a)', 'C')
    assert by_id['assumptions_and_limits'].citation == codes.citation('2.3.1.1.(3)', 'C')
    assert by_id['maintenance_operation'].citation == codes.citation('2.3.1.1.(2)(b)', 'C')
    assert by_id['analysis_detail'].citation == codes.citation('2.3.1.1.(5)', 'C')
    assert by_id['qualifications'].citation == codes.citation('2.3.1.1.(4)', 'C')
    assert by_id['design_coordinator'].citation == codes.citation('2.3.1.1.(6)', 'C')
    assert '2.3.1.1.(3)' not in (by_id['risk_assessment'].prompt + by_id['mitigating_measures'].prompt)


def test_applicant_passage_roundtrips_but_ai_cannot_fill_field():
    fact = answer_fact()
    text = ApplicantText.from_fact(fact)
    assert ApplicantText.model_validate_json(text.model_dump_json()) == text
    for changes in ({'author': 'ai'}, {'kind': 'proposed'}, {'value': 'Generated assessment.'},
                    {'source': {'type': 'code', 'ref': '2.3.1.1.', 'quote': text.value}}):
        with pytest.raises(ValidationError):
            ApplicantText.model_validate({**text.model_dump(), **changes})
    with pytest.raises(ValidationError):
        text.value = 'AI-written replacement'
    with pytest.raises(ValidationError):
        text.source.quote = 'AI-written replacement'
    with pytest.raises(ValidationError):
        ProcessField.model_validate({**process_fields(Case(), Codes())[0].model_dump(), 'answer': 'AI text'})


@pytest.mark.parametrize('fact', [answer_fact(kind='proposed', status='unconfirmed'),
                                 answer_fact(status='unconfirmed'), answer_fact(kind='computed'),
                                 answer_fact(source=Source(type='file', ref='report.pdf', quote='Different text.'))])
def test_non_applicant_values_never_become_process_answers(fact):
    fields = process_fields(Case(facts=[fact]), Codes())
    assert next(f for f in fields if f.id == 'risk_assessment').answer is None


def test_confirmed_answer_and_newer_unconfirmed_revision():
    fact = answer_fact(field='process.risk_assessment')
    case = Case(facts=[fact])
    assert next(f for f in process_fields(case, Codes()) if f.id == 'risk_assessment').answer.value == fact.value
    case.facts.append(answer_fact(status='unconfirmed'))
    assert all(f.answer is None for f in process_fields(case, Codes()))


def test_acceptable_path_does_not_request_variance_process_fields():
    case = Case(facts=[answer_fact(field='pathway', value='acceptable')])
    assert process_fields(case, Codes()) == []
