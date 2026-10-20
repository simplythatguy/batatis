"""Usage accounting through the production opener; all HTTPS stays in memory."""
import io
import json
import urllib.request
import urllib.response
from decimal import Decimal
from email.message import Message

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
from engine.tests.test_spend import _prepare, _rows


def _capture_https(monkeypatch, usage, *, content='{}'):
    calls = []

    def respond(self, request):
        payload = json.loads(request.data)
        calls.append(payload)
        body = {
            'model': payload['model'],
            'service_tier': 'default',
            'usage': usage,
            'choices': [{'finish_reason': 'stop', 'message': {'content': content}}],
        }
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
