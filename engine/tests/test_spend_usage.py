"""Usage accounting through the production opener; all HTTPS stays in memory."""
import io
import json
import urllib.request
import urllib.response
from decimal import Decimal
from email.message import Message

import pytest
from fastapi.testclient import TestClient

from engine import spend
from engine.api import create_app
from engine.identify_http import (
    IDENTIFY_MAX_OUTPUT,
    IDENTIFY_MODEL,
    KEYWORD_LABEL,
    MODEL_LABEL,
    identify_messages,
    identify_response_format,
)
from engine.llm_gate import reset_for_tests
from engine.tests.test_spend import _messages, _prepare, _rows

_MISSING_USAGE = object()


def _capture_https(monkeypatch, usage, *, content='{}'):
    calls = []
    monkeypatch.setenv('NO_PROXY', '*')

    def respond(self, request):
        payload = json.loads(request.data)
        calls.append(payload)
        body = {
            'model': payload['model'],
            'service_tier': 'default',
            'choices': [{'finish_reason': 'stop', 'message': {'content': content}}],
        }
        if usage is not _MISSING_USAGE:
            body['usage'] = usage
        response = urllib.response.addinfourl(
            io.BytesIO(json.dumps(body).encode()), Message(), request.full_url, 200)
        response.msg = 'synthetic response'
        return response

    # Retain the real opener, request serialization and response decoding.
    monkeypatch.setattr(urllib.request.HTTPSHandler, 'https_open', respond)
    return calls


def _seed_previous_spend(estimate):
    ledger = spend.open_ledger()
    previous = Decimal('20') - estimate
    row = ledger.reserve('prior lifetime', IDENTIFY_MODEL, previous, Decimal('20'))
    assert row is not None
    ledger.settle(row, previous)
    return previous


def _assert_usage_consumes_reservation(tmp_path, monkeypatch, usage):
    path = _prepare(tmp_path, monkeypatch)
    estimate = spend.token_cost(
        IDENTIFY_MODEL, spend.estimate_input_tokens(_messages()), 8)
    _seed_previous_spend(estimate)
    calls = _capture_https(monkeypatch, usage)
    result = spend.openai_chat_json(_messages(), model=IDENTIFY_MODEL, max_completion_tokens=8)
    assert not result.offline
    row = _rows(path)[-1]
    assert row['status'] == 'settled' and row['actual_usd'] == row['est_usd']
    assert sum(spend.open_ledger().totals()) == Decimal('20')
    retry = spend.openai_chat_json(_messages(), model=IDENTIFY_MODEL, max_completion_tokens=8)
    assert retry.offline and retry.notice == spend.CAP_NOTICE
    assert len(calls) == 1


@pytest.mark.parametrize('usage', [
    _MISSING_USAGE, None, {}, [], False, 104, '104',
    [{'prompt_tokens': 100, 'completion_tokens': 4, 'total_tokens': 104}],
    {'usage': {'prompt_tokens': 100, 'completion_tokens': 4, 'total_tokens': 104}},
    {'prompt_tokens': 100, 'completion_tokens': 4},
    {'prompt_tokens': 100, 'total_tokens': 104},
    {'completion_tokens': 4, 'total_tokens': 104},
    {'input_tokens': 100, 'output_tokens': 4, 'total_tokens': 104},
    {'prompt_tokens': None, 'input_tokens': 100, 'completion_tokens': 4, 'total_tokens': 104},
    {'prompt_tokens': 100, 'completion_tokens': None, 'output_tokens': 4, 'total_tokens': 104},
])
def test_missing_or_wrong_usage_shape_cannot_refund(tmp_path, monkeypatch, usage):
    _assert_usage_consumes_reservation(tmp_path, monkeypatch, usage)


@pytest.mark.parametrize('field', ['prompt_tokens', 'completion_tokens', 'total_tokens'])
@pytest.mark.parametrize('bad', [None, True, False, -1, 0.0, 1.5, '1', [], {'tokens': 1}])
def test_each_usage_counter_requires_a_nonnegative_integer(tmp_path, monkeypatch, field, bad):
    usage = {'prompt_tokens': 100, 'completion_tokens': 4, 'total_tokens': 104}
    usage[field] = bad
    _assert_usage_consumes_reservation(tmp_path, monkeypatch, usage)


@pytest.mark.parametrize('usage', [
    {'prompt_tokens': 0, 'completion_tokens': 0, 'total_tokens': 1004},
    {'prompt_tokens': 100, 'completion_tokens': 4, 'total_tokens': 0},
    {'prompt_tokens': 100, 'completion_tokens': 4, 'total_tokens': 999999},
    {'prompt_tokens': 100, 'completion_tokens': 4, 'total_tokens': 10 ** 100},
    {'prompt_tokens': 10 ** 100, 'completion_tokens': 4, 'total_tokens': 104},
    {'prompt_tokens': 100, 'completion_tokens': 10 ** 100, 'total_tokens': 104},
])
def test_contradictory_usage_cannot_refund_even_with_oversized_counts(tmp_path, monkeypatch, usage):
    _assert_usage_consumes_reservation(tmp_path, monkeypatch, usage)


