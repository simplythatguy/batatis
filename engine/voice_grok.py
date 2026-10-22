"""One server-only Grok Voice 3.0 adapter, pinned to the official realtime protocol.

No provider secret, upstream session instructions, or raw upstream errors leave
this module. The caller reserves the full allowance BEFORE opening a socket.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os

from websockets.asyncio.client import connect

MODEL = 'grok-voice-3.0'
URL = 'wss://api.x.ai/v1/realtime?model=grok-voice-3.0'
MAX_EVENT_BYTES = 256_000
MAX_TEXT_INPUTS = 20
PCM_RATE = 24_000


class VoiceFailure(Exception):
    """Fixed, non-sensitive failure; never wrap an upstream message as public text."""


class _PinnedConnect(connect):
    def process_redirect(self, exc):
        return exc  # Never forward the server credential to a redirect target.


class GrokVoice:
    def __init__(self):
        self.socket = None
        self.text_inputs = 0
        self._send_lock = asyncio.Lock()

    async def open(self):
        key = (os.environ.get('XAI_API_KEY') or '').strip()
        if not key or len(key) > 2000 or any(ord(char) < 33 or ord(char) > 126 for char in key):
            raise VoiceFailure()
        # Library wire-debug logs include Authorization and payloads. This
        # unregistered logger is disabled even if the app enables global DEBUG.
        logger = logging.Logger('batatis-voice-wire')
        logger.disabled = True
        self.socket = await _PinnedConnect(URL, additional_headers={'Authorization': 'Bearer ' + key},
            proxy=None, logger=logger, open_timeout=5, close_timeout=1,
            ping_interval=10, ping_timeout=5, max_size=MAX_EVENT_BYTES, max_queue=8)
        async with asyncio.timeout(5):
            for _ in range(10):
                event = await self.receive()
                if event['type'] == 'session.created':
                    self.check_session(event)
                    return
                if event['type'] != 'conversation.created':
                    raise VoiceFailure()
        raise VoiceFailure()

    @staticmethod
    def configuration(instructions: str) -> dict:
        return {'type': 'session.update', 'session': {'model': MODEL, 'voice': 'Eve',
            'instructions': instructions, 'tools': [], 'resumption': {'enabled': False},
            'turn_detection': {'type': 'server_vad'},
            'audio': {'input': {'format': {'type': 'audio/pcm', 'rate': PCM_RATE}},
                      'output': {'format': {'type': 'audio/pcm', 'rate': PCM_RATE}}}}}

    async def configure(self, instructions: str):
        await self.send(self.configuration(instructions))
        async with asyncio.timeout(5):
            for _ in range(10):
                event = await self.receive()
                if event['type'] == 'session.updated':
                    self.check_session(event)
                    return
                if event['type'] == 'session.created':
                    self.check_session(event)
                if event['type'] not in {'conversation.created', 'session.created'}:
                    raise VoiceFailure()
        raise VoiceFailure()

    @staticmethod
    def check_session(event: dict):
        session = event.get('session')
        if not isinstance(session, dict) or session.get('model') != MODEL or session.get('tools', []):
            raise VoiceFailure()

    async def send(self, event: dict):
        async with self._send_lock:
            if self.socket is None:
                raise VoiceFailure()
            # Count every control/context message, conservatively including
            # cancellations, as a paid text input. Audio appends have a separate
            # byte/time bound enforced by VoiceSession.
            if event['type'] != 'input_audio_buffer.append':
                if self.text_inputs >= MAX_TEXT_INPUTS:
                    raise VoiceFailure()
                self.text_inputs += 1
            await self.socket.send(json.dumps(event, ensure_ascii=False))

    async def receive(self) -> dict:
        if self.socket is None:
            raise VoiceFailure()
        raw = await self.socket.recv()
        if not isinstance(raw, str) or len(raw.encode()) > MAX_EVENT_BYTES:
            raise VoiceFailure()
        try:
            event = json.loads(raw)
        except (ValueError, RecursionError):
            raise VoiceFailure() from None
        if not isinstance(event, dict) or not isinstance(event.get('type'), str):
            raise VoiceFailure()
        if event['type'] == 'error':
            raise VoiceFailure()
        return event

    def abort(self):
        # Abort immediately, including on timeout/cancellation; a graceful
        # closing handshake must not keep a paid connection alive.
        if self.socket is not None:
            self.socket.transport.abort()

    async def close(self):
        self.abort()
        if self.socket is not None:
            try:
                async with asyncio.timeout(1):
                    await self.socket.wait_closed()
            except (TimeoutError, OSError):
                pass
            finally:
                self.socket = None
