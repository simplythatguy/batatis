"""Synthetic HTTP/WS clients, real relay/adapter, loopback-only fake upstream.

No provider key, provider call, microphone or browser is used. The wire seam is
deliberate: acknowledgement ordering and the paid-message limit need the real
adapter, not a mock of VoiceSession internals.
"""
import asyncio
from contextlib import asynccontextmanager
import json
import socket
import threading

import httpx
import pytest
import uvicorn
from websockets.asyncio.client import connect
from websockets.asyncio.server import serve
from websockets.exceptions import ConnectionClosed

from engine import llm_gate, voice, voice_grok
from engine.accounts import COOKIE
from engine.api import create_app
from engine.store import CaseStore
from engine.tests.test_voice_api import PCM, SCOPE
from engine.tests.test_voice_context import synthetic_codes


async def receive(ws, timeout=2):
    return json.loads(await asyncio.wait_for(ws.recv(), timeout))


async def collect(ws, timeout=0.1):
    """Drain until the stream goes quiet for `timeout` seconds.

    The gap is generous because a Windows event loop hops through the test client's
    portal between events; at 0.03 s it returned early, mid-stream.
    """
    events = []
    while True:
        try:
            events.append(await receive(ws, timeout))
        except (TimeoutError, ConnectionClosed):
            return events


class Remote:
    def __init__(self, ws):
        self.ws = ws
        self.messages = []
        self.number = 0
        self.ack_commit = self.ack_clear = self.ack_context = True
        self.ack_cancel = self.ack_response = True
        self.responses = {}
        self.closed = asyncio.Event()

    async def event(self, type_, **fields):
        self.number += 1
        await self.ws.send(json.dumps({'type': type_, 'event_id': f'wire-{self.number}', **fields}))

    async def wait(self, type_, count=1):
        async with asyncio.timeout(2):
            while len([m for m in self.messages if m['type'] == type_]) < count:
                await asyncio.sleep(0.001)
        return [m for m in self.messages if m['type'] == type_][count - 1]

    async def handler(self):
        try:
            await self.event('session.created', session={'model': 'grok-voice-3.0'})
            async for raw in self.ws:
                event = json.loads(raw)
                self.messages.append(event)
                type_ = event['type']
                if type_ == 'session.update':
                    assert event['session']['turn_detection'] == {'type': None}
                    await self.event('session.updated', session=event['session'])
                elif type_ == 'input_audio_buffer.commit' and self.ack_commit:
                    await self.event('input_audio_buffer.committed', item_id=f'input-{len(self.messages)}')
                elif type_ == 'input_audio_buffer.clear' and self.ack_clear:
                    await self.event('input_audio_buffer.cleared')
                elif type_ == 'conversation.item.create' and self.ack_context:
                    await self.event('conversation.item.added', item=event['item'])
                elif type_ == 'response.create' and self.ack_response:
                    rid = f'response-{len(self.messages)}'
                    self.responses[rid] = event['response']['metadata']
                    await self.event('response.created', response={'id': rid, 'metadata': self.responses[rid]})
                elif type_ == 'response.cancel' and self.ack_cancel:
                    await self.event('response.done', response={'id': event['response_id'], 'status': 'cancelled',
                                                              'metadata': self.responses[event['response_id']]})
        except ConnectionClosed:
            pass
        finally:
            self.closed.set()


