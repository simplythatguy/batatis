"""Second pass: a model points at facts the rules did not find. It can only point.

Every model fact carries a quote. A quote that is not in the source text is dropped and counted.
A quote that is found becomes a `pointed` fact when the rules, re-run over that sentence, read the
same value (`rules.supports`); otherwise the value is stored as `proposed`, which the ledger never
lets count as confirmed. The model never sees personal details: the caller passes text that went
through `engine.redact.scrub`. Live calls are off unless BATATIS_LIVE=1 and go through the spend
gate (`engine.llm_gate`). Tests and `BATATIS_PROVIDER=fake` use a deterministic fake.
"""
from __future__ import annotations

import json
import math
import os
import re
from dataclasses import dataclass, field
from typing import Callable

from .. import llm_gate
from .rules import ENUMS, FIELDS, PERSONAL, supports
from .text import find_quote, is_question, sentences

MODEL = 'gpt-6-luna'
EFFORT = 'medium'
MAX_OUTPUT_TOKENS = 6000
MAX_CHARS = 8000
OPENAI_URL = 'https://api.openai.com/v1/chat/completions'
STATEMENT = 'statement'

ASKED = tuple(name for name in FIELDS if name not in PERSONAL and name != 'claimed_provision')

SYSTEM = (
    'You read an applicant\'s description of a building project for an Alberta alternative-solution '
    '(variance) application and list the facts the text states. Each fact is {"field", "value", "quote"}. '
    '"quote" is copied word for word from the text: the shortest phrase that states the value. '
    'Use a listed field when one fits; its value is written as the text gives it (numbers as numbers, '
    'converted to metres or square metres only when the text uses those units). Use "statement" for any '
    'other fact about the building, the design, the departure from the acceptable solution, materials, '
    'evidence the applicant has, or what the applicant says is not known yet; its value is the quote. '
    'Do not infer, judge compliance, safety or adequacy, or name a code article. Leave out anything the '
    'text does not say. Personal details were replaced with placeholders in square brackets; never quote them.'
)


def schema() -> dict:
    return {
        'type': 'object', 'additionalProperties': False, 'required': ['facts'],
        'properties': {'facts': {'type': 'array', 'items': {
            'type': 'object', 'additionalProperties': False, 'required': ['field', 'value', 'quote'],
            'properties': {
                'field': {'type': 'string', 'enum': [*ASKED, STATEMENT]},
                'value': {'type': 'string'},
                'quote': {'type': 'string'}}}}},
    }


# (system, user, schema) -> (payload, usage). Raise GateClosed when the call may not be made.
Transport = Callable[[str, str, dict], tuple[dict, dict]]


class GateClosed(Exception):
    def __init__(self, source: str):
        self.source = source
        super().__init__(source)


@dataclass
class ModelFact:
    field: str
    value: str | int | float | bool
    start: int
    end: int
    verified: bool                              # rules re-derived the value from the quoted sentence


@dataclass
class ModelRun:
    status: str                                 # live, fake, gate_closed, failed, not_needed, off
    facts: list[ModelFact] = field(default_factory=list)
    dropped: int = 0
    input_tokens: int | None = 0
    output_tokens: int | None = 0
    reason: str | None = None


def _coerce(name: str, raw: str):
    kind = FIELDS[name][1]
    text = str(raw).strip()
    if kind == 'int':
        return int(text) if re.fullmatch(r'\d{1,5}', text) else None
    if kind == 'number':
        try:
            value = float(text.replace(',', ''))
        except ValueError:
            return None
        return value if math.isfinite(value) else None     # float() also accepts "nan", "inf" and "1e999"
    if kind == 'bool':
        return {'true': True, 'yes': True, 'false': False, 'no': False}.get(text.lower())
    if kind == 'enum':
        return text if text in ENUMS.get(name, ()) else None
    return text or None


def verify(payload: dict, source: str, *, skip: set[str]) -> tuple[list[ModelFact], int]:
    """Keep model facts whose quote is in `source`. `skip` holds fields the rules already read."""
    kept: list[ModelFact] = []
    dropped = 0
    seen: set[tuple[str, int, int]] = set()
    for item in (payload or {}).get('facts') or []:
        if not isinstance(item, dict):
            dropped += 1
            continue
        name, quote = item.get('field'), item.get('quote')
        if not isinstance(quote, str) or not isinstance(name, str):
            dropped += 1
            continue
        span = find_quote(source, quote)
        if span is None or re.search(r'\[(?:name|email|phone|address|postal code|personal detail)\]', quote):
            dropped += 1
            continue
        start, end = span
        if name == STATEMENT:
            if is_question(source[start:end]):
                continue
            key = (STATEMENT, start, end)
            if key not in seen:
                seen.add(key)
                kept.append(ModelFact(STATEMENT, source[start:end], start, end, True))
            continue
        if name not in ASKED or name in skip:
            continue
        value = _coerce(name, item.get('value'))
        if value is None:
            dropped += 1
            continue
        key = (name, start, end)
        if key in seen:
            continue
        seen.add(key)
        kept.append(ModelFact(name, value, start, end, supports(name, value, source, start, end)))
    return kept, dropped


