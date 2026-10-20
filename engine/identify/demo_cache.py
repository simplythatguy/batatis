"""Cached identify payloads for three demo descriptions.

Quotes in the cache file are short codedb excerpts. A match is the applicant's
description after whitespace is collapsed. The cache does not call a model.
"""
from __future__ import annotations

import copy
import json
import re
from pathlib import Path

from engine.identify.config import commit_policy
from engine.identify.departure import assess_variance, detect_redirect
from engine.identify.questions import generate_questions

_PATH = Path(__file__).with_name('demo_cache.json')
_CACHE: dict[str, dict] | None = None


def _norm(text: str) -> str:
    return re.sub(r'\s+', ' ', text or '').strip()


def _load() -> dict[str, dict]:
    global _CACHE
    if _CACHE is None:
        rows = json.loads(_PATH.read_text())
        _CACHE = {_norm(row['description']): row for row in rows}
    return _CACHE


def match_demo(prose: str, facts=None) -> dict | None:
    row = _load().get(_norm(prose))
    if row is None:
        return None
    payload = copy.deepcopy(row['payload'])
    questions = generate_questions(prose, row['candidates'], facts)
    kind, explanation = assess_variance(prose, facts)
    redirect = detect_redirect(prose)
    policy = commit_policy()
    payload['questions'] = [q['text'] for q in questions]
    payload['open_questions'] = questions
    payload['variance_needed'] = kind
    payload['variance_explanation'] = explanation
    payload['redirect_to'] = redirect
    if redirect:
        payload['intake_action'] = 'redirect'
        for article in payload['articles']:
            article['committed'] = False
    payload['commit_policy'] = policy
    status = policy['status']
    for article in payload['articles']:
        article['confidence']['calibration'] = status
    confidence = (payload.get('benchmark') or {}).get('confidence')
    if confidence is not None:
        confidence['calibration'] = status
    payload['cached'] = True
    payload['persisted'] = False
    payload['mode'] = 'cached'
    return payload