@pytest.fixture
def wire(tmp_path, monkeypatch):
    for name in ('VERCEL', 'BATATIS_STORE', 'DATABASE_URL', 'OPENAI_API_KEY', 'ANTHROPIC_API_KEY'):
        monkeypatch.delenv(name, raising=False)
    for name, value in {'BATATIS_LIVE': '1', 'XAI_API_KEY': 'synthetic-wire-secret',
                        'BATATIS_WEB_ORIGIN': 'http://localhost:5480', 'BATATIS_DAILY_SPEND_CAP_USD': '5',
                        'BATATIS_ASSIST_RATE_LIMIT': '100', 'BATATIS_LLM_RATE_LIMIT': '100'}.items():
        monkeypatch.setenv(name, value)
    # Only this opt-in synthetic test timeout is shortened; production stays3s.
    monkeypatch.setattr(voice, 'ACK_SECONDS', 0.15)
    llm_gate.reset_for_tests()
    remotes = []
    store = CaseStore(tmp_path / 'wire.sqlite')
    codes = synthetic_codes(tmp_path / 'wire-source.sqlite')

    @asynccontextmanager
    async def lifetime():
        async def upstream(ws):
            assert ws.request.headers['Authorization'] == 'Bearer synthetic-wire-secret'
            remote = Remote(ws)
            remotes.append(remote)
            await remote.handler()
        app = create_app(store=store, codes=codes)
        async with serve(upstream, '127.0.0.1', 0) as upstream_server:
            port = upstream_server.sockets[0].getsockname()[1]
            def local(url, **options):
                assert url == 'wss://api.x.ai/v1/realtime?model=grok-voice-3.0'
                return connect(f'ws://127.0.0.1:{port}', **options)
            monkeypatch.setattr(voice_grok, '_PinnedConnect', local)
            listener = socket.socket()
            listener.bind(('127.0.0.1', 0))
            listener.listen(128)
            app_port = listener.getsockname()[1]
            server = uvicorn.Server(uvicorn.Config(app, access_log=False, log_level='critical', lifespan='off'))
            serving = asyncio.create_task(server.serve(sockets=[listener]))
            try:
                async with asyncio.timeout(2):
                    while not server.started:
                        await asyncio.sleep(0.001)
                async with httpx.AsyncClient(base_url=f'http://127.0.0.1:{app_port}') as http:
                    assert (await http.post('/api/auth/signup', json={'email': 'wire@example.test',
                        'name': 'Synthetic User', 'password': 'synthetic long password'})).status_code == 201
                    assert (await http.post('/api/auth/onboarding', json={'role': 'applicant',
                        'applicant_type': 'contractor'})).status_code == 200
                    async with connect(f'ws://127.0.0.1:{app_port}/api/voice/relay/session', proxy=None,
                            origin='http://localhost:5480', subprotocols=['batatis.voice.v1'],
                            additional_headers={'Cookie': COOKIE + '=' + http.cookies.get(COOKIE)}) as ws:
                        ready = await receive(ws)
                        assert ready['type'] == 'session.ready' and not remotes
                        await ws.send(json.dumps({'type': 'session.start', 'scope': SCOPE}))
                        started = await receive(ws)
                        assert started['type'] == 'session.started'
                        yield ws, started, remotes[-1], http
            finally:
                server.should_exit = True
                await asyncio.wait_for(serving, 3)
                listener.close()
        assert all(remote.closed.is_set() for remote in remotes)
    yield lifetime
    llm_gate.reset_for_tests()


async def send(ws, started, type_, revision=0, **fields):
    await ws.send(json.dumps({'type': type_, 'session_id': started['session_id'],
        'context_id': SCOPE['context_id'], 'revision': revision, **fields}))


async def commit(ws, started, revision=0):
    await send(ws, started, 'audio.append', revision, audio=PCM)
    assert (await receive(ws))['type'] == 'audio.clear'
    await send(ws, started, 'audio.commit', revision)
    ack = await receive(ws)
    assert ack['type'] == 'audio.committed' and ack['revision'] == revision
    return ack['turn_id']


async def utterance(ws, started, remote, text='Explain the field.', revision=0):
    item = await commit(ws, started, revision)
    await remote.event('conversation.item.input_audio_transcription.completed', item_id=item, transcript=text)
    event = await receive(ws)
    assert event['type'] == 'transcript.completed' and event['turn_id'] == item
    return event


async def update(ws, started, revision=0):
    await send(ws, started, 'context.update', revision, scope={**SCOPE, 'revision': revision + 1,
                                                           'destinations': ['notifications']})
    assert (await receive(ws))['type'] == 'audio.clear'
    ack = await receive(ws)
    assert ack['type'] == 'context.updated' and ack['revision'] == revision + 1


async def answer(remote, rid, text='Choose the field.'):
    part = dict(response_id=rid, item_id='out-' + rid, output_index=0, content_index=0)
    await remote.event('response.output_audio.delta', **part, delta=PCM)
    await remote.event('response.output_audio_transcript.done', **part, transcript=text)
    await remote.event('response.done', response={'id': rid, 'status': 'completed', 'metadata': remote.responses[rid]})


