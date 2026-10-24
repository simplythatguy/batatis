"""Signed-in voice capability; the provider is never contacted by a read."""
import asyncio
import os
import time

from fastapi import APIRouter, FastAPI, Query, Request, Response, WebSocket
from urllib.parse import urlsplit
from typing import Literal
from pydantic import BaseModel

from .accounts import COOKIE, SESSION_SECONDS, SESSION_TOKEN, digest, require_user
from .access import authorize_case
from . import llm_gate
from .voice import MAX_SECONDS, NOTICE, VoiceSession
from .voice_grok import GrokVoice

PROTOCOL = 'batatis.voice.v1'


class VoiceCapability(BaseModel):
    available: bool
    reason: str | None
    protocol: Literal['batatis.voice.v1']
    relay_path: Literal['/api/voice/relay/session']
    max_seconds: int
    notice: str


def fresh_user(socket, store):
    token = socket.cookies.get(COOKIE, '')
    if not SESSION_TOKEN.fullmatch(token):
        return None
    return store.session_user(digest(token), time.time() + SESSION_SECONDS)


def web_origin():
    value = os.environ.get('BATATIS_WEB_ORIGIN', '' if os.environ.get('VERCEL') else 'http://localhost:5480').rstrip('/')
    try:
        parsed = urlsplit(value)
    except ValueError:
        return None
    if (parsed.scheme not in {'http', 'https'} or not parsed.netloc or parsed.username or parsed.password
            or parsed.path or parsed.query or parsed.fragment):
        return None
    return value


def configured():
    return (llm_gate.live_enabled('xai') and web_origin() is not None
            and (not os.environ.get('VERCEL') or os.environ.get('BATATIS_STORE') == 'postgres'))


def create_router(cases):
    router = APIRouter(tags=['voice'])

    @router.get('/voice/session', response_model=VoiceCapability)
    def capability(request: Request, response: Response,
                   case_id: str | None = Query(default=None, min_length=1, max_length=100)):
        user = require_user(request)
        if case_id:
            authorize_case(cases().access_record(case_id), user)
        response.headers['Cache-Control'] = 'no-store'
        response.headers['X-Batatis-Notice'] = NOTICE
        return {'available': configured(), 'reason': None if configured() else 'Voice unavailable',
                'protocol': PROTOCOL, 'relay_path': '/api/voice/relay/session',
                'max_seconds': MAX_SECONDS, 'notice': NOTICE}

    return router


def create_relay(cases, code):
    # A separate ASGI app keeps Request-only HTTP dependencies intact. Every WS
    # handshake authenticates explicitly; mounting never makes a socket trusted.
    app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)

    @app.websocket('/session')
    async def session(socket: WebSocket):
        origin = web_origin()
        if (socket.headers.get('origin') != origin or not origin
                or PROTOCOL not in socket.scope.get('subprotocols', []) or socket.query_params):
            await socket.close(4403)
            return
        try:
            user = await asyncio.to_thread(fresh_user, socket, cases())
        except Exception:
            await socket.close(1013, 'Voice unavailable')
            return
        if user is None:
            await socket.close(4401)
            return
        await socket.accept(subprotocol=PROTOCOL)
        await VoiceSession(socket, store=cases(), code=code, user=user,
            authenticate=lambda: fresh_user(socket, cases()), provider_factory=GrokVoice).run()

    return app
