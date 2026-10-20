"""Adversarial spending checks at the real request/ledger and HTTP seams. No network."""
from decimal import Decimal
import json
import sqlite3
import urllib.error
import urllib.request
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from engine import spend
from engine.api import create_app
from engine.llm_gate import reset_for_tests
from engine.tests.test_spend import _prepare, _rows, _messages, _reply

MODEL = 'gpt-4.1-mini'


def call(messages=None, **kwargs):
    return spend.openai_chat_json(messages or _messages(), model=MODEL,
                                  max_completion_tokens=8, **kwargs)


def test_ambiguous_billed_timeout_cannot_restore_the_lifetime_budget(tmp_path, monkeypatch):
    path = _prepare(tmp_path, monkeypatch)
    estimate = spend.token_cost(MODEL, spend.estimate_input_tokens(_messages()), 8)
    ledger = spend.open_ledger()
    row = ledger.reserve('seed', MODEL, Decimal('20') - estimate, Decimal('20'))
    ledger.settle(row, Decimal('20') - estimate)
    seen = []

    def post(payload, key):
        seen.append(payload)
        raise TimeoutError('response lost after the provider accepted the request')

    monkeypatch.setattr(spend, '_post_chat', post)
    with pytest.raises((TimeoutError, spend.SpendError)):
        call()
    result = call()
    assert result.offline and result.notice == spend.CAP_NOTICE
    assert len(seen) == 1
    assert _rows(path)[1]['status'] in {'reserved', 'settled'}
    assert sum(ledger.totals()) == Decimal('20')


def test_reservation_covers_unicode_schema_and_complete_request(tmp_path, monkeypatch):
    path = _prepare(tmp_path, monkeypatch)
    messages = _messages('💥' * 1000)
    schema = {'type': 'json_schema', 'json_schema': {
        'name': 'rank', 'strict': True, 'schema': {'type': 'object',
        'properties': {'hits': {'type': 'array', 'items': {'type': 'string', 'enum': ['a' * 2000]}}},
        'required': ['hits'], 'additionalProperties': False}}}

    def post(payload, key):
        # Byte-level BPE cannot require more tokens than its serialized UTF-8
        # bytes. Message/schema framing must be covered as well.
        byte_bound = len(json.dumps(payload, ensure_ascii=False, separators=(',', ':')).encode())
        reserved = Decimal(_rows(path)[0]['est_usd'])
        assert reserved >= spend.token_cost(MODEL, byte_bound, 8)
        assert payload['service_tier'] == 'default'
        assert payload['model'].endswith('-2025-04-14')
        return _reply(payload, 100, 1)

    monkeypatch.setattr(spend, '_post_chat', post)
    assert not call(messages, response_format=schema).offline


def test_fractional_microdollars_never_round_available_budget_up(tmp_path, monkeypatch):
    estimate = spend.token_cost(MODEL, spend.estimate_input_tokens(_messages()), 8)
    _prepare(tmp_path, monkeypatch, cap=str(estimate - Decimal('0.0000001')))
    seen = []
    monkeypatch.setattr(spend, '_post_chat', lambda payload, key: seen.append(payload) or _reply(payload, 1, 1))
    assert call().offline
    assert not seen
    assert spend.token_cost(MODEL, 2, 1) >= Decimal('0.0000024')


def test_hosted_sqlite_is_refused_before_the_provider(tmp_path, monkeypatch):
    _prepare(tmp_path, monkeypatch)
    monkeypatch.setenv('VERCEL', '1')
    seen = []
    monkeypatch.setattr(spend, '_post_chat', lambda payload, key: seen.append(payload) or _reply(payload, 1, 1))
    assert call().notice == spend.LEDGER_NOTICE
    assert not seen
    assert spend.budget_status().remaining_usd is None


