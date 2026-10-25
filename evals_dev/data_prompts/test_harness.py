"""Offline checks of the Data Prompts harness: no provider calls and no attachments needed."""
from __future__ import annotations

import json
from concurrent.futures import Future
from types import SimpleNamespace

import httpx
import pytest

from evals_dev.data_prompts import __main__ as cli
from evals_dev.data_prompts import checks, corpus, deepseek_review, gold, judge, ledger, manifest, score
from evals_dev.data_prompts.gold import Item


def test_every_case_loads_with_review_points():
    cases = corpus.load()
    assert len(cases) == 653
    assert all(c.focus and all(len(p) > 3 for p in c.focus) for c in cases)
    assert all(c.prompt for c in cases)


def test_split_keeps_shared_sources_on_one_side_and_is_stable():
    cases = corpus.load()
    sides = corpus.split(cases)
    assert set(sides.values()) == {'dev', 'holdout'}
    by_group: dict[str, set[str]] = {}
    by_file: dict[str, set[str]] = {}
    for c in cases:
        by_group.setdefault(c.source_group, set()).add(sides[c.id])
        for a in c.attachments:
            by_file.setdefault(a.sha256, set()).add(sides[c.id])
    assert all(len(s) == 1 for s in by_group.values())
    assert all(len(s) == 1 for s in by_file.values())
    corpus.split.cache_clear()
    assert corpus.split(cases) == sides
    for tier in corpus.TIERS:
        dev = sum(1 for c in cases if c.tier == tier and sides[c.id] == 'dev')
        held = sum(1 for c in cases if c.tier == tier and sides[c.id] == 'holdout')
        assert held > 0 and dev > 0


def test_prohibitions_are_read_from_wording():
    p = lambda text: judge.is_prohibition(Item('R1', 'R', text))   # noqa: E731
    assert p('do not transfer this British Columbia appeal outcome or code interpretation to Alberta')
    assert p('no compliance certification')
    assert p('Makes no compliance statement.')
    assert p('Whether it does not say the woodburner complies.')
    assert not p('no drawings or calculations attached')
    assert not p('code edition not stated')
    assert not p('Does not say the design complies or is safe; asks for the fire engineering report')
    assert not judge.is_prohibition(Item('F1', 'F', 'do not ...'))


def test_a_covered_verdict_needs_an_excerpt_that_is_in_the_report():
    report = 'FACTS READ\n- [a.pdf p.3] statement: "travel distance of 25 m to a point of choice"'
    assert judge.found('travel distance of 25 m', report)
    assert judge.found('travel distance of 25 m to a point ... choice', report)
    assert not judge.found('Travel distance of 25 m', report)
    assert not judge.found('travel distance of 30 m', report)
    assert not judge.found('ok', report)


def test_claim_guardrail_reads_only_outright_verdicts():
    assert checks.claims(['The design complies with the code.'])
    assert checks.claims(['This assembly is code-compliant.'])
    assert not checks.claims(['Batatis does not say whether the design complies with the code.'])
    assert not checks.claims(['Does the wall meet the code requirement?'])
    assert not checks.claims(['Your evidence must show that the design meets the requirements.'])


def test_edition_and_boundary_items_come_from_metadata():
    assert gold.edition_status('National Building Code – 2023 Alberta Edition') == 'current'
    assert gold.edition_status('NBC(AE) 2023 and NFC(AE) 2023; printing not stated') == 'current'
    assert gold.edition_status('Alberta Building Code 2014') == 'historical'
    assert gold.edition_status('NBC 2015') == 'historical'
    assert gold.edition_status('unknown if unstated') == 'unknown'
    cases = {c.tier: c for c in corpus.load()}
    outside = gold.boundary_items(cases['Outside Alberta - attachment comparison only'])
    assert len(outside) == 1 and 'outside Alberta' in outside[0].text


@pytest.fixture
def integrity_offline(monkeypatch, tmp_path):
    def forbidden(*args, **kwargs):
        raise AssertionError('integrity tests must never dispatch a provider request')
    monkeypatch.setattr(httpx.Client, 'post', forbidden)
    monkeypatch.setattr(ledger, 'CACHE', tmp_path / 'http')
    monkeypatch.setattr(ledger, 'ATTEMPTS', tmp_path / 'attempts.jsonl', raising=False)
    monkeypatch.setattr(judge, 'CACHE', tmp_path / 'judge')
    monkeypatch.setattr(cli, 'RUNS', tmp_path / 'runs')
    monkeypatch.setattr(cli.sut, 'load_env', lambda: None)
    monkeypatch.setattr(cli.sut, 'init_worker', lambda *args: None)
    monkeypatch.setattr(ledger, 'install', lambda **kwargs: None)
    monkeypatch.delenv('DPE_JUDGE_NONCE', raising=False)
    monkeypatch.delenv('DPE_HTTP_CACHE', raising=False)
    return tmp_path


