"""Provider transports for identify, every one metered through engine.llm_gate.

A transport is the only thing that talks to Elephant, Jev, Anthropic or OpenAI. Each call reserves its
worst-case cost first (`llm_gate.reserve`), settles with the tokens the provider reported
(`llm_gate.settle`), and releases the reservation when the call fails (`llm_gate.release`).
Unknown dispatch/usage follows the transport's own accounting policy. A shut gate raises
GateClosed (no retry), and the pipeline takes its labelled fallback.

`BATATIS_PROVIDER=fake` swaps every transport for the offline fakes in fakes.py. The fakes are
metered the same way under the same pinned model ids, so the spend path is tested without keys.
Keys are read only by the provider SDK or as a request header; they are never logged or returned.
"""
from __future__ import annotations

import json
import math
import os
import threading
from contextlib import contextmanager
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any, Callable

from engine import llm_gate

from .screen import DECISIONS_MODEL, JEV_MODEL, MAX_QUESTIONS, Ask, NoRetry

OPENAI_URL = 'https://api.openai.com/v1/chat/completions'
DECISIONS_URL = 'https://api.openai.com/v1/decisions'
DECISIONS_MAX_QUESTIONS = MAX_QUESTIONS
# OpenAI JSON transport: (name, schema, system, user, model, max_output_tokens) -> (payload, usage)
OpenAIJson = Callable[..., tuple[dict, dict]]
DecisionsRaw = Callable[[dict, float], dict]


class DecisionsProtocolError(NoRetry):
    """Invalid or refused scoring answers cannot be repaired by repeating the same request."""


class ScoringUnavailable(NoRetry, RuntimeError):
    """A configured scoring transport is unavailable; no network call or retry is appropriate."""


def raw_openai_decisions(body: dict, timeout: float) -> dict:
    """Dedicated Decisions HTTP transport. Runtime callers use metered_decisions_ask."""
    import httpx
    key = (os.environ.get('OPENAI_API_KEY') or '').strip()
    if not key:
        raise RuntimeError('OPENAI_API_KEY is not set')
    with httpx.Client(timeout=timeout, follow_redirects=False) as client:
        response = client.post(DECISIONS_URL, headers={'Authorization': 'Bearer ' + key}, json=body)
        response.raise_for_status()
        return response.json()


