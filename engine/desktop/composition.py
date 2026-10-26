"""Desktop-only routing. A closed host never falls through to hosted or ambient providers."""
from __future__ import annotations

from dataclasses import dataclass

from . import bridge
from ..provider_routing import LOCAL_MODEL as MODEL, LOCAL_EFFORT as EFFORT, local_active as active


@dataclass(frozen=True)
class Profile:
    lease: str
    generation: str
    screening: bool
    billing: str


BILLING = {'off': 'none', 'chatgpt': 'subscription', 'claude': 'subscription', 'openai': 'api'}


def profile(slot: str = 'workflow') -> Profile:
    """The host's choice for one kind of work: 'workflow' (intake, review, code picks) or 'chat' (assistant)."""
    from .host_provider import private_call
    try:
        reply = private_call('provider.profile', {'slot': slot}, context=bridge.REQUEST_CONTEXT.get(), timeout=15)
        value = reply.get('value') if reply.get('ok') else None
        if (isinstance(value, dict) and isinstance(value.get('lease'), str) and value['lease']
                and value.get('generation') in BILLING
                and type(value.get('screening')) is bool and value.get('billing') in ('none', 'subscription', 'api')):
            expected = BILLING[value['generation']]
            if value['billing'] == expected:
                return Profile(value['lease'], value['generation'], value['screening'], expected)
    except (bridge.HostUnavailable, ValueError, TypeError):
        pass
    return Profile('', 'off', False, 'none')


def review_transport():
    from ..intake.review import GateClosed, MAX_OUTPUT_TOKENS
    from ..intake.model import GateClosed as IntakeClosed
    from .host_provider import host_transport
    selected = profile()
    if selected.generation == 'off':
        return None, 'off'
    transport = host_transport('document-review', model=MODEL, effort=EFFORT,
                               max_output_tokens=MAX_OUTPUT_TOKENS, lease=selected.lease)

    def call(system, user, schema, model, effort):
        if (model, effort) != (MODEL, EFFORT):
            raise GateClosed('desktop-profile')
        try:
            return transport(system, user, schema)
        except IntakeClosed as error:
            raise GateClosed(error.source) from None
    return call, 'live'
