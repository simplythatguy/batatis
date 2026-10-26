import json

import pytest

from engine.intake import review
from evals_dev.codex_transport import CodexTransport, PendingCall, write_json


def test_pending_model_work_cannot_be_mistaken_for_failed_review(tmp_path):
    """An unattended task can resume; broad provider-error handling must not eat it."""
    transport = CodexTransport(tmp_path, 'development-case', 'review')
    with pytest.raises(PendingCall) as caught:
        review.run('Read the attached material.', [], outbound=lambda text, personal: text,
                   transport=transport, status='live')
    request = json.loads(caught.value.path.read_text())
    assert json.loads(request['user'])['request'] == 'Read the attached material.'
    assert 'evaluation' not in request
    assert request['model'] == 'gpt-6-luna'


def test_resume_uses_only_the_answer_bound_to_this_prompt(tmp_path):
    transport = CodexTransport(tmp_path, 'development-case', 'review')
    with pytest.raises(PendingCall) as caught:
        transport('source-reader', 'source pages', {'type': 'object'})
    path = caught.value.path
    request = json.loads(path.read_text())
    response = {k: request[k] for k in ('request_sha256', 'provider', 'model', 'options')}
    response.update(task_id='t3-task-123', payload={'facts': []})
    write_json(path.with_name('response.json'), response)
    assert transport('source-reader', 'source pages', {'type': 'object'}) == ({'facts': []}, {})
    with pytest.raises(PendingCall):
        transport('source-reader', 'different source', {'type': 'object'})


@pytest.mark.parametrize('field,value', [('request_sha256', 'another-request'),
                                       ('provider', 'openai'), ('model', 'another-model'),
                                       ('options', {'reasoningEffort': 'low'}), ('task_id', '')])
def test_mismatched_or_unattributed_answers_fail_closed(tmp_path, field, value):
    transport = CodexTransport(tmp_path, 'development-case', 'review')
    with pytest.raises(PendingCall) as caught:
        transport('instructions', 'pages', {})
    request = json.loads(caught.value.path.read_text())
    response = {k: request[k] for k in ('request_sha256', 'provider', 'model', 'options')}
    response.update(task_id='task-123', payload={'facts': []})
    response[field] = value
    write_json(caught.value.path.with_name('response.json'), response)
    with pytest.raises(ValueError, match='identity'):
        transport('instructions', 'pages', {})