def metered_decisions_ask(raw: DecisionsRaw, *, model: str = DECISIONS_MODEL,
                          client_ip: str | None = None, log: SpendLog | None = None) -> Ask:
    """Adapt named Decisions predicates to Judge's internal `noul` values, after settlement.

    The serialized state is text input; no JSON-part limits or generated-output parameters apply.
    Decisions reports input/output token counts directly. The existing conservative Luna price
    remains the ledger estimate, including for refused or malformed answers with reported usage.
    """
    if model != DECISIONS_MODEL:
        raise ValueError('Decisions requires the pinned scoring model')

    def ask(state, questions, timeout):
        if not 1 <= len(questions) <= DECISIONS_MAX_QUESTIONS:
            raise DecisionsProtocolError('scoring requires 1 to 400 questions')
        predicates = []
        for name, question in questions.items():
            if not isinstance(name, str) or not name or question.get('type') != 'noul' \
                    or not isinstance(question.get('instructions'), str):
                raise DecisionsProtocolError('invalid scoring question')
            predicates.append({'type': 'predicate', 'name': name, 'instructions': question['instructions']})
        body = {'model': model, 'input': json.dumps(state), 'questions': predicates}
        # One token per serialized UTF-8 byte plus framing bounds text/question tokens conservatively.
        with metered('openai_decisions', model, len(json.dumps(body).encode('utf-8')) + 64, 0,
                     client_ip=client_ip, log=log) as settle:
            data = raw(body, timeout)
            usage = data.get('usage') if isinstance(data, dict) else None
            if not isinstance(usage, dict) or any(type(usage.get(k)) is not int or usage[k] < 0
                                                  for k in ('input_tokens', 'output_tokens')):
                raise DecisionsProtocolError('scoring usage is missing or invalid')
            settle(usage['input_tokens'], usage['output_tokens'])
            if type(usage.get('total_tokens')) is not int \
                    or usage['total_tokens'] != usage['input_tokens'] + usage['output_tokens']:
                raise DecisionsProtocolError('scoring token totals do not match')
            for field, names, total in (
                ('input_tokens_details', ('cached_tokens', 'cache_write_tokens'), usage['input_tokens']),
                ('output_tokens_details', ('reasoning_tokens',), usage['output_tokens']),
            ):
                details = usage.get(field)
                if not isinstance(details, dict) or any(type(details.get(k)) is not int or not 0 <= details[k] <= total
                                                        for k in names):
                    raise DecisionsProtocolError('scoring token details are missing or invalid')
            if data.get('model') != model:
                raise DecisionsProtocolError('scoring returned an unexpected model')
            answers = data.get('answers')
            if not isinstance(answers, list) or len(answers) != len(predicates):
                raise DecisionsProtocolError('scoring answer count does not match')
            normalized = {}
            for expected, answer in zip(predicates, answers):
                if not isinstance(answer, dict) or answer.get('name') != expected['name']:
                    raise DecisionsProtocolError('scoring answer names do not match')
                probability = answer.get('probability')
                if answer.get('type') != 'predicate' or type(probability) not in (int, float) \
                        or not 0 <= probability <= 1 or not math.isfinite(probability):
                    raise DecisionsProtocolError('scoring answer is refused or invalid')
                normalized[expected['name']] = {'noul': probability}
            return {'answers': normalized, 'usage': usage, 'model': data['model']}
    ask.model, ask.method = model, 'decisions'
    return ask


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

    def usd(self) -> float | None:
        if any(row['usd'] is None for row in self.calls):
            return None
        return float(sum((Decimal(str(row['usd'])) for row in self.calls), Decimal('0')))

    def by_provider(self) -> dict[str, dict]:
        out: dict[str, dict] = {}
        for row in self.calls:
            slot = out.setdefault(row['provider'], {'requests': 0, 'input_tokens': 0, 'output_tokens': 0, 'usd': 0.0})
            slot['requests'] += 1
            for name in ('input_tokens', 'output_tokens', 'usd'):
                a, b = slot[name], row[name]
                slot[name] = None if a is None or b is None else round(a + b, 6)
            if 'billing' in row:
                slot['billing'] = row['billing']
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
    """Jev's own strict accounting, including an explicit Jev-only dollar exemption."""
    from .jev_runtime import metered_ask as wrap
    return wrap(raw, model=model, client_ip=client_ip, log=log)


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


def anthropic_opted_in() -> bool:
    """Anthropic is used only when it is the configured verifier (IdentifyConfig). A key alone never opts in."""
    from .config import ConfigError, load_config
    try:
        return load_config().verifier == 'anthropic'
    except (ConfigError, ValueError, OSError):
        return False


def live_anthropic():
    import anthropic
    return anthropic.Anthropic(max_retries=0, timeout=60, **llm_gate.anthropic_client_options())


class UnreadableResponse(RuntimeError):
    """The provider answered, and billed, but the content is unusable (a refusal or a truncated answer)."""

    def __init__(self, message: str, usage: dict):
        super().__init__(message)
        self.usage = usage


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
    usage = {'input_tokens': raw.get('prompt_tokens', 0), 'output_tokens': raw.get('completion_tokens', 0),
             'returned_model': data.get('model')}
    try:
        return json.loads(data['choices'][0]['message']['content']), usage
    except (KeyError, IndexError, TypeError, ValueError) as error:
        raise UnreadableResponse('OpenAI returned no usable JSON', usage) from error


def metered_openai_json(raw: OpenAIJson, *, client_ip: str | None = None, log: SpendLog | None = None) -> OpenAIJson:
    def call(name, schema, system, user, *, model, max_output_tokens=4096, effort=None, timeout=60):
        with metered('openai', model, estimate_tokens(system + user + json.dumps(schema)), max_output_tokens,
                     client_ip=client_ip, log=log) as settle:
            try:
                payload, usage = raw(name, schema, system, user, model=model, max_output_tokens=max_output_tokens,
                                     effort=effort, timeout=timeout)
            except UnreadableResponse as error:     # billed: settle the real usage, then fail the call
                settle(error.usage.get('input_tokens', 0), error.usage.get('output_tokens', 0))
                raise
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
    decisions: Ask | None = None
    elephant: Ask | None = None
    log: SpendLog = field(default_factory=SpendLog)
    unavailable: dict[str, str] = field(default_factory=dict)   # provider -> why