def test_buffered_old_speech_and_late_old_response_never_gain_new_revision(wire):
    async def scenario():
        async with wire() as (ws, started, remote, _):
            old = await commit(ws, started)
            await update(ws, started)
            await remote.event('input_audio_buffer.speech_started', item_id='unknown-old-buffer')
            await remote.event('conversation.item.input_audio_transcription.completed', item_id=old, transcript='Open settings')
            await remote.event('conversation.item.input_audio_transcription.completed', item_id='unknown-old-buffer', transcript='Open notifications')
            assert await collect(ws) == []
            event = await utterance(ws, started, remote, 'Open notifications', revision=1)
            assert event['navigation'] == {'destination': 'notifications'} and event['revision'] == 1
            assert [m['type'] for m in remote.messages] == ['session.update', 'input_audio_buffer.append',
                'input_audio_buffer.commit', 'input_audio_buffer.clear', 'conversation.item.create',
                'input_audio_buffer.append', 'input_audio_buffer.commit']
    asyncio.run(scenario())


def test_partial_speech_never_requests_a_response_and_premature_output_fails_closed(wire):
    async def scenario():
        async with wire() as (ws, started, remote, _):
            item = await commit(ws, started)
            await remote.event('conversation.item.input_audio_transcription.updated',
                               item_id=item, transcript='Open settings')
            assert await collect(ws) == []
            assert not any(m['type'] == 'response.create' for m in remote.messages)
            await remote.event('response.created', response={'id': 'premature', 'metadata': None})
            stopped = await receive(ws)
            assert stopped['type'] == 'session.ended' and stopped['reason'] == 'unavailable'
    asyncio.run(scenario())


@pytest.mark.parametrize('metadata', [None, {}, {'batatis_turn': 'wrong'}, {'batatis_turn': 'wrong', 'extra': 'x'}])
def test_null_wrong_or_unsolicited_response_metadata_fails_closed(wire, metadata):
    async def scenario():
        async with wire() as (ws, started, remote, _):
            remote.ack_response = False
            await utterance(ws, started, remote)
            await remote.wait('response.create')
            await remote.event('response.created', response={'id': 'unowned', 'metadata': metadata})
            stopped = await receive(ws)
            assert stopped['type'] == 'session.ended' and stopped['reason'] == 'unavailable'
    asyncio.run(scenario())


def test_late_owned_response_is_cancelled_and_new_safe_turn_still_works(wire):
    async def scenario():
        async with wire() as (ws, started, remote, _):
            remote.ack_response = False
            await utterance(ws, started, remote, 'Draft my risk assessment.')
            request = await remote.wait('response.create')
            await send(ws, started, 'context.update', scope={**SCOPE, 'revision': 1})
            assert (await receive(ws))['type'] == 'audio.clear'
            await remote.wait('input_audio_buffer.clear')
            remote.responses['late-old'] = request['response']['metadata']
            await remote.event('response.created', response={'id': 'late-old', 'metadata': remote.responses['late-old']})
            assert (await receive(ws))['type'] == 'context.updated'
            assert (await remote.wait('response.cancel'))['response_id'] == 'late-old'
            await remote.event('response.output_audio.delta', response_id='late-old', delta=PCM)
            assert await collect(ws) == []
            remote.ack_response = True
            await utterance(ws, started, remote, revision=1)
            await remote.wait('response.create', count=2)
            async with asyncio.timeout(1):
                while len(remote.responses) < 2:
                    await asyncio.sleep(0.001)
            rid = next(key for key in remote.responses if key != 'late-old')
            await answer(remote, rid)
            events = await collect(ws)
            assert [e['type'] for e in events] == ['response.text', 'response.audio', 'response.done']
            assert all(e['revision'] == 1 for e in events) and not events[0]['withheld_audio']
    asyncio.run(scenario())


@pytest.mark.parametrize('stage', ['commit', 'clear', 'context'])
def test_missing_acknowledgements_end_without_advancing_context(wire, stage):
    async def scenario():
        async with wire() as (ws, started, remote, _):
            if stage == 'commit':
                remote.ack_commit = False
                await send(ws, started, 'audio.append', audio=PCM)
                assert (await receive(ws))['type'] == 'audio.clear'
                await send(ws, started, 'audio.commit')
            else:
                setattr(remote, 'ack_' + stage, False)
                await send(ws, started, 'context.update', scope={**SCOPE, 'revision': 1})
                assert (await receive(ws))['type'] == 'audio.clear'
            stopped = await receive(ws)
            assert stopped['type'] == 'session.ended' and stopped['reason'] == 'unavailable'
            assert stopped['revision'] == 0
    asyncio.run(scenario())