def _case(cid='dev-case'):
    return SimpleNamespace(id=cid, tier=corpus.TIERS[0], case_type='issued_variance', prompt='offline request',
                           attachments=())


def _gold(case, codes):
    return gold.Gold(case.id, (Item('F1', 'F', 'a source fact'), Item('R1', 'R', 'a review point')),
                     ('3.2.1.1.',), 1, ())


def _result(cid='dev-case'):
    return {'case_id': cid, 'case': {'intake': {'review': {'status': 'off'}}, 'identify': {}},
            'errors': [], 'cost': ledger.as_dict(ledger.Ledger())}


def test_integrity_score_keeps_missing_outputs_and_judge_errors_in_denominator(integrity_offline, monkeypatch):
    import engine.codes
    cases = [_case('missing'), _case('judge-error')]
    monkeypatch.setattr(cli.corpus, 'select', lambda split: cases)
    monkeypatch.setattr(cli.gold, 'gold', _gold)
    monkeypatch.setattr(engine.codes, 'Codes', lambda path: object())
    monkeypatch.setattr(engine.codes, 'default_db', lambda: integrity_offline / 'db')
    def broken(*args):
        raise ValueError('offline judge failure')
    monkeypatch.setattr(cli, '_judge_case', broken)
    folder = cli.RUNS / 'missing-run' / 'cases'
    folder.mkdir(parents=True)
    (folder / 'judge-error.json').write_text(json.dumps(_result('judge-error')))
    status = cli.main(['score', '--name', 'missing-run', '--split', 'dev'])
    summary = json.loads(next(folder.parent.glob('*.summary.json')).read_text())
    rows = [json.loads(line) for line in next(folder.parent.glob('score-*.jsonl')).read_text().splitlines()]
    assert status != 0
    assert summary['checks'] == 6
    assert summary['cases_expected'] == 2 and summary['cases_failed'] == 2 and summary['cases_scored'] == 0
    assert len(rows) == 2 and all(not c['passed'] for row in rows for c in row['checks'])
    assert {r['failure_reasons'][0] for r in rows} == {'missing_output', 'judge_error:ValueError'}


def test_integrity_missing_output_alone_returns_failure(integrity_offline, monkeypatch):
    import engine.codes
    monkeypatch.setattr(cli.corpus, 'select', lambda split: [_case()])
    monkeypatch.setattr(cli.gold, 'gold', _gold)
    monkeypatch.setattr(engine.codes, 'Codes', lambda path: object())
    monkeypatch.setattr(engine.codes, 'default_db', lambda: integrity_offline / 'db')
    (cli.RUNS / 'empty' / 'cases').mkdir(parents=True)
    assert cli.main(['score', '--name', 'empty']) != 0


@pytest.mark.parametrize('status', ['failed', 'gate_closed'])
def test_integrity_attempted_review_failure_is_not_ran(integrity_offline, status):
    result = _result()
    result['case']['intake']['review'] = {'status': status, 'reason': 'ReadTimeout'}
    assert checks.guardrails(_case(), result, object())['ran'][0] is False


class _ImmediatePool:
    def __init__(self, *args, **kwargs):
        pass
    def __enter__(self):
        return self
    def __exit__(self, *args):
        pass
    def submit(self, fn, *args):
        future = Future()
        future.set_result(fn(*args))
        return future


@pytest.mark.parametrize('force', [False, True])
def test_integrity_run_refuses_config_drift_without_rewriting_meta(integrity_offline, monkeypatch, force):
    monkeypatch.setattr(cli.corpus, 'select', lambda split: [])
    monkeypatch.setattr(cli, 'ProcessPoolExecutor', _ImmediatePool)
    meta = {'engine_tree': 'tree', 'engine_diff_sha256': None,
            'review': {'DPE_REVIEW_TRANSPORT': 'deepseek', 'DPE_DEEPSEEK_EFFORT': 'max'}}
    monkeypatch.setattr(cli, '_meta', lambda args: json.loads(json.dumps(meta)))
    # Freeze source identity at the cmd_run seam; separately test the real manifest hashes below.
    monkeypatch.setattr(cli, '_manifest', lambda args, metadata, cases: {'resolved': metadata}, raising=False)
    assert cli.main(['run', '--name', 'frozen']) == 0
    before = (cli.RUNS / 'frozen' / 'meta.json').read_bytes()
    meta['review']['DPE_DEEPSEEK_EFFORT'] = 'high'
    assert cli.main(['run', '--name', 'frozen', *(['--force'] if force else [])]) != 0
    assert (cli.RUNS / 'frozen' / 'meta.json').read_bytes() == before


