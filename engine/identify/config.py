"""Commit policy and model pins for code identification.

The 0.75 probability threshold and the cap of 3 suggestions are placeholder_uncalibrated.
They set the identify `suggested` hint. They do not accept an article onto a case.
A later file at evals_dev/human_key/calibration.json replaces them only when it says
`"status": "calibrated"`. This module does not create that directory or invent its contents.

When a provider key is present, the HTTP default is pipeline (c): BM25 top 60, provider
rerank, provider verifier on the full article text. `BATATIS_SCREEN=llm` switches the
first stage to a model screen. `BATATIS_RERANK=jev` keeps Jev as the reranker.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

COMMIT_THRESHOLD = 0.75
MAX_COMMITS = 3
COMMIT_PARTS = {9}
POLICY_STATUS = 'placeholder_uncalibrated'
CALIBRATION_SET = 'evals_dev/human_key/'
CALIBRATION_FILE = ROOT / 'evals_dev' / 'human_key' / 'calibration.json'

TOP_K = 10
RERANK_N = 60
VERIFY_N = 15
QUESTION_K = 5

DEFAULT_PIPELINE = 'c'
# Dated snapshots, not the floating aliases. OpenAI's model pages list these
# default snapshots: gpt-4.1-mini-2025-04-14 and gpt-4.1-2025-04-14
# (platform.openai.com/docs/models/gpt-4.1-mini and .../gpt-4.1).
# BATATIS_SCREEN_MODEL, BATATIS_RERANK_MODEL, and BATATIS_VERIFY_MODEL override them.
SCREEN_MODEL = os.environ.get('BATATIS_SCREEN_MODEL', 'gpt-4.1-mini-2025-04-14')
RERANK_MODEL = os.environ.get('BATATIS_RERANK_MODEL', 'gpt-4.1-mini-2025-04-14')
VERIFY_MODEL_OPENAI = os.environ.get('BATATIS_VERIFY_MODEL', 'gpt-4.1-2025-04-14')
VERIFY_MODEL_ANTHROPIC = 'claude-sonnet-5-5'

# USD per 1M tokens, input then output. Estimates for the benchmark printer only.
# Alias keys stay so an env override of gpt-4.1 or gpt-4.1-mini still prices.
PRICES = {
    'gpt-4.1': (2.0, 8.0),
    'gpt-4.1-2025-04-14': (2.0, 8.0),
    'gpt-4.1-mini': (0.40, 1.60),
    'gpt-4.1-mini-2025-04-14': (0.40, 1.60),
}


def provider() -> str:
    return os.environ.get('BATATIS_LLM_PROVIDER', 'openai').strip().lower()


def screen_mode() -> str:
    return os.environ.get('BATATIS_SCREEN', 'bm25').strip().lower()


def rerank_mode() -> str:
    return os.environ.get('BATATIS_RERANK', 'llm').strip().lower()


def provider_key(name: str) -> str | None:
    if name == 'openai':
        return (os.environ.get('OPENAI_API_KEY') or '').strip() or None
    if name == 'anthropic':
        return (os.environ.get('ANTHROPIC_API_KEY') or '').strip() or None
    if name == 'jev':
        for var in ('JEV_API_KEY', 'TYPESAFE_API_KEY', 'OPENROUTER_API_KEY'):
            val = (os.environ.get(var) or '').strip()
            if val:
                return val
    return None


def has_live_model() -> bool:
    """True only for a key in the environment. Does not touch the OS keychain."""
    if rerank_mode() == 'jev' and provider_key('jev'):
        return True
    return bool(provider_key(provider()))


def calibration_override() -> dict | None:
    path = CALIBRATION_FILE
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(data, dict) or data.get('status') != 'calibrated':
        return None
    return data


def commit_policy() -> dict:
    over = calibration_override() or {}
    return {
        'threshold': float(over.get('threshold', COMMIT_THRESHOLD)),
        'max_commits': int(over.get('max_commits', MAX_COMMITS)),
        'parts': sorted(COMMIT_PARTS),
        'status': 'calibrated' if over else POLICY_STATUS,
        'calibration_set': CALIBRATION_SET,
    }


def estimate_usd(model: str | None, input_tokens: int, output_tokens: int) -> float | None:
    if not model or model not in PRICES:
        return None
    inn, out = PRICES[model]
    return (input_tokens * inn + output_tokens * out) / 1_000_000
