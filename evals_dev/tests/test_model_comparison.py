import json
from pathlib import Path

import pytest

from evals_dev import luna_accuracy, model_comparison
from evals_dev.codex_transport import PendingCall, write_json
from evals_dev.task_transport import LUNA_JUDGE, TaskTransport, haiku


@pytest.mark.parametrize('effort', ['low', 'medium'])
def test_only_candidate_transport_changes_and_judge_stays_luna(effort):
    original = luna_accuracy.CodexTransport
    core = model_comparison.workflow(effort)
    assert core.run_case.__code__.co_code == luna_accuracy.run_case.__code__.co_code
    assert core.grade.__code__.co_code == luna_accuracy.grade.__code__.co_code
    assert core.CodexTransport(Path('/tmp'), 'UNIT', 'review').target == haiku(effort)
    assert core.CodexTransport(Path('/tmp'), 'UNIT', 'judge').target == LUNA_JUDGE
    assert luna_accuracy.CodexTransport is original


def test_low_and_medium_have_distinct_request_identities(tmp_path):
    identities = []
    for effort in ('low', 'medium'):
        transport = TaskTransport(tmp_path, 'UNIT', 'intake', haiku(effort))
        with pytest.raises(PendingCall) as waiting:
            transport('system', 'user', {'type': 'object'})
        request = json.loads(waiting.value.path.read_text())
        assert request['provider'] == 'claudeAgent'
        assert request['model'] == 'claude-haiku-5-5'
        assert request['options'] == {'effort': effort}
        identities.append(request['request_sha256'])
    assert identities[0] != identities[1]


def test_response_cannot_substitute_a_model_or_effort(tmp_path):
    transport = TaskTransport(tmp_path, 'UNIT', 'review', haiku('low'))
    with pytest.raises(PendingCall) as waiting:
        transport('system', 'user', {'type': 'object'})
    request = json.loads(waiting.value.path.read_text())
    response = {k: request[k] for k in ('request_sha256', 'provider', 'model', 'options')}
    response.update({'task_id': 'unit-task', 'payload': {}})
    path = waiting.value.path.with_name('response.json')
    write_json(path, {**response, 'options': {'effort': 'medium'}})
    with pytest.raises(ValueError, match='identity'):
        transport('system', 'user', {'type': 'object'})
    write_json(path, response)
    assert transport('system', 'user', {'type': 'object'}) == ({}, {})


def test_same_judge_request_is_identical_in_both_arms(tmp_path):
    keys = []
    for effort in ('low', 'medium'):
        core = model_comparison.workflow(effort)
        with pytest.raises(PendingCall) as waiting:
            core.CodexTransport(tmp_path / effort, 'UNIT', 'judge')('same grading prompt', 'same report', {})
        keys.append(waiting.value.path.parent.name)
    assert keys[0] == keys[1]


def test_profile_rejects_nonce_drift_and_missing_adapter(tmp_path, monkeypatch):
    from types import SimpleNamespace
    manifest = {'candidate': haiku('low'), 'judge': LUNA_JUDGE, 'judge_nonce': '',
                'adapter_sources': {name: luna_accuracy.digest(model_comparison.REPO / name)
                                    for name in model_comparison.ADAPTER_FILES}}
    monkeypatch.delenv('DPE_JUDGE_NONCE', raising=False)
    monkeypatch.setattr(model_comparison, 'workflow', lambda effort: SimpleNamespace(selected=lambda root: []))
    write_json(tmp_path / 'manifest.json', manifest)
    model_comparison.validate(tmp_path, 'low')
    monkeypatch.setenv('DPE_JUDGE_NONCE', 'different-judge-request')
    with pytest.raises(ValueError, match='nonce'):
        model_comparison.validate(tmp_path, 'low')
    monkeypatch.delenv('DPE_JUDGE_NONCE')
    manifest['adapter_sources'].pop(model_comparison.ADAPTER_FILES[0])
    write_json(tmp_path / 'manifest.json', manifest)
    with pytest.raises(ValueError, match='inventory'):
        model_comparison.validate(tmp_path, 'low')


def test_freeze_rejects_a_different_judge_nonce_before_writing(tmp_path, monkeypatch):
    monkeypatch.setenv('DPE_JUDGE_NONCE', 'different-judge-request')
    with pytest.raises(ValueError, match='nonce'):
        model_comparison.freeze(tmp_path, 'low')
    assert not (tmp_path / 'manifest.json').exists()