@pytest.mark.parametrize('payload', [
    {'items': [{'id': 'R1', 'covered': 'false', 'evidence': ['exact report text']}]},
    {'items': []},
    {'items': [{'id': 'R1', 'covered': True, 'evidence': []},
               {'id': 'R1', 'covered': True, 'evidence': []}]},
    {'items': [{'id': 'R1', 'covered': True, 'evidence': 'not a list'}]},
])
def test_integrity_invalid_prohibition_verdicts_fail_closed(integrity_offline, monkeypatch, payload):
    monkeypatch.setattr(judge, '_call', lambda *args: payload)
    verdict = judge.grade('request', 'exact report text', [Item('R1', 'R', 'no compliance certification')],
                          model='gpt-6.1-sol', effort='low')[0]
    assert verdict.passed is False
    assert verdict.note


def test_integrity_string_false_cannot_credit_a_positive_item(integrity_offline, monkeypatch):
    monkeypatch.setattr(judge, '_call', lambda *args: {
        'items': [{'id': 'F1', 'covered': 'false', 'evidence': ['exact report text']}]})
    assert not judge.grade('q', 'exact report text', [Item('F1', 'F', 'fact')],
                           model='gpt-6.1-sol', effort='low')[0].passed


def test_integrity_short_invented_ellipsis_fragments_are_not_discarded():
    assert not judge.found('long first fragment ... XYZ ... long last fragment',
                           'long first fragment followed by long last fragment')


def test_integrity_judge_nonce_reaches_the_underlying_request(integrity_offline, monkeypatch):
    users = []
    def call(model, effort, user):
        users.append(json.loads(user))
        return {'items': [{'id': 'F1', 'covered': False, 'evidence': []}]}
    monkeypatch.setattr(judge, '_call', call)
    for nonce in ('draw-one', 'draw-two'):
        monkeypatch.setenv('DPE_JUDGE_NONCE', nonce)
        judge.grade('q', 'report', [Item('F1', 'F', 'fact')], model='gpt-6.1-sol', effort='low')
    assert users[0] != users[1]
    assert users[0]['experiment_nonce'] == 'draw-one'


def test_integrity_cached_judge_preserves_workflow_price_and_zero_fresh_spend(integrity_offline, monkeypatch):
    def call(*args):
        ledger.CURRENT.get().calls.append(ledger.Call('gpt-6.1-sol', 'low', 'coverage', 100, 0, 10, 0,
                                                       0.0123, False, 1.0))
        return {'items': [{'id': 'F1', 'covered': False, 'evidence': []}]}
    monkeypatch.setattr(judge, '_call', call)
    first, second = ledger.Ledger(), ledger.Ledger()
    for book in (first, second):
        judge.grade('q', 'report', [Item('F1', 'F', 'fact')], model='gpt-6.1-sol', effort='low', book=book)
    assert second.summary()['usd'] == first.summary()['usd'] == 0.0123
    assert second.summary()['live_usd'] == 0


def test_integrity_http_verification_cost_is_counted_once(integrity_offline, monkeypatch):
    monkeypatch.setattr(cli.gold, 'gold', _gold)
    monkeypatch.setattr(cli.render, 'report', lambda result: '')
    monkeypatch.setattr(cli.judge, 'grade', lambda *args, **kwargs: [])
    monkeypatch.setattr(cli.checks, 'articles', lambda *args: [])
    monkeypatch.setattr(cli.checks, 'guardrails', lambda *args: {})
    result = _result()
    result['cost']['summary']['usd'] = 2.0
    result['identify_spend'] = {'usd': 1.3, 'by_provider': {
        'verification': {'requests': 1, 'input_tokens': 100, 'output_tokens': 20, 'usd': 1.2},
        'scoring': {'requests': 2, 'input_tokens': 200, 'output_tokens': 10, 'usd': 0.1}}}
    row = cli._judge_case(_case(), result, object(), 'gpt-6.1-sol', 'low')
    assert row['cost']['usd'] == 2.1 and row['cost']['scoring_usd'] == 0.1