@pytest.mark.parametrize('amount', ['-1.000000', 'garbage', '1e-3', '0.0000001'])
def test_invalid_ledger_amounts_fail_closed(tmp_path, monkeypatch, amount):
    path = _prepare(tmp_path, monkeypatch)
    with sqlite3.connect(path) as con:
        con.execute("INSERT INTO spend_ledger (ts,route,model,est_usd,status) VALUES ('now','x',?,?, 'reserved')",
                    (MODEL, amount))
    seen = []
    monkeypatch.setattr(spend, '_post_chat', lambda payload, key: seen.append(payload) or _reply(payload, 1, 1))
    assert call().notice == spend.LEDGER_NOTICE
    assert not seen


@pytest.mark.parametrize('cap', ['', 'NaN', 'Infinity', '-1', '20.01', '1e100'])
def test_invalid_or_unauthorized_budget_configuration_refuses(tmp_path, monkeypatch, cap):
    _prepare(tmp_path, monkeypatch, cap=cap)
    seen = []
    monkeypatch.setattr(spend, '_post_chat', lambda payload, key: seen.append(payload) or _reply(payload, 1, 1))
    assert call().offline
    assert not seen


@pytest.mark.parametrize('bad', [Decimal('NaN'), Decimal('-1'), Decimal('0')])
def test_invalid_pricing_refuses_before_provider(tmp_path, monkeypatch, bad):
    _prepare(tmp_path, monkeypatch)
    monkeypatch.setitem(spend.MODEL_PRICES, MODEL, (bad, Decimal('1.60')))
    seen = []
    monkeypatch.setattr(spend, '_post_chat', lambda payload, key: seen.append(payload) or _reply(payload, 1, 1))
    assert call().offline
    assert not seen


@pytest.mark.parametrize('content', [
    [{'type': 'image_url', 'image_url': {'url': 'https://example.test/image'}}],
    {'text': 'not a text-only message'},
])
def test_unpriced_modalities_are_refused(tmp_path, monkeypatch, content):
    _prepare(tmp_path, monkeypatch)
    seen = []
    monkeypatch.setattr(spend, '_post_chat', lambda payload, key: seen.append(payload) or _reply(payload, 1, 1))
    assert call([{'role': 'user', 'content': content}]).offline
    assert not seen


def test_jev_adapter_and_lowest_transport_are_disabled_when_hosted(monkeypatch):
    from engine.identify.screen import jev_ask
    from engine.identify.jevkit import client
    monkeypatch.setenv('VERCEL', '1')
    seen = []
    with monkeypatch.context() as patch:
        patch.setattr(client, 'ask', lambda *args, **kwargs: seen.append('adapter'))
        with pytest.raises(RuntimeError):
            jev_ask()({'proposal': 'fixture'}, {'q': client.noul('fixture')}, 1)
    monkeypatch.setattr(client._POOL, 'borrow', lambda *args: seen.append('wire'))
    with pytest.raises(RuntimeError):
        client.post('https://example.test', b'{}', {}, 1)
    assert not seen


def test_default_identify_uses_query_and_validated_corpus_ids(tmp_path, monkeypatch):
    _prepare(tmp_path, monkeypatch)
    reset_for_tests()
    monkeypatch.setattr('engine.identify.corpus.bm25_rank', lambda *a, **k: ['9.10.15.4.', '9.9.10.1.'])
    monkeypatch.setattr('engine.identify.corpus.articles', lambda *a: {
        '9.10.15.4.': {'title': 'Openings', 'text': 'Fixture text'},
        '9.9.10.1.': {'title': 'Egress', 'text': 'Fixture text'},
    })
    seen = []

    def post(payload, key):
        seen.append(payload)
        result = _reply(payload, 100, 8)
        result['choices'] = [{'finish_reason': 'stop', 'message': {'content': json.dumps({
            'hits': ['9.9.10.1.', '9.10.15.4.']})}}]
        return result

    monkeypatch.setattr(spend, '_post_chat', post)
    response = TestClient(create_app()).post('/identify', json={'query': 'soffit fixture'})
    assert response.status_code == 200
    assert response.json()['label'] == 'model output, not verified'
    assert response.json()['hits'] == ['9.9.10.1.', '9.10.15.4.']
    assert 'soffit fixture' in json.dumps(seen[0]['messages'])
    assert seen[0]['response_format']['type'] == 'json_schema'


