"""A document-review transport for DeepSeek V4.1 Flash (API name deepseek-flash), to compare with Luna.

Same prompt and same engine checks as the Luna review; only the provider changes. DeepSeek's API has a
JSON mode but no strict schema, so the schema goes into the instructions and the engine's checks apply
as usual. Responses are cached by request, and every call is priced in the run's ledger at DeepSeek's
list price for the hour it ran (peak: 01:00-04:00 and 06:00-10:00 UTC on weekdays).

    DPE_REVIEW_TRANSPORT=deepseek DPE_DEEPSEEK_EFFORT=max .venv/bin/python -m evals_dev.data_prompts run ...
"""
from __future__ import annotations

import json
import os
import time
from datetime import datetime, timezone

import httpx

from . import ledger

URL = 'https://api.deepseek.com/chat/completions'
MODEL = os.environ.get('DPE_DEEPSEEK_MODEL', 'deepseek-flash')
EFFORT = os.environ.get('DPE_DEEPSEEK_EFFORT', 'max')
MAX_TOKENS = 64_000
TIMEOUT = 900
# USD per 1M tokens: cache hit, cache miss, output; off-peak then peak (api-docs.deepseek.com, read 2026-10-25).
PRICES = {'deepseek-flash': ((0.003, 0.15, 0.6), (0.006, 0.3, 1.2)),
          'deepseek-v4-pro': ((0.022, 0.66, 1.98), (0.044, 1.32, 3.96))}


def _key() -> str:
    key = (os.environ.get('DEEPSEEK_API_KEY') or '').strip()
    if not key:
        raise RuntimeError('DEEPSEEK_API_KEY is not set')
    return key


def peak(now: datetime | None = None) -> bool:
    now = now or datetime.now(timezone.utc)
    return now.weekday() < 5 and (1 <= now.hour < 4 or 6 <= now.hour < 10)


def price(model: str, usage: dict, at_peak: bool) -> float:
    hit_p, miss_p, out_p = PRICES[model][1 if at_peak else 0]
    hit = int(usage.get('prompt_cache_hit_tokens') or 0)
    miss = int(usage.get('prompt_cache_miss_tokens') or max(0, int(usage.get('prompt_tokens') or 0) - hit))
    return (hit * hit_p + miss * miss_p + int(usage.get('completion_tokens') or 0) * out_p) / 1_000_000


def chat_json(model: str, effort: str, system: str, user: str, *, stage: str) -> tuple[dict, dict]:
    """One JSON-mode chat completion, cached by request and priced into the current ledger."""
    body = {'model': model, 'reasoning_effort': effort, 'max_tokens': MAX_TOKENS,
            'response_format': {'type': 'json_object'},
            'messages': [{'role': 'system', 'content': system}, {'role': 'user', 'content': user}]}
    key = ledger._key(URL, body)
    hit = ledger._load(key)
    if hit is None:
        started = time.monotonic()
        for attempt in range(4):
            try:
                with httpx.Client(timeout=TIMEOUT) as client:
                    response = client.post(URL, json=body, headers={'Authorization': 'Bearer ' + _key()})
                if response.status_code in (429, 500, 502, 503, 504) and attempt < 3:
                    time.sleep(5 * (attempt + 1))
                    continue
                response.raise_for_status()
                break
            except (httpx.ConnectError, httpx.ConnectTimeout, httpx.ReadError, httpx.RemoteProtocolError):
                if attempt == 3:
                    raise
                time.sleep(5 * (attempt + 1))
        data = response.json()
        hit = {'response': data, 'seconds': round(time.monotonic() - started, 3), 'peak': peak()}
        ledger._store(key, hit)
        from_cache = False
    else:
        from_cache = True
    data = hit['response']
    usage = data.get('usage') or {}
    book = ledger.CURRENT.get() or ledger.UNATTRIBUTED
    book.calls.append(ledger.Call(model, effort, stage, int(usage.get('prompt_tokens') or 0),
                                  int(usage.get('prompt_cache_hit_tokens') or 0),
                                  int(usage.get('completion_tokens') or 0),
                                  int((usage.get('completion_tokens_details') or {}).get('reasoning_tokens') or 0),
                                  price(model, usage, bool(hit.get('peak'))), from_cache, hit.get('seconds', 0.0)))
    content = data['choices'][0]['message'].get('content') or ''
    tokens = {'input_tokens': int(usage.get('prompt_tokens') or 0),
              'output_tokens': int(usage.get('completion_tokens') or 0)}
    return _object(content), tokens


class InvalidJson(ValueError):
    pass


def _object(content: str) -> dict:
    """The answer's JSON object; when it runs past one complete object, the first complete object."""
    try:
        value = json.loads(content)
    except json.JSONDecodeError:
        try:
            value, _ = json.JSONDecoder().raw_decode(content.strip())
        except json.JSONDecodeError as error:
            raise InvalidJson(str(error)) from error
        INVALID.append('recovered')
    if not isinstance(value, dict):
        raise InvalidJson('not an object')
    return value


INVALID: list[str] = []      # per process: answers that needed recovery (reported by the comparison)


def transport(system: str, user: str, schema: dict, model: str, effort: str) -> tuple[dict, dict]:
    """engine.intake.review transport signature; `model`/`effort` name the Luna slot DeepSeek replaces."""
    instructions = (system + '\n\nAnswer with one JSON object only, matching this JSON Schema exactly (every listed '
                    'key present, no other keys):\n' + json.dumps(schema, separators=(',', ':')))
    try:
        return chat_json(MODEL, EFFORT, instructions, user, stage='document_review')
    except InvalidJson:
        INVALID.append('retried')       # one fresh attempt; a second invalid answer fails the review
        return chat_json(MODEL, EFFORT, instructions + '\n', user, stage='document_review')
