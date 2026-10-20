"""OpenAI and Anthropic screen, rerank, and verifier.

Quote checking stays in verify.check_quotes and does not depend on the provider.
Ids the model returns that are not in the candidate list are dropped. Missing scores
are left missing; they are not invented.
"""
from __future__ import annotations

import json
import os

import httpx

from .config import (RERANK_MODEL, SCREEN_MODEL, VERIFY_MODEL_ANTHROPIC, VERIFY_MODEL_OPENAI,
                     provider, provider_key)
from .corpus import card
from .verify import SYSTEM, Pick, Verification, check_quotes

_SCORE_SCHEMA = {
    'type': 'object',
    'additionalProperties': False,
    'properties': {
        'scores': {
            'type': 'array',
            'items': {
                'type': 'object',
                'additionalProperties': False,
                'properties': {
                    'article': {'type': 'string'},
                    'probability': {'type': 'number'},
                },
                'required': ['article', 'probability'],
            },
        },
    },
    'required': ['scores'],
}

_PICK_SCHEMA = {
    'type': 'object',
    'additionalProperties': False,
    'properties': {
        'picks': {
            'type': 'array',
            'items': {
                'type': 'object',
                'additionalProperties': False,
                'properties': {
                    'article': {'type': 'string'},
                    'quote': {'type': 'string'},
                    'reason': {'type': 'string'},
                    'confidence': {'type': 'number'},
                },
                'required': ['article', 'quote', 'reason', 'confidence'],
            },
        },
    },
    'required': ['picks'],
}


def _empty_usage() -> dict:
    return {'input_tokens': 0, 'output_tokens': 0, 'requests': 0}


def _add(usage: dict, extra: dict, model: str | None = None) -> None:
    inn = int(extra.get('input_tokens') or 0)
    out = int(extra.get('output_tokens') or 0)
    usage['input_tokens'] += inn
    usage['output_tokens'] += out
    usage['requests'] += 1
    if model:
        slot = usage.setdefault('by_model', {}).setdefault(model, {'input_tokens': 0, 'output_tokens': 0, 'returned': []})
        slot['input_tokens'] += inn
        slot['output_tokens'] += out
        returned = extra.get('returned_model')
        if returned and returned not in slot['returned']:
            slot['returned'].append(returned)


def complete_json(name: str, schema: dict, system: str, user: str, *, model: str, which: str | None = None,
                  timeout: float = 60) -> tuple[dict, dict]:
    which = which or provider()
    if which == 'anthropic':
        return _anthropic_json(system, user, model=model, timeout=timeout)
    return _openai_json(name, schema, system, user, model=model, timeout=timeout)


def _openai_json(name, schema, system, user, *, model, timeout) -> tuple[dict, dict]:
    key = provider_key('openai')
    if not key:
        raise RuntimeError('OPENAI_API_KEY is not set')
    response = httpx.post(
        'https://api.openai.com/v1/chat/completions',
        headers={'Authorization': f'Bearer {key}'},
        json={
            'model': model,
            'messages': [{'role': 'system', 'content': system}, {'role': 'user', 'content': user}],
            'response_format': {'type': 'json_schema', 'json_schema': {'name': name, 'strict': True, 'schema': schema}},
        },
        timeout=timeout,
    )
    response.raise_for_status()
    data = response.json()
    content = data['choices'][0]['message']['content']
    raw = data.get('usage') or {}
    return json.loads(content), {
        'input_tokens': raw.get('prompt_tokens', 0),
        'output_tokens': raw.get('completion_tokens', 0),
        'returned_model': data.get('model'),
    }


def _anthropic_json(system, user, *, model, timeout) -> tuple[dict, dict]:
    key = provider_key('anthropic')
    if not key:
        raise RuntimeError('ANTHROPIC_API_KEY is not set')
    response = httpx.post(
        'https://api.anthropic.com/v1/messages',
        headers={'x-api-key': key, 'anthropic-version': '2023-06-01', 'content-type': 'application/json'},
        json={
            'model': model, 'max_tokens': 4096, 'system': system,
            'messages': [{'role': 'user', 'content': user + '\nRespond with one JSON object and no other text.'}],
        },
        timeout=timeout,
    )
    response.raise_for_status()
    data = response.json()
    text = ''.join(block.get('text', '') for block in data.get('content') or [] if block.get('type') == 'text')
    start, end = text.find('{'), text.rfind('}')
    if start < 0 or end < start:
        raise RuntimeError('anthropic response had no JSON object')
    raw = data.get('usage') or {}
    return json.loads(text[start:end + 1]), {'input_tokens': raw.get('input_tokens', 0), 'output_tokens': raw.get('output_tokens', 0)}


def _keep_scores(payload: dict, allowed: list[str]) -> list[tuple[str, float]]:
    ok = set(allowed)
    out, seen = [], set()
    for row in payload.get('scores') or []:
        art = row.get('article')
        if art not in ok or art in seen or not isinstance(row.get('probability'), (int, float)):
            continue
        seen.add(art)
        out.append((art, max(0.0, min(1.0, float(row['probability'])))))
    return out


def score_candidates(query: str, arts: dict, ids: list[str], *, model: str | None = None,
                     chars: int | None = 700, usage: dict | None = None) -> list[tuple[str, float]]:
    """Rerank or screen `ids`. Returned list is only ids the model scored, in its order."""
    which = provider()
    model = model or (RERANK_MODEL if which == 'openai' else VERIFY_MODEL_ANTHROPIC)
    listed = '\n\n'.join(f'<article id="{a}">\n{card(arts[a], chars)}\n</article>' for a in ids if a in arts)
    system = ('Score each listed Division B article for whether the proposal must meet it, relies on it, '
              'or departs from it. Return only article ids from the list. Do not judge compliance.')
    user = f'<proposal>\n{query}\n</proposal>\n\n<candidates>\n{listed}\n</candidates>'
    payload, spent = complete_json('scores', _SCORE_SCHEMA, system, user, model=model, which=which)
    if usage is not None:
        _add(usage, spent, model)
    return _keep_scores(payload, [a for a in ids if a in arts])


def verify_candidates(query: str, arts: dict, ids: list[str], *, model: str | None = None,
                      chars: int | None = None, usage: dict | None = None) -> Verification:
    which = provider()
    model = model or (VERIFY_MODEL_OPENAI if which == 'openai' else VERIFY_MODEL_ANTHROPIC)
    listed = '\n\n'.join(f'<article id="{a}">\n{card(arts[a], chars)}\n</article>' for a in ids if a in arts)
    user = f'<proposal>\n{query}\n</proposal>\n\n<candidates>\n{listed}\n</candidates>'
    payload, spent = complete_json('picks', _PICK_SCHEMA, SYSTEM, user, model=model, which=which)
    if usage is not None:
        _add(usage, spent, model)
    picks = [Pick(article=p['article'], quote=p['quote'], reason=p['reason'],
                  confidence=max(0.0, min(1.0, float(p['confidence']))))
             for p in payload.get('picks') or [] if isinstance(p, dict) and 'article' in p]
    keep, dropped = check_quotes(picks, [a for a in ids if a in arts], arts)
    return Verification(keep, dropped, usage=spent)
