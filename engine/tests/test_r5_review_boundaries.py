"""Bounded R5 review assertions. All input is synthetic and all real sockets are denied."""
import pytest

from engine.intake import review
from evals_dev.data_prompts import checks


def reviewed(payload, text='An attachment records a wall dimension.'):
    return review.run('Review the attached record.', [('file1', 'source.txt', text.encode())],
                      outbound=lambda s, _: s, transport=lambda *args: (payload, {}), status='live')


def conflict(text, quotes):
    return reviewed({'conflicts': [{'text': 'The wall dimensions disagree.',
                                   'evidence': [{'file': 'file1', 'page': None, 'quote': q}
                                                for q in quotes]}]}, text)


@pytest.mark.parametrize('dash', ['-', '\u2013'])
def test_distinct_labelled_rows_with_spaced_trailing_dash_remain_independent(dash):
    out = conflict(f'Wall length: 25 metres {dash}\nWall length: 30 metres',
                   ['Wall length: 25 metres', 'Wall length: 30 metres'])
    assert len(out.conflicts) == 1


@pytest.mark.parametrize('dash', ['\ufe63', '\uff0d'])
def test_compatibility_hyphen_word_wrap_does_not_create_independent_assertions(dash):
    text = f'Wall length: exactly 25 metres and con{dash}\nfiguration: north face.'
    out = conflict(text, ['Wall length: exactly 25 metres', 'north face'])
    assert out.conflicts == []


@pytest.mark.parametrize('colon', ['\uff1a', '\ufe55'])
def test_compatibility_colon_labelled_rows_remain_independent(colon):
    out = conflict(f'Wall length{colon} 25 metres\nWall length{colon} 30 metres',
                   ['Wall length: 25 metres', 'Wall length: 30 metres'])
    assert len(out.conflicts) == 1


QUESTIONS = [
    'Does the design comply with the code and satisfy the requirements?',
    'Does the design meet the requirements and comply with the code?',
    'Will the design be safe and comply with the code?',
]


@pytest.mark.parametrize('question', QUESTIONS)
def test_shared_subject_compound_question_is_kept_by_public_review(question):
    out = reviewed({'questions': [{'text': question, 'why': ''}]})
    assert [x.text for x in out.questions] == [question]


@pytest.mark.parametrize('question', QUESTIONS)
def test_shared_subject_compound_question_is_not_a_harness_claim(question):
    assert checks.claims([question]) == []
