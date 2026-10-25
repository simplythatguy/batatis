"""Elephant selection and typed Decisions contract; synthetic inputs, no live calls."""
import asyncio
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
import json
import os
import ssl
import threading
import time
import traceback

import httpx
import pytest

from engine import llm_gate
from engine.identify import elephant_runtime as runtime, providers
from engine.identify.commit import load_policy
from engine.identify.config import ConfigError, load_config
from engine.identify.screen import ELEPHANT_MODEL, GOVERN, Judge
from engine.relevance import scoring_bands
from engine.tests._network_guard import block_network

STATE = {'proposal': 'SYNTHETIC: a blue square.'}
QUESTIONS = {
    'blue': {'type': 'noul', 'instructions': 'Does the object have a blue colour?'},
    'shape': {'type': 'choice', 'instructions': 'Which shape is the object?',
              'criteria': {'square': 'A square shape', 'circle': 'A circular shape'}},
    'urgency': {'type': 'score', 'instructions': 'How urgent is this synthetic request?',
                'criteria': ['Can wait', 'Needs attention today', 'Blocking operation']} }


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    for name in list(os.environ):
        if name.startswith(('BATATIS_', 'VERCEL')) or name in {
            'OPENROUTER_API_KEY', 'OPENAI_API_KEY', 'ANTHROPIC_API_KEY', 'JEV_API_KEY', 'TYPESAFE_API_KEY'}:
            monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv('BATATIS_LIVE', '0')
    monkeypatch.setenv('BATATIS_LIVE_ELEPHANT', '1')
    monkeypatch.setenv('OPENROUTER_API_KEY', 'synthetic-only-key')
    block_network(monkeypatch)
    llm_gate.reset_for_tests()
    yield
    llm_gate.reset_for_tests()


def reply(**changes):
    data = {'model': runtime.RESPONSE_MODEL,
            'answers': {'blue': {'type': 'noul', 'noul': 0.0},
                        'shape': {'type': 'choice', 'choice': 'square', 'confidence': 0.5,
                                  'probabilities': {'square': 0.75, 'circle': 0.25}},
                        'urgency': {'type': 'score', 'score': 1.25, 'confidence': 0.5,
                                    'probabilities': {'0': 0.0, '1': 0.75, '2': 0.25},
                                    'legend': {'0': 'Can wait', '1': 'Needs attention today', '2': 'Blocking operation'}}},
            'usage': {'input_tokens': 201, 'output_tokens': 2, 'cost': 0}}
    return {**data, **changes}


def wire(monkeypatch, handler):
    sent, transport_options, client_options = [], [], []
    def transport(**kw):
        transport_options.append(kw)
        async def send(request):
            sent.append(request)
            response = handler(request)
            return await response if hasattr(response, '__await__') else response
        return httpx.MockTransport(send)
    client = httpx.AsyncClient
    def make_client(**kw):
        client_options.append(kw)
        return client(**kw)
    monkeypatch.setattr(httpx, 'AsyncHTTPTransport', transport)
    monkeypatch.setattr(httpx, 'AsyncClient', make_client)
    return sent, transport_options, client_options


def ask(log=None):
    return runtime.metered_ask(runtime.raw_ask(), log=log)


def test_default_scoring_is_elephant_with_separate_existing_quote_verifier():
    config = load_config(env={})
    assert config.screen == config.rerank == 'elephant'
    assert config.screen_model == config.rerank_model == 'baseten/elephant-1:free'
    assert (config.verifier, config.verifier_model, config.verifier_effort) == ('openai', 'gpt-6-luna', 'medium')
    assert config.exhaustive