def test_integrity_deepseek_records_retry_invalid_json_success_and_cache_hit(integrity_offline, monkeypatch):
    monkeypatch.setenv('DEEPSEEK_API_KEY', 'secret-test-key')
    monkeypatch.setattr(deepseek_review.time, 'sleep', lambda seconds: None)
    request = httpx.Request('POST', deepseek_review.URL)
    usage = {'prompt_tokens': 1000, 'completion_tokens': 200, 'prompt_cache_hit_tokens': 0}
    responses = iter([httpx.Response(503, request=request),
                      httpx.Response(200, json={'usage': usage, 'choices': [{'message': {'content': 'invalid'}}]},
                                     request=request),
                      httpx.Response(200, json={'usage': usage, 'choices': [{'message': {'content': '{"ok":true}'}}]},
                                     request=request)])
    monkeypatch.setattr(httpx.Client, 'post', lambda *args, **kwargs: next(responses))
    book = ledger.Ledger()
    token = ledger.CURRENT.set(book)
    try:
        for _ in range(2):
            assert deepseek_review.transport('instructions', 'PRIVATE DOCUMENT', {}, 'slot', 'low')[0] == {'ok': True}
    finally:
        ledger.CURRENT.reset(token)
    assert ledger.ATTEMPTS.exists()
    events = [json.loads(line) for line in ledger.ATTEMPTS.read_text().splitlines()]
    attempts = [e for e in events if e['event'] == 'attempt_finished']
    assert [e['status'] for e in attempts] == ['http_error', 'invalid_json', 'succeeded']
    assert attempts[0]['usd'] is None and attempts[0]['cost_status'] == 'unknown'
    assert all(e['request_hash'] and e['stage'] == 'document_review' for e in events)
    assert sum(e['event'] == 'cache_hit' for e in events) >= 1
    assert book.summary()['live_unknown_cost_attempts'] == 1
    assert book.summary()['unknown_cost_attempts'] == 2  # original workflow plus its cached replay
    assert 'PRIVATE DOCUMENT' not in ledger.ATTEMPTS.read_text()
    assert 'secret-test-key' not in ledger.ATTEMPTS.read_text()


@pytest.mark.parametrize('payload', [None, [], {'items': 'bad'}, {'items': [None]},
                                     {'items': [{'id': 'unknown', 'covered': True, 'evidence': []}]}])
def test_integrity_malformed_payloads_fail_all_expected_checks(integrity_offline, monkeypatch, payload):
    monkeypatch.setattr(judge, '_call', lambda *args: payload)
    items = [Item('F1', 'F', 'fact'), Item('R1', 'R', 'no compliance certification')]
    verdicts = judge.grade('q', 'report', items, model='gpt-6.1-sol', effort='low')
    assert len(verdicts) == 2 and all(not v.passed and v.note for v in verdicts)


def test_integrity_violations_require_all_exact_ordered_fragments(integrity_offline, monkeypatch):
    report = 'first long fragment 25 m final long fragment'
    assert judge.found('first long fragment ... 25 m ... final long fragment', report)
    assert judge.found('25', report)
    assert not judge.found('First long fragment', report)
    assert not judge.found('final long fragment ... first long fragment', report)
    monkeypatch.setattr(judge, '_call', lambda *args: {'items': [
        {'id': 'R1', 'covered': False, 'evidence': ['first long fragment', 'invented']} ]})
    verdict = judge.grade('q', report, [Item('R1', 'R', 'no compliance certification')],
                          model='gpt-6.1-sol', effort='low')[0]
    assert not verdict.passed and verdict.note == 'unverified'


@pytest.mark.parametrize('offline', [True, False])
def test_integrity_disabled_review_and_legitimate_lexical_stages_are_complete(integrity_offline, offline):
    meta = {'offline': offline, 'review_resolved': {'enabled': False},
            'identify_config': {'screen': 'bm25', 'rerank': 'none', 'verifier': 'none'}}
    result = _result()
    result['expected_stages'] = cli._expectations(meta, _case())
    if not offline:
        result['case']['intake']['model'] = {'status': 'not_needed'}
        result['case']['identify'] = {'mode': 'live', 'trace': {'verifier': 'not run: verifier off'}}
    assert checks.completion(result) == []
    assert checks.guardrails(_case(), result, object())['ran'][0]


@pytest.mark.parametrize('fault', ['review_off', 'model_failed', 'fallback', 'verify_failed',
                                  'missing_screen', 'partial_screen'])
