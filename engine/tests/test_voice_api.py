"""Synthetic voice contracts: isolated stores, no microphone or live provider."""
from fastapi.testclient import TestClient
import pytest
from starlette.websockets import WebSocketDisconnect

from engine.api import create_app
from engine import llm_gate, routes_voice
from engine.store import CaseStore
from engine.tests.test_accounts import signup, onboard
from engine.tests.test_voice_context import synthetic_codes, pdf_bytes
from engine.accounts import COOKIE, digest
from decimal import Decimal
import asyncio
import base64
import threading


def test_capability_requires_sign_in_without_provider_or_spend(tmp_path, monkeypatch):
    monkeypatch.delenv('VERCEL', raising=False)
    monkeypatch.delenv('BATATIS_STORE', raising=False)
    monkeypatch.delenv('BATATIS_LIVE', raising=False)
    with TestClient(create_app(store=CaseStore(tmp_path / 'voice.sqlite')),
                    base_url='http://localhost') as client:
        result = client.get('/voice/session')
    assert result.status_code == 401
    assert result.json()['detail'] == 'Sign in to continue'


def test_websocket_requires_a_real_cookie_session_before_accepting(tmp_path, monkeypatch):
    monkeypatch.delenv('VERCEL', raising=False)
    monkeypatch.delenv('BATATIS_STORE', raising=False)
    with TestClient(create_app(store=CaseStore(tmp_path / 'voice.sqlite')),
                    base_url='http://localhost') as client:
        with pytest.raises(WebSocketDisconnect) as rejected:
            with client.websocket_connect('/api/voice/relay/session',
                    headers={'Origin': 'http://localhost:5480'}, subprotocols=['batatis.voice.v1']):
                pass
        assert rejected.value.code == 4401


@pytest.fixture
def voice_app(tmp_path, monkeypatch):
    for name in ('VERCEL', 'BATATIS_STORE', 'ANTHROPIC_API_KEY', 'OPENAI_API_KEY'):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv('BATATIS_LIVE', '1')
    monkeypatch.setenv('XAI_API_KEY', 'synthetic-xai-secret')
    monkeypatch.setenv('BATATIS_WEB_ORIGIN', 'http://localhost:5480')
    monkeypatch.setenv('BATATIS_DAILY_SPEND_CAP_USD', '5')
    monkeypatch.setenv('BATATIS_ASSIST_RATE_LIMIT', '12')
    monkeypatch.setenv('BATATIS_LLM_RATE_LIMIT', '20')
    llm_gate.reset_for_tests()
    providers = []

    class SyntheticProvider:
        def __init__(self):
            self.events = asyncio.Queue()
            self.sent = []
            self.aborted = False
            self.closed = 0
            providers.append(self)

        async def open(self):
            pass

        async def configure(self, instructions):
            self.instructions = instructions

        async def send(self, event):
            self.sent.append(event)

        async def receive(self):
            return await self.events.get()

        def abort(self):
            self.aborted = True

        async def close(self):
            self.closed += 1
            self.abort()

    monkeypatch.setattr(routes_voice, 'GrokVoice', SyntheticProvider)
    store = CaseStore(tmp_path / 'voice.sqlite')
    codes = synthetic_codes(tmp_path / 'voice-codes.sqlite')
    with TestClient(create_app(store=store, codes=codes), base_url='http://localhost') as client:
        assert signup(client).status_code == 201
        onboard(client)
        yield client, store, providers
    llm_gate.reset_for_tests()


SCOPE = {'context_id': 'synthetic-context-0001', 'screen': 'settings', 'destinations': ['settings']}
WS = 'ws://localhost/api/voice/relay/session'
WS_OPTIONS = {'headers': {'Origin': 'http://localhost:5480'}, 'subprotocols': ['batatis.voice.v1']}


def ws_options():
    # Starlette adds Upgrade/protocol headers to the supplied dict in place.
    return {'headers': dict(WS_OPTIONS['headers']), 'subprotocols': list(WS_OPTIONS['subprotocols'])}


