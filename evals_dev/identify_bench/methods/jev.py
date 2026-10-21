"""Jev arms: the exhaustive screen (R4) and the one-request rerank (R5 after the screen, R6 after BM25).

These run the production ``engine.identify.screen.Judge`` unchanged: 700-character cards, batches under 56,000
characters, eight requests in flight, the question "Article A{i} states a requirement that directly governs the
situation described in `proposal`...". The model id is pinned (``jev-1.13.0``), never ``jev-latest``. The only
thing swapped in is the ``ask`` callable, so every request is counted.

The screen asserts that every Division B article was scored and records the expected and actual request counts
(about 21 per case); a mismatch is reported, not hidden.
"""
from __future__ import annotations

from evals_dev.identify_bench import pricing
from evals_dev.identify_bench.datasets import BenchCase
from evals_dev.identify_bench.rows import SCREEN_ORDER_KEEP, RowDraft

from .base import Arm, RunContext, UpstreamMissing, append_rest

PINNED = 'jev-1.13.0'
PROVIDER = 'typesafe'
THRESHOLDS = (0.05, 0.10, 0.30, 0.50, 0.80, 0.90)


def live_jev_ask(model: str):
    """The vendored client, pinned model. Needs TYPESAFE_API_KEY (JEV_API_KEY maps to it) and SSL_CERT_FILE on this Mac."""
    from engine.identify.jevkit import client

    def ask(state, questions, timeout):
        return client.ask(state, questions, timeout=timeout, model=model, provider=PROVIDER)
    return ask


def _stage_numbers(judge, model: str) -> tuple[dict, float, dict]:
    u = judge.usage
    lat = sorted(u.latency_ms)
    tokens = {'jev': {'requests': u.requests, 'input': u.input_tokens, 'output': u.output_tokens,
                      'errors': u.errors}}
    usd = float(pricing.cost_usd(model, u.input_tokens, u.output_tokens))
    pct = lambda q: round(lat[min(len(lat) - 1, int(q * len(lat)))], 1) if lat else None
    return tokens, usd, {'request_p50': pct(0.5), 'request_p95': pct(0.95), 'request_max': pct(1.0)}


def _book(ctx: RunContext, model: str, arm: str, case: BenchCase, tokens: dict, usd: float) -> None:
    if ctx.jev_ledger is None:
        return
    j = tokens['jev']
    res = ctx.jev_ledger.reserve(model=model, worst_case_usd=0, arm=arm, case=case.id)
    ctx.jev_ledger.settle(res, usd=usd, input_tokens=j['input'], output_tokens=j['output'], requests=j['requests'],
                          arm=arm, case=case.id)


class JevScreenArm(Arm):
    kind = 'screen'
    live = True
    provider = 'jev'
    repeats = 3

    def __init__(self, name: str = 'R4-jev-screen', *, model: str = PINNED, card_chars: int = 700,
                 max_state: int = 56000, workers: int = 8, timeout: float = 60, attempts: int = 4):
        self.name, self.model, self.card_chars, self.max_state = name, model, card_chars, max_state
        self.workers, self.timeout, self.attempts = workers, timeout, attempts

    def config(self) -> dict:
        from engine.identify.screen import GOVERN
        return {'method': 'jev noul over every article, no rerank', 'model': self.model, 'provider': PROVIDER,
                'card_chars': self.card_chars, 'max_state': self.max_state, 'question': GOVERN}

    def run(self, case: BenchCase, repeat: int, ctx: RunContext) -> RowDraft:
        from engine.identify.screen import Judge
        judge = Judge(ctx.jev_ask(self.model), chars=self.card_chars, max_state=self.max_state, workers=self.workers,
                      timeout=self.timeout, attempts=self.attempts)
        ids = list(ctx.arts)
        expected = len(judge.batches(case.query, ctx.arts, ids))
        t0 = ctx.clock()
        probs: dict[str, float] = {}
        errors: list[dict] = []
        try:
            probs = judge.judge(case.query, ctx.arts, ids)
        except Exception as e:                                       # noqa: BLE001 - recorded, not raised
            errors.append({'stage': 'screen', 'category': 'jev_failed', 'detail': type(e).__name__})
        screen_ms = (ctx.clock() - t0) * 1000
        tokens, usd, req_lat = _stage_numbers(judge, self.model)
        if probs and len(probs) != len(ids):
            errors.append({'stage': 'screen', 'category': 'incomplete',
                           'detail': f'{len(probs)} of {len(ids)} articles scored'})
            probs = {}
        notes = {'expected_requests': expected, 'requests': tokens['jev']['requests'], 'articles_scored': len(probs),
                 'request_count_ok': tokens['jev']['requests'] == expected and not tokens['jev']['errors']}
        order = sorted(ids, key=lambda a: -probs[a]) if probs else []
        if probs:
            notes['at_or_above'] = {str(t): sum(1 for p in probs.values() if p >= t) for t in THRESHOLDS}
        _book(ctx, self.model, self.name, case, tokens, usd)
        return RowDraft(order=order, probabilities={a: probs[a] for a in order[:60]}, tokens=tokens, usd=usd,
                        latency_ms={'screen': screen_ms, **{k: v for k, v in req_lat.items() if v is not None}},
                        errors=errors, model_ids={'requested': self.model}, notes=notes, order_keep=SCREEN_ORDER_KEEP)