def test_integrity_incomplete_expected_work_has_failed_checks_without_judge_calls(integrity_offline, monkeypatch, fault):
    result = _result()
    result['expected_stages'] = {'intake_model': True, 'document_review': True, 'identify': True,
                                 'identify_stages': ['screen', 'rerank', 'verify'], 'verify': True,
                                 'exhaustive': True}
    result['case']['intake'] = {'model': {'status': 'live'}, 'review': {'status': 'live'}}
    trace = {'verifier': '1 picked, 0 dropped', 'exhaustive': True, 'articles_expected': 2080,
             'articles_scored': 2080, 'stages': [{'stage': s, 'requests': 1} for s in ('screen', 'rerank', 'verify')]}
    result['case']['identify'] = {'mode': 'live', 'trace': trace}
    if fault == 'review_off':
        result['case']['intake']['review']['status'] = 'off'
    elif fault == 'model_failed':
        result['case']['intake']['model']['status'] = 'failed'
    elif fault == 'fallback':
        result['case']['identify']['mode'] = 'bm25_fallback'
    elif fault == 'verify_failed':
        trace['verifier'] = 'failed: unavailable'
    elif fault == 'missing_screen':
        trace['stages'].pop(0)
    else:
        trace['articles_scored'] = 100
    monkeypatch.setattr(cli.gold, 'gold', _gold)
    def no_judge(*args, **kwargs):
        pytest.fail('incomplete work should be caught before dispatching a judge')
    monkeypatch.setattr(cli.judge, 'grade', no_judge)
    row = cli._judge_case(_case(), result, object(), 'gpt-6.1-sol', 'low')
    assert len(row['checks']) == 3 and all(not c['passed'] and not c['scored'] for c in row['checks'])
    assert row['failure_reasons'] and not row['guardrails']['ran'][0]


def test_integrity_resume_is_nonzero_for_previously_failed_output_and_preserves_history(integrity_offline, monkeypatch):
    case = _case()
    monkeypatch.setattr(cli.corpus, 'select', lambda split: [case])
    monkeypatch.setattr(cli, 'ProcessPoolExecutor', _ImmediatePool)
    monkeypatch.setattr(cli, '_meta', lambda args: {'offline': True})
    monkeypatch.setattr(cli, '_manifest', lambda *args: {'sources': 'unchanged'})
    monkeypatch.setattr(cli.sut, 'run_case', lambda case: {**_result(), 'errors': ['worker: ReadTimeout']})
    assert cli.main(['run', '--name', 'resume', '--offline']) == 1
    folder = cli.RUNS / 'resume'
    meta = (folder / 'meta.json').read_bytes()
    first = (folder / 'cases' / f'{case.id}.json').read_bytes()
    monkeypatch.setattr(cli.sut, 'run_case', lambda case: pytest.fail('resume must not silently rerun'))
    assert cli.main(['run', '--name', 'resume', '--offline']) == 1
    assert (folder / 'meta.json').read_bytes() == meta
    assert (folder / 'cases' / f'{case.id}.json').read_bytes() == first
    monkeypatch.setattr(cli.sut, 'run_case', lambda case: _result())
    assert cli.main(['run', '--name', 'resume', '--offline', '--force']) == 0
    assert (folder / 'meta.json').read_bytes() == meta
    assert next((folder / 'cases' / 'history').glob('*.json')).read_bytes() == first
    current = json.loads((folder / 'cases' / f'{case.id}.json').read_text())
    assert current['manifest_fingerprint'] == json.loads(meta)['manifest_fingerprint']


def test_integrity_legacy_runs_are_readable_labelled_and_cannot_be_upgraded(integrity_offline):
    folder = cli.RUNS / 'legacy'
    folder.mkdir(parents=True)
    (folder / 'meta.json').write_text('{"engine_tree":"old"}')
    assert cli.main(['run', '--name', 'legacy', '--force', '--offline']) == 2
    assert (folder / 'meta.json').read_text() == '{"engine_tree":"old"}'
    row_path = folder / 'score-old.jsonl'
    row_path.write_text('{"case_id":"dev-case"}\n')
    row = score.load_rows(row_path)[0]
    assert row['validator_version'] == 'old-validator' and row['provenance'] == 'legacy/unverified'
    assert 'validator_version' not in row_path.read_text()