def test_explicit_old_providers_keep_historical_hashes_and_no_automatic_calibration():
    elephant = load_config(env={})
    old = {provider: load_config(env={'BATATIS_IDENTIFY_SCREEN': provider, 'BATATIS_IDENTIFY_RERANK': provider})
           for provider in ('jev', 'decisions')}
    assert old['jev'].config_hash == '5f1c92331550984a'
    assert old['decisions'].config_hash == '43272040048a6036'
    assert elephant.config_hash not in {c.config_hash for c in old.values()}
    assert load_policy(elephant.config_hash).status == 'uncalibrated'
    bands = scoring_bands('relevance-3', {'screen': 'relevance-3', 'rerank': 'relevance-3'}, elephant.config_hash)
    assert (bands.x, bands.y, bands.status) == (0, 1, 'uncalibrated; display range only')
    for method in ('elephant', 'jev', 'decisions'):
        with pytest.raises(ConfigError):
            load_config(env={'BATATIS_IDENTIFY_SCREEN': method, 'BATATIS_IDENTIFY_SCREEN_MODEL': 'stale-alias'})


def test_wire_pin_typed_answers_no_retries_redirects_proxies_or_paid_routing(monkeypatch):
    sent, options, clients = wire(monkeypatch, lambda _: httpx.Response(200, json=reply()))
    log = providers.SpendLog()
    result = ask(log)(STATE, QUESTIONS, 2)
    assert len(sent) == 1 and str(sent[0].url) == runtime.ENDPOINT
    assert sent[0].method == 'POST' and sent[0].headers['authorization'] == 'Bearer synthetic-only-key'
    body = json.loads(sent[0].content)
    assert body == {'model': ELEPHANT_MODEL, 'state': STATE, 'questions': QUESTIONS, 'provider': runtime.ROUTING}
    assert options[0]['retries'] == 0 and options[0]['trust_env'] is False
    assert options[0]['verify'].verify_mode == ssl.CERT_REQUIRED and options[0]['verify'].check_hostname
    assert clients[0]['follow_redirects'] is False and clients[0]['trust_env'] is False
    assert result['model'] == runtime.RESPONSE_MODEL and result['answers']['blue']['noul'] == 0
    assert result['answers']['shape']['choice'] == 'square' and result['answers']['urgency']['score'] == 1.25
    assert log.calls[0]['provider'] == 'elephant' and log.calls[0]['accounting'] == 'settled'
    assert log.calls[0]['input_tokens'] == 201 and log.usd() == llm_gate._memory.today() == 0


@pytest.mark.parametrize('model', [None, ELEPHANT_MODEL, 'elephant-1', 'baseten/elephant-1',
                                   'baseten/elephant-1-20261020', 'typesafe/jev-1.13'])
def test_nonmatching_or_unversioned_response_is_rejected(monkeypatch, model):
    sent, _, _ = wire(monkeypatch, lambda _: httpx.Response(200, json=reply(model=model)))
    log = providers.SpendLog()
    with pytest.raises(runtime.ElephantError, match='unexpected_model'):
        ask(log)(STATE, QUESTIONS, 2)
    assert len(sent) == 1 and log.calls[0]['accounting'] == 'unknown'


@pytest.mark.parametrize('damage', [
    lambda d: d.update(answers=[]),
    lambda d: d['answers'].pop('blue'),
    lambda d: d['answers'].update(extra={'type': 'noul', 'noul': 0.5}),
    lambda d: d['answers']['blue'].update(type='refusal'),
    lambda d: d['answers']['shape'].update(choice='unknown'),
    lambda d: d['answers']['shape'].update(choice='circle'),
    lambda d: d['answers']['shape']['probabilities'].update(square=0.5),
    lambda d: d['answers']['shape']['probabilities'].pop('circle'),
    lambda d: d['answers']['shape'].update(confidence=True),
    lambda d: d['answers']['urgency'].update(score=0.5),
    lambda d: d['answers']['urgency'].update(score=10 ** 400),
    lambda d: d['answers']['urgency']['legend'].update({'1': 'Rewritten level'}),
    lambda d: d['answers']['urgency']['probabilities'].update({'4': 0.0}),
] + [lambda d, p=p: d['answers']['blue'].update(noul=p)
     for p in (None, True, '0.1', -0.1, 1.1, float('nan'), float('inf'), 10 ** 400)])
