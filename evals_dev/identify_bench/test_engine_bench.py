"""The engine benchmark must measure delivered output and keep failures visible."""
import json

from . import engine_bench
from .cases import Case


def record(kind='benchmark', *, usable=True, returned=('9.1.1.1.',), picked=()):
    return dict(kind=kind, usable=usable, gold=['9.1.1.1.'], returned=list(returned),
                picked=list(picked), committed=[], usd=0)


def test_failed_case_cannot_be_hidden_by_successful_candidate_retrieval():
    summary = engine_bench.summarize([record(), record(usable=False)])
    assert summary['positive_attempted'] == 2
    assert summary['positive_usable'] == 1
    assert summary['failed_cases'] == 1
    assert summary['complete_cases'] == 1
    assert summary['all_attempted_positive']['complete@all'] == 0.5
    assert summary['returned_including_fallbacks']['complete@all'] == 1
    assert summary['conditional_usable']['complete@all'] == 1


def test_intake_diagnostics_do_not_inflate_positive_recall():
    summary = engine_bench.summarize([
        record(returned=()), record('branches'), record('out_of_scope', picked=('9.1.1.1.',)),
    ])
    assert summary['positive_attempted'] == 1
    assert summary['all_attempted_positive']['complete@all'] == 0
    assert summary['branch_diagnostics']['complete@all'] == 1
    assert summary['out_of_scope']['cases_with_model_picks'] == 1


def test_report_reads_saved_results_without_executing_providers(tmp_path, monkeypatch, capsys):
    path = tmp_path / 'result.json'
    rows = [{**record(), 'case': 'first'}, {**record(usable=False), 'case': 'second'}]
    path.write_text(json.dumps({'selected_ids': ['first', 'second'], 'records': rows,
                               'summary': {'failed_cases': 0, 'attempted': 0}}))

    def forbidden(*args, **kwargs):
        raise AssertionError('a saved report must never dispatch an engine/provider run')

    monkeypatch.setattr(engine_bench, 'evaluate_case', forbidden)
    assert engine_bench.main(['report', '--output', str(path)]) == 1
    assert json.loads(capsys.readouterr().out)['attempted'] == 2


def test_partial_checkpoint_is_not_a_valid_headline():
    document = {'selected_ids': ['first', 'unfinished'], 'records': [{**record(), 'case': 'first'}]}
    summary = engine_bench.saved_summary(document)
    assert summary['unrecorded_cases'] == 1
    assert summary['selected_cases'] == 2
    assert summary['headline_valid'] is False


def test_reported_failure_usage_is_retained_in_engine_record(monkeypatch):
    error = engine_bench.live.ProviderFailure('invalid_response')
    error.usage = dict(input_tokens=100, output_tokens=40, usd=0.00005, unknown_usage=False)
    def failed(*args, **kwargs):
        raise error
    def engine(proposal, *, transports, **kwargs):
        transports.openai('pool_review', {}, 'system', 'proposal', model='gpt-6-luna')
    monkeypatch.setattr(engine_bench.live, 'openai_json', failed)
    monkeypatch.setattr(engine_bench, 'Codes', lambda _: object())
    monkeypatch.setattr(engine_bench, 'run', engine)
    case = Case('failure', 'dev', 'A proposal.', ('9.1.1.1.',))
    result = engine_bench.evaluate_case(case, object(), live_calls=False)
    assert result['requests'] == 1
    assert result['input_tokens'] == 100 and result['output_tokens'] == 40
    assert result['usd'] == 0.00005
    assert result['provider_errors'][0]['code'] == 'invalid_response'


def test_wal_drift_during_evaluation_invalidates_headline(monkeypatch, tmp_path):
    database = tmp_path / 'synthetic.sqlite'
    database.write_bytes(b'unchanged primary file')
    monkeypatch.setattr(engine_bench, 'DB', database)
    monkeypatch.setattr(engine_bench, 'source_digest', lambda: 'stable')
    monkeypatch.setattr(engine_bench, 'selected_cases', lambda: [
        Case('first', 'dev', 'A proposal.', ('9.1.1.1.',))])
    def evaluate(*args, **kwargs):
        (tmp_path / 'synthetic.sqlite-wal').write_bytes(b'changed WAL')
        return {**record(), 'case': 'first'}
    monkeypatch.setattr(engine_bench, 'evaluate_case', evaluate)
    output = tmp_path / 'report.json'
    assert engine_bench.main(['run', '--limit', '1', '--output', str(output)]) == 1
    saved = json.loads(output.read_text())
    assert saved['corpus_changed_during_run'] is True
    assert saved['summary']['headline_valid'] is False