@pytest.fixture
def integrity_sources(integrity_offline, monkeypatch):
    import engine.codes
    root = integrity_offline / 'repo'
    metadata, harness = root / 'Data Prompts', root / 'harness'
    for path in (root / 'engine' / 'example.py', root / 'codedb' / 'lookup.py', root / 'codedb.sqlite',
                 metadata / 'index.json', *(metadata / 'sample' / n for n in
                     ('prompt.txt', 'source.json', 'evaluation.json', 'attachment.txt')),
                 *(harness / n for n in ('judge.py', 'gold.py', 'texts.py', 'corpus.py', 'availability.json'))):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text('fixture contents')
    attachment = corpus.Attachment('attachment.txt', 'input', 'recorded-sha', 16)
    case = SimpleNamespace(id='dev-case', folder='sample', attachments=(attachment,),
                           tier=corpus.TIERS[0], case_type='issued_variance', prompt='offline request',
                           path=lambda a: metadata / 'sample' / a.filename)
    sides = {'dev-case': 'dev'}
    monkeypatch.setattr(manifest, 'HARNESS', harness)
    monkeypatch.setattr(corpus, 'REPO', root)
    monkeypatch.setattr(corpus, 'METADATA_ROOT', metadata)
    monkeypatch.setattr(corpus, 'load', lambda: (case,))
    monkeypatch.setattr(corpus, 'split', lambda: dict(sides))
    monkeypatch.setattr(engine.codes, 'default_db', lambda: root / 'codedb.sqlite')
    return root, case, sides


@pytest.mark.parametrize('change', ['config', 'engine', 'harness', 'corpus', 'split', 'gold', 'availability',
                                   'codedb', 'attachment'])
def test_integrity_manifest_changes_for_every_protected_input(integrity_sources, change):
    root, case, sides = integrity_sources
    args = SimpleNamespace(split='dev', limit=0)
    meta = {'offline': True, 'review_resolved': {'model': 'deepseek-flash', 'effort': 'max', 'transport': 'deepseek'}}
    before = manifest.fingerprint(manifest.build(args, meta, [case]))
    paths = {'engine': root / 'engine' / 'example.py', 'harness': root / 'harness' / 'judge.py',
             'corpus': root / 'Data Prompts' / 'sample' / 'source.json', 'gold': root / 'harness' / 'gold.py',
             'availability': root / 'harness' / 'availability.json', 'codedb': root / 'codedb.sqlite',
             'attachment': root / 'Data Prompts' / 'sample' / 'attachment.txt'}
    if change == 'config':
        meta['review_resolved']['effort'] = 'high'
    elif change == 'split':
        sides[case.id] = 'holdout'
    else:
        paths[change].write_text('changed source')
    assert manifest.fingerprint(manifest.build(args, meta, [case])) != before


def test_integrity_manifest_hashes_repeated_attachment_only_once(integrity_sources, monkeypatch):
    _, case, _ = integrity_sources
    original = manifest.file_hash
    seen = []
    def counted(path):
        seen.append(path)
        return original(path)
    monkeypatch.setattr(manifest, 'file_hash', counted)
    manifest.build(SimpleNamespace(split='dev', limit=0), {}, [case, case])
    assert seen.count(case.path(case.attachments[0])) == 1


def test_integrity_deepseek_terminal_timeouts_are_durable_unknown_cost(integrity_offline, monkeypatch):
    monkeypatch.setenv('DEEPSEEK_API_KEY', 'test-secret')
    monkeypatch.setattr(deepseek_review.time, 'sleep', lambda seconds: None)
    def timeout(*args, **kwargs):
        raise httpx.ReadTimeout('private provider exception content')
    monkeypatch.setattr(httpx.Client, 'post', timeout)
    book = ledger.Ledger()
    token = ledger.CURRENT.set(book)
    try:
        with pytest.raises(httpx.ReadTimeout):
            deepseek_review.chat_json('deepseek-flash', 'max', 'SYSTEM', 'DOCUMENT', stage='judge')
    finally:
        ledger.CURRENT.reset(token)
    events = [json.loads(line) for line in ledger.ATTEMPTS.read_text().splitlines()]
    assert len(events) == 8
    finished = [e for e in events if e['event'] == 'attempt_finished']
    assert len(finished) == 4 and all(e['usd'] is None and e['status'] == 'transport_error' for e in finished)
    assert book.summary()['usd'] == 0 and book.summary()['unknown_cost_attempts'] == 4
    assert 'private provider exception content' not in ledger.ATTEMPTS.read_text()


