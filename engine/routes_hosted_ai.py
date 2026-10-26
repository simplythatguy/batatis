"""The hosted AI that an access code unlocks for the desktop app: Batatis's own steps on the team's keys.

The desktop app sends one workflow request at a time with its access code. Only the pinned desktop
profile (GPT-6 Luna at medium effort, one of the workflow's tasks, a strict output schema) is
answered, metered against the site's daily spend cap like every other AI call. The keys never leave
this server, and no answer echoes them.
"""
from __future__ import annotations

import json
import os

from fastapi import APIRouter, Header, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field

from . import ai_access, llm_gate
from .llm_gate import client_ip_from

MODEL, EFFORT = 'gpt-6-luna', 'medium'
TASKS = {'intake', 'document-review', 'identify-picks', 'assistant'}
MAX_TEXT = 2_500_000
# The largest workflow budget: document review asks for 32,000 output tokens.
MAX_OUTPUT_TOKENS = 32_000
FAILED_CODES_PER_WINDOW, FAILED_CODE_WINDOW = 10, 600.0
OPENAI_URL = 'https://api.openai.com/v1/chat/completions'
JEV_URL = 'https://api.typesafe.ai/v1/systemone'
JEV_MODEL = 'jev-1.13.0'


class HostedCompletion(BaseModel):
    model_config = ConfigDict(extra='forbid')
    task: str
    system: str
    user: str
    schema_: dict = Field(alias='schema')
    model: str
    effort: str
    maxOutputTokens: int | None = None


class HostedScreening(BaseModel):
    model_config = ConfigDict(extra='forbid')
    body: str = Field(max_length=MAX_TEXT)


def unlocked(store, request: Request, code: str | None) -> str:
    """The code's name. Too many wrong codes from one address stop all checks there for ten minutes."""
    from .accounts import digest
    bucket = digest('hosted-ai-code:' + client_ip_from(request))
    if store.account_rate_full(bucket, FAILED_CODES_PER_WINDOW):
        raise HTTPException(429, 'Too many attempts; try again later', headers={'Retry-After': str(int(FAILED_CODE_WINDOW))})
    name = ai_access.name_for(code)
    if name is None:
        store.account_rate(bucket, FAILED_CODES_PER_WINDOW, FAILED_CODE_WINDOW)
        raise HTTPException(403, 'That access code isn’t valid')
    ai_access.GRANTED.set(True)
    return name


def closed(source: str) -> HTTPException:
    if source == 'rate-limited':
        return HTTPException(429, 'Too many AI requests; try again later')
    return HTTPException(503, 'Batatis AI is unavailable right now. Try again later.')


def unusable() -> HTTPException:
    return HTTPException(502, 'The AI service did not return a usable answer')


