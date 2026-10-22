"""Identify pipeline configuration: the interface the benchmark (WP-11/12) hands its winner through.

One frozen `IdentifyConfig` names every choice that changes results: screen, rerank, verifier,
pinned model ids, effort, shortlist sizes and card length. Its `config_hash` is recorded on
every result and must match the hash in calibration.json before any automatic commit is made,
so a threshold fitted on one pipeline is never applied to another.

Resolution order: defaults below -> JSON file (`BATATIS_IDENTIFY_CONFIG`, else
engine/identify/pipeline.json when present) -> `BATATIS_IDENTIFY_<FIELD>` environment overrides.
The temporary 2026-10-22 default is OpenAI Decisions for every Division B article and the
top-60 rerank, followed by the existing OpenAI full-text verifier on the top 15. Explicit Jev
configuration remains available. These scoring configurations have different hashes. The Anthropic
verifier adapter (ClaudeVerifier, claude-sonnet-5-5) is kept but off unless configured.
Haiku models are refused.
"""
from __future__ import annotations

import hashlib
import json
import os
from dataclasses import asdict, dataclass, fields
from pathlib import Path

from .screen import DECISIONS_MODEL, JEV_MODEL
from .verify import VERIFIER_MODEL

HERE = Path(__file__).resolve().parent
PIPELINE_FILE = HERE / 'pipeline.json'
DIVISION_B_ARTICLES = 2080           # NBC(AE) 2023 2nd printing; asserted on every exhaustive model screen

SCREENS = ('decisions', 'jev', 'bm25', 'bm25_v3')
RERANKS = ('decisions', 'jev', 'openai', 'none')
VERIFIERS = ('anthropic', 'openai', 'none')
FALLBACKS = ('bm25', 'bm25_v3')
EFFORTS = ('low', 'medium', 'high', 'xhigh', 'max')
OPENAI_EFFORTS = ('low', 'medium', 'high')
# GPT Luna, confirmed against the account's model list (2026-10-21). Reasoning effort medium, standard
# service tier (no service_tier is sent). Priced in engine.llm_gate.PRICES.
OPENAI_VERIFIER = 'gpt-6-luna'
OPENAI_RERANK = 'gpt-6-luna'
ANTHROPIC_VERIFIER = VERIFIER_MODEL           # off by default; only when verifier='anthropic'


class ConfigError(ValueError):
    pass


@dataclass(frozen=True)
class IdentifyConfig:
    screen: str = 'decisions'            # decisions/jev judge all 2,080; lexical arms are not exhaustive
    screen_model: str = DECISIONS_MODEL
    card_chars: int = 700                # screen and rerank card length
    rerank: str = 'decisions'
    rerank_model: str = DECISIONS_MODEL
    rerank_n: int = 60
    verifier: str = 'openai'
    verifier_model: str = OPENAI_VERIFIER
    verifier_effort: str = 'medium'      # OpenAI reasoning_effort (verifier and rerank) or Anthropic output_config.effort
    verify_n: int = 15                   # rerank top-N the verifier reads in full text
    fallback: str = 'bm25'               # lexical ranking when the model path fails; commits nothing
    top_k: int = 10                      # article cards returned
    choices_k: int = 3                   # quoted choices offered

    def __post_init__(self):
        checks = [('screen', SCREENS), ('rerank', RERANKS), ('verifier', VERIFIERS), ('fallback', FALLBACKS),
                  ('verifier_effort', EFFORTS)]
        for name, allowed in checks:
            if getattr(self, name) not in allowed:
                raise ConfigError(f'{name} must be one of {", ".join(allowed)}')
        if (self.verifier == 'openai' or self.rerank == 'openai') and self.verifier_effort not in OPENAI_EFFORTS:
            raise ConfigError(f'OpenAI reasoning effort must be one of {", ".join(OPENAI_EFFORTS)}')
        for name in ('screen_model', 'rerank_model', 'verifier_model'):
            if 'haiku' in getattr(self, name).lower():
                raise ConfigError('Haiku models are not used')
        if (self.screen == 'jev' and self.screen_model != JEV_MODEL) or (
                self.rerank == 'jev' and self.rerank_model != JEV_MODEL):
            raise ConfigError(f'Jev stages use the pinned {JEV_MODEL}')
        if (self.screen == 'decisions' and self.screen_model != DECISIONS_MODEL) or (
                self.rerank == 'decisions' and self.rerank_model != DECISIONS_MODEL):
            raise ConfigError('Decisions stages require the pinned scoring model')
        for name in ('card_chars', 'rerank_n', 'verify_n', 'top_k', 'choices_k'):
            if getattr(self, name) < 1:
                raise ConfigError(f'{name} must be at least 1')
        if self.verify_n > self.rerank_n:
            raise ConfigError('verify_n cannot exceed rerank_n')

    @property
    def exhaustive(self) -> bool:
        """True when the screen judges every Division B article."""
        return self.screen in ('decisions', 'jev')

    def as_dict(self) -> dict:
        return asdict(self)

    @property
    def config_hash(self) -> str:
        blob = json.dumps(self.as_dict(), sort_keys=True, separators=(',', ':'))
        return hashlib.sha256(blob.encode()).hexdigest()[:16]

    def model_ids(self) -> dict[str, str | None]:
        return {'screen': self.screen_model if self.exhaustive else None,
                'rerank': self.rerank_model if self.rerank != 'none' else None,
                'verifier': self.verifier_model if self.verifier != 'none' else None}


def _coerce(name: str, raw):
    kind = {f.name: f.type for f in fields(IdentifyConfig)}[name]
    if kind == 'int':
        try:
            return int(raw)
        except (TypeError, ValueError):
            raise ConfigError(f'{name} must be an integer') from None
    return str(raw).strip()


def load_config(path: Path | str | None = None, env: dict | None = None) -> IdentifyConfig:
    env = os.environ if env is None else env
    names = {f.name for f in fields(IdentifyConfig)}
    values: dict = {}
    source = Path(path) if path else (Path(env['BATATIS_IDENTIFY_CONFIG']) if env.get('BATATIS_IDENTIFY_CONFIG')
                                      else PIPELINE_FILE)
    if source.is_file():
        data = json.loads(source.read_text())
        unknown = set(data) - names - {'comment', 'chosen_by', 'chosen_at'}
        if unknown:
            raise ConfigError(f'unknown identify config keys: {", ".join(sorted(unknown))}')
        values.update({k: _coerce(k, v) for k, v in data.items() if k in names})
    elif path or env.get('BATATIS_IDENTIFY_CONFIG'):
        raise ConfigError('identify config file not found')
    for name in names:
        raw = env.get('BATATIS_IDENTIFY_' + name.upper())
        if raw not in (None, ''):
            values[name] = _coerce(name, raw)
    # Infer pins only when omitted, including for the explicit switch back to Jev. Validate
    # explicit pins before constructing transports; a stale key never selects a provider.
    for stage in ('screen', 'rerank'):
        if f'{stage}_model' not in values:
            method = values.get(stage, 'decisions')
            if method in ('jev', 'decisions', 'openai'):
                values[f'{stage}_model'] = JEV_MODEL if method == 'jev' else DECISIONS_MODEL
    if 'verifier_model' not in values and values.get('verifier') == 'anthropic':
        values['verifier_model'] = ANTHROPIC_VERIFIER
    return IdentifyConfig(**values)
