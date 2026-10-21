"""Provider transports for identify, every one metered through engine.llm_gate.

A transport is the only thing that talks to Jev, Anthropic or OpenAI. Each call reserves its
worst-case cost first (`llm_gate.reserve`), settles with the tokens the provider reported
(`llm_gate.settle`), and releases the reservation when the call fails (`llm_gate.release`).
A shut gate raises GateClosed (no retry), and the pipeline takes its labelled fallback.

`BATATIS_PROVIDER=fake` swaps every transport for the offline fakes in fakes.py. The fakes are
metered the same way under the same pinned model ids, so the spend path is tested without keys.
Keys are read only by the provider SDK or as a request header; they are never logged or returned.
"""
from __future__ import annotations

import json
import os
import threading
from contextlib import contextmanager
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any, Callable

from engine import llm_gate

from .screen import JEV_MODEL, Ask, NoRetry

OPENAI_URL = 'https://api.openai.com/v1/chat/completions'
# OpenAI JSON transport: (name, schema, system, user, model, max_output_tokens) -> (payload, usage)
OpenAIJson = Callable[..., tuple[dict, dict]]


class GateClosed(NoRetry):
    def __init__(self, provider: str, source: str):
        self.provider, self.source = provider, source
        super().__init__(f'{provider}: {source}')


def estimate_tokens(text: str | int) -> int:
    """Conservative token count for a reservation: one token per three characters, plus framing."""
    return (text if isinstance(text, int) else len(text)) // 3 + 64


@dataclass
class SpendLog:
    """What this run settled, per call. Feeds the trace (cost per case) and the tests."""
    calls: list[dict] = field(default_factory=list)
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    def add(self, **row) -> None:
        with self._lock:
            self.calls.append(row)

    def usd(self) -> float:
        return float(sum((Decimal(str(row['usd'])) for row in self.calls), Decimal('0')))

    def by_provider(self) -> dict[str, dict]:
        out: dict[str, dict] = {}
        for row in self.calls:
            slot = out.setdefault(row['provider'], {'requests': 0, 'input_tokens': 0, 'output_tokens': 0, 'usd': 0.0})
            slot['requests'] += 1
            slot['input_tokens'] += row['input_tokens']
            slot['output_tokens'] += row['output_tokens']
            slot['usd'] = round(slot['usd'] + row['usd'], 6)
        return out


@contextmanager
def metered(provider: str, model: str, max_input_tokens: int, max_output_tokens: int, *,
            client_ip: str | None = None, log: SpendLog | None = None):
    """Reserve, then yield `settle(input_tokens, output_tokens)`. Unsettled reservations are released."""
    decision = llm_gate.reserve(provider=provider, model=model, max_input_tokens=max_input_tokens,
                                max_output_tokens=max_output_tokens, client_ip=client_ip)
    if not decision.allowed:
        raise GateClosed(provider, decision.source)
    done = {'settled': False}

    def settle(input_tokens: int, output_tokens: int) -> None:
        if done['settled']:
            return
        done['settled'] = True
        usd = llm_gate.settle(decision, model=model, input_tokens=int(input_tokens or 0),
                              output_tokens=int(output_tokens or 0))
        if log is not None:
            log.add(provider=provider, model=model, input_tokens=int(input_tokens or 0),
                    output_tokens=int(output_tokens or 0), usd=float(usd))
    try:
        yield settle
    finally:
        if not done['settled']:
            llm_gate.release(decision)


def metered_ask(raw: Ask, *, model: str = JEV_MODEL, client_ip: str | None = None,
                log: SpendLog | None = None) -> Ask:
    """Wrap a Jev ask so each request is reserved and settled. Estimated from the request size."""
    def ask(state, questions, timeout):
        size = len(json.dumps(state)) + len(json.dumps(questions))
        with metered('jev', model, estimate_tokens(size), 32 * len(questions) + 256,
                     client_ip=client_ip, log=log) as settle:
            reply = raw(state, questions, timeout)
            usage = reply.get('usage') or {}
            settle(usage.get('input_tokens', 0), usage.get('output_tokens', 0))
            return reply
    return ask


class _MeteredMessages:
    def __init__(self, raw_messages, client_ip, log):
        self._raw, self._ip, self._log = raw_messages, client_ip, log

    def parse(self, **kw):
        prompt = (kw.get('system') or '') + ''.join(str(m.get('content', '')) for m in kw.get('messages') or [])
        with metered('anthropic', kw['model'], estimate_tokens(prompt), int(kw.get('max_tokens') or 16000),
                     client_ip=self._ip, log=self._log) as settle:
            response = self._raw.parse(**kw)
            usage = getattr(response, 'usage', None)
            settle(getattr(usage, 'input_tokens', 0), getattr(usage, 'output_tokens', 0))
            return response


