"""Cached identify payloads for the offline demo.

A hit is the exact case id, or the SHA-256 of the normalized description:
Unicode NFC, stripped, with internal whitespace collapsed. Answers are applied
after a hit and are not part of the key. The cache does not call a model.
"""
from __future__ import annotations

import copy
import hashlib
import json
import re
import unicodedata
from pathlib import Path

from engine.identify.config import commit_policy
from engine.identify.departure import assess_variance, detect_redirect
from engine.identify.questions import generate_questions

_PATH = Path(__file__).with_name('demo_cache.json')
_CACHE: dict | None = None
DEMO_CASE_IDS = (
    'a-manufacturer-nailbase-sheathing',
    'b-contractor-firestop-nonconformance',
    'c-homebuilder-infill-house',
)
OFFLINE_MISS = 'offline: no cached result for this case'


def normalize_case_input(text: str) -> str:
    flat = unicodedata.normalize('NFC', text or '')
    return re.sub(r'\s+', ' ', flat).strip()


def cache_key(text: str) -> str:
    return hashlib.sha256(normalize_case_input(text).encode('utf-8')).hexdigest()


def _load() -> dict:
    """Index by description hash and by exact case id. A description is not a substring match."""
    global _CACHE
    if _CACHE is None:
        rows = json.loads(_PATH.read_text())
        by_hash: dict[str, dict] = {}
        by_id: dict[str, dict] = {}
        for row in rows:
            by_hash[cache_key(row['description'])] = row
            by_id[normalize_case_input(row['id'])] = row
        _CACHE = {'hash': by_hash, 'id': by_id}
    return _CACHE


def reset_cache() -> None:
    """Drop the in-process index. Tests and the build script call this after rewriting the file."""
    global _CACHE
    _CACHE = None


def offline_miss() -> dict:
    """Empty identify payload. No articles and no citations."""
    return {
        'source': 'offline-miss',
        'message': OFFLINE_MISS,
        'articles': [],
        'section_c': [],
        'benchmark': {
            'identified': False,
            'role': 'benchmark_acceptable_solution',
            'explanation': OFFLINE_MISS,
            'quote': None,
            'citation': None,
            'section_c': [],
        },
        'questions': [],
        'open_questions': [],
        'mode': 'offline',
        'persisted': False,
        'cached': False,
        'model_ids': {'screen': None, 'rerank': None, 'verifier': None, 'invoked': False},
    }


def match_demo(prose: str, facts=None) -> dict | None:
    index = _load()
    normalized = normalize_case_input(prose)
    row = index['hash'].get(cache_key(prose)) or index['id'].get(normalized)
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
            article['suggested'] = False
            article.pop('committed', None)
    payload['commit_policy'] = policy
    status = policy['status']
    for article in payload['articles']:
        article['confidence']['calibration'] = status
    confidence = (payload.get('benchmark') or {}).get('confidence')
    if confidence is not None:
        confidence['calibration'] = status
    payload['cached'] = True
    payload['persisted'] = False
    payload['mode'] = 'cached_demo'
    payload['source'] = 'cache'
    return payload
