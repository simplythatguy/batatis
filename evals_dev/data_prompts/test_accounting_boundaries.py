"""Offline regressions from the independent measurement review."""
import json

import httpx
import pytest

from evals_dev.data_prompts import checks, deepseek_review, judge, ledger, manifest
from evals_dev.data_prompts.__main__ import _case_cost
from evals_dev.data_prompts.gold import Item
from evals_dev.data_prompts.test_harness import integrity_offline, integrity_sources, _result

INSTALL = ledger.install


def test_all_openai_dispatches_and_unknown_usage_are_recorded(integrity_offline, monkeypatch):
    monkeypatch.setattr(ledger, '_installed', False)
    monkeypatch.setattr(judge.time, 'sleep', lambda _: None)
    request = httpx.Request('POST', judge.URL)
    replies = iter([httpx.Response(503, request=request), httpx.ReadTimeout('unknown outcome'),
                    httpx.Response(200, request=request, json={'choices': [{'message': {'content':
                        '{"items":[{"id":"F1","covered":false,"evidence":[]}]}'}}]})])
    def post(*args, **kwargs):
        reply = next(replies)
        if isinstance(reply, Exception):
            raise reply
        return reply
    monkeypatch.setattr(httpx.Client, 'post', post)
    INSTALL()
    book = ledger.Ledger()
    judge.grade('request', 'report', [Item('F1', 'F', 'a fact')], model='gpt-6-luna', effort='low', book=book)
    assert book.summary()['live_calls'] == 3
    assert book.summary()['unknown_cost_attempts'] == 3
    events = [json.loads(line) for line in ledger.ATTEMPTS.read_text().splitlines()]
    assert sum(e['event'] == 'attempt_finished' for e in events) == 3


def test_openai_cache_preserves_original_cost(integrity_offline, monkeypatch):
    monkeypatch.setattr(ledger, '_installed', False)
    def post(self, url, **kwargs):
        return httpx.Response(200, request=httpx.Request('POST', url), json={
            'usage': {'prompt_tokens': 1000, 'completion_tokens': 200}, 'choices': []})
    monkeypatch.setattr(httpx.Client, 'post', post)
    INSTALL()
    book = ledger.Ledger()
    token = ledger.CURRENT.set(book)
    try:
        with httpx.Client() as client:
            client.post(judge.URL, json={'model': 'gpt-6-luna'})
            first = book.summary()['usd']
            monkeypatch.setitem(ledger.PRICES, 'gpt-6-luna', ((9, 9, 9), (9, 9, 9)))
            client.post(judge.URL, json={'model': 'gpt-6-luna'})
        assert book.summary()['usd'] == first * 2
        assert book.summary()['live_usd'] == first
    finally:
        ledger.CURRENT.reset(token)


@pytest.mark.parametrize('change', ['system', 'schema'])
def test_actual_judge_instructions_and_schema_change_cache_identity(integrity_offline, monkeypatch, change):
    before = judge._key('deepseek-flash', 'max', 'q', 'r', [Item('F1', 'F', 'fact')])
    if change == 'system':
        monkeypatch.setattr(judge, 'SYSTEM', judge.SYSTEM + '\nChanged measurement instruction.')
    else:
        monkeypatch.setattr(judge, 'schema', lambda: {'type': 'object', 'properties': {}})
    assert judge._key('deepseek-flash', 'max', 'q', 'r', [Item('F1', 'F', 'fact')]) != before


def test_measurement_source_change_is_part_of_frozen_provenance(integrity_sources):
    root, case, _ = integrity_sources
    before = manifest.scoring_sources()
    (root / 'harness/judge.py').write_text('changed grading code')
    assert manifest.scoring_sources() != before


@pytest.mark.parametrize('finish,content', [('length', '{"items":[]}'), ('stop', '{"items":[]} {"items":[')])
def test_truncated_or_trailing_malformed_judge_output_is_rejected(integrity_offline, monkeypatch, finish, content):
    monkeypatch.setenv('DEEPSEEK_API_KEY', 'synthetic-key')
    def post(self, url, **kwargs):
        return httpx.Response(200, request=httpx.Request('POST', url), json={
            'usage': {'prompt_tokens': 100, 'completion_tokens': 100},
            'choices': [{'finish_reason': finish, 'message': {'content': content}}]})
    monkeypatch.setattr(httpx.Client, 'post', post)
    book = ledger.Ledger()
    token = ledger.CURRENT.set(book)
    try:
        with pytest.raises(deepseek_review.InvalidJson):
            deepseek_review.chat_json('deepseek-flash', 'max', 'system', 'user', stage='judge')
        assert book.summary()['usd'] > 0
    finally:
        ledger.CURRENT.reset(token)


def test_unread_input_is_reported_separately_from_successful_review_execution():
    result = _result()
    result['case']['intake']['review'] = {'status': 'live', 'flags': [{'kind': 'not_read', 'text': 'An image was not read.'}]}
    assert checks.completion(result) == []


def test_terminal_rerank_failure_is_not_a_successful_stage():
    result = _result()
    result['expected_stages'] = {'identify': True, 'identify_stages': ['rerank']}
    result['case']['identify'] = {'mode': 'live', 'trace': {'stages': [
        {'stage': 'rerank', 'requests': 1, 'errors': 1, 'detail': 'Rerank unavailable; tentative candidate order retained'}]}}
    assert checks.completion(result)


def test_non_http_verification_spend_is_retained():
    result = _result()
    result['identify_spend'] = {'by_provider': {'verification': {'usd': .123}},
                                'transport_calls': [{'provider': 'anthropic', 'usd': .123, 'http_request_hash': None}]}
    assert _case_cost(result)['usd'] == .123


def test_http_call_identity_prevents_double_counting():
    result = _result()
    result['cost']['summary']['usd'] = .1
    result['cost']['calls'] = [{'request_hash': 'same-http-request', 'usd': .1}]
    result['identify_spend'] = {'transport_calls': [
        {'provider': 'openai', 'usd': .2, 'http_request_hash': 'same-http-request'},
        {'provider': 'anthropic', 'usd': .123, 'http_request_hash': None}]}
    assert _case_cost(result)['usd'] == .223


def test_a_successful_retry_is_not_mistaken_for_a_terminal_failure():
    result = _result()
    result['expected_stages'] = {'identify': True, 'identify_stages': ['rerank']}
    result['identify_stage_events'] = [{'stage': 'rerank', 'status': 'done'}]
    result['case']['identify'] = {'mode': 'live', 'trace': {'stages': [
        {'stage': 'rerank', 'requests': 2, 'errors': 1, 'detail': None}]}}
    assert checks.completion(result) == []


def test_each_http_dispatch_can_cover_only_one_metered_call():
    from evals_dev.data_prompts.sut import accounted_calls
    raw = {'provider': 'openai', 'model': 'gpt-6-luna', 'input_tokens': 100, 'output_tokens': 5, 'usd': .1}
    http = ledger.Call('gpt-6-luna', 'low', 'verify', 100, 0, 5, 0, .05, False, 1, 'request-one')
    out = accounted_calls([raw, raw], [http])
    assert [row['http_request_hash'] for row in out] == ['request-one', None]


def test_legacy_verification_overlap_does_not_claim_complete_cost_accounting():
    result = _result()
    result['identify_spend'] = {'by_provider': {'verification': {'usd': .123}}}
    assert _case_cost(result)['cost_complete'] is False
