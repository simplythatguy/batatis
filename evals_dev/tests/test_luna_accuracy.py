from types import SimpleNamespace

import pytest

from evals_dev import luna_accuracy as experiment
from evals_dev.codex_transport import write_json
from evals_dev.data_prompts.gold import Gold, Item


def grading_case(monkeypatch, tmp_path):
    case = SimpleNamespace(id='TEST-001', city='Calgary', tier='Calgary / Edmonton', prompt='Review this record.')
    monkeypatch.setattr(experiment, 'selected', lambda root: [case])
    monkeypatch.setattr('engine.codes.Codes', lambda: None)
    monkeypatch.setattr(experiment.gold, 'gold', lambda case, codes: Gold(
        case.id, (Item('F1', 'F', 'The source states a fact.'),), (), 1, ()))
    monkeypatch.setattr(experiment.checks, 'completion', lambda result: [] if result else ['missing_case'])
    monkeypatch.setattr(experiment.checks, 'guardrails', lambda *args: {
        name: (True, '') for name in ('ran', 'no_claims', 'citations_resolve',
                                     'no_alberta_commit_outside_alberta')})
    monkeypatch.setattr(experiment.render, 'report', lambda result: 'The source states a fact.')
    write_json(tmp_path / 'manifest.json', {'input_hashes': {case.id: {'prompt': 'fixture'}}})
    return case


def test_a_pending_judge_stays_in_the_denominator(monkeypatch, tmp_path):
    case = grading_case(monkeypatch, tmp_path)
    write_json(tmp_path / 'results' / f'{case.id}.json', experiment.seal(
        tmp_path, case.id, {'case_id': case.id, 'case': {}}, []))
    summary = experiment.grade(tmp_path)
    assert summary['cases_expected'] == summary['cases'] == 1
    assert summary['checks_expected'] == summary['checks'] == 1
    assert summary['checks_unscored'] == 1
    assert summary['cases_judged'] == 0
    assert summary['accuracy'] == 0
    assert summary['failure_reasons'] == {'pending_judge': 1}
    assert not summary['check_coverage_target_met']


def test_a_missing_engine_output_stays_in_the_denominator(monkeypatch, tmp_path):
    grading_case(monkeypatch, tmp_path)
    summary = experiment.grade(tmp_path)
    assert summary['cases_failed'] == summary['checks_failed'] == summary['checks_unscored'] == 1
    assert summary['failure_reasons'] == {'missing_case': 1}


def test_unread_input_is_reported_even_when_a_judge_passes_the_text(monkeypatch, tmp_path):
    from evals_dev.data_prompts.judge import Verdict
    case = grading_case(monkeypatch, tmp_path)
    result = {'case_id': case.id, 'case': {'intake': {'review': {'status': 'live', 'flags': [
        {'kind': 'not_read', 'text': 'The supplied drawing has no readable text.'}]}}}}
    write_json(tmp_path / 'results' / f'{case.id}.json', experiment.seal(tmp_path, case.id, result, []))
    monkeypatch.setattr(experiment.judge, 'grade', lambda *args, **kwargs: [Verdict('F1', 'F', True, 'quote', '')])
    summary = experiment.grade(tmp_path)
    assert summary['accuracy'] == 1
    assert summary['cases_with_unread_input'] == 1
    assert not summary['check_coverage_target_met']


@pytest.mark.parametrize('change,reason', [('new_file', 'frozen source changed'),
                                         ('codedb', 'frozen source changed'),
                                         ('web', 'frozen source changed'),
                                         ('city_metadata', 'frozen case index changed')])
