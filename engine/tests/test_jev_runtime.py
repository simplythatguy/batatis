"""Offline behavioral reproductions. Never reaches a provider or canonical process."""
from decimal import Decimal
import json
import os
import socket
import ssl
import time

import pytest
from engine import llm_gate
from engine.identify.providers import GateClosed, SpendLog, metered_ask, metered_openai_json
from engine.identify import jev_runtime
from engine.identify.jev_runtime import JevResponseError


@pytest.fixture(autouse=True)
def offline_only(monkeypatch):
    # This separate test process alone uses the repository's offline provider mechanism.
    monkeypatch.setenv('BATATIS_PROVIDER', 'fake')
    monkeypatch.setenv('BATATIS_STORE', 'file')
    monkeypatch.setenv('BATATIS_LIVE', '0')
    monkeypatch.setenv('BATATIS_DAILY_SPEND_CAP_USD', '0.01')
    monkeypatch.delenv('VERCEL', raising=False)
    monkeypatch.delenv('BATATIS_JEV_UNCAPPED', raising=False)
    for name in ('OPENAI_API_KEY','ANTHROPIC_API_KEY','XAI_API_KEY','TYPESAFE_API_KEY','JEV_API_KEY'):
        monkeypatch.delenv(name, raising=False)
    def forbidden(*args, **kwargs):
        pytest.fail('unexpected_network_attempt')
    monkeypatch.setattr(socket.socket, 'connect', forbidden)
    llm_gate.reset_for_tests()
    yield
    llm_gate.reset_for_tests()


STATE = {'proposal': 'A synthetic exterior wall requires a fire resistance rating.'}
QUESTIONS = {'wall': {'type': 'noul', 'instructions': 'The proposal concerns an exterior wall.'}}


def test_ambiguous_dispatched_failure_retains_spend_reservation():
    attempts = []
    def attempted(state, questions, timeout):
        attempts.append(1)  # Simulates dispatch; no actual socket or provider.
        raise TimeoutError('synthetic lost acknowledgement after dispatch')
    ask = metered_ask(attempted)
    with pytest.raises(TimeoutError):
        ask(STATE, QUESTIONS, 1)
    assert len(attempts) == 1
    assert llm_gate._memory.today() > Decimal('0'), (
        'An attempted request with unknown billing must not regain the reserved allowance')


def test_usable_answer_without_usage_retains_spend_reservation():
    ask = metered_ask(lambda *args: {'answers': {'wall': {'type':'noul','noul':0.9}}})
    with pytest.raises(JevResponseError, match='invalid_usage'):
        ask(STATE, QUESTIONS, 1)
    assert llm_gate._memory.today() > Decimal('0'), (
        'Missing usage must not be treated as a free successful provider request')


def test_invalid_negative_usage_never_creates_new_allowance():
    ask = metered_ask(lambda *args: {
        'answers': {'wall': {'type':'noul','noul':0.9}},
        'usage': {'input_tokens': -1000000, 'output_tokens': -1000000}})
    with pytest.raises(JevResponseError, match='invalid_usage'):
        ask(STATE, QUESTIONS, 1)
    assert llm_gate._memory.today() >= Decimal('0'), 'Invalid usage must never credit the ledger'


def test_live_adapter_has_one_transport_attempt_and_pins_typesafe(monkeypatch):
    from engine.identify.screen import raw_jev_ask
    from engine.identify.jevkit import client
    sent = {}
    def capture(*args, **kwargs):
        sent.update(kwargs)
        return {'answers': {}, 'usage': {'input_tokens': 1, 'output_tokens': 0}}
    monkeypatch.setattr(client, 'ask', capture)
    raw_jev_ask()(STATE, QUESTIONS, 1)
    assert sent.get('retries') == 0
    assert sent['provider'] == 'typesafe' and sent['model'] == 'jev-1.13.0'
    assert callable(sent.get('transport'))