def create_router(cases):
    router = APIRouter(prefix='/hosted-ai', tags=['hosted AI'])

    @router.post('/complete')
    def complete(body: HostedCompletion, request: Request, x_batatis_access_code: str | None = Header(default=None)):
        unlocked(cases(), request, x_batatis_access_code)
        if body.task not in TASKS or body.model != MODEL or body.effort != EFFORT:
            raise HTTPException(422, 'The request does not match the pinned desktop workflow profile')
        if len((body.system + body.user).encode()) > MAX_TEXT:
            raise HTTPException(413, 'The request is too large')
        limit = MAX_OUTPUT_TOKENS if body.maxOutputTokens is None else min(body.maxOutputTokens, MAX_OUTPUT_TOKENS)
        if limit < 1:
            raise HTTPException(422, 'The output budget must be positive')
        if not (os.environ.get('OPENAI_API_KEY') or '').strip():
            raise closed('offline')
        max_input = len((body.system + body.user + json.dumps(body.schema_)).encode()) // 3 + 256
        decision = llm_gate.authorize(model=MODEL, max_input_tokens=max_input, max_output_tokens=limit,
                                      client_ip=client_ip_from(request), provider='openai')
        if not decision.allowed:
            raise closed(decision.source)
        import httpx
        payload = {'model': MODEL, 'reasoning_effort': EFFORT, 'max_completion_tokens': limit,
                   'messages': [{'role': 'system', 'content': body.system}, {'role': 'user', 'content': body.user}],
                   'response_format': {'type': 'json_schema', 'json_schema': {
                       'name': body.task.replace('-', '_'), 'strict': True, 'schema': body.schema_}}}
        try:
            with httpx.Client(timeout=170, follow_redirects=False) as client:
                response = client.post(OPENAI_URL, json=payload, headers={'Authorization': 'Bearer ' + os.environ['OPENAI_API_KEY']})
        except httpx.ConnectError:
            llm_gate.release(decision)                 # never reached the service, so nothing was used
            raise closed('offline') from None
        except httpx.HTTPError:
            raise closed('offline') from None          # it may have used tokens: the reservation stands
        if response.status_code != 200:
            raise HTTPException(502, 'The AI service could not complete this request')
        try:
            data = response.json()
            usage = data.get('usage')
            choice = (data.get('choices') or [{}])[0]
            message = choice.get('message') or {}
        except (ValueError, AttributeError, IndexError, TypeError):
            raise unusable() from None
        counts = [usage.get(key) if isinstance(usage, dict) else None for key in ('prompt_tokens', 'completion_tokens')]
        tokens = None
        if all(isinstance(count, int) and not isinstance(count, bool) and count >= 0 for count in counts):
            tokens = {'input_tokens': counts[0], 'output_tokens': counts[1]}
            llm_gate.record(model=MODEL, reserved_usd=decision.reserved_usd, **tokens)
        # Without reported usage the worst-case reservation stands, so the cap never undercounts.
        if choice.get('finish_reason') != 'stop' or message.get('refusal') or not isinstance(message.get('content'), str):
            raise HTTPException(502, 'The AI service did not return a completed answer')
        try:
            answer = json.loads(message['content'])
        except ValueError:
            raise unusable() from None
        return {'json': answer, 'model': MODEL, 'effort': EFFORT,
                'usage': tokens and {'inputTokens': tokens['input_tokens'], 'outputTokens': tokens['output_tokens']}}

    @router.post('/screen')
    def screen(body: HostedScreening, request: Request, x_batatis_access_code: str | None = Header(default=None)):
        unlocked(cases(), request, x_batatis_access_code)
        try:
            parsed = json.loads(body.body)
        except ValueError:
            raise HTTPException(422, 'The screening request is not valid JSON') from None
        if not isinstance(parsed, dict) or parsed.get('model') != JEV_MODEL or not isinstance(parsed.get('questions'), dict) \
                or not 1 <= len(parsed['questions']) <= 400 or 'state' not in parsed:
            raise HTTPException(422, 'The screening request does not match its pinned profile')
        from .identify.jevkit import keystore
        from .identify.screen import JEV_PROVIDER
        key = keystore.resolve(JEV_PROVIDER) if os.environ.get('BATATIS_LIVE') == '1' else None
        if not key:
            raise closed('offline')
        decision = llm_gate.reserve(provider='jev', model=JEV_MODEL, max_input_tokens=len(body.body.encode()) // 3 + 256,
                                    max_output_tokens=0, client_ip=client_ip_from(request))
        if not decision.allowed:
            raise closed(decision.source)
        import httpx
        try:
            with httpx.Client(timeout=170, follow_redirects=False) as client:
                response = client.post(JEV_URL, content=body.body, headers={
                    'Authorization': 'Bearer ' + key, 'Content-Type': 'application/json', 'User-Agent': 'hermes-jev-skills/0.1'})
        except httpx.ConnectError:
            llm_gate.release(decision)
            raise closed('offline') from None
        except httpx.HTTPError:
            raise closed('offline') from None
        text = response.text
        if key in text:
            raise HTTPException(502, 'The screening service returned an unusable answer')
        try:
            reply = response.json() if response.status_code == 200 else None
        except ValueError:
            raise unusable() from None
        usage = reply.get('usage') if isinstance(reply, dict) else None
        reported = usage.get('input_tokens') if isinstance(usage, dict) else None
        # Without reported usage the worst-case reservation stands, so the cap never undercounts.
        if isinstance(reported, int) and not isinstance(reported, bool) and reported >= 0:
            llm_gate.settle(decision, model=JEV_MODEL, input_tokens=reported, output_tokens=0)
        return {'status': response.status_code, 'body': text if response.status_code == 200 else '{}'}

    return router