def test_invalid_typed_output_fails_once_preserving_valid_usage(monkeypatch, damage):
    data = reply()
    damage(data)
    sent, _, _ = wire(monkeypatch, lambda _: httpx.Response(200, content=json.dumps(data)))
    log = providers.SpendLog()
    with pytest.raises(runtime.ElephantError):
        ask(log)(STATE, QUESTIONS, 2)
    assert len(sent) == 1
    assert log.calls[0]['accounting'] == ('unknown' if 'NaN' in json.dumps(data) or 'Infinity' in json.dumps(data) else 'settled')


@pytest.mark.parametrize('usage', [None, {}, {'input_tokens': True, 'output_tokens': 0, 'cost': 0},
    {'input_tokens': -1, 'output_tokens': 0, 'cost': 0},
    {'input_tokens': 16384, 'output_tokens': 1, 'cost': 0},
    {'input_tokens': 1, 'output_tokens': 0}, {'input_tokens': 1, 'output_tokens': 0, 'cost': 0.01},
    {'input_tokens': 1, 'output_tokens': 0, 'cost': '0'},
    {'input_tokens': 1, 'output_tokens': 0, 'cost': 0, 'total_tokens': 10}])
def test_unknown_or_nonfree_billing_is_never_accepted(monkeypatch, usage):
    wire(monkeypatch, lambda _: httpx.Response(200, json=reply(usage=usage)))
    log = providers.SpendLog()
    with pytest.raises(runtime.ElephantError, match='invalid_usage'):
        ask(log)(STATE, QUESTIONS, 2)
    assert log.calls[0]['accounting'] == 'unknown' and log.calls[0]['input_tokens'] == 0


@pytest.mark.parametrize('status', [307, 400, 401, 402, 403, 429, 500, 503])
def test_http_failures_do_not_retry_or_forward_credentials(monkeypatch, status):
    sent, _, _ = wire(monkeypatch, lambda _: httpx.Response(status, content=b'{}',
                                                           headers={'Location': 'https://untrusted.invalid'}))
    with pytest.raises(runtime.ElephantError) as caught:
        ask()(STATE, QUESTIONS, 2)
    assert len(sent) == 1
    assert 'synthetic-only-key' not in ''.join(traceback.format_exception(caught.value))


@pytest.mark.parametrize('failure', ['timeout', 'disconnect', 'invalid_json', 'duplicate', 'oversized'])
def test_transport_and_protocol_errors_are_safe_single_attempts(monkeypatch, failure):
    def broken(request):
        if failure == 'timeout':
            raise httpx.ReadTimeout('Bearer synthetic-only-key applicant prose', request=request)
        if failure == 'disconnect':
            raise httpx.RemoteProtocolError('Bearer synthetic-only-key')
        content = b'not json' if failure == 'invalid_json' else b'{"model":"a","model":"b"}' \
            if failure == 'duplicate' else b' ' * (runtime.MAX_RESPONSE_BYTES + 1)
        return httpx.Response(200, content=content)
    sent, _, _ = wire(monkeypatch, broken)
    with pytest.raises(runtime.ElephantError) as caught:
        ask()(STATE, QUESTIONS, 2)
    assert len(sent) == 1
    text = ''.join(traceback.format_exception(caught.value))
    assert 'synthetic-only-key' not in text and 'applicant prose' not in text