def test_source_and_city_changes_invalidate_an_experiment(monkeypatch, tmp_path, change, reason):
    repo = tmp_path / 'checkout'
    for name in ('engine/original.py', 'evals_dev/codex_transport.py', 'evals_dev/luna_accuracy.py',
                 'Data Prompts/test/source.json', 'Data Prompts/test/evaluation.json', 'Data Prompts/index.json'):
        path = repo / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text('{}')
    case = SimpleNamespace(id='TEST-001', folder='test', prompt='Fixture only.', attachments=())
    monkeypatch.setattr(experiment, 'REPO', repo)
    monkeypatch.setattr(experiment.corpus, 'METADATA_ROOT', repo / 'Data Prompts')
    monkeypatch.setattr(experiment.corpus, 'select', lambda selection: [case])
    monkeypatch.setattr(experiment.corpus, 'load', lambda: (case,))
    monkeypatch.setattr(experiment.corpus, 'split', lambda: {case.id: 'dev'})
    monkeypatch.setattr(experiment.corpus, '_components', lambda cases: {case.id: case.id})
    database = tmp_path / 'test-database'
    database.write_text('fingerprint fixture; not a source database')
    monkeypatch.setenv('BATATIS_CODEDB', str(database))
    root = tmp_path / 'experiment'
    experiment.freeze(root, 'dev')
    assert experiment.selected(root) == [case]
    if change == 'new_file':
        (repo / 'engine' / 'new_behavior.py').write_text('changed = True')
    elif change in ('codedb', 'web'):
        path = repo / ('codedb/api.py' if change == 'codedb' else 'web/src/DocumentReview.tsx')
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text('changed = true')
    else:
        (repo / 'Data Prompts/index.json').write_text('{"city_or_town":"Edmonton"}')
    with pytest.raises(ValueError, match=reason):
        experiment.selected(root)


def test_a_copied_result_cannot_bypass_the_frozen_workflow(monkeypatch, tmp_path):
    case = grading_case(monkeypatch, tmp_path)
    write_json(tmp_path / 'results' / f'{case.id}.json', {'case_id': case.id, 'case': {}})
    summary = experiment.grade(tmp_path)
    assert summary['failure_reasons'] == {'result_provenance_mismatch': 1}
    assert summary['checks_expected'] == summary['checks_unscored'] == 1


def test_a_changed_sealed_result_cannot_be_reused(monkeypatch, tmp_path):
    case = grading_case(monkeypatch, tmp_path)
    value = experiment.seal(tmp_path, case.id, {'case_id': case.id, 'case': {'facts': []}}, [])
    path = tmp_path / 'results' / f'{case.id}.json'
    write_json(path, value)
    assert experiment.bound_result(tmp_path, case.id) == value
    value['case']['facts'] = ['copied from another run']
    write_json(path, value)
    with pytest.raises(ValueError, match='not bound'):
        experiment.bound_result(tmp_path, case.id)


@pytest.mark.parametrize('selection', ['TEST-001', 'local-dev'])
def test_one_city_cannot_meet_the_two_city_target(monkeypatch, tmp_path, selection):
    from evals_dev.data_prompts.judge import Verdict
    case = grading_case(monkeypatch, tmp_path)
    write_json(tmp_path / 'manifest.json', {'selection': selection,
                                          'input_hashes': {case.id: {'prompt': 'fixture'}}})
    monkeypatch.setattr(experiment, 'local_development', lambda: [case])
    write_json(tmp_path / 'results' / f'{case.id}.json', experiment.seal(
        tmp_path, case.id, {'case_id': case.id, 'case': {}}, []))
    monkeypatch.setattr(experiment.judge, 'grade', lambda *args, **kwargs: [Verdict('F1', 'F', True, 'quote', '')])
    summary = experiment.grade(tmp_path)
    assert summary['accuracy'] == 1
    assert not summary['check_coverage_target_met']
    assert not summary['complete_local_development_selection']


def test_parallel_resume_only_writes_the_assigned_frozen_case(monkeypatch, tmp_path):
    cases = [SimpleNamespace(id='TEST-001'), SimpleNamespace(id='TEST-002')]
    monkeypatch.setattr(experiment, 'selected', lambda root: cases)
    visited = []
    def run_case(case, root):
        visited.append(case.id)
        return {'case_id': case.id, 'case': {}}
    monkeypatch.setattr(experiment, 'run_case', run_case)
    monkeypatch.setattr(experiment.checks, 'completion', lambda result: [])
    assert experiment.resume(tmp_path, 'TEST-002') == {'complete': 1}
    assert visited == ['TEST-002']
    assert not (tmp_path / 'results' / 'TEST-001.json').exists()
    assert (tmp_path / 'results' / 'TEST-002.json').exists()
    with pytest.raises(ValueError, match='outside this frozen experiment'):
        experiment.resume(tmp_path, 'TEST-003')


