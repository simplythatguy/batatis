"""Synthetic public lifecycle regressions for context/input/response ownership."""
from engine.tests.test_voice_api import PCM, SCOPE, begin, upstream, voice_app
import threading


def command(started, type_, revision=0, **fields):
    return {'type': type_, 'session_id': started['session_id'],
            'context_id': SCOPE['context_id'], 'revision': revision, **fields}


def test_old_uncommitted_audio_cannot_be_relabelled_after_a_context_update(voice_app):
    client, _, providers = voice_app
    socket, started = begin(client)
    try:
        provider = providers[0]
        socket.send_json(command(started, 'audio.append', audio=PCM))
        assert socket.receive_json()['type'] == 'audio.clear'
        socket.send_json(command(started, 'context.update', scope={**SCOPE, 'revision': 1}))
        assert socket.receive_json()['type'] == 'audio.clear'
        assert socket.receive_json()['type'] == 'context.updated'
        upstream(client, provider, type='input_audio_buffer.speech_started', item_id='old-buffer')
        upstream(client, provider, type='conversation.item.input_audio_transcription.completed',
                 item_id='old-buffer', transcript='Open settings')
        socket.send_json(command(started, 'session.end', revision=1))
        # The old provider events must produce neither a transcript nor a plan.
        assert socket.receive_json()['type'] == 'session.ended'
        assert 'input_audio_buffer.clear' in [event['type'] for event in provider.sent]
    finally:
        socket.__exit__(None, None, None)


def test_preparation_consumes_the_whole_lifetime_without_a_provider_or_reservation(voice_app, monkeypatch):
    import engine.voice as voice
    client, _, providers = voice_app
    entered, release = threading.Event(), threading.Event()
    prepare = voice.prepare_context
    def paused(*args, **kwargs):
        entered.set()
        assert release.wait(2)
        return prepare(*args, **kwargs)
    monkeypatch.setattr(voice, 'prepare_context', paused)
    monkeypatch.setattr(voice, 'MAX_SECONDS', 0.1)  # production remains55seconds
    socket = None
    try:
        socket, stopped = begin(client)
        assert entered.is_set()
        assert stopped['type'] == 'session.ended' and stopped['reason'] == 'expired'
        assert not providers
        from engine import llm_gate
        assert llm_gate._memory.today() == 0
    finally:
        release.set()
        if socket:
            socket.__exit__(None, None, None)