@pytest.mark.parametrize('out', [0, -1, True, 1.5, 32_769])
def test_invalid_output_limit_never_reaches_transport(tmp_path, monkeypatch, out):
    _prepare(tmp_path, monkeypatch)
    seen = []
    monkeypatch.setattr(spend, '_post_chat', lambda payload, key: seen.append(payload))
    result = spend.openai_chat_json(_messages(), model=MODEL, max_completion_tokens=out)
    assert result.offline and not seen


@pytest.mark.parametrize('usage', [
    {'prompt_tokens': -1, 'completion_tokens': 1},
    {'prompt_tokens': 1.9, 'completion_tokens': 1},
    {'prompt_tokens': True, 'completion_tokens': 1},
    {'prompt_tokens': '1', 'completion_tokens': '1'},
    {},
])
def test_missing_or_untrusted_usage_consumes_the_whole_reservation(tmp_path, monkeypatch, usage):
    path = _prepare(tmp_path, monkeypatch)
    def post(payload, key):
        reply = _reply(payload, 1, 1)
        reply['usage'] = usage
        return reply
    monkeypatch.setattr(spend, '_post_chat', post)
    assert not call().offline
    row = _rows(path)[0]
    assert row['actual_usd'] == row['est_usd']


def test_responses_style_usage_objects_use_the_reported_tokens():
    assert spend._usage_tokens(SimpleNamespace(usage=SimpleNamespace(input_tokens=2, output_tokens=3))) == (2, 3)


def test_failed_settlement_keeps_the_reservation_and_refuses_a_retry(tmp_path, monkeypatch):
    estimate = spend.token_cost(MODEL, spend.estimate_input_tokens(_messages()), 8)
    path = _prepare(tmp_path, monkeypatch, cap=str(estimate))
    seen = []
    def post(payload, key):
        seen.append(payload)
        return _reply(payload, 1, 1)
    def unavailable(*args):
        raise spend.LedgerUnavailable
    monkeypatch.setattr(spend, '_post_chat', post)
    monkeypatch.setattr(spend._SqliteLedger, 'settle', unavailable)
    assert not call().offline
    assert call().notice == spend.CAP_NOTICE
    assert len(seen) == 1 and _rows(path)[0]['status'] == 'reserved'


def test_reported_overrun_is_recorded_in_full_and_freezes_future_calls(tmp_path, monkeypatch):
    path = _prepare(tmp_path, monkeypatch)
    seen = []
    def post(payload, key):
        seen.append(payload)
        return _reply(payload, 40_000, 10_000)
    monkeypatch.setattr(spend, '_post_chat', post)
    with pytest.raises(spend.SpendError, match='bounds'):
        call()
    row = _rows(path)[0]
    assert Decimal(row['actual_usd']) == spend.token_cost(MODEL, 40_000, 10_000)
    assert Decimal(row['actual_usd']) > Decimal(row['est_usd'])
    assert call().notice == spend.LEDGER_NOTICE
    assert len(seen) == 1


@pytest.mark.parametrize('fault', ['model', 'tier', 'missing_tier', 'refusal', 'choices', 'parse'])
def test_post_send_errors_never_refund_the_attempt(tmp_path, monkeypatch, fault):
    path = _prepare(tmp_path, monkeypatch)
    def post(payload, key):
        reply = _reply(payload, 1, 1)
        if fault == 'model':
            reply['model'] = 'gpt-4.1'
        elif fault == 'tier':
            reply['service_tier'] = 'priority'
        elif fault == 'missing_tier':
            reply.pop('service_tier')
        elif fault == 'refusal':
            reply['choices'][0]['message']['refusal'] = 'refused'
        elif fault == 'choices':
            reply['choices'] = []
        else:
            raise spend.SpendError('response was not JSON')
        return reply
    monkeypatch.setattr(spend, '_post_chat', post)
    with pytest.raises(spend.SpendError):
        call()
    assert _rows(path)[0]['status'] == 'reserved'