def test_explicit_socket_start_end_and_capability_are_bounded(voice_app):
    client, _, providers = voice_app
    status = client.get('/voice/session')
    assert status.status_code == 200 and status.json()['available'] is True
    assert status.headers['cache-control'] == 'no-store'
    assert not providers
    with client.websocket_connect(WS, **ws_options()) as socket:
        assert socket.receive_json()['type'] == 'session.ready'
        assert not providers
        socket.send_json({'type': 'session.start', 'scope': SCOPE})
        started = socket.receive_json()
        assert started['type'] == 'session.started'
        assert 'secret' not in str(started) and 'synthetic-xai' not in str(started)
        socket.send_json({'type': 'session.end', 'session_id': started['session_id'],
                          'context_id': SCOPE['context_id']})
        assert socket.receive_json()['type'] == 'session.ended'
    assert len(providers) == 1 and providers[0].closed == 1
    assert providers[0].aborted
    assert llm_gate._memory.today() == Decimal('0.160000')


def begin(client, scope=None):
    socket = client.websocket_connect(WS, **ws_options())
    socket.__enter__()
    assert socket.receive_json()['type'] == 'session.ready'
    socket.send_json({'type': 'session.start', 'scope': scope or SCOPE})
    return socket, socket.receive_json()


def upstream(client, provider, **event):
    client.portal.call(provider.events.put, event)


def test_only_a_completed_explicit_utterance_can_offer_native_navigation(voice_app):
    client, _, providers = voice_app
    socket, started = begin(client)
    try:
        assert started['type'] == 'session.started'
        provider = providers[0]
        upstream(client, provider, type='input_audio_buffer.speech_started', item_id='utterance-1')
        assert socket.receive_json()['type'] == 'audio.clear'
        upstream(client, provider, type='conversation.item.input_audio_transcription.updated',
                 item_id='utterance-1', transcript='Open settings')
        upstream(client, provider, type='conversation.item.input_audio_transcription.completed',
                 item_id='utterance-1', transcript='Open settings')
        final = socket.receive_json()
        assert final['type'] == 'transcript.completed'
        assert final['navigation'] == {'destination': 'settings'}
        assert final['context_id'] == SCOPE['context_id'] and final['revision'] == 0
        assert not provider.sent  # no model tool or mutation is executed
    finally:
        socket.__exit__(None, None, None)


@pytest.mark.parametrize('origin', [None, 'null', 'https://untrusted.example', 'http://localhost:5480/other'])
def test_websocket_origin_is_explicit_and_exact_even_with_a_valid_login(voice_app, origin):
    client, _, providers = voice_app
    headers = {'Origin': origin} if origin else {}
    with pytest.raises(WebSocketDisconnect) as error:
        with client.websocket_connect(WS, headers=headers, subprotocols=['batatis.voice.v1']):
            pass
    assert error.value.code == 4403 and not providers


@pytest.mark.parametrize('change', [{'subprotocols': []}, {'url': WS + '?secret=not-accepted'}])
def test_websocket_requires_its_protocol_and_never_accepts_query_credentials(voice_app, change):
    client, _, providers = voice_app
    options = {**ws_options(), **change}
    with pytest.raises(WebSocketDisconnect) as error:
        with client.websocket_connect(options.pop('url', WS), **options):
            pass
    assert error.value.code == 4403 and not providers


@pytest.mark.parametrize('credential_state', ['disabled', 'missing', 'openai-only'])
def test_disabled_start_does_not_construct_a_provider_or_reserve(voice_app, monkeypatch, credential_state):
    client, _, providers = voice_app
    if credential_state == 'disabled':
        monkeypatch.setenv('BATATIS_LIVE', '0')
    else:
        monkeypatch.delenv('XAI_API_KEY')
        if credential_state == 'openai-only':
            monkeypatch.setenv('OPENAI_API_KEY', 'synthetic-other-provider')
    assert client.get('/voice/session').json()['available'] is False
    socket, stopped = begin(client)
    try:
        assert stopped['type'] == 'session.ended' and stopped['reason'] == 'unavailable'
    finally:
        socket.__exit__(None, None, None)
    assert not providers and llm_gate._memory.today() == 0