def wire(monkeypatch, handler):
    """Real request construction and validators; substitute only the HTTP socket boundary."""
    import httpx
    from engine.identify.jevkit import keystore
    requests, options = [], []
    monkeypatch.setattr(keystore, 'resolve', lambda *args: 'synthetic-test-key')
    def transport(**kwargs):
        options.append(kwargs)
        def send(request):
            requests.append(request)
            return handler(request)
        return httpx.MockTransport(send)
    monkeypatch.setattr(httpx, 'HTTPTransport', transport)
    monkeypatch.setattr(httpx, 'AsyncHTTPTransport', transport)
    return requests, options


def response(**changes):
    payload = {'model': 'jev-1.13.0', 'answers': {'wall': {'type': 'noul', 'noul': 0.9}},
               'usage': {'input_tokens': 1000, 'output_tokens': 20}}
    payload.update(changes)
    return payload


def test_verified_tls_is_jev_local_and_ignores_broken_shared_ssl_environment(monkeypatch):
    monkeypatch.setenv('SSL_CERT_FILE', '/synthetic/missing-ca.pem')
    monkeypatch.setenv('SSL_CERT_DIR', '/synthetic/missing-certs')
    before = dict(os.environ)
    context = jev_runtime._tls_context()
    assert context.check_hostname and context.verify_mode == ssl.CERT_REQUIRED
    assert context.get_ca_certs()
    assert dict(os.environ) == before


def test_wire_success_has_fixed_origin_and_no_hidden_retry_or_redirect(monkeypatch):
    import httpx
    requests, options = wire(monkeypatch, lambda request: httpx.Response(200, json=response()))
    log = SpendLog()
    reply = metered_ask(jev_runtime.raw_ask(), log=log)(STATE, QUESTIONS, 1)
    assert reply['model'] == 'jev-1.13.0' and reply['answers']['wall']['noul'] == 0.9
    assert len(requests) == 1
    request = requests[0]
    assert str(request.url) == 'https://api.typesafe.ai/v1/systemone'
    assert request.method == 'POST'
    assert json.loads(request.content)['model'] == 'jev-1.13.0'
    assert 'X-Typesafe-Long-Context' not in request.headers
    assert options[0]['retries'] == 0 and options[0]['trust_env'] is False
    assert options[0]['verify'].verify_mode == ssl.CERT_REQUIRED
    assert llm_gate._memory.today() == Decimal('0.000042')  # output is free
    assert log.calls[0]['output_tokens'] == 20


@pytest.mark.parametrize('failure', ['timeout', 'disconnect', 'redirect'])
def test_ambiguous_wire_failure_is_one_attempt_and_does_not_forward_credentials(monkeypatch, failure):
    import httpx
    def handler(request):
        if failure == 'timeout':
            raise httpx.ReadTimeout('synthetic lost acknowledgement', request=request)
        if failure == 'disconnect':
            raise httpx.RemoteProtocolError('synthetic disconnect')
        return httpx.Response(307, headers={'Location': 'https://other.invalid/'}, json={})
    requests, _ = wire(monkeypatch, handler)
    with pytest.raises(JevResponseError) as caught:
        metered_ask(jev_runtime.raw_ask())(STATE, QUESTIONS, 1)
    assert len(requests) == 1
    assert 'synthetic-test-key' not in str(caught.value)
    assert llm_gate._memory.today() > 0


@pytest.mark.parametrize('bad', [
    {'answers': {}},
    {'answers': {'wall': {'type': 'noul', 'noul': -0.2}}},
    {'answers': {'wall': {'type': 'noul', 'noul': float('nan')}}},
    {'answers': {'wall': {'type': 'noul', 'noul': True}}},
    {'answers': {'wall': {'type': 'choice', 'choice': 'yes'}}},
    {'answers': {'wall': {'type': 'noul', 'noul': 0.8}, 'unasked': {'type': 'noul', 'noul': 1}}},
    {'model': 'jev-latest'},
    {'model': None},
])
def test_malformed_or_drifted_result_is_never_accepted_and_billing_is_retained(monkeypatch, bad):
    import httpx
    requests, _ = wire(monkeypatch, lambda request: httpx.Response(200, json=response(**bad))
                       if 'nan' not in repr(bad) else httpx.Response(200, content=json.dumps(response(**bad))))
    log = SpendLog()
    with pytest.raises(JevResponseError):
        metered_ask(jev_runtime.raw_ask(), log=log)(STATE, QUESTIONS, 1)
    assert len(requests) == 1
    assert llm_gate._memory.today() > 0
    assert len(log.calls) == 1


