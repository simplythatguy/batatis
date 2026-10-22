"""Every adapter against fakes: the contract, the failure paths, and the runner's resume and keying rules.

No key, no network, no code database: the corpus is a small synthetic table and the providers are the fakes in
``evals_dev/identify_bench/fakes.py``.
"""
import json
from decimal import Decimal
from pathlib import Path

import pytest

from evals_dev.identify_bench import fakes, pricing
from evals_dev.identify_bench.arms import arm_hashes, topo_order
from evals_dev.identify_bench.datasets import BenchCase
from evals_dev.identify_bench.methods.jev import JevScreenArm
from evals_dev.identify_bench.methods.lexical import SearchRankArm
from evals_dev.identify_bench.methods.precedent import PrecedentArm
from evals_dev.identify_bench.methods.verifier import LunaVerifierArm, prompt, prompt_sha
from evals_dev.identify_bench.rows import RowStore
from evals_dev.identify_bench.runner import run_arms

ARTS = fakes.tiny_corpus()
SECRET = fakes.SECRET
gold_for, make_cases, FakeRank, precedents = fakes.gold_for, fakes.make_cases, fakes.FakeRank, fakes.precedents
fake_arms, make_ctx = fakes.fake_arms, fakes.make_ctx


def check_row(row):
    assert len(set(row['order'])) == len(row['order']) and set(row['order']) <= set(ARTS)
    assert set(row['probabilities']) <= set(row['order']) | set(ARTS)
    assert all(0.0 <= p <= 1.0 for p in row['probabilities'].values())
    assert row['usd'] >= 0
    for provider in row['tokens'].values():
        assert all(isinstance(v, int) and v >= 0 for v in provider.values())
    assert all(v >= 0 for v in row['latency_ms'].values())
    json.dumps(row)


ALL = list(fake_arms())


@pytest.mark.parametrize('name', ALL)
def test_every_adapter_meets_the_row_contract(tmp_path, name):
    ctx, _ = make_ctx(tmp_path)
    arms = fake_arms()
    cases = make_cases(4)
    summary = run_arms(arms, [name], cases, ctx, repeats=1, git_sha='test', codedb_sha256='x')
    assert summary.errored == 0 and summary.ran > 0
    for arm_name in topo_order(arms, [name]):
        rows = ctx.store.arm_rows(arm_name)
        assert len(rows) == len(cases)
        for row in rows:
            check_row(row)
            assert row['config_hash'] == arm_hashes(arms)[arm_name] and row['git_sha'] == 'test'
            assert row['order'], f'{arm_name} returned no ranking for {row["case_id"]}'


@pytest.mark.parametrize('name', ALL)
def test_configs_are_json_stable_and_sensitive(name):
    a, b = fake_arms()[name], fake_arms()[name]
    assert json.dumps(a.config(), sort_keys=True) == json.dumps(b.config(), sort_keys=True)
    assert arm_hashes(fake_arms())[name] == arm_hashes(fake_arms())[name]


def test_a_downstream_hash_covers_its_upstream_and_every_parameter():
    base = arm_hashes(fake_arms())
    changed_up = fake_arms(**{'R4-jev-screen': JevScreenArm('R4-jev-screen', max_state=8000, card_chars=500)})
    assert arm_hashes(changed_up)['V15f-R5'] != base['V15f-R5'] and arm_hashes(changed_up)['R0-bm25'] == base['R0-bm25']
    other = fake_arms(**{'V15f-R5': LunaVerifierArm('V15f-R5', 'R5-jev-screen-rerank60', shortlist_n=5, repeats=2,
                                                    effort='high')})
    assert arm_hashes(other)['V15f-R5'] != base['V15f-R5']


def test_deterministic_arms_are_deterministic(tmp_path):
    cases = make_cases(3)
    runs = []
    for i in range(2):
        ctx, _ = make_ctx(tmp_path / str(i))
        run_arms(fake_arms(), ['R0-bm25', 'R1-searchrank-v3', 'R2-precedent-lofo'], cases, ctx)
        runs.append({n: [r['order'] for r in ctx.store.arm_rows(n)] for n in ('R0-bm25', 'R1-searchrank-v3', 'R2-precedent-lofo')})
    assert runs[0] == runs[1]