def run(source: str, outbound: str, transport: Transport | None, *, skip: set[str], status: str) -> ModelRun:
    """One model call over `outbound` (the scrubbed copy of `source`), verified against `source`."""
    if transport is None:
        return ModelRun(status='off')
    user = json.dumps({'fields': {name: FIELDS[name][0] for name in ASKED if name not in skip},
                       'text': outbound[:MAX_CHARS]}, ensure_ascii=False)
    try:
        payload, usage = transport(SYSTEM, user, schema())
    except GateClosed as closed:
        return ModelRun(status='gate_closed', reason=closed.source, input_tokens=None, output_tokens=None)
    except Exception as exc:                     # provider text may carry request details; keep only the type
        return ModelRun(status='failed', reason=type(exc).__name__, input_tokens=None, output_tokens=None)
    facts, dropped = verify(payload, source, skip=skip)
    return ModelRun(status=status, facts=facts, dropped=dropped,
                    input_tokens=usage.get('input_tokens'), output_tokens=usage.get('output_tokens'))


def openai_transport(client_ip: str | None = None) -> Transport:
    """Chat Completions with a strict schema, metered: reserve before, record after. No retry."""
    def call(system: str, user: str, body_schema: dict) -> tuple[dict, dict]:
        import httpx
        max_input = len((system + user + json.dumps(body_schema)).encode()) // 3 + 256
        decision = llm_gate.authorize(model=MODEL, max_input_tokens=max_input, max_output_tokens=MAX_OUTPUT_TOKENS,
                                      client_ip=client_ip, provider='openai')
        if not decision.allowed:
            raise GateClosed(decision.source)
        body = {'model': MODEL, 'max_completion_tokens': MAX_OUTPUT_TOKENS, 'reasoning_effort': EFFORT,
                'messages': [{'role': 'system', 'content': system}, {'role': 'user', 'content': user}],
                'response_format': {'type': 'json_schema',
                                    'json_schema': {'name': 'intake_facts', 'strict': True, 'schema': body_schema}}}
        # A failed call keeps its reservation: it may still have used tokens.
        with httpx.Client(timeout=60, follow_redirects=False) as client:
            response = client.post(OPENAI_URL, json=body,
                                   headers={'Authorization': 'Bearer ' + os.environ['OPENAI_API_KEY']})
            response.raise_for_status()
            data = response.json()
        usage = data.get('usage') or {}
        tokens = {'input_tokens': usage.get('prompt_tokens', 0), 'output_tokens': usage.get('completion_tokens', 0)}
        llm_gate.record(model=MODEL, reserved_usd=decision.reserved_usd, **tokens)
        return json.loads(data['choices'][0]['message']['content']), tokens
    return call


_FAKE_CUE = re.compile(r"(?i)\b(?:no|not|without|instead|only|omit|we want|we propose|unspecified|have not)\b")


def fake_transport(system: str, user: str, body_schema: dict) -> tuple[dict, dict]:
    """Deterministic stand-in: points at each statement sentence with a departure or a gap cue.
    It reads the outbound text only, like the real model. Not a measurement."""
    text = json.loads(user)['text']
    facts = [{'field': STATEMENT, 'value': text[a:b], 'quote': text[a:b]}
             for a, b in sentences(text) if _FAKE_CUE.search(text[a:b]) and not is_question(text[a:b])]
    return {'facts': facts}, {'input_tokens': len(system + user) // 4, 'output_tokens': 40 * len(facts)}


def default_transport(client_ip: str | None = None) -> tuple[Transport | None, str]:
    """The transport this deployment allows, and the status label for its results."""
    from .. import provider_routing
    if provider_routing.local_active():
        selected = provider_routing.local_profile()
        if selected.generation == 'off':
            return None, 'off'
        return provider_routing.local_transport('intake', model=MODEL, effort=EFFORT, max_output_tokens=MAX_OUTPUT_TOKENS,
                                                lease=selected.lease), 'live'
    if (os.environ.get('BATATIS_PROVIDER') or '').strip().lower() == 'fake' and not os.environ.get('VERCEL'):
        return fake_transport, 'fake'
    if llm_gate.live_enabled('openai'):
        return openai_transport(client_ip), 'live'
    return None, 'off'