@pytest.mark.parametrize('question', [
    'Do not open settings', 'Open settings and delete my application', 'If I said open settings',
    'Open "settings"', 'Tell me how to open settings', 'Open https://untrusted.example',
])
def test_quoted_negated_hypothetical_mixed_and_external_speech_never_navigates(voice_app, question):
    client, _, providers = voice_app
    socket, started = begin(client)
    try:
        upstream(client, providers[0], type='input_audio_buffer.speech_started', item_id='u')
        assert socket.receive_json()['type'] == 'audio.clear'
        upstream(client, providers[0], type='conversation.item.input_audio_transcription.completed',
                 item_id='u', transcript=question)
        assert socket.receive_json()['navigation'] is None
    finally:
        socket.__exit__(None, None, None)


PCM = base64.b64encode(b'\0\0' * 240).decode()


def scripted_response(client, provider, *, text='Choose the field you want to explain.', user_text='Explain this field.'):
    upstream(client, provider, type='input_audio_buffer.speech_started', item_id='u')
    upstream(client, provider, type='response.created', response={'id': 'r'})
    upstream(client, provider, type='response.output_audio.delta', response_id='r', delta=PCM)
    upstream(client, provider, type='response.output_audio_transcript.done', response_id='r', transcript=text)
    upstream(client, provider, type='response.done', response={'id': 'r', 'status': 'completed'})
    # Output arrived before the final input transcription. It must stay buffered.
    upstream(client, provider, type='conversation.item.input_audio_transcription.completed',
             item_id='u', transcript=user_text)


def test_audio_waits_for_whole_utterance_and_complete_checked_response(voice_app):
    client, _, providers = voice_app
    socket, _ = begin(client)
    try:
        scripted_response(client, providers[0])
        assert socket.receive_json()['type'] == 'audio.clear'
        assert socket.receive_json()['type'] == 'transcript.completed'
        text = socket.receive_json()
        assert text['type'] == 'response.text' and text['withheld_audio'] is False
        audio = socket.receive_json()
        assert audio['type'] == 'response.audio' and audio['audio'] == PCM
        assert socket.receive_json()['type'] == 'response.done'
    finally:
        socket.__exit__(None, None, None)


@pytest.mark.parametrize('text,user_text', [
    ('Your design is safe.', 'Explain this field.'),
    ('Use 9.99.99.99.(1).', 'Explain this field.'),
    ('Use 9.10.9.16.(1).', 'Explain this field.'),  # exists in synthetic DB, absent from supplied context
    ('Email a.person@example.test.', 'Explain this field.'),
    ('Here is a complete risk statement.', 'Draft my risk assessment.'),
    ('', 'Explain this field.'),
])
def test_rejected_response_audio_is_never_sent(voice_app, text, user_text):
    client, _, providers = voice_app
    socket, _ = begin(client)
    try:
        scripted_response(client, providers[0], text=text, user_text=user_text)
        assert socket.receive_json()['type'] == 'audio.clear'
        assert socket.receive_json()['type'] == 'transcript.completed'
        result = socket.receive_json()
        assert result['type'] == 'response.text' and result['withheld_audio'] is True
        assert socket.receive_json()['type'] == 'response.done'  # no audio frame in between
    finally:
        socket.__exit__(None, None, None)