@pytest.mark.parametrize('kind', ['headers', 'body', 'validation'])
def test_total_deadline_cancels_and_cleans_up_request(monkeypatch, kind):
    events = []
    class Partial(httpx.AsyncByteStream):
        async def __aiter__(self):
            yield b'{'
            await asyncio.sleep(1)
            events.append('completed')
        async def aclose(self):
            events.append('closed')
    async def delayed(_):
        try:
            await asyncio.sleep(1)
            events.append('completed')
        finally:
            events.append('closed')
        return httpx.Response(200, json=reply())
    sent, _, _ = wire(monkeypatch, delayed if kind == 'headers' else
                       lambda _: httpx.Response(200, stream=Partial()) if kind == 'body' else httpx.Response(200, json=reply()))
    if kind == 'validation':
        original = runtime._validate
        def slow(*args):
            time.sleep(0.15)
            return original(*args)
        monkeypatch.setattr(runtime, '_validate', slow)
    with pytest.raises(runtime.ElephantError, match='timeout'):
        ask()(STATE, QUESTIONS, 0.1)
    assert len(sent) == 1 and events == ([] if kind == 'validation' else ['closed'])


def test_tls_setup_exhausting_deadline_never_dispatches(monkeypatch):
    context = runtime._tls_context()
    initialized = []
    def slow_context():
        initialized.append(True)
        time.sleep(0.15)
        return context
    monkeypatch.setattr(runtime, '_tls_context', slow_context)
    sent, _, _ = wire(monkeypatch, lambda _: httpx.Response(200, json=reply()))
    with pytest.raises(runtime.ElephantError, match='timeout') as caught:
        ask()(STATE, QUESTIONS, 0.1)
    assert initialized == [True]
    assert sent == []
    assert caught.value.dispatched is False


def test_verified_tls_ignores_shared_ca_overrides_and_version_drift_fails_locally(monkeypatch):
    import httpcore
    monkeypatch.setenv('SSL_CERT_FILE', '/missing/synthetic.pem')
    monkeypatch.setenv('SSL_CERT_DIR', '/missing/synthetic-certs')
    before = dict(os.environ)
    context = runtime._tls_context()
    assert context.verify_mode == ssl.CERT_REQUIRED and context.check_hostname and context.get_ca_certs()
    assert dict(os.environ) == before
    monkeypatch.setattr(httpcore, '__version__', 'unverified')
    with pytest.raises(runtime.ElephantError, match='transport_version_unverified'):
        ask()(STATE, QUESTIONS, 1)


def test_saturation_does_not_queue_or_repeat_work(monkeypatch):
    entered, release = threading.Event(), threading.Event()
    def blocked(*_):
        entered.set()
        assert release.wait(2)
        return 200, json.dumps(reply()).encode()
    monkeypatch.setattr(runtime, '_post_once', blocked)
    with ThreadPoolExecutor(max_workers=1) as pool:
        first = pool.submit(ask(), STATE, QUESTIONS, 2)
        assert entered.wait(1)
        try:
            with pytest.raises(runtime.ElephantError, match='scoring_busy'):
                ask()(STATE, QUESTIONS, 1)
        finally:
            release.set()
        assert first.result()['model'] == runtime.RESPONSE_MODEL


@pytest.mark.parametrize('mode', ['eof', 'cancel'])
def test_installed_tls_handshake_closes_acquired_tcp_stream_on_failure(monkeypatch, mode):
    import anyio
    from httpcore._backends.anyio import AnyIOStream
    streams, posts = [], []
    class Peer:
        closed = False
        async def send(self, data):
            posts.append(data.startswith(b'POST '))
        async def receive(self, max_bytes=65536):
            if mode == 'eof':
                raise anyio.EndOfStream
            await asyncio.sleep(1)
            return b''
        async def aclose(self):
            self.closed = True
    class Backend:
        async def connect_tcp(self, **kwargs):
            peer = Peer()
            streams.append(peer)
            return AnyIOStream(peer)
        async def sleep(self, seconds):
            pytest.fail('hidden HTTP retry')
    original = httpx.AsyncHTTPTransport
    def owned_peer(**kwargs):
        transport = original(**kwargs)
        transport._pool._network_backend = Backend()
        return transport
    monkeypatch.setattr(httpx, 'AsyncHTTPTransport', owned_peer)
    with pytest.raises(runtime.ElephantError):
        ask()(STATE, QUESTIONS, 0.1)
    assert len(streams) == 1 and not any(posts)
    assert all(peer.closed for peer in streams)