@pytest.mark.parametrize('bad_usage', [None, {}, {'input_tokens': 1},
    {'input_tokens': True, 'output_tokens': 0}, {'input_tokens': 1.5, 'output_tokens': 0},
    {'input_tokens': -1, 'output_tokens': 0}, {'input_tokens': 1, 'output_tokens': -1},
    {'input_tokens': 65537, 'output_tokens': 0}])
def test_invalid_usage_retains_full_reservation(monkeypatch, bad_usage):
    import httpx
    wire(monkeypatch, lambda request: httpx.Response(200, json=response(usage=bad_usage)))
    log = SpendLog()
    with pytest.raises(JevResponseError, match='invalid_usage'):
        metered_ask(jev_runtime.raw_ask(), log=log)(STATE, QUESTIONS, 1)
    assert llm_gate._memory.today() == llm_gate.estimate_usd('jev-1.13.0', 65536, 0)
    assert log.calls[0]['accounting'] == 'held'


def test_explicit_jev_uncapped_does_not_change_any_shared_balance_or_other_provider_cap(monkeypatch):
    monkeypatch.setenv('BATATIS_JEV_UNCAPPED', '1')
    monkeypatch.setenv('BATATIS_DAILY_SPEND_CAP_USD', '0')
    before = dict(llm_gate._memory.by_day)
    log = SpendLog()
    reply = metered_ask(lambda *args: response(), log=log)(STATE, QUESTIONS, 1)
    assert reply['answers']['wall']['noul'] == 0.9
    assert llm_gate._memory.by_day == before
    assert log.calls[0]['accounting'] == 'uncapped'
    def no_openai(*args, **kwargs):
        pytest.fail('Jev authorization must not enable another provider')
    with pytest.raises(GateClosed):
        metered_openai_json(no_openai)('test', {}, '', '', model='gpt-6-luna')
    assert llm_gate._memory.by_day == before


def test_jev_uncapped_does_not_enable_live_calls_or_resolve_a_secret(monkeypatch):
    from engine.identify.jevkit import keystore
    monkeypatch.setenv('BATATIS_JEV_UNCAPPED', '1')
    monkeypatch.delenv('BATATIS_PROVIDER')
    def forbidden(*args):
        pytest.fail('offline calls must not consult credentials')
    monkeypatch.setattr(keystore, 'resolve', forbidden)
    with pytest.raises(GateClosed, match='offline'):
        metered_ask(lambda *args: pytest.fail('offline dispatch'))(STATE, QUESTIONS, 1)


def test_jev_uncapped_does_not_reset_or_bypass_existing_run_rate_windows(monkeypatch):
    monkeypatch.setenv('BATATIS_JEV_UNCAPPED', '1')
    monkeypatch.setenv('BATATIS_IDENTIFY_RATE_LIMIT', '1')
    monkeypatch.setenv('BATATIS_RELEVANCE_RATE_LIMIT', '1')
    assert llm_gate.identify_retry_after('synthetic-ip') is None
    assert llm_gate.relevance_retry_after('synthetic-ip') is None
    metered_ask(lambda *args: response())(STATE, QUESTIONS, 1)
    assert llm_gate.identify_retry_after('synthetic-ip') > 0
    assert llm_gate.relevance_retry_after('synthetic-ip') > 0


def test_reply_after_entire_request_deadline_is_rejected(monkeypatch):
    import httpx
    def delayed(request):
        time.sleep(0.15)
        return httpx.Response(200, json=response())
    requests, _ = wire(monkeypatch, delayed)
    with pytest.raises(JevResponseError, match='timeout'):
        metered_ask(jev_runtime.raw_ask())(STATE, QUESTIONS, 0.1)
    assert len(requests) == 1
    assert llm_gate._memory.today() > 0


