"""Identify pipeline configuration: the interface the benchmark (WP-11/12) hands its winner through.

One frozen `IdentifyConfig` names every choice that changes results: screen, rerank, verifier,
pinned model ids, effort, shortlist sizes and card length. Its `config_hash` is recorded on
every result and must match the hash in calibration.json before any automatic commit is made,
so a threshold fitted on one pipeline is never applied to another.

Resolution order: defaults below -> JSON file (`BATATIS_IDENTIFY_CONFIG`, else
engine/identify/pipeline.json when present) -> `BATATIS_IDENTIFY_<FIELD>` environment overrides.
The default is Elephant's typed Decisions for every Division B article and the
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

from .screen import DECISIONS_MODEL, ELEPHANT_MODEL, JEV_MODEL
from .verify import VERIFIER_MODEL

HERE = Path(__file__).resolve().parent
PIPELINE_FILE = HERE / 'pipeline.json'
DIVISION_B_ARTICLES = 2080           # NBC(AE) 2023 2nd printing; asserted on every exhaustive model screen

SCREENS = ('elephant', 'decisions', 'jev', 'bm25', 'bm25_v3', 'shortlist')
RERANKS = ('elephant', 'decisions', 'jev', 'openai', 'none')
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
    screen: str = 'elephant'             # model screens judge all 2,080; lexical arms are not exhaustive
    screen_model: str = ELEPHANT_MODEL
    card_chars: int = 700                # screen and rerank card length
    rerank: str = 'elephant'
    rerank_model: str = ELEPHANT_MODEL
    rerank_n: int = 60
    verifier: str = 'openai'
    verifier_model: str = OPENAI_VERIFIER
    verifier_effort: str = 'medium'      # OpenAI reasoning_effort (verifier and rerank) or Anthropic output_config.effort
    verify_n: int = 15                   # rerank top-N the verifier reads in full text
    fallback: str = 'bm25'               # lexical ranking when the model path fails; commits nothing
    top_k: int = 10                      # article cards returned
    choices_k: int = 3                   # quoted choices offered
    question_style: str = 'shared'       # self is an explicit Elephant-only experiment
    shortlist_n: int = 60                # bounded TOC + keyword union; used only by screen='shortlist'
    shortlist_toc_n: int = 40

    def __post_init__(self):
        checks = [('screen', SCREENS), ('rerank', RERANKS), ('verifier', VERIFIERS), ('fallback', FALLBACKS),
                  ('verifier_effort', EFFORTS)]
        for name, allowed in checks:
            if getattr(self, name) not in allowed:
                raise ConfigError(f'{name} must be one of {", ".join(allowed)}')
        if self.question_style not in ('shared', 'self'):
            raise ConfigError('question_style must be shared or self')
        if self.question_style == 'self' and 'elephant' not in (self.screen, self.rerank):
            raise ConfigError('self question style requires an Elephant stage')
        if self.screen == 'shortlist':
            if self.screen_model != OPENAI_VERIFIER or self.verifier not in ('openai', 'none'):
                raise ConfigError('shortlist requires the pinned text screen and an openai or none verifier')
            if self.rerank not in ('elephant', 'none'):
                raise ConfigError('shortlist supports elephant or none rerank')
            if any(type(getattr(self, name)) is not int for name in ('shortlist_n', 'shortlist_toc_n')) \
                    or not 1 <= self.shortlist_toc_n <= self.shortlist_n <= 120:
                raise ConfigError('shortlist sizes must satisfy 1 <= shortlist_toc_n <= shortlist_n <= 120')
        if (self.verifier == 'openai' or self.rerank == 'openai' or self.screen == 'shortlist') \
                and self.verifier_effort not in OPENAI_EFFORTS:
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
        if (self.screen == 'elephant' and self.screen_model != ELEPHANT_MODEL) or (
                self.rerank == 'elephant' and self.rerank_model != ELEPHANT_MODEL):
            raise ConfigError('Elephant stages require the pinned free scoring model')
        for name in ('card_chars', 'rerank_n', 'verify_n', 'top_k', 'choices_k'):
            if getattr(self, name) < 1:
                raise ConfigError(f'{name} must be at least 1')
        if self.verify_n > self.rerank_n:
            raise ConfigError('verify_n cannot exceed rerank_n')

    @property
    def exhaustive(self) -> bool:
        """True when the screen judges every Division B article."""
        return self.screen in ('elephant', 'decisions', 'jev')

    def as_dict(self) -> dict:
        values = asdict(self)
        # Inactive options must not invalidate historical hashes or calibration.
        if self.question_style == 'shared':
            values.pop('question_style')
        if self.screen != 'shortlist':
            values.pop('shortlist_n')
            values.pop('shortlist_toc_n')
        return values

    @property
    def tentative(self) -> bool:
        return self.screen == 'shortlist' or self.question_style == 'self'

    @property
    def config_hash(self) -> str:
        values = self.as_dict()
        if 'elephant' in (self.screen, self.rerank):
            from .elephant_runtime import IDENTITY
            values['scoring_identity'] = IDENTITY
        if self.question_style == 'self':
            from .screen import SELF_QUESTION
            values['question_identity'] = SELF_QUESTION
        if self.screen == 'shortlist':
            from .shortlist import identity
            values['shortlist_identity'] = identity()
        blob = json.dumps(values, sort_keys=True, separators=(',', ':'))
        return hashlib.sha256(blob.encode()).hexdigest()[:16]

    def model_ids(self) -> dict[str, str | None]:
        return {'screen': self.screen_model if self.exhaustive or self.screen == 'shortlist' else None,
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
        data = json.loads(source.read_text(encoding='utf-8'))
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
            method = values.get(stage, 'elephant')
            pin = {'jev': JEV_MODEL, 'elephant': ELEPHANT_MODEL,
                   'decisions': DECISIONS_MODEL, 'openai': OPENAI_RERANK,
                   'shortlist': OPENAI_VERIFIER}.get(method)
            if pin is not None:
                values[f'{stage}_model'] = pin
    if 'verifier_model' not in values and values.get('verifier') == 'anthropic':
        values['verifier_model'] = ANTHROPIC_VERIFIER
    return IdentifyConfig(**values)