@pytest.mark.parametrize('failure', ['error', 'model-mismatch', 'tool-prose'])
def test_upstream_errors_mismatch_or_tools_fail_closed_without_payload_leaks(voice_app, failure, caplog):
    client, _, providers = voice_app
    socket, _ = begin(client)
    try:
        event = ({'type': 'error', 'message': 'synthetic-xai-secret PRIVATE SOURCE'} if failure == 'error' else
                 {'type': 'session.updated', 'session': {'model': 'grok-voice-latest'}} if failure == 'model-mismatch' else
                 {'type': 'response.function_call_arguments.done', 'name': 'delete_case',
                  'arguments': '{"url":"https://untrusted.example"}'})
        upstream(client, providers[0], **event)
        result = socket.receive_json()
        assert result['type'] == 'session.ended' and result['reason'] == 'unavailable'
        assert 'PRIVATE SOURCE' not in str(result) + caplog.text
        assert 'synthetic-xai-secret' not in str(result) + caplog.text
    finally:
        socket.__exit__(None, None, None)
    assert providers[0].aborted and providers[0].closed == 1
    assert llm_gate._memory.today() == Decimal('0.16')


def test_logout_is_rechecked_before_completed_speech_can_plan_navigation(voice_app):
    client, store, providers = voice_app
    socket, _ = begin(client)
    try:
        upstream(client, providers[0], type='input_audio_buffer.speech_started', item_id='u')
        assert socket.receive_json()['type'] == 'audio.clear'
        store.delete_session(digest(client.cookies.get(COOKIE)))
        upstream(client, providers[0], type='conversation.item.input_audio_transcription.completed',
                 item_id='u', transcript='Open settings')
        stopped = socket.receive_json()
        assert stopped['type'] == 'session.ended' and stopped['reason'] == 'authorization_changed'
        assert not providers[0].sent
    finally:
        socket.__exit__(None, None, None)


def test_case_changes_are_rechecked_before_audio_or_navigation_is_delivered(voice_app):
    client, store, providers = voice_app
    case = client.post('/cases', json={'title': 'Synthetic case'}).json()
    scope = {**SCOPE, 'case_id': case['id'], 'case_version': case['version']}
    socket, started = begin(client, scope)
    try:
        assert started['type'] == 'session.started'
        store.rename_title(case['id'], 'Changed while voice runs')
        socket.send_json({'type': 'audio.append', 'session_id': started['session_id'],
                          'context_id': scope['context_id'], 'revision': 0, 'audio': PCM})
        stopped = socket.receive_json()
        assert stopped['type'] == 'session.ended' and stopped['reason'] == 'context_changed'
        assert not providers[0].sent
    finally:
        socket.__exit__(None, None, None)


def test_idle_session_revalidates_real_auth_without_waiting_for_new_input(voice_app):
    client, store, providers = voice_app
    socket, _ = begin(client)
    try:
        store.delete_session(digest(client.cookies.get(COOKIE)))
        stopped = socket.receive_json()
        assert stopped['type'] == 'session.ended' and stopped['reason'] == 'authorization_changed'
    finally:
        socket.__exit__(None, None, None)


def test_explicit_end_interrupts_a_pending_provider_connection_and_holds_the_reservation(voice_app, monkeypatch):
    client, _, providers = voice_app
    entered = threading.Event()
    async def waiting(self):
        entered.set()
        await asyncio.Future()
    monkeypatch.setattr(routes_voice.GrokVoice, 'open', waiting)
    with client.websocket_connect(WS, **ws_options()) as socket:
        ready = socket.receive_json()
        socket.send_json({'type': 'session.start', 'scope': SCOPE})
        assert entered.wait(2)
        socket.send_json({'type': 'session.end', 'session_id': ready['session_id'],
                          'context_id': SCOPE['context_id']})
        assert socket.receive_json()['reason'] == 'ended'
    assert providers[0].aborted and providers[0].closed == 1
    assert llm_gate._memory.today() == Decimal('0.16')


