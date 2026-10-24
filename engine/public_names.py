"""The words a client may read about how Batatis works.

The product owner does not want users to learn which third-party services sit behind Batatis. Provider names,
model pins, credentials and environment variable names stay on the server and in its logs. What a response, a
stored result, a stage event or the schema says about the scoring and verification stages goes through here.

Every function is idempotent: neutral input comes back unchanged. A result stored before this existed is cleaned
when it loads, and the next write stores the neutral form. engine/tests/test_no_provider_names_exposed.py holds
every route to it.
"""
from __future__ import annotations

import re

from .relevance_models import DECISIONS_PUBLIC_MODEL, ELEPHANT_PUBLIC_MODEL, PUBLIC_MODEL

# Private: model pin -> the opaque version a client sees. A pin that is not listed reads as CUSTOM.
MODEL_VERSIONS = {'jev-1.13.0': PUBLIC_MODEL, 'gpt-6-luna': 'verifier-1', 'claude-sonnet-5-5': 'verifier-2',
                  'baseten/elephant-1:free': ELEPHANT_PUBLIC_MODEL,
                  'baseten/elephant-1-20261021': ELEPHANT_PUBLIC_MODEL}
CUSTOM = 'custom'
MODEL = 'model'
# Methods that are a third-party service. The keyword arms (bm25, bm25_v3) and 'none' are not.
PROVIDER_METHODS = frozenset({'jev', 'openai', 'anthropic', 'decisions', 'elephant'})
# Spend is shown by what it paid for, not by who was paid.
SPEND_ROLES = {'jev': 'scoring', 'openai_decisions': 'scoring', 'elephant': 'scoring',
               'openai': 'verification', 'anthropic': 'verification'}
UNAVAILABLE = 'scoring unavailable'
VERIFIER_UNAVAILABLE = 'failed: scoring unavailable'
GENERIC_LABEL = {
    'live': 'Articles were scored, re-checked and read in full.',
    'fake': 'Articles were scored, re-checked and read in full. Offline fake providers: for testing only, not a measurement.',
    'bm25_fallback': 'Ranked by keyword search because scoring was unavailable. Nothing is committed.',
}
# A provider, a model, a credential or an environment variable that names one.
PROVIDER_TEXT = re.compile(r'jev|typesafe|openai|anthropic|claude|gpt|luna|elephant|baseten|openrouter|BATATIS_[A-Z_]+|[A-Z][A-Z_]*_API_KEY', re.I)


def names_a_provider(text: str | None) -> bool:
    return bool(text) and PROVIDER_TEXT.search(text) is not None


def public_method(method):
    """A third-party service reads as 'model'; the keyword methods and 'none' are kept."""
    return MODEL if method in PROVIDER_METHODS else method


def public_model_id(pin: str | None) -> str | None:
    """The opaque version for a model pin. Unknown pins read as CUSTOM; an id that is already neutral is kept."""
    if pin is None:
        return None
    if pin in MODEL_VERSIONS:
        return MODEL_VERSIONS[pin]
    return pin if pin in {CUSTOM, DECISIONS_PUBLIC_MODEL} or pin in MODEL_VERSIONS.values() else CUSTOM


def public_stage_model(method: str, pin: str | None) -> str | None:
    """Scoring and quote verification using the same private pin are distinct product versions."""
    return DECISIONS_PUBLIC_MODEL if method == 'decisions' and pin == 'gpt-6-luna' else public_model_id(pin)


def public_ranker(ranker: str) -> str:
    return re.sub(r'\b(?:jev|openai|anthropic|decisions|elephant)\b', MODEL, ranker, flags=re.I)


def public_text(text: str | None, instead: str) -> str | None:
    """`text` unless it names a provider, a model or a credential. Then `instead`."""
    return instead if names_a_provider(text) else text


def public_label(label: str, mode: str | None) -> str:
    """The sentence saying what ran. One that names a provider is replaced by the generic sentence for its mode."""
    return GENERIC_LABEL.get(mode, GENERIC_LABEL['live']) if names_a_provider(label) else label


def public_config(config: dict) -> dict:
    """The run's configuration with services read as 'model' and pins as opaque versions. Unused stages hold None."""
    out = dict(config)
    for stage in ('screen', 'rerank', 'verifier'):
        method = out.get(stage)
        if stage in out:
            out[stage] = public_method(method)
        if f'{stage}_model' in out:
            used = method in PROVIDER_METHODS or method in (MODEL, 'shortlist')
            out[f'{stage}_model'] = public_stage_model(method, out[f'{stage}_model']) if used else None
    return out


def public_spend(spend: dict) -> dict:
    """Spend keyed by role. Figures for services with the same role are added."""
    out: dict[str, dict] = {}
    for key, figures in spend.items():
        role = SPEND_ROLES.get(key) or ('other' if names_a_provider(key) else key)
        slot = out.setdefault(role, {})
        for name, value in (figures.items() if isinstance(figures, dict) else ()):
            slot[name] = round(slot.get(name, 0) + value, 6) if isinstance(value, (int, float)) else value
    return out


def public_event(payload: dict) -> dict:
    """A stage event as a client reads it."""
    return {**payload, 'method': public_method(payload['method'])} if 'method' in payload else payload
