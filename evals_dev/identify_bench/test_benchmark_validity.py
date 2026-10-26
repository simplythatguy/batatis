"""Offline regressions for attempted-case denominators, saved reports and split hygiene."""
from __future__ import annotations

import json
import os
from dataclasses import replace

import pytest

from evals_dev.identify_bench import cases, groups, metrics, pipeline_bench as bench


def case(cid, gold=('9.8.8.1.',), **kwargs):
    return cases.Case(cid, 'dev', 'A proposal ' + cid, gold, **kwargs)


def record(c, *, error=None):
    r = {'case': c.id, 'source': c.source, 'kind': c.kind, 'fold': c.fold,
         'gold': list(c.gold), 'context': list(c.context)}
    if error:
        return {**r, 'error': error, 'error_stage': 'labels'}
    return {**r, 'pool': list(c.gold), 'labels': {a: {'label': 'check', 'reason': 'r'} for a in c.gold}}


def test_errors_stay_in_headline_and_completed_metrics_are_separate():
    good, bad = case('good'), case('bad')
    s = bench.summarize([record(good), record(bad, error='timeout')], ['pool', 'luna'])
    assert (s['attempted'], s['completed'], s['errors']) == (2, 1, 1)
    assert s['luna']['complete_surfaced'] == 0.5
    assert s['pool_ranking']['complete@all'] == 0.5
    assert s['conditional_completed']['luna']['complete_surfaced'] == 1


def test_nonpositive_case_kinds_never_inflate_final_recall():
    cs = [case('positive'), case('branch', kind='branches'), case('outside', gold=(), kind='out_of_scope'),
          case('checklist', kind='checklist')]
    s = bench.summarize([record(c) for c in cs], ['luna'])
    assert s['attempted'] == 4 and s['luna']['cases'] == 1
    assert s['kind_counts'] == {'benchmark': 1, 'branches': 1, 'out_of_scope': 1, 'checklist': 1}


def test_unavailable_elephant_is_counted_as_failure_not_removed():
    cs = [case('scored'), case('unscored')]
    rows = [record(c) for c in cs]
    rows[0]['elephant'] = {cs[0].gold[0]: 0.8}
    s = bench.summarize(rows, ['elephant-bands@0.1,0.9'])
    assert s['elephant-bands@0.1,0.9']['complete_surfaced'] == 0.5
    assert s['elephant-bands@0.1,0.9']['errors'] == 1


def test_missing_candidate_is_a_retrieval_miss_not_an_unlikely_label():
    r = {**record(case('missing')), 'pool': [], 'labels': {}}
    miss, = bench.misses([r], 'luna')
    assert miss['label'] is None and miss['failure'] == 'not_retrieved'


def test_label_only_metrics_explicitly_describe_conditional_gold_preservation():
    s = metrics.label_summary([metrics.label_outcome({'a': 'check'}, ['a'])])
    assert s['metric_scope'] == 'gold_preservation_given_pool'
    assert 'completed' not in s  # Labels alone do not establish provider-attempt status.


@pytest.mark.parametrize('elephant', [False, True])
def test_cli_persists_errors_returns_failure_and_prints_valid_json(monkeypatch, tmp_path, capsys, elephant):
    cs = [case(fold_id('tune', 'ok')), case(fold_id('tune', 'failed'))]
    monkeypatch.setattr(bench, 'all_cases', lambda: cs)
    monkeypatch.setattr(bench, 'articles', lambda _: {})
    monkeypatch.setattr(bench, 'corpus_fingerprint', lambda _: 'synthetic-corpus')
    monkeypatch.setattr(bench, 'RESULTS', tmp_path)

    def run(c, *args, **kwargs):
        if c.id == cs[1].id:
            raise RuntimeError('sk-secret /private/path Authorization: Bearer secret')
        row = record(c)
        if elephant:
            row['elephant'] = {a: 0.8 for a in c.gold}
        return row

    monkeypatch.setattr(bench, 'run_case', run)
    args = ['run', '--fold', 'tune', '--workers', '2'] + (['--with-elephant'] if elephant else [])
    assert bench.main(args) == 1
    captured = capsys.readouterr()
    output = json.loads(captured.out)
    saved = json.loads(next(tmp_path.glob('*.json')).read_text())
    assert output['summary']['errors'] == saved['summary']['errors'] == 1
    assert len(saved['records']) == 2
    assert saved['records'][1]['error'] == 'internal_error'
    assert 'sk-secret' not in captured.out + captured.err + json.dumps(saved)
    assert '/private/path' not in captured.out + captured.err + json.dumps(saved)


