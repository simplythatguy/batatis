"""Turn the chosen pipeline into the file the identify service reads: ``engine/identify/pipeline.json``.

WP-20 (branch ``feat/wp20-identify``) defines ``IdentifyConfig`` in ``engine/identify/config.py`` with these fields; the loader
reads ``engine/identify/pipeline.json`` and rejects unknown keys other than ``comment``, ``chosen_by`` and ``chosen_at``.
The mapping below writes exactly those fields. A pipeline the schema cannot express (precedent matching, fusion) raises
``NotRepresentable`` rather than being approximated: the schema would have to grow first.

``config_hash`` uses WP-20's algorithm (sha256 of the sorted-key compact JSON of the fields, first 16 hex characters) so the
memo can name the hash that ``calibration.json`` must carry once thresholds are fitted.
"""
from __future__ import annotations

import hashlib
import json

from .methods.base import Arm
from .arms import topo_order

FIELDS = ('screen', 'screen_model', 'card_chars', 'rerank', 'rerank_model', 'rerank_n', 'verifier', 'verifier_model',
          'verifier_effort', 'verify_n', 'fallback', 'top_k', 'choices_k')


class NotRepresentable(ValueError):
    pass


def config_hash(fields: dict) -> str:
    blob = json.dumps({k: fields[k] for k in FIELDS}, sort_keys=True, separators=(',', ':'))
    return hashlib.sha256(blob.encode()).hexdigest()[:16]


def pin_for(arms: dict[str, Arm], winner: str, *, fallback: str = 'bm25') -> dict:
    chain = [arms[n] for n in topo_order(arms, [winner])]
    cfg = {'screen': 'bm25', 'screen_model': 'jev-1.13.0', 'card_chars': 700, 'rerank': 'none', 'rerank_model': 'jev-1.13.0',
           'rerank_n': 60, 'verifier': 'none', 'verifier_model': 'gpt-6-luna', 'verifier_effort': 'medium', 'verify_n': 15,
           'fallback': fallback, 'top_k': 10, 'choices_k': 3}
    for a in chain:
        c = a.config()
        if a.kind == 'screen':
            cfg.update(screen='jev', screen_model=c['model'], card_chars=c['card_chars'])
        elif a.kind == 'rank' and a.name.startswith('R0'):
            cfg.update(screen='bm25')
        elif a.kind == 'rank' and a.name.startswith('R1'):
            cfg.update(screen='bm25_v3')
        elif a.kind == 'rerank' and 'provider' in c:
            cfg.update(rerank='jev', rerank_model=c['model'], rerank_n=c['n'])
        elif a.kind == 'rerank':
            cfg.update(rerank='openai', rerank_model=c['model'], rerank_n=c['n'])
        elif a.kind == 'verify':
            if c['article_text'] != 'full':
                raise NotRepresentable('the identify config always reads full article text')
            cfg.update(verifier='openai', verifier_model=c['model'], verifier_effort=c['reasoning_effort'], verify_n=c['shortlist_n'])
        else:
            raise NotRepresentable(f'{a.name} ({a.kind}) has no field in the identify pipeline config')
    return cfg


def pipeline_json(fields: dict, *, chosen_at: str, memo_sha: str) -> str:
    out = dict(fields)
    out['chosen_by'] = 'WP-12 benchmark (docs/accuracy/code-id-decision.md)'
    out['chosen_at'] = chosen_at
    out['comment'] = (f'config_hash {config_hash(fields)}; pinned by evals_dev.identify_bench from result rows (memo sha256 {memo_sha[:16]}). '
                      'Not calibrated: engine/identify/calibration.json must name this config_hash with status calibrated before '
                      'any automatic Part 9 commit.')
    return json.dumps(out, indent=2) + '\n'