def test_total_deadline_cancels_wait_for_headers_without_retry(monkeypatch):
    import asyncio
    import httpx
    events = []
    async def delayed(request):
        try:
            await asyncio.sleep(1)
            events.append('completed')
            return httpx.Response(200, json=response())
        finally:
            events.append('closed')
    requests, _ = wire(monkeypatch, delayed)
    with pytest.raises(JevResponseError, match='timeout'):
        metered_ask(jev_runtime.raw_ask())(STATE, QUESTIONS, 0.1)
    assert events == ['closed'] and len(requests) == 1
    assert llm_gate._memory.today() > 0


def test_total_deadline_cancels_a_partial_response_and_closes_the_stream(monkeypatch):
    import asyncio
    import httpx
    events = []
    class Partial(httpx.AsyncByteStream):
        async def __aiter__(self):
            yield b'{'
            await asyncio.sleep(1)
            events.append('completed')
            yield b'}'
        async def aclose(self):
            events.append('closed')
    requests, _ = wire(monkeypatch, lambda request: httpx.Response(200, stream=Partial()))
    with pytest.raises(JevResponseError, match='timeout'):
        metered_ask(jev_runtime.raw_ask())(STATE, QUESTIONS, 0.1)
    assert events == ['closed'] and len(requests) == 1


def test_oversized_reply_is_rejected_after_one_request(monkeypatch):
    import httpx
    requests, _ = wire(monkeypatch, lambda request: httpx.Response(200, content=b' ' * 1_000_001))
    with pytest.raises(JevResponseError, match='response_too_large'):
        metered_ask(jev_runtime.raw_ask())(STATE, QUESTIONS, 1)
    assert len(requests) == 1 and llm_gate._memory.today() > 0


@pytest.mark.parametrize('status', [401, 429, 500, 307])
@pytest.mark.parametrize('returned_model', [None, 'unrequested-model'])
def test_error_status_cannot_settle_usage_from_an_unverified_model(monkeypatch, status, returned_model):
    import httpx
    wire(monkeypatch, lambda request: httpx.Response(status, json=response(
        model=returned_model, usage={'input_tokens': 0, 'output_tokens': 0})))
    log = SpendLog()
    with pytest.raises(JevResponseError):
        metered_ask(jev_runtime.raw_ask(), log=log)(STATE, QUESTIONS, 1)
    assert llm_gate._memory.today() == Decimal('0.002753')
    assert log.calls[0]['accounting'] == 'held'


@pytest.mark.parametrize('uncapped', [False, True])
@pytest.mark.parametrize('ambiguous', [
    '{"model":"jev-1.13.0","answers":{"wall":{"type":"noul","noul":0.9}},'
    '"usage":{"input_tokens":60000,"input_tokens":0,"output_tokens":0}}',
    '{"model":"jev-1.13.0","answers":{"wall":{"type":"noul","noul":0.9}},'
    '"usage":{"input_tokens":60000,"output_tokens":0},"usage":{"input_tokens":0,"output_tokens":0}}',
    '{"model":"unrequested-model","model":"jev-1.13.0",'
    '"answers":{"wall":{"type":"noul","noul":0.9}},"usage":{"input_tokens":0,"output_tokens":0}}',
    '{"model":"jev-1.13.0","answers":{"wall":{"type":"noul","noul":0.1,"noul":0.9}},'
    '"usage":{"input_tokens":0,"output_tokens":0}}',
])
def test_duplicate_protocol_members_are_rejected_with_or_without_dollar_exemption(monkeypatch, uncapped, ambiguous):
    import httpx
    if uncapped:
        monkeypatch.setenv('BATATIS_JEV_UNCAPPED', '1')
    requests, _ = wire(monkeypatch, lambda request: httpx.Response(200, content=ambiguous))
    with pytest.raises(JevResponseError):
        metered_ask(jev_runtime.raw_ask())(STATE, QUESTIONS, 1)
    assert len(requests) == 1
    assert llm_gate._memory.today() == (Decimal('0') if uncapped else Decimal('0.002753'))