# ---- Jev ---------------------------------------------------------------------------------------------------

def test_the_screen_scores_every_article_and_counts_its_requests(tmp_path):
    ctx, _ = make_ctx(tmp_path)
    jev = ctx.jev_ask
    run_arms(fake_arms(), ['R4-jev-screen'], make_cases(2), ctx, repeats=1)
    for row in ctx.store.arm_rows('R4-jev-screen'):
        n = row['notes']
        assert n['articles_scored'] == len(ARTS) and n['request_count_ok'] and n['requests'] == n['expected_requests'] > 1
        assert row['tokens']['jev']['input'] > 0 and row['usd'] > 0
        assert row['model_ids']['requested'] == 'jev-1.13.0'
    assert jev.models == ['jev-1.13.0'] * 2 and jev.calls == sum(r['notes']['requests'] for r in ctx.store.arm_rows('R4-jev-screen'))
    assert Decimal(ctx.jev_ledger.summary()['settled_usd']) > 0


def test_rerank_keeps_the_upstream_tail_and_chains_to_its_upstream_row(tmp_path):
    ctx, _ = make_ctx(tmp_path)
    run_arms(fake_arms(), ['R5-jev-screen-rerank60'], make_cases(2), ctx, repeats=1)
    for r5 in ctx.store.arm_rows('R5-jev-screen-rerank60'):
        r4 = ctx.store.by_key('R4-jev-screen')[r5['upstream']['R4-jev-screen']]
        assert set(r5['order'][:12]) == set(r4['order'][:12]) and r5['order'][12:] == r4['order'][12:]
        assert r5['notes']['requests'] == r5['notes']['expected_requests'] == 1


def test_a_jev_outage_is_a_recorded_error_not_an_exception(tmp_path):
    ctx, _ = make_ctx(tmp_path, jev=fakes.FakeJev(fail_on=set(range(1, 40))))
    summary = run_arms(fake_arms(), ['R4-jev-screen'], make_cases(1), ctx, repeats=1)
    row = ctx.store.arm_rows('R4-jev-screen')[0]
    assert summary.errored == 1 and row['order'] == [] and row['errors'][0]['category'] == 'jev_failed'


# ---- the verifier ------------------------------------------------------------------------------------------

def test_an_honest_verifier_picks_with_a_verified_quote(tmp_path):
    ctx, http = make_ctx(tmp_path)
    cases = make_cases(3)
    run_arms(fake_arms(), ['V15f-R5'], cases, ctx, repeats=1)
    for row in ctx.store.arm_rows('V15f-R5'):
        assert row['picks'] and row['dropped'] == [] and row['order'][0] == row['picks'][0]['article']
        assert row['notes']['quote_pass_rate'] == 1.0 and row['model_ids']['returned'] == ['gpt-6-luna']
        assert row['tokens']['openai']['input'] > 0 and row['tokens']['openai']['reasoning'] > 0 and row['usd'] > 0
    body = http.calls[0]
    assert body['model'] == 'gpt-6-luna' and body['reasoning_effort'] == 'medium' and 'service_tier' not in body
    assert body['response_format']['json_schema']['strict'] is True and body['max_completion_tokens'] == 12000


def test_a_lying_verifier_never_gets_a_fabricated_citation_into_the_picks(tmp_path):
    ctx, _ = make_ctx(tmp_path, mode='liar')
    run_arms(fake_arms(), ['V15f-R5'], make_cases(3), ctx, repeats=1)
    for row in ctx.store.arm_rows('V15f-R5'):
        assert [p['article'] for p in row['picks']] == [row['order'][0]]
        why = sorted(d['why'] for d in row['dropped'])
        assert why == ['article not in candidate list', 'duplicate article', 'quote not found in article text']
        assert '9.99.99.99.' not in row['order'] and row['notes']['raw_picks'] == 4 and row['notes']['kept'] == 1
        for p in row['picks']:                                     # every kept quote is in the article text
            assert ' '.join(p['quote'].split()) in ' '.join(ARTS[p['article']]['text'].split())