def test_integrity_attempt_ledger_concurrent_append_is_lossless(integrity_offline):
    from concurrent.futures import ThreadPoolExecutor
    with ThreadPoolExecutor(8) as pool:
        list(pool.map(lambda i: ledger.attempt_event('cache_hit', request_hash=f'request-{i}', stage='judge',
                                                     model='deepseek-flash', effort='max', usd=0.1), range(80)))
    rows = [json.loads(line) for line in ledger.ATTEMPTS.read_text().splitlines()]
    assert len(rows) == len({r['request_hash'] for r in rows}) == 80


def test_integrity_judge_spend_is_retained_on_a_failed_judge(integrity_offline, monkeypatch):
    monkeypatch.setattr(cli.gold, 'gold', _gold)
    monkeypatch.setattr(cli.render, 'report', lambda result: 'report')
    def failed_grade(*args, book, **kwargs):
        book.calls.append(ledger.Call('deepseek-flash', 'max', 'judge', 100, 0, 10, 0, 0.01, False, 1))
        raise deepseek_review.InvalidJson('invalid output')
    monkeypatch.setattr(cli.judge, 'grade', failed_grade)
    row = cli._judge_case(_case(), _result(), object(), 'deepseek-flash', 'max')
    assert row['judge_usd'] == row['judge_live_usd'] == 0.01
    assert len(row['checks']) == 3 and row['failure_reasons'] == ['judge_error:InvalidJson']


def test_integrity_unknown_judge_spend_survives_exception_into_summary(integrity_offline, monkeypatch):
    monkeypatch.setattr(cli.gold, 'gold', _gold)
    monkeypatch.setattr(cli.render, 'report', lambda result: 'report')
    def failed_grade(*args, book, **kwargs):
        book.calls.append(ledger.Call('deepseek-flash', 'max', 'judge', 0, 0, 0, 0, None, False, 1))
        raise httpx.ReadTimeout('offline timeout')
    monkeypatch.setattr(cli.judge, 'grade', failed_grade)
    summary = score.summarize([cli._judge_case(_case(), _result(), object(), 'deepseek-flash', 'max')])
    assert summary['cost']['judge_unknown_cost_attempts'] == 1
    assert not summary['cost']['cost_complete']


def test_integrity_deepseek_cache_keeps_frozen_price_without_repricing(integrity_offline, monkeypatch):
    monkeypatch.setenv('DEEPSEEK_API_KEY', 'test-secret')
    response = httpx.Response(200, request=httpx.Request('POST', deepseek_review.URL), json={
        'usage': {'prompt_tokens': 1000, 'completion_tokens': 200},
        'choices': [{'message': {'content': '{"ok":true}'}}]})
    monkeypatch.setattr(httpx.Client, 'post', lambda *args, **kwargs: response)
    book = ledger.Ledger()
    token = ledger.CURRENT.set(book)
    try:
        deepseek_review.chat_json('deepseek-flash', 'max', 'instructions', 'private', stage='document_review')
        first = book.summary()['usd']
        def no_reprice(*args):
            pytest.fail('cache replay must keep the original price')
        monkeypatch.setattr(deepseek_review, 'price', no_reprice)
        monkeypatch.setattr(httpx.Client, 'post', no_reprice)
        deepseek_review.chat_json('deepseek-flash', 'max', 'instructions', 'private', stage='document_review')
    finally:
        ledger.CURRENT.reset(token)
    assert book.summary()['usd'] == 2 * first and book.summary()['live_usd'] == first


def _append_integrity_events(path):
    from pathlib import Path
    ledger.ATTEMPTS = Path(path)
    for _ in range(10):
        ledger.attempt_event('cache_hit', request_hash='multiprocess', stage='judge', model='deepseek-flash', effort='max')


def test_integrity_attempt_ledger_is_safe_across_processes(integrity_offline):
    import multiprocessing
    from concurrent.futures import ProcessPoolExecutor
    with ProcessPoolExecutor(3, mp_context=multiprocessing.get_context('spawn')) as pool:
        list(pool.map(_append_integrity_events, [str(ledger.ATTEMPTS)] * 6))
    rows = [json.loads(line) for line in ledger.ATTEMPTS.read_text().splitlines()]
    assert len(rows) == len({r['attempt_id'] for r in rows}) == 60


def test_integrity_split_counts_remain_frozen(integrity_offline):
    assert len(corpus.select('dev')) == 334
    assert len(corpus.select('holdout')) == 319


