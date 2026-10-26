"""Actual predictor capture from a key-free export; no accuracy claim or paid calls."""
import json
import shutil

from engine.codes import Codes


def test_engine_capture_runs_from_input_only_export_and_keeps_unobserved_layers_missing(tmp_path, monkeypatch):
    from evals_dev.requirement_bench.manifest import export_inputs, seal, snapshot_catalog
    from evals_dev.requirement_bench.protocol import write_json
    from evals_dev.requirement_bench.score import evaluate, key_template
    from evals_dev.requirement_capture import frozen_config, main

    for name in ('BATATIS_IDENTIFY_CONFIG', 'BATATIS_IDENTIFY_SCREEN', 'BATATIS_IDENTIFY_RERANK',
                 'BATATIS_IDENTIFY_VERIFIER'):
        monkeypatch.delenv(name, raising=False)
    from engine.identify import pipeline
    monkeypatch.setattr(pipeline, 'default_transports', lambda *a, **k: (_ for _ in ()).throw(AssertionError('provider')))
    db = tmp_path / 'source.sqlite'
    shutil.copyfile(Codes().db_path, db)
    bundle = tmp_path / 'private'
    bundle.mkdir()
    write_json(bundle / 'catalog.json', snapshot_catalog(db))
    write_json(bundle / 'config.json', frozen_config())
    write_json(bundle / 'input.json', {'schema_version': 1, 'case_id': 'capture-smoke',
        'narrative': '9.10.15.5.', 'facts': [], 'attachments': []})
    write_json(bundle / 'answer.json', key_template('capture-smoke'))
    write_json(bundle / 'plan.json', {'schema_version': 1, 'dataset_id': 'capture-smoke-unknown-key',
        'catalog': 'catalog.json', 'config': 'config.json', 'cases': [{
            'case_id': 'capture-smoke', 'split': 'dev', 'groups': ['capture-smoke'],
            'input': 'input.json', 'answer': 'answer.json',
            'leakage_review': {'status': 'unreviewed', 'reviewer': None, 'evidence': []}}]})
    seal(bundle / 'plan.json', bundle / 'manifest.json')
    exported = tmp_path / 'predictor-only'
    export_inputs(bundle / 'manifest.json', 'dev', 'capture-smoke-run', exported)
    assert not (exported / 'answer.json').exists()
    out = tmp_path / 'capture'
    assert main(['--bundle', str(exported), '--out', str(out), '--db', str(db)]) == 0
    prediction = json.loads((out / 'predictions.jsonl').read_text())
    assert prediction['status'] == 'ok' and prediction['requests'] == []
    assert prediction['layers']['application_included'] is None
    assert prediction['layers']['applicant_visible'] is None
    evidence = json.loads((out / prediction['layers']['retrieval_candidates']['path']).read_text())
    assert any(r['reference']['provision'] == '9.10.15.5.'
               for r in evidence['layers']['retrieval_candidates']['items'])
    report = evaluate(bundle / 'manifest.json', out / 'predictions.jsonl', 'dev', 'capture-smoke-run')
    assert report['expert_headline']['eligible_cases'] == 0
    assert report['expert_headline']['metrics'] is None
    assert report['cases'][0]['layers']['applicant_visible']['status'] == 'not_supplied'
    # A changed predictor after real execution must fail the capture, keeping the
    # planned attempt rather than publishing it under the earlier source hash.
    import copy
    import evals_dev.requirement_capture as adapter
    frozen = frozen_config()
    calls = 0
    def changed_after_execution():
        nonlocal calls
        calls += 1
        value = copy.deepcopy(frozen)
        if calls >= 3:
            value['predictor']['source_sha256'] = '0' * 64
        return value
    monkeypatch.setattr(adapter, 'frozen_config', changed_after_execution)
    changed = tmp_path / 'changed-capture'
    assert main(['--bundle', str(exported), '--out', str(changed), '--db', str(db)]) == 1
    failed = json.loads((changed / 'predictions.jsonl').read_text())
    assert failed['status'] == 'error' and 'changed during capture' in failed['error']