def test_server_deadline_aborts_even_an_idle_upstream_without_a_client_timer(voice_app, monkeypatch):
    import engine.voice as voice
    client, _, providers = voice_app
    monkeypatch.setattr(voice, 'MAX_SECONDS', 0.1)  # test clock; production bound is a fixed 55s
    socket, started = begin(client)
    try:
        assert started['type'] == 'session.started'
        assert socket.receive_json()['reason'] == 'expired'
    finally:
        socket.__exit__(None, None, None)
    assert providers[0].aborted and providers[0].closed == 1
    assert llm_gate._memory.today() == Decimal('0.16')


def test_actual_uploaded_document_can_be_added_as_bounded_context_without_case_mutation(voice_app):
    client, store, providers = voice_app
    case = client.post('/cases', json={'title': 'Document context'}).json()
    scope = {**SCOPE, 'case_id': case['id'], 'case_version': case['version']}
    socket, started = begin(client, scope)
    try:
        assert started['type'] == 'session.started'
        saved = client.post(f"/cases/{case['id']}/files", content=pdf_bytes('Real authorized upload text'),
                            headers={'Content-Type': 'application/pdf', 'X-Filename': 'document.pdf'}).json()
        before = store.get(case['id']).model_dump()
        socket.send_json({'type': 'context.update', 'session_id': started['session_id'],
            'context_id': scope['context_id'], 'revision': 0,
            'scope': {**scope, 'revision': 1, 'attachment_ids': [saved['id']]}})
        assert socket.receive_json()['type'] == 'audio.clear'
        update = socket.receive_json()
        assert update['type'] == 'context.updated' and update['revision'] == 1
        context = providers[0].sent[-1]['item']['content'][0]['text']
        assert 'Real authorized upload text' in context and saved['id'] in context and case['id'] in context
        assert 'input_image' not in context
        assert store.get(case['id']).model_dump() == before
    finally:
        socket.__exit__(None, None, None)


def test_context_update_discards_old_utterances_and_restricts_new_plans_to_current_offers(voice_app):
    client, _, providers = voice_app
    socket, started = begin(client)
    try:
        upstream(client, providers[0], type='input_audio_buffer.speech_started', item_id='old')
        assert socket.receive_json()['type'] == 'audio.clear'
        socket.send_json({'type': 'context.update', 'session_id': started['session_id'],
            'context_id': SCOPE['context_id'], 'revision': 0,
            'scope': {**SCOPE, 'revision': 1, 'destinations': ['notifications']}})
        assert socket.receive_json()['type'] == 'audio.clear'
        assert socket.receive_json()['type'] == 'context.updated'
        upstream(client, providers[0], type='conversation.item.input_audio_transcription.completed',
                 item_id='old', transcript='Open settings')
        upstream(client, providers[0], type='input_audio_buffer.speech_started', item_id='new')
        assert socket.receive_json()['type'] == 'audio.clear'  # no old transcript/plan escaped
        upstream(client, providers[0], type='conversation.item.input_audio_transcription.completed',
                 item_id='new', transcript='Open settings')
        result = socket.receive_json()
        assert result['type'] == 'transcript.completed' and result['navigation'] is None
        assert result['revision'] == 1
    finally:
        socket.__exit__(None, None, None)


@pytest.mark.parametrize('error', [TimeoutError('synthetic-xai-secret PRIVATE'),
                                  ConnectionRefusedError('synthetic-xai-secret PRIVATE')])
