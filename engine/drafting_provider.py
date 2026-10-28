"""One injectable JSON seam; hosted calls are metered."""
from __future__ import annotations

from dataclasses import dataclass
import os
from typing import Callable

from . import llm_gate
from .identify.providers import metered_openai_json, raw_openai_json

MODEL, EFFORT = 'gpt-6.1-sol', 'medium'
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
    if os.environ.get('BATATIS_PROVIDER') == 'fake' or not llm_gate.live_enabled('openai'):
        raise DraftingUnavailable('Drafting unavailable: a live, authorized AI connection is required.')
    metered = metered_openai_json(raw_openai_json, client_ip=client_ip)

    def call(name, system, user, schema):
        return metered(name, schema, system, user, model=MODEL, effort=EFFORT,
                       max_output_tokens=MAX_OUTPUT_TOKENS, timeout=120)
    return DraftingProvider(call, 'openai', MODEL, EFFORT)