def test_numeric_overflow_is_nonretryable_and_preserves_known_usage(monkeypatch):
    import httpx
    from engine.identify import screen
    monkeypatch.setenv('BATATIS_DAILY_SPEND_CAP_USD', '0.1')
    monkeypatch.setattr(screen, 'card', lambda *args: 'Synthetic article about emergency escape windows.')
    monkeypatch.setattr(screen.time, 'sleep', lambda *args: None)
    def huge(request):
        names = json.loads(request.content)['questions']
        return httpx.Response(200, json=response(answers={name: {'type': 'noul', 'noul': 10**400} for name in names}))
    requests, _ = wire(monkeypatch, huge)
    log = SpendLog()
    judge = screen.Judge(ask=metered_ask(jev_runtime.raw_ask(), log=log), attempts=4)
    with pytest.raises(JevResponseError):
        judge.judge('Synthetic escape window', {'fixture': {}}, ['fixture'])
    assert len(requests) == 1 and judge.usage.errors == 1
    assert llm_gate._memory.today() == Decimal('0.000042')
    assert log.calls[0]['accounting'] == 'settled'


@pytest.mark.parametrize('questions,timeout', [({}, 1), ({'wall': {'type': 'noul'}}, 1), (QUESTIONS, 0.01)])
def test_proven_local_rejection_does_not_consume_the_next_calls_allowance(monkeypatch, questions, timeout):
    import httpx
    monkeypatch.setenv('BATATIS_DAILY_SPEND_CAP_USD', '0.003')
    requests, _ = wire(monkeypatch, lambda request: httpx.Response(200, json=response()))
    log = SpendLog()
    ask = metered_ask(jev_runtime.raw_ask(), log=log)
    with pytest.raises(JevResponseError):
        ask(STATE, questions, timeout)
    assert not requests and llm_gate._memory.today() == Decimal('0')
    if timeout < 0.05:
        assert log.calls == []  # rejected before the metered body/reservation was entered
    else:
        assert log.calls[0]['accounting'] == 'not_dispatched'
    assert ask(STATE, QUESTIONS, 1)['answers']['wall']['noul'] == 0.9
    assert len(requests) == 1 and llm_gate._memory.today() == Decimal('0.000042')


def test_local_tls_setup_failure_does_not_consume_shared_allowance(monkeypatch):
    import httpx
    requests, _ = wire(monkeypatch, lambda request: httpx.Response(200, json=response()))
    def missing_roots():
        raise FileNotFoundError('synthetic missing trust bundle')
    monkeypatch.setattr(jev_runtime, '_tls_context', missing_roots)
    with pytest.raises(JevResponseError):
        metered_ask(jev_runtime.raw_ask())(STATE, QUESTIONS, 1)
    assert not requests and llm_gate._memory.today() == Decimal('0')


def test_accounting_acknowledgement_failure_never_repeats_a_billed_request(monkeypatch):
    import httpx
    from engine.identify import screen
    monkeypatch.setenv('BATATIS_DAILY_SPEND_CAP_USD', '0.1')
    monkeypatch.setattr(screen, 'card', lambda *args: 'Synthetic article about emergency escape windows.')
    monkeypatch.setattr(screen.time, 'sleep', lambda *args: None)
    def success(request):
        names = json.loads(request.content)['questions']
        return httpx.Response(200, json=response(answers={name: {'type': 'noul', 'noul': 0.9} for name in names}))
    requests, _ = wire(monkeypatch, success)
    def failed_ack(*args, **kwargs):
        raise OSError('synthetic unknown ledger acknowledgement')
    monkeypatch.setattr(llm_gate, 'settle', failed_ack)
    judge = screen.Judge(ask=metered_ask(jev_runtime.raw_ask()), attempts=4)
    with pytest.raises(JevResponseError, match='accounting_unavailable'):
        judge.judge('Synthetic escape window', {'fixture': {}}, ['fixture'])
    assert len(requests) == 1 and llm_gate._memory.today() == Decimal('0.002753')