@pytest.mark.parametrize('status', [None, 302, 429, 500, 'timeout', 'bad_json'])
def test_production_http_request_has_one_attempt_and_a_bounded_payload(tmp_path, monkeypatch, status):
    path = _prepare(tmp_path, monkeypatch)
    requests = []
    handlers = []

    class Response:
        def __enter__(self):
            return self
        def __exit__(self, *args):
            return False
        def read(self, size):
            assert size == spend._MAX_RESPONSE_BYTES + 1
            if status == 'bad_json':
                return b'invalid JSON'
            return json.dumps(_reply(json.loads(requests[0].data), 1, 1)).encode()

    class Opener:
        def open(self, request, timeout):
            requests.append(request)
            assert timeout == 60 and request.method == 'POST'
            assert request.full_url == 'https://' + 'api.' + 'openai.com/v1/chat/completions'
            assert request.get_header('Authorization') == 'Bearer test-openai-key'
            payload = json.loads(request.data)
            assert payload['model'] == 'gpt-4.1-mini-2025-04-14'
            assert payload['max_completion_tokens'] == 8 and payload['service_tier'] == 'default'
            assert payload['n'] == 1 and payload['store'] is False
            if isinstance(status, int):
                raise urllib.error.HTTPError(request.full_url, status, 'synthetic', None, None)
            if status == 'timeout':
                raise TimeoutError('synthetic timeout')
            return Response()

    def build(*args):
        handlers.extend(args)
        return Opener()

    monkeypatch.setattr(urllib.request, 'build_opener', build)
    if status is None:
        assert not call().offline
        assert _rows(path)[0]['status'] == 'settled'
    else:
        with pytest.raises(spend.SpendError):
            call()
        assert _rows(path)[0]['status'] == 'reserved'
    assert len(requests) == 1
    assert len(handlers) == 1 and isinstance(handlers[0], spend._NoRedirect)
    assert handlers[0].redirect_request(requests[0], None, 307, '', {}, 'https://example.test') is None


@pytest.mark.parametrize('bad_output', [
    {'hits': ['9.10.15.4.', '99.99.99.99.']},
    {'hits': ['9.10.15.4.', '9.10.15.4.']},
    {'hits': '9.10.15.4.'},
    {'hits': [12]},
    {'hits': ['9.10.15.4.'], 'accuracy': '9/11'},
    'not JSON',
])
def test_invalid_rankings_return_keyword_fallback_without_leaking_output(tmp_path, monkeypatch, bad_output):
    _prepare(tmp_path, monkeypatch)
    reset_for_tests()
    monkeypatch.setattr('engine.identify.corpus.bm25_rank', lambda *a, **k: ['9.10.15.4.'])
    monkeypatch.setattr('engine.identify.corpus.articles', lambda *a: {
        '9.10.15.4.': {'title': 'Fixture', 'text': 'Fixture text'},
    })
    def post(payload, key):
        reply = _reply(payload, 1, 1)
        reply['choices'][0]['message']['content'] = bad_output if isinstance(bad_output, str) else json.dumps(bad_output)
        return reply
    monkeypatch.setattr(spend, '_post_chat', post)
    response = TestClient(create_app()).post('/identify', json={'query': 'soffit'})
    assert response.status_code == 200
    assert response.json()['label'] == 'keyword search, no AI'
    assert response.json()['notice']
    assert response.json()['hits'] == ['9.10.15.4.']
    assert '99.99' not in response.text and 'accuracy' not in response.text


def test_missing_corpus_never_spends_on_an_ungrounded_query(tmp_path, monkeypatch):
    path = _prepare(tmp_path, monkeypatch)
    reset_for_tests()
    monkeypatch.setattr('engine.identify.corpus.bm25_rank', lambda *a, **k: ['9.10.15.4.'])
    monkeypatch.setattr('engine.identify.corpus.articles', lambda *a: {})
    seen = []
    monkeypatch.setattr(spend, '_post_chat', lambda payload, key: seen.append(payload))
    response = TestClient(create_app()).post('/identify', json={'query': 'soffit'})
    assert response.status_code == 200 and response.json()['label'] == 'keyword search, no AI'
    assert not seen and _rows(path) == []