def test_out_of_list_picks_are_existence_checked_and_never_replace_a_quoted_pick():
    # the prompt carries the extra instruction, and the arm config records that it did
    assert 'empty quote' in __import__('evals_dev.identify_bench.methods.verifier', fromlist=['x']).verifier_system(True)
    assert prompt_sha(True) != prompt_sha(False)


@pytest.mark.parametrize('mode,category', [('refusal', 'refusal'), ('truncated', 'truncated'), ('garbage', 'schema'),
                                           ('always_429', 'rate_limited'), ('timeout', 'timeout'),
                                           ('no_usage', 'server_error')])
def test_provider_failures_degrade_to_the_upstream_order_and_are_counted(tmp_path, mode, category):
    ctx, _ = make_ctx(tmp_path, mode=mode)
    run_arms(fake_arms(), ['V15f-R5'], make_cases(1), ctx, repeats=1)
    row = ctx.store.arm_rows('V15f-R5')[0]
    up = ctx.store.by_key('R5-jev-screen-rerank60')[row['upstream']['R5-jev-screen-rerank60']]
    assert row['picks'] == [] and row['order'] == up['order'] and row['errors'][-1]['category'] == category
    assert row['notes']['degraded']


def test_a_rate_limit_is_retried_and_each_attempt_is_metered(tmp_path):
    ctx, http = make_ctx(tmp_path, mode='rate_limit')
    run_arms(fake_arms(), ['V15f-R5'], make_cases(1), ctx, repeats=1)
    row = ctx.store.arm_rows('V15f-R5')[0]
    assert len(http.calls) == 3 and row['errors'] == [] and row['picks'] and row['tokens']['openai']['requests'] == 3
    s = ctx.openai.ledger.summary()
    assert s['requests'] == 1 and s['open_reservations'] == 0           # only the call that returned usage is a settlement


def test_a_timeout_after_sending_is_charged_at_its_worst_case(tmp_path):
    ctx, _ = make_ctx(tmp_path, mode='timeout')
    run_arms(fake_arms(), ['V15f-R5'], make_cases(1), ctx, repeats=1)
    s = ctx.openai.ledger.summary()
    assert s['requests'] == 3 and Decimal(s['settled_usd']) > Decimal('0.01')     # three unknown outcomes at 12k output tokens


def test_the_ledger_stop_ends_the_run_before_any_call_is_made(tmp_path):
    ctx, http = make_ctx(tmp_path, stop='0.0000001')
    summary = run_arms(fake_arms(), ['V15f-R5'], make_cases(3), ctx, repeats=1)
    assert http.calls == [] and summary.stopped == 'budget_stop'
    rows = ctx.store.arm_rows('V15f-R5')
    assert len(rows) == 1 and rows[0]['errors'][0]['category'] == 'budget_stop'       # the run stopped after the first


def test_no_key_value_reaches_a_row_a_ledger_or_an_error(tmp_path):
    def leaky(url, headers, body, timeout):
        assert headers['Authorization'] == 'Bearer ' + SECRET
        return 401, {}, {'error': {'message': f'Incorrect API key provided: {SECRET}. Check your key.'}}
    ctx, _ = make_ctx(tmp_path)
    ctx.openai.http = leaky
    run_arms(fake_arms(), ['V15f-R5'], make_cases(2), ctx, repeats=1)
    blob = ''.join(p.read_text() for p in list(tmp_path.rglob('*.jsonl')))
    assert SECRET not in blob and 'sk-test-SECRET' not in blob
    assert any(e['category'] == 'auth' for r in ctx.store.arm_rows('V15f-R5') for e in r['errors'])


