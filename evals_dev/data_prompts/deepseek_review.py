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
from dataclasses import asdict
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
PRICING_VERSION = 'deepseek-local-2026-10-25'
RETRY_HTTP = (429, 500, 502, 503, 504)
RETRY_ERRORS = (httpx.ConnectError, httpx.ConnectTimeout, httpx.ReadError, httpx.ReadTimeout,
                httpx.RemoteProtocolError, httpx.WriteError, httpx.PoolTimeout)


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
    """Cache a request's whole attempt cost; append a durable record around every dispatch."""
    if model not in PRICES:
        raise ValueError('DeepSeek model has no supported local price table')
    body = {'model': model, 'reasoning_effort': effort, 'max_tokens': MAX_TOKENS,
            'response_format': {'type': 'json_object'},
            'messages': [{'role': 'system', 'content': system}, {'role': 'user', 'content': user}]}
    key = ledger._key(URL, body)
    hit = ledger._load(key) if os.environ.get('DPE_HTTP_CACHE', 'read') != 'refresh' else None
    book = ledger.CURRENT.get() or ledger.UNATTRIBUTED
    if hit is not None:
        calls = hit.get('attempt_calls')
        if calls is not None:
            ledger.replay(calls, book)
            cost_status = 'unknown' if any(c['usd'] is None for c in calls) else 'priced'
            usd = None if cost_status == 'unknown' else sum(c['usd'] for c in calls)
        else:
            # Old responses did not freeze their prices/attempts. Keep them readable, never relabel
            # them as newly verified or assume that the final response was the whole request cost.
            usage = _usage(hit['response'])
            book.calls.append(_call(model, effort, stage, usage, None, True, hit.get('seconds', 0.0), key,
                                    'legacy_unverified'))
            cost_status, usd = 'legacy_unverified', None
        ledger.attempt_event('cache_hit', request_hash=key, stage=stage, model=model, effort=effort,
                             status='cache_hit', dispatched=False, usd=usd, cost_status=cost_status)
        data = hit['response']
        value = _completion(data, strict=stage == 'judge')
        usage = _usage(data)
        return value, _tokens(usage)

    headers = {'Authorization': 'Bearer ' + _key()}
    request_calls = []
    for attempt in range(4):
        at_peak = peak()
        started = time.monotonic()
        attempt_id = ledger.attempt_event('attempt_started', request_hash=key, stage=stage, model=model,
                                          effort=effort, status='dispatching', dispatched=True,
                                          usd=None, cost_status='unknown', attempt=attempt + 1)
        response, data, usage, usd = None, None, {}, None
        recovered = False
        status = 'transport_error'
        retry = False
        try:
            with httpx.Client(timeout=TIMEOUT) as client:
                response = client.post(URL, json=body, headers=headers)
            try:
                data = response.json()
            except ValueError:
                status = 'invalid_response_json'
                response.raise_for_status()
                raise InvalidJson('response is not JSON') from None
            usage = _usage(data)
            if all(k in usage for k in ('prompt_tokens', 'completion_tokens')):
                usd = price(model, usage, at_peak)
            status = 'http_error'
            response.raise_for_status()
            status = 'invalid_json'
            before_recovery = len(INVALID)
            value = _completion(data, strict=stage == 'judge')
            recovered = len(INVALID) != before_recovery
            status = 'succeeded'
        except httpx.HTTPStatusError:
            status = 'http_error'
            retry = response.status_code in RETRY_HTTP and attempt < 3
            if not retry:
                raise
        except RETRY_ERRORS:
            retry = attempt < 3
            if not retry:
                raise
        except (KeyError, IndexError, TypeError) as error:
            status = 'invalid_json'
            raise InvalidJson('missing or invalid completion shape') from error
        finally:
            seconds = round(time.monotonic() - started, 3)
            call = _call(model, effort, stage, usage, usd, False, seconds, key, status)
            book.calls.append(call)
            request_calls.append(asdict(call))
            ledger.attempt_event('attempt_finished', attempt_id=attempt_id, request_hash=key, stage=stage,
                                 model=model, effort=effort, status=status, dispatched=True,
                                 http_status=response.status_code if response is not None else None,
                                 seconds=seconds, usage=usage, usd=usd,
                                 json_recovered=recovered,
                                 cost_status='priced' if usd is not None else 'unknown',
                                 pricing_version=PRICING_VERSION, peak=at_peak)
            if status in ('succeeded', 'invalid_json') and data is not None:
                ledger._store(key, {'response': data, 'seconds': sum(c['seconds'] for c in request_calls),
                                    'peak': at_peak, 'pricing_version': PRICING_VERSION,
                                    'attempt_calls': request_calls})
        if not retry:
            return value, _tokens(usage)
        time.sleep(5 * (attempt + 1))
    raise RuntimeError('DeepSeek request failed')


def _usage(data) -> dict:
    """Keep only numeric token counts, never provider text, in the durable attempt ledger."""
    raw = data.get('usage') if isinstance(data, dict) else None
    if not isinstance(raw, dict):
        return {}
    out = {k: raw[k] for k in ('prompt_tokens', 'completion_tokens', 'prompt_cache_hit_tokens',
                                'prompt_cache_miss_tokens') if type(raw.get(k)) is int and raw[k] >= 0}
    details = raw.get('completion_tokens_details')
    if isinstance(details, dict) and type(details.get('reasoning_tokens')) is int and details['reasoning_tokens'] >= 0:
        out['completion_tokens_details'] = {'reasoning_tokens': details['reasoning_tokens']}
    return out


def _tokens(usage: dict) -> dict:
    return {'input_tokens': usage.get('prompt_tokens', 0), 'output_tokens': usage.get('completion_tokens', 0)}


def _completion(data, *, strict=False) -> dict:
    try:
        choice = data['choices'][0]
        content = choice['message'].get('content') or ''
        if choice.get('finish_reason') not in (None, 'stop'):
            raise InvalidJson('completion did not finish')
        if not strict:
            return _object(content)
        try:
            value = json.loads(content)
        except ValueError as error:
            raise InvalidJson('judge completion is not a complete JSON object') from error
        if not isinstance(value, dict):
            raise InvalidJson('judge completion is not an object')
        return value
    except (KeyError, IndexError, TypeError) as error:
        raise InvalidJson('missing or invalid completion shape') from error


def _call(model, effort, stage, usage, usd, from_cache, seconds, request_hash, status) -> ledger.Call:
    return ledger.Call(model, effort, stage, usage.get('prompt_tokens', 0), usage.get('prompt_cache_hit_tokens', 0),
                       usage.get('completion_tokens', 0),
                       (usage.get('completion_tokens_details') or {}).get('reasoning_tokens', 0),
                       usd, from_cache, seconds, request_hash, status)


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