def test_failed_connection_retry_holds_full_allowance_and_never_uses_token_settlement(voice_app, monkeypatch, error):
    client, _, providers = voice_app
    monkeypatch.setenv('BATATIS_DAILY_SPEND_CAP_USD', '0.16')
    def forbidden(*args, **kwargs):
        pytest.fail('Voice was incorrectly settled/refunded as text tokens')
    monkeypatch.setattr(llm_gate, 'record', forbidden)
    monkeypatch.setattr(llm_gate, 'release', forbidden)
    async def fail(self):
        raise error
    monkeypatch.setattr(routes_voice.GrokVoice, 'open', fail)
    socket, stopped = begin(client)
    try:
        assert stopped['type'] == 'session.ended'
        assert 'PRIVATE' not in str(stopped) and 'synthetic-xai-secret' not in str(stopped)
    finally:
        socket.__exit__(None, None, None)
    socket, rejected = begin(client)
    try:
        assert rejected['type'] == 'session.error' and rejected['status'] == 503
        assert socket.receive_json()['reason'] == 'unavailable'
    finally:
        socket.__exit__(None, None, None)
    assert len(providers) == 1 and providers[0].aborted and providers[0].closed == 1
    assert llm_gate._memory.today() == Decimal('0.16')


def test_no_cost_capability_reads_do_not_consume_the_shared_start_rate(voice_app, monkeypatch):
    client, _, providers = voice_app
    monkeypatch.setenv('BATATIS_ASSIST_RATE_LIMIT', '1')
    for _ in range(4):
        assert client.get('/voice/session').json()['available'] is True
    socket, started = begin(client)
    try:
        assert started['type'] == 'session.started'
        socket.send_json({'type': 'session.end', 'session_id': started['session_id'],
                          'context_id': SCOPE['context_id']})
        assert socket.receive_json()['type'] == 'session.ended'
    finally:
        socket.__exit__(None, None, None)
    socket, limited = begin(client)
    try:
        assert limited['type'] == 'session.error' and limited['status'] == 429
        assert limited['retry_after'] >= 1
    finally:
        socket.__exit__(None, None, None)
    assert len(providers) == 1 and llm_gate._memory.today() == Decimal('0.16')


@pytest.mark.parametrize('change', [{'session_id': 'some-other-session'}, {'context_id': 'some-other-context'},
                                  {'revision': 1}, {'audio': 'not-base64'}, {'audio': 'AA=='},
                                  {'scope': {**SCOPE}}])
def test_stale_malformed_or_cross_session_audio_is_not_forwarded(voice_app, change):
    client, _, providers = voice_app
    socket, started = begin(client)
    try:
        socket.send_json({'type': 'audio.append', 'session_id': started['session_id'],
                          'context_id': SCOPE['context_id'], 'revision': 0, 'audio': PCM, **change})
        stopped = socket.receive_json()
        assert stopped['type'] == 'session.ended'
        assert stopped['reason'] in {'invalid_request', 'context_changed'}
        assert not providers[0].sent
    finally:
        socket.__exit__(None, None, None)


def test_successful_pcm_input_is_the_only_client_audio_event_forwarded(voice_app):
    client, _, providers = voice_app
    socket, started = begin(client)
    try:
        socket.send_json({'type': 'audio.append', 'session_id': started['session_id'],
                          'context_id': SCOPE['context_id'], 'revision': 0, 'audio': PCM})
        socket.send_json({'type': 'audio.clear', 'session_id': started['session_id'],
                          'context_id': SCOPE['context_id'], 'revision': 0})
        assert socket.receive_json()['type'] == 'audio.clear'
        assert providers[0].sent == [{'type': 'input_audio_buffer.append', 'audio': PCM},
                                     {'type': 'input_audio_buffer.clear'}]
    finally:
        socket.__exit__(None, None, None)


def test_end_during_context_preparation_never_reserves_or_opens_a_provider(voice_app, monkeypatch):
    import engine.voice as voice
    client, _, providers = voice_app
    entered, resume = threading.Event(), threading.Event()
    prepare = voice.prepare_context
    def waiting(*args, **kwargs):
        entered.set()
        assert resume.wait(2)
        return prepare(*args, **kwargs)
    monkeypatch.setattr(voice, 'prepare_context', waiting)
    try:
        with client.websocket_connect(WS, **ws_options()) as socket:
            ready = socket.receive_json()
            socket.send_json({'type': 'session.start', 'scope': SCOPE})
            assert entered.wait(2)
            socket.send_json({'type': 'session.end', 'session_id': ready['session_id'],
                              'context_id': SCOPE['context_id']})
            resume.set()
            assert socket.receive_json()['type'] == 'session.ended'
    finally:
        resume.set()
    assert not providers
    assert llm_gate._memory.today() == 0