def scoring_ask(tp: Transports, method: str) -> Ask:
    """Choose only the configured scoring transport; credentials cannot select a method."""
    ask = {'decisions': tp.decisions, 'jev': tp.jev, 'elephant': tp.elephant}.get(method)
    if ask is None:
        raise ScoringUnavailable(tp.unavailable.get(method, 'exhaustive scoring transport unavailable'))
    return ask


def transports(client_ip: str | None = None, *, jev_model: str = JEV_MODEL, anthropic: bool = False,
               scoring: set[str] | None = None) -> Transports:
    """Live transports where the gate is open, or the fakes when BATATIS_PROVIDER=fake. No call is made here.

    Only selected scoring transports are built. An unselected Jev credential is never resolved.
    The full-text OpenAI verifier is separate from Decisions. An Anthropic client is built only
    when the run's config asks for it (`anthropic=True`), regardless of credential presence.
    """
    from .. import provider_routing
    if provider_routing.local_active():
        return provider_routing.local_identify_transports(scoring=scoring if scoring is not None else {'jev'},
                                                         jev_model=jev_model, anthropic=anthropic)
    if scoring is None:
        from .config import load_config
        config = load_config()
        scoring = {config.screen, config.rerank}
    log = SpendLog()
    if llm_gate.fake_providers():
        from . import fakes
        from .elephant_runtime import metered_ask as metered_elephant, raw_ask as raw_elephant
        return Transports(
            kind='fake', log=log,
            elephant=(metered_elephant(raw_elephant(post=fakes.fake_elephant_post,
                                                    credential=lambda: 'offline-fake'), client_ip=client_ip, log=log)
                      if 'elephant' in scoring else None),
            jev=(metered_ask(fakes.fake_jev_ask(), model=jev_model, client_ip=client_ip, log=log)
                 if 'jev' in scoring else None),
            decisions=(metered_decisions_ask(fakes.fake_decisions, client_ip=client_ip, log=log)
                       if 'decisions' in scoring else None),
            anthropic=MeteredAnthropic(fakes.FakeAnthropic(), client_ip=client_ip, log=log),
            openai=metered_openai_json(fakes.fake_openai_json, client_ip=client_ip, log=log))
    out = Transports(kind='live', log=log)
    if 'elephant' not in scoring:
        out.unavailable['elephant'] = 'Elephant is not a configured scoring provider'
    elif llm_gate.provider_enabled('elephant'):
        from .elephant_runtime import metered_ask as metered_elephant, raw_ask as raw_elephant
        out.elephant = metered_elephant(raw_elephant(), client_ip=client_ip, log=log)
    else:
        out.unavailable['elephant'] = 'BATATIS_LIVE_ELEPHANT/BATATIS_LIVE is off or OPENROUTER_API_KEY is absent'
    if 'jev' not in scoring:
        out.unavailable['jev'] = 'Jev is not a configured scoring provider'
    elif llm_gate.provider_enabled('jev'):
        from .screen import raw_jev_ask
        out.jev = metered_ask(raw_jev_ask(jev_model), model=jev_model, client_ip=client_ip, log=log)
    else:
        out.unavailable['jev'] = 'BATATIS_LIVE is off or the TypeSafe credential is absent'
    if not anthropic:
        out.unavailable['anthropic'] = 'Anthropic is not a configured identify provider'
    elif llm_gate.provider_enabled('anthropic'):
        out.anthropic = MeteredAnthropic(live_anthropic(), client_ip=client_ip, log=log)
    else:
        out.unavailable['anthropic'] = 'BATATIS_LIVE is off or ANTHROPIC_API_KEY is absent'
    if llm_gate.provider_enabled('openai'):
        out.openai = metered_openai_json(raw_openai_json, client_ip=client_ip, log=log)
        if 'decisions' in scoring:
            out.decisions = metered_decisions_ask(raw_openai_decisions, client_ip=client_ip, log=log)
    else:
        out.unavailable['openai'] = 'BATATIS_LIVE is off or OPENAI_API_KEY is absent'
    if out.decisions is None:
        out.unavailable['decisions'] = 'OpenAI Decisions is not configured or BATATIS_LIVE/OPENAI_API_KEY is absent'
    return out
