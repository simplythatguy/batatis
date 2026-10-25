import pytest

from evals_dev.data_prompts.render import report


@pytest.mark.parametrize('status', ['live', 'fake'])
def test_judged_review_keeps_actual_evidence_without_inventing_a_reading_guarantee(status):
    result = {'case': {'intake': {
        'files': [{'file_id': 'scan', 'name': 'UNIT-FIXTURE.pdf', 'status': 'not_read',
                   'pages': 2, 'pages_read': [], 'pages_not_read': [1, 2], 'reason': 'No text layer'}],
        'review': {'status': status, 'flags': [{'kind': 'not_read', 'text': 'UNIT-FIXTURE.pdf was not read.'}],
                   'facts': [{'status': 'stated', 'text': 'The request describes a proposed assembly.',
                              'evidence': [{'source_ref': 'description', 'page': None,
                                            'quote': 'UNIT FIXTURE: a proposed assembly.'}]}]},
    }}}
    text = report(result)
    assert 'UNIT-FIXTURE.pdf was not read.' in text
    assert 'UNIT FIXTURE: a proposed assembly.' in text
    assert 'request text' in text
    assert 'read every readable page' not in text
    assert 'each fact quotes the page it comes from' not in text