class MeteredAnthropic:
    """Anthropic client facade exposing `messages.parse`, the only method the verifier uses."""

    def __init__(self, raw_client, *, client_ip: str | None = None, log: SpendLog | None = None):
        self.messages = _MeteredMessages(raw_client.messages, client_ip, log)


def live_anthropic():
    import anthropic
    return anthropic.Anthropic(max_retries=0, timeout=60)


def raw_openai_json(name: str, schema: dict, system: str, user: str, *, model: str,
                    max_output_tokens: int = 4096, effort: str | None = None, timeout: float = 60) -> tuple[dict, dict]:
    """One Chat Completions request with a strict JSON schema. Unmetered: use metered_openai_json.

    Sends `reasoning_effort` when given and `max_completion_tokens` (which bounds reasoning plus answer).
    No `service_tier` is sent, so the request runs on the standard tier.
    """
    import httpx
    key = (os.environ.get('OPENAI_API_KEY') or '').strip()
    if not key:
        raise RuntimeError('OPENAI_API_KEY is not set')
    with httpx.Client(timeout=timeout, follow_redirects=False) as client:
        body = {
            'model': model, 'max_completion_tokens': max_output_tokens,
            'messages': [{'role': 'system', 'content': system}, {'role': 'user', 'content': user}],
            'response_format': {'type': 'json_schema', 'json_schema': {'name': name, 'strict': True, 'schema': schema}},
        }
        if effort:
            body['reasoning_effort'] = effort
        response = client.post(OPENAI_URL, headers={'Authorization': 'Bearer ' + key}, json=body)
        response.raise_for_status()
        data = response.json()
    raw = data.get('usage') or {}
    return json.loads(data['choices'][0]['message']['content']), {
        'input_tokens': raw.get('prompt_tokens', 0), 'output_tokens': raw.get('completion_tokens', 0),
        'returned_model': data.get('model')}


def metered_openai_json(raw: OpenAIJson, *, client_ip: str | None = None, log: SpendLog | None = None) -> OpenAIJson:
    def call(name, schema, system, user, *, model, max_output_tokens=4096, effort=None, timeout=60):
        with metered('openai', model, estimate_tokens(system + user + json.dumps(schema)), max_output_tokens,
                     client_ip=client_ip, log=log) as settle:
            payload, usage = raw(name, schema, system, user, model=model, max_output_tokens=max_output_tokens,
                                 effort=effort, timeout=timeout)
            settle(usage.get('input_tokens', 0), usage.get('output_tokens', 0))
            return payload, usage
    return call


@dataclass
class Transports:
    """The provider calls one identify run may make. None = that provider is not available."""
    kind: str                                  # 'live' or 'fake'
    jev: Ask | None = None
    anthropic: Any = None                      # has .messages.parse
    openai: OpenAIJson | None = None
    log: SpendLog = field(default_factory=SpendLog)
    unavailable: dict[str, str] = field(default_factory=dict)   # provider -> why


def transports(client_ip: str | None = None, *, jev_model: str = JEV_MODEL) -> Transports:
    """Live transports where the gate is open, or the fakes when BATATIS_PROVIDER=fake. No call is made here."""
    log = SpendLog()
    if llm_gate.fake_providers():
        from . import fakes
        return Transports(
            kind='fake', log=log,
            jev=metered_ask(fakes.fake_jev_ask(), model=jev_model, client_ip=client_ip, log=log),
            anthropic=MeteredAnthropic(fakes.FakeAnthropic(), client_ip=client_ip, log=log),
            openai=metered_openai_json(fakes.fake_openai_json, client_ip=client_ip, log=log))
    out = Transports(kind='live', log=log)
    if llm_gate.provider_enabled('jev'):
        from .screen import raw_jev_ask
        out.jev = metered_ask(raw_jev_ask(jev_model), model=jev_model, client_ip=client_ip, log=log)
    else:
        out.unavailable['jev'] = 'BATATIS_LIVE is off or the TypeSafe credential is absent'
    if llm_gate.provider_enabled('anthropic'):
        out.anthropic = MeteredAnthropic(live_anthropic(), client_ip=client_ip, log=log)
    else:
        out.unavailable['anthropic'] = 'BATATIS_LIVE is off or ANTHROPIC_API_KEY is absent'
    if llm_gate.provider_enabled('openai'):
        out.openai = metered_openai_json(raw_openai_json, client_ip=client_ip, log=log)
    else:
        out.unavailable['openai'] = 'BATATIS_LIVE is off or OPENAI_API_KEY is absent'
    return out