class JevRerankArm(Arm):
    """Re-judge the top ``n`` of an upstream ranking together in one request, then keep the rest in upstream order."""
    kind = 'rerank'
    live = True
    provider = 'jev'
    repeats = 3

    def __init__(self, name: str, upstream: str, *, n: int = 60, model: str = PINNED, card_chars: int = 700,
                 max_state: int = 56000, timeout: float = 60, attempts: int = 4, repeats: int = 3):
        self.name, self.upstream_names, self.n, self.model = name, (upstream,), n, model
        self.card_chars, self.max_state, self.timeout, self.attempts, self.repeats = (
            card_chars, max_state, timeout, attempts, repeats)

    def config(self) -> dict:
        from engine.identify.screen import GOVERN
        return {'method': 'jev noul over the upstream top n in one request', 'n': self.n, 'model': self.model,
                'provider': PROVIDER, 'card_chars': self.card_chars, 'max_state': self.max_state, 'question': GOVERN}

    def run(self, case: BenchCase, repeat: int, ctx: RunContext) -> RowDraft:
        from engine.identify.screen import Judge
        try:
            up = ctx.upstream(self.upstream_names[0], case, repeat, clamp=True)
        except UpstreamMissing as e:
            return RowDraft(errors=[{'stage': 'rerank', 'category': 'upstream_missing', 'detail': str(e)}])
        judge = Judge(ctx.jev_ask(self.model), chars=self.card_chars, max_state=self.max_state, workers=1,
                      timeout=self.timeout, attempts=self.attempts)
        cand = [a for a in up['order'][:self.n] if a in ctx.arts]
        expected = len(judge.batches(case.query, ctx.arts, cand))
        t0 = ctx.clock()
        probs: dict[str, float] = {}
        errors: list[dict] = []
        try:
            probs = judge.judge(case.query, ctx.arts, cand)
        except Exception as e:                                       # noqa: BLE001
            errors.append({'stage': 'rerank', 'category': 'jev_failed', 'detail': type(e).__name__})
        ms = (ctx.clock() - t0) * 1000
        tokens, usd, req_lat = _stage_numbers(judge, self.model)
        _book(ctx, self.model, self.name, case, tokens, usd)
        notes = {'expected_requests': expected, 'requests': tokens['jev']['requests'], 'candidates': len(cand),
                 'request_count_ok': tokens['jev']['requests'] == expected and not tokens['jev']['errors']}
        if probs:
            ranked = sorted(cand, key=lambda a: -probs[a])
            order = append_rest(ranked, up['order'])
        else:
            order = list(up['order'])                                # degraded: keep the upstream order, report the error
            notes['degraded'] = 'rerank failed; upstream order kept'
        return RowDraft(order=order, probabilities={a: probs[a] for a in cand if a in probs}, tokens=tokens, usd=usd,
                        latency_ms={'rerank': ms, **{k: v for k, v in req_lat.items() if v is not None}},
                        upstream={self.upstream_names[0]: up['key']}, errors=errors,
                        model_ids={'requested': self.model}, notes=notes, order_keep=SCREEN_ORDER_KEEP)