def test_total_deadline_also_refuses_slow_response_validation_with_known_usage(monkeypatch):
    import httpx
    from engine.identify.jevkit import client
    check = client._check_answer
    def slow(*args, **kwargs):
        time.sleep(0.15)
        return check(*args, **kwargs)
    monkeypatch.setattr(client, '_check_answer', slow)
    requests, _ = wire(monkeypatch, lambda request: httpx.Response(200, json=response()))
    with pytest.raises(JevResponseError, match='timeout'):
        metered_ask(jev_runtime.raw_ask())(STATE, QUESTIONS, 0.1)
    assert len(requests) == 1 and llm_gate._memory.today() == Decimal('0.000042')


def test_matching_model_on_error_keeps_known_usage_instead_of_overholding(monkeypatch):
    import httpx
    requests, _ = wire(monkeypatch, lambda request: httpx.Response(500, json=response()))
    log = SpendLog()
    with pytest.raises(JevResponseError, match='http_500'):
        metered_ask(jev_runtime.raw_ask(), log=log)(STATE, QUESTIONS, 1)
    assert len(requests) == 1 and llm_gate._memory.today() == Decimal('0.000042')
    assert log.calls[0]['accounting'] == 'settled'


def test_unique_zero_usage_and_optional_metadata_remain_valid(monkeypatch):
    import httpx
    wire(monkeypatch, lambda request: httpx.Response(200, json=response(usage={
        'input_tokens': 0, 'output_tokens': 0, 'optional_metadata': 'allowed'})))
    assert metered_ask(jev_runtime.raw_ask())(STATE, QUESTIONS, 1)['answers']['wall']['noul'] == 0.9
    assert llm_gate._memory.today() == Decimal('0')


def test_missing_credential_at_fake_gate_seam_is_proven_not_dispatched(monkeypatch):
    import httpx
    from engine.identify.jevkit import keystore
    requests, _ = wire(monkeypatch, lambda request: httpx.Response(200, json=response()))
    monkeypatch.setattr(keystore, 'resolve', lambda *args: None)
    log = SpendLog()
    with pytest.raises(JevResponseError, match='no_key'):
        metered_ask(jev_runtime.raw_ask(), log=log)(STATE, QUESTIONS, 1)
    assert not requests and llm_gate._memory.today() == Decimal('0')
    assert log.calls[0]['accounting'] == 'not_dispatched'


def test_uncertain_release_acknowledgement_is_never_retried(monkeypatch):
    from engine.identify import screen
    monkeypatch.setattr(screen, 'card', lambda *args: 'Synthetic article about emergency escape windows.')
    attempts = []
    def local(*args):
        attempts.append(1)
        raise JevResponseError('invalid_request', dispatched=False)
    def failed_ack(*args):
        raise OSError('synthetic unknown release acknowledgement')
    monkeypatch.setattr(llm_gate, 'release', failed_ack)
    judge = screen.Judge(ask=metered_ask(local), attempts=4)
    with pytest.raises(JevResponseError, match='accounting_unavailable'):
        judge.judge('Synthetic escape window', {'fixture': {}}, ['fixture'])
    assert len(attempts) == 1 and llm_gate._memory.today() == Decimal('0.002753')


def test_deadline_expired_during_local_key_lookup_never_starts_a_post(monkeypatch):
    import httpx
    from engine.identify.jevkit import keystore
    requests, _ = wire(monkeypatch, lambda request: httpx.Response(200, json=response()))
    def slow(*args):
        time.sleep(0.15)
        return 'synthetic-test-key'
    monkeypatch.setattr(keystore, 'resolve', slow)
    with pytest.raises(JevResponseError, match='timeout'):
        metered_ask(jev_runtime.raw_ask())(STATE, QUESTIONS, 0.1)
    assert not requests and llm_gate._memory.today() == Decimal('0')


