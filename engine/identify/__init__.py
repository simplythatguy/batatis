"""Code identification: which Division B articles govern a described situation.

The configured provider screens every Division B article in batches, then reranks the top N.
The default is Elephant; Decisions and Jev remain explicit options. Historical benchmark results
apply to their measured configuration only. This module returns scores and private provenance;
the API/pipeline maps them to neutral versions. Nothing here commits an article.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field, replace
from pathlib import Path

from .corpus import articles, bm25_rank
from .screen import JEV_MODEL, Judge


@dataclass
class Identification:
    ranked: list[tuple[str, float]]        # rerank order: (article id, rerank probability)
    screen: dict[str, float]               # exhaustive screen probability for every article
    usage: dict
    screen_seconds: float
    rerank_seconds: float
    model: str
    config_hash: str | None = None
    model_ids: dict[str, str | None] = field(default_factory=dict)
    methods: dict[str, str] = field(default_factory=dict)


def identify(query: str, db_path: Path | str, judge: Judge | None = None, *, rerank_n: int | None = None,
             parts: set[int] | None = None) -> Identification:
    """Exhaustive scoring (optionally only `parts`) and configured rerank, without automatic commits."""
    from .config import DIVISION_B_ARTICLES, load_config
    from .providers import scoring_ask, transports
    config = load_config()
    tp = None
    if judge is None:
        if not config.exhaustive:
            raise ValueError('relevance requires an exhaustive scoring configuration')
        tp = transports(scoring={config.screen, config.rerank})
        judge = Judge(scoring_ask(tp, config.screen), chars=config.card_chars,
                      model=config.screen_model, method=config.screen,
                      question_style=config.question_style if config.screen == 'elephant' else 'shared')
    elif judge.config is not None:
        config = judge.config
        tp = judge.transports
    else:
        config = replace(config, screen=judge.method, screen_model=judge.model,
                         rerank=judge.method, rerank_model=judge.model, card_chars=judge.chars,
                         question_style=judge.question_style)
    n = rerank_n if rerank_n is not None else config.rerank_n
    if n != config.rerank_n:
        config = replace(config, rerank_n=n, verify_n=min(config.verify_n, n))
    arts = articles(Path(db_path))
    ids = [a for a, v in arts.items() if parts is None or v['part'] in parts]
    t0 = time.monotonic()
    screen = judge.judge(query, arts, ids)
    if (parts is None and len(ids) != DIVISION_B_ARTICLES) or set(screen) != set(ids):
        raise RuntimeError('exhaustive scoring did not cover every Division B article')
    t1 = time.monotonic()
    top = sorted(ids, key=lambda a: -screen[a])[:n]
    rerank_requests_before = judge.usage.requests
    calls_before = len(tp.log.calls) if tp is not None else 0
    reranker = judge
    if config.rerank in ('elephant', 'decisions', 'jev'):
        if config.rerank != judge.method:
            reranker = Judge(scoring_ask(tp, config.rerank), chars=config.card_chars,
                             model=config.rerank_model, method=config.rerank,
                             question_style=config.question_style if config.rerank == 'elephant' else 'shared')
        rer = reranker.judge(query, arts, top)
    elif config.rerank == 'openai':
        from .llm import score_candidates
        if tp is None or tp.openai is None:
            raise RuntimeError('scoring rerank transport unavailable')
        scores, _ = score_candidates(tp.openai, query, arts, top, model=config.rerank_model,
                                     chars=config.card_chars, effort=config.verifier_effort)
        rer = dict(scores)
        if set(rer) != set(top):
            raise RuntimeError('rerank did not cover every candidate')
    else:
        rer = {a: screen[a] for a in top}
    t2 = time.monotonic()
    usage = judge.usage.summary() | {'rerank_requests': (judge.usage.requests - rerank_requests_before
                                                        if reranker is judge else reranker.usage.requests)}
    if reranker is not judge:
        for key in ('requests', 'input_tokens', 'output_tokens', 'errors'):
            usage[key] += getattr(reranker.usage, key)
    if tp is not None:
        usage.update(requests=len(tp.log.calls), rerank_requests=len(tp.log.calls) - calls_before,
                     input_tokens=sum(c['input_tokens'] for c in tp.log.calls),
                     output_tokens=sum(c['output_tokens'] for c in tp.log.calls))
    return Identification(ranked=sorted(((a, rer[a]) for a in top), key=lambda x: -x[1]), screen=screen,
                          usage=usage, screen_seconds=t1 - t0, rerank_seconds=t2 - t1, model=config.screen_model,
                          config_hash=config.config_hash,
                          model_ids={stage: model for stage, model in config.model_ids().items() if stage != 'verifier'},
                          methods={'screen': config.screen, 'rerank': config.rerank})


__all__ = ['identify', 'Identification', 'Judge', 'bm25_rank', 'articles', 'JEV_MODEL']