@pytest.mark.parametrize(('usage', 'expected'), [
    ({'prompt_tokens': 100, 'completion_tokens': 4, 'total_tokens': 104}, Decimal('0.000047')),
    ({'prompt_tokens': 0, 'completion_tokens': 0, 'total_tokens': 0}, Decimal('0')),
    ({'prompt_tokens': 100, 'completion_tokens': 4, 'total_tokens': 104,
      'prompt_tokens_details': {'cached_tokens': 50},
      'completion_tokens_details': {'reasoning_tokens': 2}}, Decimal('0.000047')),
])
def test_valid_chat_usage_still_settles_reported_cost(tmp_path, monkeypatch, usage, expected):
    path = _prepare(tmp_path, monkeypatch)
    calls = _capture_https(monkeypatch, usage)
    assert not spend.openai_chat_json(_messages(), model=IDENTIFY_MODEL, max_completion_tokens=8).offline
    row = _rows(path)[0]
    assert row['status'] == 'settled' and Decimal(row['actual_usd']) == expected
    assert expected < Decimal(row['est_usd'])
    assert spend.open_ledger().totals() == (expected, Decimal('0'))
    assert len(calls) == 1


def test_public_identify_cannot_reuse_allowance_after_contradictory_usage(tmp_path, monkeypatch):
    path = _prepare(tmp_path, monkeypatch)
    reset_for_tests()
    query = 'abcd ' * 300
    candidates = {'fixture-A': {'title': 'Synthetic', 'text': 'not code'}}
    monkeypatch.setattr('engine.identify.corpus.bm25_rank', lambda *a, **k: ['fixture-A'])
    monkeypatch.setattr('engine.identify.corpus.articles', lambda *a: candidates)
    estimate = spend.token_cost(
        IDENTIFY_MODEL,
        spend.estimate_input_tokens(
            identify_messages(query, candidates), identify_response_format(list(candidates)),
            model=IDENTIFY_MODEL, max_completion_tokens=IDENTIFY_MAX_OUTPUT),
        IDENTIFY_MAX_OUTPUT)
    previous = _seed_previous_spend(estimate)
    calls = _capture_https(monkeypatch, {
        'prompt_tokens': 0, 'completion_tokens': 0, 'total_tokens': 1004,
    }, content='{"hits":["fixture-A"]}')
    client = TestClient(create_app())
    first = client.post('/identify', json={'query': query})
    assert first.status_code == 200 and first.json()['label'] == MODEL_LABEL
    # Assume each fake provider attempt used 1000 input + 4 output tokens,
    # within both server bounds: exact synthetic cost is US$0.0004064.
    synthetic_charge = Decimal('0.0004064')
    assert synthetic_charge <= estimate
    for i in range(int(estimate / synthetic_charge) + 1):
        response = client.post('/identify', json={'query': query}, headers={
            'x-forwarded-for': f'192.0.2.{i + 1}',
        })
        assert response.status_code == 200
        assert response.json()['label'] == KEYWORD_LABEL
        assert response.json()['notice'] == spend.CAP_NOTICE
    assert len(calls) == 1
    assert previous + synthetic_charge * len(calls) <= Decimal('20')
    assert sum(spend.open_ledger().totals()) == Decimal('20')
    row = _rows(path)[-1]
    assert row['status'] == 'settled' and row['actual_usd'] == row['est_usd']
    assert client.get('/status/budget').json()['remaining_usd'] == 0


def test_coherent_public_usage_refunds_unused_allowance(tmp_path, monkeypatch):
    path = _prepare(tmp_path, monkeypatch)
    reset_for_tests()
    candidates = {'fixture-A': {'title': 'Synthetic', 'text': 'not code'}}
    monkeypatch.setattr('engine.identify.corpus.bm25_rank', lambda *a, **k: ['fixture-A'])
    monkeypatch.setattr('engine.identify.corpus.articles', lambda *a: candidates)
    query = 'abcd ' * 300
    estimate = spend.token_cost(
        IDENTIFY_MODEL,
        spend.estimate_input_tokens(
            identify_messages(query, candidates), identify_response_format(list(candidates)),
            model=IDENTIFY_MODEL, max_completion_tokens=IDENTIFY_MAX_OUTPUT),
        IDENTIFY_MAX_OUTPUT)
    # Enough allowance for one reservation plus one valid charge. Refunding
    # the first unused reserve is what makes the second request affordable.
    previous = _seed_previous_spend(estimate + Decimal('0.000047'))
    calls = _capture_https(monkeypatch, {
        'prompt_tokens': 100, 'completion_tokens': 4, 'total_tokens': 104,
    }, content='{"hits":["fixture-A"]}')
    client = TestClient(create_app())
    for _ in range(2):
        response = client.post('/identify', json={'query': query})
        assert response.status_code == 200 and response.json()['label'] == MODEL_LABEL
    refused = client.post('/identify', json={'query': query})
    assert refused.status_code == 200 and refused.json()['notice'] == spend.CAP_NOTICE
    assert len(calls) == 2
    assert sum(spend.open_ledger().totals()) == previous + Decimal('0.000094')
    assert [row['actual_usd'] for row in _rows(path)[1:]] == ['0.000047', '0.000047']
