"""Synthetic protocol adapter contract; no network, keychain, microphone or real provider."""
import asyncio
import json
from types import SimpleNamespace

import pytest

from engine import voice_grok
from engine.voice_grok import GrokVoice, VoiceFailure


@pytest.fixture
def transport(monkeypatch):
    monkeypatch.setenv('XAI_API_KEY', 'synthetic-server-secret')
    calls = []
    class Socket:
        def __init__(self):
            self.events = [json.dumps({'type': 'session.created', 'session': {'model': 'grok-voice-3.0'}}),
                           json.dumps({'type': 'session.updated', 'session': {'model': 'grok-voice-3.0', 'tools': []}})]
            self.sent = []
            self.aborted = 0
            self.transport = SimpleNamespace(abort=self.abort)

        def abort(self):
            self.aborted += 1

        async def recv(self):
            return self.events.pop(0)

        async def send(self, raw):
            self.sent.append(json.loads(raw))

        async def wait_closed(self):
            pass
    socket = Socket()
    async def connect(url, **options):
        calls.append((url, options))
        return socket
    monkeypatch.setattr(voice_grok, '_PinnedConnect', connect)
    return socket, calls


def test_exact_model_auth_protocol_configuration_and_all_non_audio_message_accounting(transport):
    socket, calls = transport
    async def scenario():
        adapter = GrokVoice()
        try:
            await adapter.open()
            await adapter.configure('Synthetic Batatis instructions')
            assert adapter.text_inputs == 1
            assert calls[0][0] == 'wss://api.x.ai/v1/realtime?model=grok-voice-3.0'
            options = calls[0][1]
            assert options['additional_headers'] == {'Authorization': 'Bearer synthetic-server-secret'}
            assert options['proxy'] is None and options['logger'].disabled
            config = socket.sent[0]['session']
            assert config['model'] == 'grok-voice-3.0' and config['tools'] == []
            assert config['resumption'] == {'enabled': False}
            assert config['audio'] == {'input': {'format': {'type': 'audio/pcm', 'rate': 24000}},
                                       'output': {'format': {'type': 'audio/pcm', 'rate': 24000}}}
            # Actual session.update, user reference context, input clear and
            # response.cancel messages ALL consume this same paid-message bound.
            kinds = ['conversation.item.create', 'input_audio_buffer.clear', 'response.cancel', 'session.update']
            for index in range(19):
                await adapter.send({'type': kinds[index % len(kinds)]})
            assert adapter.text_inputs == 20 and len(socket.sent) == 20
            for _ in range(5):
                await adapter.send({'type': 'input_audio_buffer.append', 'audio': 'AAA='})
            assert adapter.text_inputs == 20 and len(socket.sent) == 25
            with pytest.raises(VoiceFailure):
                await adapter.send({'type': 'response.cancel'})
            assert len(socket.sent) == 25  # the 21st paid/control frame never leaves
        finally:
            await adapter.close()
            await adapter.close()
        assert socket.aborted == 1  # cleanup is idempotent
    asyncio.run(scenario())


@pytest.mark.parametrize('stage,model', [('created', 'grok-voice-latest'), ('created', 'grok-voice-2.0'),
                                        ('created', None), ('updated', 'grok-voice-latest')])
def test_model_mismatch_never_becomes_an_active_pinned_session(transport, stage, model):
    socket, _ = transport
    socket.events[0 if stage == 'created' else 1] = json.dumps(
        {'type': 'session.' + stage, 'session': {'model': model}})
    async def scenario():
        adapter = GrokVoice()
        try:
            with pytest.raises(VoiceFailure):
                await adapter.open()
                await adapter.configure('Synthetic context')
        finally:
            await adapter.close()
        assert socket.aborted == 1
    asyncio.run(scenario())


@pytest.mark.parametrize('raw', ['not-json', '[]', '{}', '{"type":123}',
                                '{"type":"error","message":"synthetic-server-secret PRIVATE"}',
                                b'\0\0', '{"type":"unknown","data":"' + 'x' * 256_000 + '"}'])
def test_malformed_or_error_events_are_sanitized_and_never_returned(transport, raw):
    socket, _ = transport
    socket.events = [raw]
    async def scenario():
        adapter = GrokVoice()
        try:
            with pytest.raises(VoiceFailure) as error:
                await adapter.open()
            assert 'synthetic-server-secret' not in str(error.value)
            assert 'PRIVATE' not in str(error.value)
        finally:
            await adapter.close()
    asyncio.run(scenario())


@pytest.mark.parametrize('key', ['', ' ', 'not\na\nheader', 'x' * 2001])
def test_malformed_server_credentials_never_open_transport(transport, monkeypatch, key):
    _, calls = transport
    monkeypatch.setenv('XAI_API_KEY', key)
    with pytest.raises(VoiceFailure):
        asyncio.run(GrokVoice().open())
    assert not calls


def test_enabled_tools_in_upstream_configuration_are_refused(transport):
    socket, _ = transport
    socket.events[1] = json.dumps({'type': 'session.updated', 'session': {
        'model': 'grok-voice-3.0', 'tools': [{'type': 'web_search'}]}})
    async def scenario():
        adapter = GrokVoice()
        try:
            await adapter.open()
            with pytest.raises(VoiceFailure):
                await adapter.configure('Synthetic context')
        finally:
            await adapter.close()
    asyncio.run(scenario())


def test_an_intervening_session_created_cannot_silently_change_the_pin(transport):
    socket, _ = transport
    socket.events.insert(1, json.dumps({'type': 'session.created', 'session': {'model': 'grok-voice-2.0'}}))
    async def scenario():
        adapter = GrokVoice()
        try:
            await adapter.open()
            with pytest.raises(VoiceFailure):
                await adapter.configure('Synthetic context')
        finally:
            await adapter.close()
    asyncio.run(scenario())


def test_local_synthetic_websocket_proves_abort_closes_real_transport_on_cancellation(monkeypatch):
    from websockets.asyncio.server import serve
    from websockets.asyncio.client import connect
    monkeypatch.setenv('XAI_API_KEY', 'synthetic-server-secret')
    async def scenario():
        closed = asyncio.Event()
        saw_configuration = asyncio.Event()
        async def upstream(socket):
            assert socket.request.headers['Authorization'] == 'Bearer synthetic-server-secret'
            await socket.send(json.dumps({'type': 'session.created', 'session': {'model': 'grok-voice-3.0'}}))
            configuration = json.loads(await socket.recv())
            assert configuration['session']['model'] == 'grok-voice-3.0'
            saw_configuration.set()
            await socket.wait_closed()
            closed.set()
        async with serve(upstream, '127.0.0.1', 0) as server:
            port = server.sockets[0].getsockname()[1]
            def local_transport(url, **options):
                assert url == 'wss://api.x.ai/v1/realtime?model=grok-voice-3.0'
                return connect(f'ws://127.0.0.1:{port}', **options)
            monkeypatch.setattr(voice_grok, '_PinnedConnect', local_transport)
            adapter = GrokVoice()
            try:
                await adapter.open()
                # Real local transport, intentionally missing session.updated.
                # Cancelling configuration must still close the paid socket.
                with pytest.raises(TimeoutError):
                    async with asyncio.timeout(0.05):
                        await adapter.configure('Synthetic context')
                assert saw_configuration.is_set()
            finally:
                await adapter.close()
            async with asyncio.timeout(1):
                await closed.wait()
    asyncio.run(scenario())
