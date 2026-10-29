"""One injectable JSON seam; hosted calls are metered."""
from __future__ import annotations

from dataclasses import dataclass
import json
import os
from typing import Callable

from . import anthropic_json, llm_gate
from .identify.providers import estimate_tokens, metered

MODEL, EFFORT = anthropic_json.MODEL, 'medium'
MAX_OUTPUT_TOKENS = 14000
JsonCall = Callable[[str, str, str, dict], tuple[dict, dict]]


class DraftingUnavailable(RuntimeError):
    pass


@dataclass(frozen=True)
class DraftingProvider:
    call: JsonCall
    provider: str
    model: str
    effort: str


def configured_provider(client_ip: str | None = None) -> DraftingProvider:
    if os.environ.get('BATATIS_PROVIDER') == 'fake' or not llm_gate.live_enabled('anthropic'):
        raise DraftingUnavailable('Drafting unavailable: a live, authorized AI connection is required.')

    def call(name, system, user, schema):
        with metered('anthropic', MODEL, estimate_tokens(system + user + json.dumps(schema)), MAX_OUTPUT_TOKENS,
                     client_ip=client_ip) as settle:
            try:
                payload, usage = anthropic_json.call(system, user, schema, model=MODEL, effort=EFFORT,
                                                     max_output_tokens=MAX_OUTPUT_TOKENS, timeout=120)
            except anthropic_json.UnreadableJson as error:     # billed: settle the real usage, then fail the call
                settle(error.usage['input_tokens'], error.usage['output_tokens'])
                raise
            settle(usage['input_tokens'], usage['output_tokens'])
            return payload, usage
    return DraftingProvider(call, 'anthropic', MODEL, EFFORT)