def test_accounting_failure_does_not_repeat_a_successful_post(monkeypatch):
    sent, _, _ = wire(monkeypatch, lambda _: httpx.Response(200, json=reply()))
    def unavailable(*_, **__):
        raise OSError('synthetic-only-key private ledger details')
    monkeypatch.setattr(llm_gate, 'settle', unavailable)
    with pytest.raises(runtime.ElephantError, match='accounting_unavailable') as caught:
        ask()(STATE, QUESTIONS, 1)
    assert len(sent) == 1 and 'private ledger' not in ''.join(traceback.format_exception(caught.value))


@pytest.mark.parametrize('live,override,key,enabled', [
    ('0', None, 'synthetic', False), ('0', '1', '', False), ('0', '1', 'synthetic', True),
    ('1', None, 'synthetic', True), ('1', '', 'synthetic', True), ('1', '0', 'synthetic', False)])
def test_mode_and_key_admission_is_explicit(monkeypatch, live, override, key, enabled):
    monkeypatch.setenv('BATATIS_LIVE', live)
    if override is None:
        monkeypatch.delenv('BATATIS_LIVE_ELEPHANT')
    else:
        monkeypatch.setenv('BATATIS_LIVE_ELEPHANT', override)
    monkeypatch.setenv('OPENROUTER_API_KEY', key)
    assert llm_gate.provider_enabled('elephant') is enabled
    assert bool(providers.transports().elephant) is enabled
    if not enabled:
        with pytest.raises(providers.GateClosed):
            runtime.metered_ask(lambda *_: pytest.fail('gate bypass'))(STATE, QUESTIONS, 1)


def test_elephant_only_switch_never_enables_other_providers_or_credential_resolution(monkeypatch):
    from engine.identify.jevkit import keystore
    monkeypatch.setattr(keystore, 'resolve', lambda *_: pytest.fail('Jev credential resolution'))
    monkeypatch.setenv('OPENAI_API_KEY', 'synthetic-openai')
    monkeypatch.setenv('ANTHROPIC_API_KEY', 'synthetic-anthropic')
    tp = providers.transports()
    assert tp.elephant and tp.jev is None and tp.decisions is None and tp.openai is None and tp.anthropic is None
    assert not llm_gate.authorize(max_input_tokens=1, max_output_tokens=1).allowed
    assert not llm_gate.reserve(provider='elephant', model='baseten/elephant-1',
                                max_input_tokens=1, max_output_tokens=1).allowed
    monkeypatch.setenv('BATATIS_PROVIDER', 'fake')
    monkeypatch.delenv('OPENROUTER_API_KEY')
    assert providers.transports().elephant
    monkeypatch.setenv('VERCEL', '1')
    assert not llm_gate.fake_providers() and providers.transports().elephant is None


def test_elephant_preserves_existing_run_limits_and_unrelated_spend(monkeypatch):
    from decimal import Decimal
    monkeypatch.setenv('BATATIS_IDENTIFY_RATE_LIMIT', '1')
    monkeypatch.setenv('BATATIS_RELEVANCE_RATE_LIMIT', '1')
    assert llm_gate.identify_retry_after('synthetic-ip') is None
    assert llm_gate.relevance_retry_after('synthetic-ip') is None
    llm_gate._memory.adjust(Decimal('0.123'))  # an unrelated existing reservation
    runtime.metered_ask(lambda *_: reply())(STATE, QUESTIONS, 1)
    assert llm_gate._memory.today() == Decimal('0.123')
    assert llm_gate.identify_retry_after('synthetic-ip') > 0
    assert llm_gate.relevance_retry_after('synthetic-ip') > 0


@pytest.mark.parametrize('timeout', [True, 0, 0.01, 61, float('nan'), float('inf'), 10 ** 400])
def test_invalid_timeout_is_rejected_before_admission(monkeypatch, timeout):
    monkeypatch.setattr(llm_gate, 'reserve', lambda **_: pytest.fail('invalid timeout admitted'))
    with pytest.raises(runtime.ElephantError, match='invalid_timeout'):
        ask()(STATE, QUESTIONS, timeout)