@pytest.mark.parametrize('tamper', ['availability', 'output', 'manifest'])
def test_integrity_scoring_rejects_provenance_mismatch_without_dispatch(integrity_sources, monkeypatch, tamper):
    import engine.codes
    root, case, _ = integrity_sources
    monkeypatch.setattr(corpus, 'select', lambda split: [case])
    monkeypatch.setattr(cli.gold, 'gold', _gold)
    monkeypatch.setattr(engine.codes, 'Codes', lambda path: object())
    monkeypatch.setattr(cli, '_judge_case', lambda *args: pytest.fail('unverified outputs cannot be sent to a judge'))
    folder = cli.RUNS / 'provenance' / 'cases'
    folder.mkdir(parents=True)
    frozen = manifest.build(SimpleNamespace(split='dev', limit=0), {'offline': True}, [case])
    fingerprint = manifest.fingerprint(frozen)
    (folder.parent / 'manifest.json').write_text(json.dumps(frozen))
    (folder.parent / 'meta.json').write_text(json.dumps({'offline': True, 'manifest_fingerprint': fingerprint}))
    result = {**_result(), 'manifest_fingerprint': fingerprint}
    if tamper == 'availability':
        (root / 'harness' / 'availability.json').write_text('changed labels')
    elif tamper == 'output':
        result['manifest_fingerprint'] = 'other-experiment'
    else:
        frozen['version'] = 'tampered'
        (folder.parent / 'manifest.json').write_text(json.dumps(frozen))
    (folder / f'{case.id}.json').write_text(json.dumps(result))
    assert cli.main(['score', '--name', 'provenance']) == 1
    row = json.loads(next(folder.parent.glob('score-*.jsonl')).read_text())
    assert row['provenance'].startswith('unverified:')
    assert len(row['checks']) == 3 and all(not c['passed'] for c in row['checks'])


def test_integrity_guardrails_stay_outside_accuracy_and_fail_exit(integrity_offline, monkeypatch):
    import engine.codes
    case = _case()
    monkeypatch.setattr(corpus, 'select', lambda split: [case])
    monkeypatch.setattr(engine.codes, 'Codes', lambda path: object())
    monkeypatch.setattr(engine.codes, 'default_db', lambda: integrity_offline / 'db')
    def row(*args):
        return {'case_id': case.id, 'tier': case.tier, 'case_type': case.case_type, 'scored': True,
                'checks': [{'id': 'F1', 'kind': 'F', 'passed': True}], 'failure_reasons': [],
                'guardrails': {'ran': (True, ''), 'no_claims': (False, 'outright claim')}}
    monkeypatch.setattr(cli, '_judge_case', row)
    folder = cli.RUNS / 'guardrail' / 'cases'
    folder.mkdir(parents=True)
    (folder / f'{case.id}.json').write_text(json.dumps(_result()))
    assert cli.main(['score', '--name', 'guardrail']) == 1
    summary = json.loads(next(folder.parent.glob('*.summary.json')).read_text())
    assert summary['accuracy'] == 1.0 and summary['checks'] == 1
    assert summary['guardrails']['no_claims']['passed'] == 0


def test_integrity_legacy_deepseek_cache_is_not_silently_repriced_or_rewritten(integrity_offline):
    body = {'model': 'deepseek-flash', 'reasoning_effort': 'max', 'max_tokens': deepseek_review.MAX_TOKENS,
            'response_format': {'type': 'json_object'},
            'messages': [{'role': 'system', 'content': 'instructions'}, {'role': 'user', 'content': 'private'}]}
    key = ledger._key(deepseek_review.URL, body)
    data = {'usage': {'prompt_tokens': 1000, 'completion_tokens': 200},
            'choices': [{'message': {'content': '{"ok":true}'}}]}
    ledger._store(key, {'response': data, 'seconds': 2.0, 'peak': False})
    path = ledger.CACHE / key[:2] / f'{key}.json'
    before = path.read_bytes()
    book = ledger.Ledger()
    token = ledger.CURRENT.set(book)
    try:
        assert deepseek_review.chat_json('deepseek-flash', 'max', 'instructions', 'private', stage='judge')[0]['ok']
    finally:
        ledger.CURRENT.reset(token)
    assert path.read_bytes() == before
    assert book.calls[0].status == 'legacy_unverified' and book.calls[0].usd is None
    assert book.summary()['live_calls'] == 0


def test_integrity_unknown_deepseek_model_fails_before_dispatch(integrity_offline):
    with pytest.raises(ValueError, match='local price table'):
        deepseek_review.chat_json('unpriced-model', 'max', 's', 'u', stage='judge')
    assert not ledger.ATTEMPTS.exists()