def test_saved_report_does_not_load_cases_corpus_or_call_providers(monkeypatch, tmp_path, capsys):
    path = tmp_path / 'saved.json'
    rows = [record(case('ok')), record(case('failed'), error='timeout')]
    path.write_text(json.dumps({'schema_version': 2, 'records': rows, 'rules': ['luna']}))

    def boom(*a, **k):
        pytest.fail('report must use saved records only')

    for attr in ('all_cases', 'articles', 'run_case'):
        monkeypatch.setattr(bench, attr, boom)
    assert bench.main(['report', '--input', str(path)]) == 1
    assert json.loads(capsys.readouterr().out)['summary']['luna']['complete_surfaced'] == 0.5
    assert json.loads(path.read_text())['records'] == rows


def test_legacy_report_does_not_claim_known_attempt_denominator(monkeypatch, tmp_path, capsys):
    path = tmp_path / 'legacy.json'
    path.write_text(json.dumps({'records': [record(case('only_completed'))]}))
    assert bench.main(['report', '--input', str(path)]) == 0
    out = json.loads(capsys.readouterr().out)
    assert out['summary']['attempts_known'] is False
    assert out['summary']['headline_valid'] is False


def fold_id(fold, prefix):
    return next(f'{prefix}{i}' for i in range(1000)
                if case(f'{prefix}{i}').fold == fold)


def test_duplicate_groups_close_rewrite_chains_and_gold_links_in_any_order():
    tune = replace(case(fold_id('tune', 'origin')), source='precedent')
    rewrite = replace(case(fold_id('test', 'rewrite'), ('9.10.15.5.',)), source='web-ab',
                      meta={'rewrite_of': tune.id})
    twin = replace(case(fold_id('test', 'twin'), rewrite.gold), source='web-ca')
    chain = replace(case(fold_id('test', 'chain'), ('3.2.4.1.',)), source='web-ab',
                    meta={'rewrite_of': rewrite.id})
    cs = [chain, twin, rewrite, tune]
    forward, reverse = groups.duplicate_groups(cs), groups.duplicate_groups(list(reversed(cs)))
    assert len(set(forward.values())) == 1 and forward == reverse
    assert groups.clean_test(cs) == []


def test_source_rewrites_with_different_gold_and_test_twins_are_guarded():
    tune = replace(case(fold_id('tune', 'source')), source='web-ab',
                   meta={'source_url': 'https://example.org/variance.pdf?utm_source=search#page=2'})
    rewrite = replace(case(fold_id('test', 'source'), ('3.2.4.1.',)), source='web-ca',
                      meta={'source_url': 'https://example.org/variance.pdf#page=9'})
    assert groups.clean_test([rewrite, tune]) == []
    twins = [replace(case(fold_id('test', f'unseen{i}')), source='precedent') for i in range(2)]
    assert len(groups.clean_test(twins)) == 1


def test_clean_cli_checks_leakage_before_source_and_kind_filters(monkeypatch, tmp_path, capsys):
    tune = case(fold_id('tune', 'scope'), kind='branches')
    twin = replace(case(fold_id('test', 'scope')), source='web-ab')
    monkeypatch.setattr(bench, 'all_cases', lambda: [tune, twin])
    monkeypatch.setattr(bench, 'articles', lambda _: {})
    monkeypatch.setattr(bench, 'RESULTS', tmp_path)
    monkeypatch.setattr(bench, 'run_case', lambda *a, **k: pytest.fail('leaked case was evaluated'))
    assert bench.main(['run', '--clean', '--sources', 'web-ab']) == 0
    assert json.loads(capsys.readouterr().out)['summary']['attempted'] == 0


def test_canonical_development_selection_rejects_file_id_mismatch(monkeypatch, tmp_path):
    monkeypatch.setattr(cases, 'DEV_DIR', tmp_path)
    for i in range(1, 61):
        cid = f'dev-{i:03}'
        payload = {'id': cid, 'topic': 'guards', 'description': 'a proposal',
                   'gold': {'intake_action': 'proceed_conditionally', 'must_cite': [
                       {'division': 'B', 'provision': '9.8.8.1.(1)'}]}}
        (tmp_path / f'{cid}.json').write_text(json.dumps(payload))
    assert len(cases.dev_cases()) == 60
    path = tmp_path / 'dev-001.json'
    payload = json.loads(path.read_text())
    payload['id'] = 'dev-002'
    path.write_text(json.dumps(payload))
    with pytest.raises(ValueError):
        cases.dev_cases()


def test_ranking_summary_accepts_gold_iterators_once():
    s = metrics.ranking_summary([(['a'], iter(['a']))])
    assert s['complete@all'] == 1 and s['gold_articles'] == 1