@pytest.mark.parametrize('questions,state', [({}, STATE), (QUESTIONS, 'x' * 20000),
    ({'x': {'type': 'noul'}}, STATE), ({'x': {'type': 'score', 'instructions': 'Rate', 'criteria': ['one']}}, STATE),
    ({'x': {'type': 'noul', 'instructions': 'Blue?', 'criteria': {'true': 'yes'}}}, STATE)])
def test_invalid_or_oversized_request_is_rejected_before_admission(monkeypatch, questions, state):
    monkeypatch.setattr(llm_gate, 'reserve', lambda **_: pytest.fail('invalid input admitted'))
    with pytest.raises(runtime.ElephantError):
        ask()(state, questions, 2)


def synthetic_articles(n=2080):
    return {str(i): {'title': f'SYNTHETIC {i}', 'part': 9, 'section': 'Walls', 'subsection': 'Materials',
                     'text': 'A synthetic requirement about walls. ' * 30} for i in range(n)}


def test_full_corpus_batches_include_all_questions_and_cards_without_hidden_truncation(monkeypatch):
    from engine.identify.corpus import card
    arts, sent = synthetic_articles(), []
    query = 'SYNTHETIC: wall proposal ☃' * 15
    def capture(state, questions, timeout):
        blob = runtime.request_bytes(state, questions)
        sent.append((deepcopy(state), deepcopy(questions), len(blob)))
        return {'answers': {name: {'noul': 0.5} for name in questions},
                'usage': {'input_tokens': 1, 'output_tokens': 0}}
    capture.method, capture.model = 'elephant', ELEPHANT_MODEL
    judge = Judge(capture, workers=8, attempts=4)
    scores = judge.judge(query, arts, list(arts))
    assert len(scores) == 2080 and set(scores) == set(arts)
    assert sum(len(qs) for _, qs, _ in sent) == 2080
    assert len(sent) > 1 and all(state['proposal'] == query for state, _, _ in sent)
    outgoing = [text for state, _, _ in sent for text in state['articles'].values()]
    assert outgoing == [card(art, 700) for art in arts.values()]
    assert all(q['instructions'] == GOVERN.format(L=f'A{i}')
               for _, qs, _ in sent for i, q in enumerate(qs.values()))
    assert all(size + runtime.FRAMING_TOKENS + len(qs) * 128 <= runtime.CONTEXT_TOKENS for _, qs, size in sent)
    # The 60-item rerank is also split at the actual wire budget.
    assert len(judge.batches(query, arts, list(arts)[:60])) > 1


def test_first_failure_aborts_remaining_batches_without_retry_or_partial_result():
    calls = []
    def broken(*_):
        calls.append(1)
        raise runtime.ElephantError('rate_limited')
    broken.method, broken.model = 'elephant', ELEPHANT_MODEL
    judge = Judge(broken, workers=8, attempts=4)
    arts = synthetic_articles()
    with pytest.raises(runtime.ElephantError, match='rate_limited'):
        judge.judge('SYNTHETIC', arts, list(arts))
    assert len(calls) == 1 and judge.usage.errors == 1


def test_oversized_late_article_and_proposal_fail_before_any_batch_is_sent():
    arts = synthetic_articles(2)
    arts['1']['text'] = '☃' * 20000
    def forbidden(*_):
        pytest.fail('partial corpus dispatched')
    forbidden.method, forbidden.model = 'elephant', ELEPHANT_MODEL
    judge = Judge(forbidden, chars=50000)
    with pytest.raises(runtime.ElephantError, match='request_too_large'):
        judge.judge('SYNTHETIC', arts, list(arts))
    with pytest.raises(runtime.ElephantError, match='request_too_large'):
        judge.judge('SYNTHETIC' * 3000, arts, list(arts))
