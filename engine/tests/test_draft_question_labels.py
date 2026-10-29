"""An open question from accepted draft wording reads as a question, never as its internal key."""
from engine.completeness import Gap
from engine.completeness_policy import _gap_element


def test_a_draft_question_gap_is_labelled_in_words_not_by_its_draft_id():
    gap = Gap(id='draft-q', section='B', field='drafting.questions.draft_12068ca83011.0', severity='warning',
              message='Which specific assembly is proposed?', routed_to='applicant', fix_hint='Answer it.')
    element = _gap_element(gap)
    assert element.label == 'Open question from the drafted wording'
    assert 'draft_' not in element.label and element.reason == 'Which specific assembly is proposed?'