@pytest.mark.parametrize('selection,expected', [('local-dev', True), ('TEST-001,TEST-002', False)])
def test_coverage_requires_the_predeclared_complete_local_run(monkeypatch, tmp_path, selection, expected):
    from evals_dev.data_prompts.judge import Verdict
    first = grading_case(monkeypatch, tmp_path)
    second = SimpleNamespace(id='TEST-002', city='Edmonton', tier=first.tier, prompt=first.prompt)
    cases = [first, second]
    monkeypatch.setattr(experiment, 'selected', lambda root: cases)
    monkeypatch.setattr(experiment, 'local_development', lambda: cases)
    write_json(tmp_path / 'manifest.json', {'selection': selection,
                                          'input_hashes': {c.id: {'prompt': 'fixture'} for c in cases}})
    for case in cases:
        write_json(tmp_path / 'results' / f'{case.id}.json', experiment.seal(
            tmp_path, case.id, {'case_id': case.id, 'case': {}}, []))
    monkeypatch.setattr(experiment.judge, 'grade', lambda *args, **kwargs: [Verdict('F1', 'F', True, 'quote', '')])
    summary = experiment.grade(tmp_path)
    assert summary['accuracy'] == 1
    assert summary['check_coverage_target_met'] is expected
    assert not summary['target_met']
    assert not summary['production_accuracy_established']


def test_generic_judge_cache_cannot_bypass_the_codex_response(monkeypatch, tmp_path):
    import json
    from evals_dev.codex_transport import CodexTransport, PendingCall
    from evals_dev.data_prompts import judge
    items = [Item('F1', 'F', 'A source fact.')]
    key = judge._key('gpt-6-luna', 'max', 'request', 'Exact report fact.', items)
    write_json(tmp_path / 'judge-cache' / key[:2] / f'{key}.json', {
        'validator_version': judge.VERSION, 'request_hash': 'copied-from-another-request',
        'payload': {'items': [{'id': 'F1', 'covered': True, 'evidence': ['Exact report fact.']}]}, 'calls': []})
    bridge = CodexTransport(tmp_path, 'TEST-001', 'judge', [])
    def grade():
        return judge.grade('request', 'Exact report fact.', items, model='gpt-6-luna', effort='max',
                           transport=bridge, cache_root=tmp_path / 'judge-cache')
    with pytest.raises(PendingCall) as waiting:
        grade()
    request = json.loads(waiting.value.path.read_text())
    path = waiting.value.path.with_name('response.json')
    write_json(path, {**{k: request[k] for k in ('request_sha256', 'provider', 'model', 'options')},
                      'task_id': 'unit-fixture-task',
                      'payload': {'items': [{'id': 'F1', 'covered': True, 'evidence': ['Exact report fact.']}]}})
    assert grade()[0].passed
    assert bridge.calls[0]['task_id'] == 'unit-fixture-task'
    path.unlink()
    with pytest.raises(PendingCall):
        grade()


def test_legacy_judge_rejects_a_cache_from_another_request(monkeypatch, tmp_path):
    from evals_dev.data_prompts import judge
    items = [Item('F1', 'F', 'A source fact.')]
    key = judge._key('gpt-6-luna', 'max', 'request', 'Exact report fact.', items)
    write_json(tmp_path / key[:2] / f'{key}.json', {
        'validator_version': judge.VERSION, 'request_hash': 'different-request',
        'payload': {'items': [{'id': 'F1', 'covered': True, 'evidence': ['Exact report fact.']}]}, 'calls': []})
    monkeypatch.setattr(judge, '_call', lambda *args: pytest.fail('must not dispatch a provider'))
    verdict = judge.grade('request', 'Exact report fact.', items, model='gpt-6-luna', effort='max', cache_root=tmp_path)[0]
    assert not verdict.passed
    assert verdict.note == 'cache_request_mismatch'