@pytest.mark.parametrize('event', [
    {'type': 'input_audio_buffer.committed', 'item_id': 'unsolicited'},
    {'type': 'input_audio_buffer.cleared'},
])
def test_unsolicited_out_of_order_acknowledgements_cannot_establish_ownership(wire, event):
    async def scenario():
        async with wire() as (ws, _, remote, _):
            await remote.event(event['type'], **{k: v for k, v in event.items() if k != 'type'})
            stopped = await receive(ws)
            assert stopped['type'] == 'session.ended' and stopped['reason'] == 'unavailable'
    asyncio.run(scenario())


@pytest.mark.parametrize('stage', ['commit', 'clear', 'context'])
def test_duplicate_acknowledgements_fail_closed(wire, stage):
    async def scenario():
        async with wire() as (ws, started, remote, _):
            if stage == 'commit':
                item = await commit(ws, started)
                await remote.event('input_audio_buffer.committed', item_id=item)
            elif stage == 'clear':
                await send(ws, started, 'audio.clear')
                assert (await receive(ws))['type'] == 'audio.clear'
                await remote.event('input_audio_buffer.cleared')
            else:
                await update(ws, started)
                context = await remote.wait('conversation.item.create')
                await remote.event('conversation.item.added', item=context['item'])
            stopped = await receive(ws)
            assert stopped['type'] == 'session.ended' and stopped['reason'] == 'unavailable'
    asyncio.run(scenario())


def test_clear_ack_does_not_skip_an_old_pending_commit_or_its_epoch(wire):
    async def scenario():
        async with wire() as (ws, started, remote, _):
            remote.ack_commit = remote.ack_clear = False
            await send(ws, started, 'audio.append', audio=PCM)
            assert (await receive(ws))['type'] == 'audio.clear'
            await send(ws, started, 'audio.commit')
            await remote.wait('input_audio_buffer.commit')
            await send(ws, started, 'context.update', scope={**SCOPE, 'revision': 1})
            assert (await receive(ws))['type'] == 'audio.clear'
            await remote.wait('input_audio_buffer.clear')
            await remote.event('input_audio_buffer.cleared')
            assert await collect(ws) == []  # old commit acknowledgement is still outstanding
            await remote.event('input_audio_buffer.committed', item_id='old-commit')
            ack = await receive(ws)
            assert ack['type'] == 'context.updated' and ack['revision'] == 1
            await remote.event('conversation.item.input_audio_transcription.completed',
                               item_id='old-commit', transcript='Open settings')
            assert await collect(ws) == []
            remote.ack_commit = True
            event = await utterance(ws, started, remote, 'Open settings', revision=1)
            assert event['navigation'] == {'destination': 'settings'}
    asyncio.run(scenario())


def test_wrong_context_item_ack_is_not_a_barrier(wire):
    async def scenario():
        async with wire() as (ws, started, remote, _):
            remote.ack_context = False
            await send(ws, started, 'context.update', scope={**SCOPE, 'revision': 1})
            assert (await receive(ws))['type'] == 'audio.clear'
            reference = await remote.wait('conversation.item.create')
            await remote.event('conversation.item.added', item={**reference['item'], 'id': 'wrong-context'})
            assert await collect(ws) == []
            await remote.event('conversation.item.added', item=reference['item'])
            assert (await receive(ws))['type'] == 'context.updated'
    asyncio.run(scenario())


@pytest.mark.parametrize('metadata', [None, {}, {'batatis_turn': 'wrong'}])
def test_final_response_metadata_must_still_match_the_committed_turn(wire, metadata):
    async def scenario():
        async with wire() as (ws, started, remote, _):
            await utterance(ws, started, remote)
            await remote.wait('response.create')
            while not remote.responses:
                await asyncio.sleep(0.001)
            rid = next(iter(remote.responses))
            await remote.event('response.output_audio.delta', response_id=rid, item_id='out',
                               output_index=0, content_index=0, delta=PCM)
            await remote.event('response.output_audio_transcript.done', response_id=rid, item_id='out',
                               output_index=0, content_index=0, transcript='Choose the field.')
            await remote.event('response.done', response={'id': rid, 'status': 'completed', 'metadata': metadata})
            stopped = await receive(ws)
            assert stopped['type'] == 'session.ended' and stopped['reason'] == 'unavailable'
    asyncio.run(scenario())