@pytest.mark.parametrize('stage', ['reserve', 'settle'])
def test_public_deadline_includes_real_accounting_work(monkeypatch, stage):
    import httpx
    requests, _ = wire(monkeypatch, lambda request: httpx.Response(200, json=response()))
    name = 'try_reserve' if stage == 'reserve' else 'adjust'
    original = getattr(llm_gate._memory, name)
    def slow(*args, **kwargs):
        time.sleep(0.15)
        return original(*args, **kwargs)
    monkeypatch.setattr(llm_gate._memory, name, slow)
    with pytest.raises(JevResponseError, match='timeout'):
        metered_ask(jev_runtime.raw_ask())(STATE, QUESTIONS, 0.1)
    assert len(requests) == (0 if stage == 'reserve' else 1)
    assert llm_gate._memory.today() == (Decimal('0') if stage == 'reserve' else Decimal('0.000042'))


@pytest.mark.parametrize('mode', ['eof', 'cancel'])
@pytest.mark.parametrize('uncapped', [False, True])
def test_installed_tls_handshake_closes_acquired_stream_on_cancellation(monkeypatch, mode, uncapped):
    import asyncio
    import anyio
    import httpx
    from httpcore._backends.anyio import AnyIOStream
    if uncapped:
        monkeypatch.setenv('BATATIS_JEV_UNCAPPED', '1')
    monkeypatch.setenv('TYPESAFE_API_KEY', 'synthetic-owned-test-credential')
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
            pytest.fail('hidden retry')
    transport = httpx.AsyncHTTPTransport
    def owned_peer(**kwargs):
        client = transport(**kwargs)
        client._pool._network_backend = Backend()
        return client
    monkeypatch.setattr(httpx, 'AsyncHTTPTransport', owned_peer)
    with pytest.raises(JevResponseError):
        metered_ask(jev_runtime.raw_ask())(STATE, QUESTIONS, 0.1)
    closed_before_test_cleanup = [peer.closed for peer in streams]
    async def cleanup():
        for peer in streams:
            if not peer.closed:
                await peer.aclose()
    asyncio.run(cleanup())
    assert len(streams) == 1 and not any(posts)
    assert all(closed_before_test_cleanup), 'acquired TLS stream must close before returning'


def test_runtime_freeze_blocks_cached_asks_without_dispatch_or_accounting():
    attempts = []
    def raw(*args):
        attempts.append(1)
        return response()
    ask = metered_ask(raw)
    jev_runtime._freeze_runtime()
    try:
        with pytest.raises(JevResponseError, match='runtime_busy'):
            ask(STATE, QUESTIONS, 1)
        assert not attempts and llm_gate._memory.today() == Decimal('0')
    finally:
        jev_runtime._resume_runtime()
    assert ask(STATE, QUESTIONS, 1)['answers']['wall']['noul'] == 0.9


def test_runtime_freeze_refuses_an_active_call_and_preserves_it():
    import threading
    started, release = threading.Event(), threading.Event()
    completed = []
    def raw(*args):
        started.set()
        assert release.wait(3)
        return response()
    ask = metered_ask(raw)
    worker = threading.Thread(target=lambda: completed.append(ask(STATE, QUESTIONS, 2)))
    worker.start()
    try:
        assert started.wait(2)
        with pytest.raises(JevResponseError, match='runtime_busy'):
            jev_runtime._freeze_runtime()
    finally:
        release.set()
        worker.join(timeout=3)
    assert not worker.is_alive() and completed[0]['answers']['wall']['noul'] == 0.9
    assert llm_gate._memory.today() == Decimal('0.000042')


def test_runtime_freeze_is_jev_only_and_keeps_other_provider_behavior():
    from engine.identify.providers import metered_openai_json
    jev_runtime._freeze_runtime()
    try:
        call = metered_openai_json(lambda *args, **kwargs: ({'ok': True}, {'input_tokens': 1, 'output_tokens': 1}))
        result, usage = call('synthetic', {}, '', '', model='gpt-6-luna')
        assert result == {'ok': True} and usage['input_tokens'] == 1
    finally:
        jev_runtime._resume_runtime()