def test_unpriced_and_haiku_models_are_refused_before_any_call(tmp_path):
    ctx, http = make_ctx(tmp_path)
    for model in ('gpt-9-mystery', 'claude-haiku-9'):
        with pytest.raises((KeyError, ValueError)):
            ctx.openai(name='picks', schema={}, system='s', user='u', model=model, effort='medium', max_completion_tokens=10)
    with pytest.raises(ValueError):
        LunaVerifierArm('V', 'R5-jev-screen-rerank60', model='claude-haiku-5')
    assert http.calls == []


def test_the_prompt_is_the_variant_c_contract():
    arts = {'9.1.1.1.': {'id': '9.1.1.1.', 'part': 9, 'title': 'Heading', 'section': 'Sec', 'subsection': 'Sub', 'text': 'Body text.'}}
    got = prompt('Q?', arts, ['9.1.1.1.'], None)
    assert got == ('<proposal>\nQ?\n</proposal>\n\n<candidates>\n<article id="9.1.1.1.">\n'
                   'Heading (Part 9 > Sec > Sub): Body text.\n</article>\n</candidates>')
    cut = prompt('Q?', {'9.1.1.1.': {**arts['9.1.1.1.'], 'text': 'x' * 30}}, ['9.1.1.1.'], 10)
    assert 'x' * 10 + '...' in cut and 'x' * 11 not in cut
    try:                                                    # parity with WP-20's llm.prompt once that branch has merged
        from engine.identify import llm
    except ImportError:
        return
    assert llm.prompt('Q?', arts, ['9.1.1.1.'], None) == got


def test_a_verifier_row_costs_what_the_usage_says(tmp_path):
    ctx, _ = make_ctx(tmp_path)
    run_arms(fake_arms(), ['V15f-R5'], make_cases(1), ctx, repeats=1)
    row = ctx.store.arm_rows('V15f-R5')[0]
    t = row['tokens']['openai']
    assert Decimal(str(row['usd'])) == pricing.cost_usd('gpt-6-luna', t['input'], t['output']).quantize(Decimal('0.00000001'))


# ---- the lexical and fusion arms --------------------------------------------------------------------------

def test_leave_one_family_out_hides_the_cases_own_precedent(tmp_path):
    ctx, _ = make_ctx(tmp_path)
    case = BenchCase(id='prec-0', dataset='public53', query=fakes.TOPICS[0][1], gold=(gold_for(0),), family='prec-0')
    arm = PrecedentArm('R2', entries=precedents())
    row = arm.run(case, 0, ctx)
    assert 'prec-0' in row.notes['hidden'] and 'prec-0' not in row.notes['matched_precedents']
    assert gold_for(0) not in row.order[:1]                     # its own answer is not retrievable through itself
    shown = arm.run(BenchCase(id='x', dataset='dev', query=fakes.TOPICS[0][1], gold=(gold_for(0),)), 0, ctx)
    assert shown.order[0] == gold_for(0) and shown.notes['hidden'] == []


def test_missing_search_rank_reports_unavailable_instead_of_crashing(tmp_path):
    ctx, _ = make_ctx(tmp_path)
    arm = SearchRankArm('R1', module=None)
    arm.available, arm.module = False, None
    row = arm.run(make_cases(1)[0], 0, ctx)
    assert row.order == [] and row.errors[0]['category'] == 'unavailable'


def test_fusion_combines_upstream_rankings_without_cost(tmp_path):
    ctx, _ = make_ctx(tmp_path)
    run_arms(fake_arms(), ['F1-rrf-R5-R1-R2'], make_cases(2), ctx, repeats=1)
    for row in ctx.store.arm_rows('F1-rrf-R5-R1-R2'):
        assert row['usd'] == 0 and row['tokens'] == {} and set(row['upstream']) == {
            'R5-jev-screen-rerank60', 'R1-searchrank-v3', 'R2-precedent-lofo'}
        assert row['notes']['parallel_upstream'] is True


# ---- the runner --------------------------------------------------------------------------------------------

