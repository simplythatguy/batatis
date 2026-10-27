"""One injectable JSON seam; hosted calls are metered, desktop calls use its leased workflow slot."""
from __future__ import annotations

from dataclasses import dataclass
import os
from typing import Callable

from . import llm_gate, provider_routing
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
    if provider_routing.local_active():
        selected = provider_routing.local_profile('workflow')
        if selected.generation == 'off' or not selected.lease:
            raise DraftingUnavailable('Drafting unavailable: the desktop workflow connection is off.')
        # The current host supports four task names and a pinned logical profile. Document-review is
        # its general source-backed JSON workflow slot; do not invent an unsupported host task/model.
        transport = provider_routing.local_transport('document-review', model=provider_routing.LOCAL_MODEL,
            effort=provider_routing.LOCAL_EFFORT, max_output_tokens=MAX_OUTPUT_TOKENS, lease=selected.lease)
        if transport is None:
            raise DraftingUnavailable('Drafting unavailable: no desktop workflow transport.')

        def call(name, system, user, schema):
            return transport(system, user, schema)
        return DraftingProvider(call, 'desktop-workflow:' + selected.generation,
                                provider_routing.LOCAL_MODEL, provider_routing.LOCAL_EFFORT)
    if os.environ.get('BATATIS_PROVIDER') == 'fake' or not llm_gate.live_enabled('openai'):
        raise DraftingUnavailable('Drafting unavailable: a live, authorized AI connection is required.')
    metered = metered_openai_json(raw_openai_json, client_ip=client_ip)

    def call(name, system, user, schema):
        return metered(name, schema, system, user, model=MODEL, effort=EFFORT,
                       max_output_tokens=MAX_OUTPUT_TOKENS, timeout=120)
    return DraftingProvider(call, 'openai', MODEL, EFFORT)