def test_end_during_attachment_context_refresh_interrupts_preparation(voice_app, monkeypatch):
    import engine.voice as voice
    client, _, providers = voice_app
    socket, started = begin(client)
    entered, resume = threading.Event(), threading.Event()
    prepare = voice.prepare_context
    def waiting(*args, **kwargs):
        entered.set()
        assert resume.wait(2)
        return prepare(*args, **kwargs)
    monkeypatch.setattr(voice, 'prepare_context', waiting)
    try:
        socket.send_json({'type': 'context.update', 'session_id': started['session_id'],
            'context_id': SCOPE['context_id'], 'revision': 0, 'scope': {**SCOPE, 'revision': 1}})
        assert socket.receive_json()['type'] == 'audio.clear'
        assert entered.wait(2)
        socket.send_json({'type': 'session.end', 'session_id': started['session_id'],
                          'context_id': SCOPE['context_id']})
        assert socket.receive_json()['reason'] == 'ended'
        assert not providers[0].sent
    finally:
        resume.set()
        socket.__exit__(None, None, None)
    assert providers[0].aborted and providers[0].closed == 1
    assert llm_gate._memory.today() == Decimal('0.16')


def test_logout_while_upstream_configuration_is_pending_closes_before_activation(voice_app, monkeypatch):
    client, store, providers = voice_app
    entered = threading.Event()
    async def pending(self, instructions):
        entered.set()
        await asyncio.Future()
    monkeypatch.setattr(routes_voice.GrokVoice, 'configure', pending)
    with client.websocket_connect(WS, **ws_options()) as socket:
        assert socket.receive_json()['type'] == 'session.ready'
        socket.send_json({'type': 'session.start', 'scope': SCOPE})
        assert entered.wait(2)
        store.delete_session(digest(client.cookies.get(COOKIE)))
        result = socket.receive_json()
        assert result['type'] == 'session.ended' and result['reason'] == 'authorization_changed'
    assert providers[0].aborted and providers[0].closed == 1


def test_concurrent_sockets_cannot_reuse_a_reserved_last_allowance(voice_app, monkeypatch):
    client, _, providers = voice_app
    monkeypatch.setenv('BATATIS_DAILY_SPEND_CAP_USD', '0.16')
    first, started = begin(client)
    try:
        assert started['type'] == 'session.started'
        second, rejected = begin(client)
        try:
            assert rejected['type'] == 'session.error' and rejected['status'] == 503
        finally:
            second.__exit__(None, None, None)
        assert len(providers) == 1
        first.send_json({'type': 'session.end', 'session_id': started['session_id'],
                         'context_id': SCOPE['context_id']})
        assert first.receive_json()['type'] == 'session.ended'
    finally:
        first.__exit__(None, None, None)
    assert llm_gate._memory.today() == Decimal('0.16')


def test_capability_case_authorization_and_rejected_start_never_read_private_context(voice_app, monkeypatch):
    client, store, providers = voice_app
    from engine.models import Case
    other = store.put(Case(owner_id='some-other-owner'))
    def forbidden(*args, **kwargs):
        pytest.fail('Unauthorized content was read')
    monkeypatch.setattr(store, 'get', forbidden)
    monkeypatch.setattr(store, 'get_file', forbidden)
    assert client.get('/voice/session', params={'case_id': other.id}).status_code == 404
    socket, stopped = begin(client, {**SCOPE, 'case_id': other.id, 'case_version': other.version})
    try:
        assert stopped['type'] == 'session.ended' and stopped['reason'] == 'unavailable'
    finally:
        socket.__exit__(None, None, None)
    assert not providers and llm_gate._memory.today() == 0