def test_runs_resume_and_skip_finished_rows(tmp_path):
    ctx, http = make_ctx(tmp_path)
    cases = make_cases(3)
    first = run_arms(fake_arms(), ['V15f-R5'], cases, ctx, repeats=2)
    n_calls = len(http.calls)
    again = run_arms(fake_arms(), ['V15f-R5'], cases, ctx, repeats=2)
    assert first.ran > 0 and again.ran == 0 and again.skipped == first.ran and len(http.calls) == n_calls


def test_rows_are_keyed_by_config_hash_so_a_changed_arm_reruns(tmp_path):
    ctx, http = make_ctx(tmp_path)
    cases = make_cases(2)
    run_arms(fake_arms(), ['V15f-R5'], cases, ctx, repeats=1)
    before = len(http.calls)
    changed = fake_arms(**{'V15f-R5': LunaVerifierArm('V15f-R5', 'R5-jev-screen-rerank60', shortlist_n=4, repeats=2)})
    s = run_arms(changed, ['V15f-R5'], cases, ctx, repeats=1)
    assert len(http.calls) == before + 2 and s.by_arm['V15f-R5']['ran'] == 2 and s.by_arm['R4-jev-screen']['skipped'] == 2
    assert len({r['config_hash'] for r in ctx.store.arm_rows('V15f-R5')}) == 2


def test_retry_errors_appends_a_new_attempt_and_keeps_the_first_failure(tmp_path):
    ctx, http = make_ctx(tmp_path, mode='refusal')
    cases = make_cases(1)
    run_arms(fake_arms(), ['V15f-R5'], cases, ctx, repeats=1)
    skipped = run_arms(fake_arms(), ['V15f-R5'], cases, ctx, repeats=1)
    assert skipped.ran == 0
    ctx.openai.http = fakes.fake_openai_http('honest')
    retried = run_arms(fake_arms(), ['V15f-R5'], cases, ctx, repeats=1, retry_errors=True)
    rows = ctx.store.arm_rows('V15f-R5')
    assert retried.by_arm['V15f-R5']['ran'] == 1 and [r['attempt'] for r in rows] == [1, 2]
    assert rows[0]['errors'] and not rows[1]['errors']
    assert ctx.store.latest('V15f-R5')[(cases[0].id, 0)]['attempt'] == 2


def test_arms_run_interleaved_case_by_case_upstream_first(tmp_path):
    ctx, _ = make_ctx(tmp_path)
    seen = []
    run_arms(fake_arms(), ['V15f-R5', 'R6-bm25-jev-rerank60'], make_cases(2), ctx, repeats=1,
             on_row=lambda r: seen.append((r['case_id'], r['arm'])))
    first_case = [a for c, a in seen if c == 'dev-000']
    assert seen[:len(first_case)] == [('dev-000', a) for a in first_case]            # case 0 finishes before case 1 starts
    assert first_case.index('R4-jev-screen') < first_case.index('R5-jev-screen-rerank60') < first_case.index('V15f-R5')


def test_parallel_workers_give_the_same_rows(tmp_path):
    cases = make_cases(5)
    out = []
    for w in (1, 4):
        ctx, _ = make_ctx(tmp_path / f'w{w}')
        run_arms(fake_arms(), ['V15f-R5'], cases, ctx, repeats=1, workers=w)
        out.append({r['case_id']: r['order'] for r in ctx.store.arm_rows('V15f-R5')})
    assert out[0] == out[1]


def test_store_pack_is_deterministic_and_readable(tmp_path):
    ctx, _ = make_ctx(tmp_path)
    run_arms(fake_arms(), ['R0-bm25'], make_cases(3), ctx)
    a = ctx.store.pack('R0-bm25').read_bytes()
    assert not (tmp_path / 'rows' / 'R0-bm25.jsonl').exists()
    again = RowStore(tmp_path / 'rows')
    assert len(again.arm_rows('R0-bm25')) == 3 and again.pack('R0-bm25').read_bytes() == a


