"""One Anthropic Messages request that must answer with JSON matching a schema. Unmetered: callers meter.

Drafting, description reading and document review use it. Structured outputs accept a subset of JSON
Schema, so `api_schema` drops the constraints they reject; callers still validate what comes back.
"""
from __future__ import annotations

import json
import re

from . import llm_gate

MODEL = 'claude-sonnet-5-5'

# Constraints structured outputs reject. The caller's own validation (Pydantic or field checks) still applies them.
_DROPPED = {'minLength', 'maxLength', 'pattern', 'minimum', 'maximum', 'exclusiveMinimum', 'exclusiveMaximum',
            'multipleOf', 'maxItems', 'default', 'title'}
_DATA_URL = re.compile(r'data:(image/[a-z+.-]+);base64,(.+)', re.S)


class UnreadableJson(RuntimeError):
    """The model answered, and was billed, but gave no usable JSON (a refusal or a cut-off answer)."""

    def __init__(self, message: str, usage: dict):
        super().__init__(message)
        self.usage = usage


def api_schema(schema):
    """A copy with only what structured outputs accept, and every object closed."""
    if isinstance(schema, list):
        return [api_schema(item) for item in schema]
    if not isinstance(schema, dict):
        return schema
    out = {}
    for key, value in schema.items():
        if key in _DROPPED and not (key == 'title' and isinstance(value, dict)):
            continue
        if key == 'minItems' and value not in (0, 1):
            continue
        out[key] = api_schema(value) if key not in {'enum', 'const', 'required'} else value
    if out.get('type') == 'object' or 'properties' in out:
        out['additionalProperties'] = False
    return out


def _content(user) -> str | list[dict]:
    """Chat-style parts ({'type': 'text'} / {'type': 'image_url'}) as Messages content blocks."""
    if isinstance(user, str):
        return user
    blocks = []
    for part in user:
        if part.get('type') == 'text':
            blocks.append({'type': 'text', 'text': part['text']})
        elif part.get('type') == 'image_url':
            url = part['image_url']['url']
            m = _DATA_URL.fullmatch(url)
            source = ({'type': 'base64', 'media_type': m.group(1), 'data': m.group(2)} if m
                      else {'type': 'url', 'url': url})
            blocks.append({'type': 'image', 'source': source})
    return blocks


def call(system: str, user, schema: dict, *, model: str = MODEL, effort: str = 'low',
         max_output_tokens: int = 8000, timeout: float = 60) -> tuple[dict, dict]:
    """(payload, {'input_tokens', 'output_tokens'}). Raises the SDK's errors, or UnreadableJson."""
    import anthropic
    with anthropic.Anthropic(max_retries=0, timeout=timeout, **llm_gate.anthropic_client_options()) as client:
        response = client.messages.create(
            model=model, max_tokens=max_output_tokens, system=system,
            messages=[{'role': 'user', 'content': _content(user)}],
            output_config={'effort': effort, 'format': {'type': 'json_schema', 'schema': api_schema(schema)}})
    u = response.usage
    usage = {'input_tokens': (u.input_tokens or 0) + (u.cache_creation_input_tokens or 0)
             + (u.cache_read_input_tokens or 0), 'output_tokens': u.output_tokens or 0,
             'returned_model': response.model}
    if response.stop_reason in ('refusal', 'max_tokens'):
        raise UnreadableJson(f'AI answer ended with {response.stop_reason}', usage)
    text = next((b.text for b in response.content if b.type == 'text'), None)
    try:
        return json.loads(text), usage
    except (TypeError, ValueError) as error:
        raise UnreadableJson('AI returned no usable JSON', usage) from error