def test_an_old_metadata_nonce_cannot_be_reused_after_new_clean_speech(wire):
    async def scenario():
        async with wire() as (ws, started, remote, _):
            await utterance(ws, started, remote)
            await remote.wait('response.create')
            while not remote.responses:
                await asyncio.sleep(0.001)
            rid = next(iter(remote.responses))
            old_metadata = remote.responses[rid]
            await answer(remote, rid)
            assert [e['type'] for e in await collect(ws)] == ['response.text', 'response.audio', 'response.done']
            await update(ws, started)
            await utterance(ws, started, remote, revision=1)
            await remote.wait('response.create', count=2)
            await remote.event('response.created', response={'id': 'old-late', 'metadata': old_metadata})
            stopped = await receive(ws)
            assert stopped['type'] == 'session.ended' and stopped['reason'] == 'unavailable'
    asyncio.run(scenario())


@pytest.mark.parametrize('action', ['finish', 'fail', 'session.end', 'audio.clear', 'response.cancel', 'context.update', 'logout'])
def test_context_preparation_cannot_revive_old_completed_or_partial_speech(wire, monkeypatch, action):
    entered, release = threading.Event(), threading.Event()
    prepare = voice.prepare_context
    def paused(scope, **kwargs):
        if scope.revision == 1:
            entered.set()
            assert release.wait(2)
            if action == 'fail':
                from fastapi import HTTPException
                raise HTTPException(422, 'Synthetic invalid attachment')
        return prepare(scope, **kwargs)
    monkeypatch.setattr(voice, 'prepare_context', paused)
    async def scenario():
        async with wire() as (ws, started, remote, http):
            old = await commit(ws, started)
            await send(ws, started, 'context.update', scope={**SCOPE, 'revision': 1})
            assert (await receive(ws))['type'] == 'audio.clear'
            assert await asyncio.to_thread(entered.wait, 1)
            await remote.event('conversation.item.input_audio_transcription.updated', item_id=old, transcript='Open settings')
            await remote.event('conversation.item.input_audio_transcription.completed', item_id=old, transcript='Open settings')
            assert await collect(ws) == []
            if action == 'logout':
                assert (await http.post('/api/auth/logout', json={})).status_code == 204
            elif action not in {'finish', 'fail'}:
                fields = {'scope': {**SCOPE, 'revision': 2}} if action == 'context.update' else {}
                await send(ws, started, action, **fields)
            release.set()
            event = await receive(ws)
            if action == 'finish':
                assert event['type'] == 'context.updated'
                event = await utterance(ws, started, remote, 'Open settings', revision=1)
                assert event['navigation'] == {'destination': 'settings'}
            else:
                assert event['type'] == 'session.ended'
                assert not any(m['type'] == 'conversation.item.create' for m in remote.messages)
    try:
        asyncio.run(scenario())
    finally:
        release.set()


def test_configuration_commit_response_cancel_clear_and_reference_share_the_same_twenty_frames(wire):
    async def scenario():
        async with wire() as (ws, started, remote, _):
            for count in range(1, 7):
                await utterance(ws, started, remote)
                await remote.wait('response.create', count=count)
                while len(remote.responses) < count:
                    await asyncio.sleep(0.001)
                await answer(remote, list(remote.responses)[-1])
                # Await the reply before using the short idle window to check for extra events.
                events = [await receive(ws) for _ in range(3)]
                assert [e['type'] for e in events] == ['response.text', 'response.audio', 'response.done']
                assert await collect(ws) == []
            await update(ws, started)
            await utterance(ws, started, remote, revision=1)
            await remote.wait('response.create', count=7)
            while len(remote.responses) < 7:
                await asyncio.sleep(0.001)
            await update(ws, started, revision=1)  # cancels the7th response and clears real input
            from collections import Counter
            actual = Counter(m['type'] for m in remote.messages if m['type'] != 'input_audio_buffer.append')
            assert actual == {'session.update': 1, 'input_audio_buffer.commit': 7, 'response.create': 7,
                              'response.cancel': 1, 'input_audio_buffer.clear': 2, 'conversation.item.create': 2}
            assert sum(actual.values()) == 20
            await send(ws, started, 'audio.clear', revision=2)
            stopped = await receive(ws)
            assert stopped['type'] == 'session.ended' and stopped['reason'] == 'unavailable'
            assert len([m for m in remote.messages if m['type'] != 'input_audio_buffer.append']) == 20
            assert str(llm_gate._memory.today()) == '0.160000'
    asyncio.run(scenario())