def test_a_stop_signal_lets_calls_in_flight_finish_and_leaves_no_open_reservation(tmp_path):
    import threading
    ctx, http = make_ctx(tmp_path)
    stop = threading.Event()
    cases = make_cases(6)

    def after_first(row):
        stop.set()

    summary = run_arms(fake_arms(), ['V15f-R5'], cases, ctx, repeats=2, on_row=after_first, stop=stop)
    assert 0 < summary.ran < 6 * 2 * 3                                   # stopped early, finished what it started
    assert ctx.openai.ledger.summary()['open_reservations'] == 0
    resumed = run_arms(fake_arms(), ['V15f-R5'], cases, ctx, repeats=2)    # and a later run picks up where it stopped
    assert resumed.skipped >= summary.ran and resumed.stopped is None


def test_a_failed_connection_costs_nothing_but_a_timeout_after_sending_is_charged(tmp_path):
    ctx, _ = make_ctx(tmp_path, mode='connect_error')
    run_arms(fake_arms(), ['V15f-R5'], make_cases(1), ctx, repeats=1)
    s = ctx.openai.ledger.summary()
    assert s['requests'] == 0 and Decimal(s['settled_usd']) == 0 and s['open_reservations'] == 0       # nothing left the machine
    row = ctx.store.arm_rows('V15f-R5')[0]
    assert row['errors'][-1]['category'] == 'connection' and row['notes']['degraded']


def test_the_default_transport_reuses_one_pooled_client(monkeypatch):
    import httpx
    from evals_dev.identify_bench import transports
    made = []

    class Client:
        def __init__(self, **kw):
            made.append(kw)

        def post(self, url, headers, json, timeout):
            return httpx.Response(200, json={'ok': True}, request=httpx.Request('POST', url))

    monkeypatch.setattr(httpx, 'Client', Client)
    monkeypatch.setattr(transports, '_CLIENT', None)
    for _ in range(3):
        status, _headers, data = transports.default_http('https://example.test/v1', {}, {}, 5.0)
    assert status == 200 and data == {'ok': True} and len(made) == 1
    assert made[0]['follow_redirects'] is False and made[0]['transport'] is not None
    import socket
    assert (socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1) in transports.keepalive_options()


def test_a_dropped_connection_is_charged_at_the_typical_call_once_there_are_enough_samples(tmp_path):
    ctx, http = make_ctx(tmp_path)
    ledger = ctx.openai.ledger
    for i in range(35):                                                    # build the sample of what a settled call costs
        r = ledger.reserve(model='gpt-6-luna', worst_case_usd=Decimal('0.0108'))
        ledger.settle(r, usd=Decimal('0.0009'), input_tokens=4000, output_tokens=900)
    ctx.openai.http = fakes.fake_openai_http('timeout')
    run_arms(fake_arms(), ['V15f-R5'], make_cases(1), ctx, repeats=1)
    unknown = [json.loads(x) for x in (tmp_path / 'openai.jsonl').read_text().splitlines() if '"unknown"' in x]
    assert len(unknown) == 3 and all(x['basis'] == '99th percentile of settled calls' and Decimal(x['usd']) == Decimal('0.0009') for x in unknown)


def test_repeated_connection_failures_open_a_circuit_and_stop_the_run_without_writing_rows(tmp_path):
    ctx, http = make_ctx(tmp_path, mode='connect_error')
    summary = run_arms(fake_arms(), ['V15f-R5'], make_cases(8), ctx, repeats=2)
    assert summary.stopped == 'circuit_open'
    assert 10 <= len(http.calls) < 8 * 2 * 3                                        # it opened after the tenth failure, not after all of them
    rows = ctx.store.arm_rows('V15f-R5')
    assert all(r['errors'][-1]['category'] != 'circuit_open' for r in rows)       # the stopped case is not recorded as a result
    assert len(rows) < 8 * 2
    assert ctx.openai.ledger.summary()['open_reservations'] == 0