def test_foreign_topic_is_selectable_only_as_diagnostic_and_keeps_exclusion(monkeypatch, tmp_path):
    path = tmp_path / 'web.json'
    rows = [{'id': 'ab', 'description': 'Alberta proposal', 'gold': ['9.8.8.1.']},
            {'id': 'foreign', 'description': 'Foreign substitution', 'gold': ['9.32.3.9.'],
             'evaluation_scope': 'foreign_topic', 'evaluation_exclusion': 'Related topic only.'}]
    path.write_text(json.dumps(rows))
    monkeypatch.setitem(cases.WEB, 'web-ca', path)
    loaded = cases.web_cases('web-ca')
    assert [c.id for c in cases.select(loaded)] == ['ab']
    foreign, = cases.select(loaded, kinds=('foreign_topic',))
    assert foreign.meta['evaluation_exclusion'] == 'Related topic only.'
    assert bench._case_record(foreign)['evaluation_exclusion'] == 'Related topic only.'
    summary = bench.summarize([record(c) for c in loaded], ['luna'])
    assert summary['attempted'] == 2 and summary['luna']['cases'] == 1


def test_saved_selection_preserves_unrecorded_attempt_as_failure(tmp_path, capsys):
    cs = [case('recorded'), case('interrupted')]
    path = tmp_path / 'saved.json'
    path.write_text(json.dumps({'schema_version': 2, 'rules': ['luna'],
                                'selected_cases': [bench._case_record(c) for c in cs],
                                'records': [record(cs[0])]}))
    assert bench.main(['report', '--input', str(path)]) == 1
    out = json.loads(capsys.readouterr().out)
    assert out['summary']['attempted'] == 2 and out['summary']['errors'] == 1
    assert out['summary']['luna']['complete_surfaced'] == 0.5
    assert out['records'][1]['error_stage'] == 'not_recorded'


def test_default_cli_replay_refuses_uncached_verification_before_credentials(monkeypatch, tmp_path, capsys):
    from engine.identify import providers
    from evals_dev.identify_bench import live
    from evals_dev.identify_bench.cache import Store
    c = case('uncached')
    arts = {c.gold[0]: {'id': c.gold[0], 'title': 'Guards', 'part': '9', 'section': 'Stairs',
                       'subsection': 'Guards', 'text': 'Provide a guard.'}}
    stores = tuple(Store(name, tmp_path / 'cache') for name in ('elephant', 'openai', 'spend'))
    monkeypatch.setattr(live, '_stores', lambda: stores)
    monkeypatch.setattr(live, 'load_keys', lambda *a: pytest.fail('credential read'))
    monkeypatch.setattr(providers, 'raw_openai_json', lambda *a, **k: pytest.fail('network'))
    monkeypatch.setattr(bench, 'all_cases', lambda: [c])
    monkeypatch.setattr(bench, 'articles', lambda _: arts)
    monkeypatch.setattr(bench, 'corpus_fingerprint', lambda _: 'synthetic-corpus')
    monkeypatch.setattr(bench, 'candidate_pool', lambda *a: ([c.gold[0]], {}))
    monkeypatch.setattr(bench, 'RESULTS', tmp_path / 'results')
    assert bench.main(['run', '--fold', 'all']) == 1
    out = json.loads(capsys.readouterr().out)
    rec, = out['records']
    assert rec['error'] == 'live_disabled' and rec['error_stage'] == 'labels'
    assert rec['pool'] == list(c.gold) and out['summary']['luna']['complete_surfaced'] == 0
    assert stores[2].rows() == []


def test_changed_corpus_during_run_cannot_report_success(monkeypatch, tmp_path, capsys):
    db = tmp_path / 'synthetic.sqlite'
    db.write_bytes(b'first snapshot')
    c = case('corpus-change')
    monkeypatch.setattr(bench, 'DB', db)
    monkeypatch.setattr(bench, 'all_cases', lambda: [c])
    monkeypatch.setattr(bench, 'articles', lambda _: {})
    monkeypatch.setattr(bench, 'RESULTS', tmp_path / 'results')

    def run(*a, **k):
        stamp = db.stat()
        db.write_bytes(b'other snapshot')
        os.utime(db, ns=(stamp.st_atime_ns, stamp.st_mtime_ns + 1_000_000_000))
        return record(c)

    monkeypatch.setattr(bench, 'run_case', run)
    assert bench.main(['run', '--fold', 'all']) == 1
    out = json.loads(capsys.readouterr().out)
    assert out['records'][0]['error'] == 'corpus_changed'
    assert out['summary']['luna']['complete_surfaced'] == 0
