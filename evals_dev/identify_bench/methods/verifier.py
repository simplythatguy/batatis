"""OpenAI arms: the verifier (V) and an OpenAI rerank of an upstream shortlist (A9).

The verifier follows PR #12's variant c, as WP-20 ports it into ``engine/identify/llm.py``: the pinned system prompt
(``engine.identify.verify.SYSTEM``), a user message of ``<proposal>`` and ``<candidates>`` with each shortlisted article's
full text, a strict JSON schema of ``picks`` (article, quote, reason, confidence), and the word-for-word quote check of
``engine.identify.verify.check_quotes``. A pick whose article is not in the shortlist, or whose quote is not in the
article text after whitespace normalisation, is dropped, never repaired. This module is self-contained on purpose:
WP-20's branch was not pushed when the benchmark was written. ``tests/test_identify_bench_contract.py`` pins the prompt
text, and compares it with ``engine.identify.llm.prompt`` when that module exists.

Everything runs on the standard tier at the configured reasoning effort, through the hard-stop ledger.
"""
from __future__ import annotations

import hashlib
import json

from evals_dev.identify_bench.datasets import BenchCase
from evals_dev.identify_bench.rows import SCREEN_ORDER_KEEP, RowDraft

from .base import Arm, RunContext, UpstreamMissing, append_rest

PICK_SCHEMA = {
    'type': 'object', 'additionalProperties': False, 'required': ['picks'],
    'properties': {'picks': {'type': 'array', 'items': {
        'type': 'object', 'additionalProperties': False, 'required': ['article', 'quote', 'reason', 'confidence'],
        'properties': {'article': {'type': 'string'}, 'quote': {'type': 'string'},
                       'reason': {'type': 'string'}, 'confidence': {'type': 'number'}}}}},
}
SCORE_SCHEMA = {
    'type': 'object', 'additionalProperties': False, 'required': ['scores'],
    'properties': {'scores': {'type': 'array', 'items': {
        'type': 'object', 'additionalProperties': False, 'required': ['article', 'probability'],
        'properties': {'article': {'type': 'string'}, 'probability': {'type': 'number'}}}}},
}
RERANK_SYSTEM = ('Score each listed Division B article for whether the proposal must meet it, relies on it, '
                 'or departs from it. Return only article ids from the list. Do not judge compliance.')
OUT_OF_LIST_NOTE = ('\nIf you are confident that up to two other Division B articles not in the list also govern, you may '
                    'name them with an empty quote; they are checked for existence only and never replace a quoted pick.')


def verifier_system(out_of_list: bool) -> str:
    from engine.identify.verify import SYSTEM
    return SYSTEM + (OUT_OF_LIST_NOTE if out_of_list else '')


def prompt(query: str, arts: dict, ids: list[str], chars: int | None) -> str:
    """The user message. Mirrors ``engine.identify.llm.prompt`` (WP-20) character for character."""
    from engine.identify.corpus import card
    listed = '\n\n'.join(f'<article id="{a}">\n{card(arts[a], chars)}\n</article>' for a in ids if a in arts)
    return f'<proposal>\n{query}\n</proposal>\n\n<candidates>\n{listed}\n</candidates>'


def prompt_sha(out_of_list: bool = False) -> str:
    blob = verifier_system(out_of_list) + json.dumps(PICK_SCHEMA, sort_keys=True) + prompt('Q', {'A': {
        'id': 'A', 'part': 1, 'title': 'T', 'section': 'S', 'subsection': 'U', 'text': 'body'}}, ['A'], None)
    return hashlib.sha256(blob.encode()).hexdigest()[:10]


def _openai_numbers(res) -> tuple[dict, float, dict]:
    tokens = {'openai': {'requests': res.attempts, 'input': res.input_tokens, 'output': res.output_tokens,
                         'reasoning': res.reasoning_tokens, 'cached': res.cached_tokens}}
    ids = {'returned': [res.returned_model] if res.returned_model else [], 'service_tier': res.service_tier,
           'request_id': res.request_id}
    return tokens, float(res.usd), ids


class LunaVerifierArm(Arm):
    kind = 'verify'
    live = True
    provider = 'openai'
    repeats = 5

    def __init__(self, name: str, upstream: str, *, model: str = 'gpt-6-luna', effort: str = 'medium',
                 shortlist_n: int = 15, chars: int | None = None, max_completion_tokens: int = 12000,
                 upstream_repeat: int | None = None, upstream_cycle: int | None = None, out_of_list: bool = False,
                 repeats: int = 5):
        if 'haiku' in model.lower():
            raise ValueError('Haiku models are not used')
        self.name, self.upstream_names, self.model, self.effort = name, (upstream,), model, effort
        self.shortlist_n, self.chars, self.max_completion_tokens = shortlist_n, chars, max_completion_tokens
        self.upstream_repeat, self.upstream_cycle, self.out_of_list, self.repeats = (
            upstream_repeat, upstream_cycle, out_of_list, repeats)

    def config(self) -> dict:
        return {'method': 'verifier over the upstream shortlist, full-text quote match', 'model': self.model,
                'reasoning_effort': self.effort, 'service_tier': 'default (standard)', 'shortlist_n': self.shortlist_n,
                'article_text': 'full' if self.chars is None else f'{self.chars} characters',
                'max_completion_tokens': self.max_completion_tokens,
                'upstream_repeat': self._upstream_label(),
                'out_of_list': self.out_of_list, 'prompt_sha': prompt_sha(self.out_of_list),
                'pattern': 'PR #12 variant c (WP-20 engine/identify/llm.py)'}

    def _upstream_label(self):
        if self.upstream_cycle:
            return f'repeat mod {self.upstream_cycle}'
        return 'same repeat' if self.upstream_repeat is None else self.upstream_repeat

    def _upstream_repeat(self, repeat: int) -> int:
        if self.upstream_cycle:
            return repeat % self.upstream_cycle
        return repeat if self.upstream_repeat is None else self.upstream_repeat

    def run(self, case: BenchCase, repeat: int, ctx: RunContext) -> RowDraft:
        from engine.identify.verify import Pick, check_quotes
        try:
            up = ctx.upstream(self.upstream_names[0], case, self._upstream_repeat(repeat), clamp=True)
        except UpstreamMissing as e:
            return RowDraft(errors=[{'stage': 'verify', 'category': 'upstream_missing', 'detail': str(e)}])
        cand = [a for a in up['order'][:self.shortlist_n] if a in ctx.arts]
        res = ctx.openai(name='picks', schema=PICK_SCHEMA, system=verifier_system(self.out_of_list),
                         user=prompt(case.query, ctx.arts, cand, self.chars), model=self.model, effort=self.effort,
                         max_completion_tokens=self.max_completion_tokens, arm=self.name, case=f'{case.id}#r{repeat}')
        tokens, usd, ids = _openai_numbers(res)
        base = dict(tokens=tokens, usd=usd, upstream={self.upstream_names[0]: up['key']},
                    model_ids={'requested': self.model, **ids}, order_keep=SCREEN_ORDER_KEEP)
        notes = {'shortlist': len(cand), 'finish_reason': res.finish_reason, 'attempts': res.attempts,
                 'upstream_repeat': self._upstream_repeat(repeat)}
        lat = {'verify': res.latency_ms}
        if res.payload is None:
            notes['degraded'] = 'verifier failed; upstream order kept'
            return RowDraft(order=list(up['order']), probabilities=dict(up['probabilities']), latency_ms=lat,
                            errors=[{'stage': 'verify', **{k: v for k, v in e.items() if k != 'fatal'}} for e in res.errors],
                            notes=notes, **base)
        raw = []
        for p in res.payload.get('picks') or []:
            if isinstance(p, dict) and isinstance(p.get('article'), str):
                try:
                    conf = max(0.0, min(1.0, float(p.get('confidence') or 0)))
                except (TypeError, ValueError):
                    conf = 0.0
                raw.append(Pick(article=p['article'], quote=str(p.get('quote') or ''), reason=str(p.get('reason') or ''),
                                confidence=conf))
        outside: list = []
        if self.out_of_list:
            outside = [p for p in raw if p.article not in cand and p.article in ctx.arts and not p.quote.strip()]
            raw_checked = [p for p in raw if p not in outside]
        else:
            raw_checked = raw
        keep, dropped = check_quotes(raw_checked, cand, ctx.arts)
        picks = [{'article': p.article, 'quote': p.quote, 'reason': p.reason, 'confidence': p.confidence} for p in keep]
        head = [p.article for p in keep] + [p.article for p in outside if p.article not in {k.article for k in keep}]
        order = append_rest(head, up['order'])
        notes.update(raw_picks=len(raw), kept=len(keep), dropped=len(dropped), empty_picks=not raw,
                     quote_pass_rate=(len(keep) / len(raw_checked)) if raw_checked else None,
                     outside_picks=[p.article for p in outside])
        return RowDraft(order=order, probabilities=dict(up['probabilities']), picks=picks,
                        dropped=[{'article': p.article, 'why': why} for p, why in dropped], latency_ms=lat,
                        errors=[], notes=notes, **base)


class LunaRerankArm(Arm):
    """A9: an OpenAI model scores the top ``n`` of an upstream ranking (700-character cards) in one request."""
    kind = 'rerank'
    live = True
    provider = 'openai'
    repeats = 3

    def __init__(self, name: str, upstream: str, *, model: str = 'gpt-6-luna', effort: str = 'medium', n: int = 60,
                 chars: int = 700, max_completion_tokens: int = 12000, repeats: int = 3):
        self.name, self.upstream_names, self.model, self.effort, self.n = name, (upstream,), model, effort, n
        self.chars, self.max_completion_tokens, self.repeats = chars, max_completion_tokens, repeats

    def config(self) -> dict:
        return {'method': 'openai scores the upstream top n in one request', 'model': self.model,
                'reasoning_effort': self.effort, 'n': self.n, 'card_chars': self.chars,
                'max_completion_tokens': self.max_completion_tokens, 'system': RERANK_SYSTEM,
                'pattern': 'PR #12 variant b (WP-20 engine/identify/llm.py)'}

    def run(self, case: BenchCase, repeat: int, ctx: RunContext) -> RowDraft:
        try:
            up = ctx.upstream(self.upstream_names[0], case, repeat, clamp=True)
        except UpstreamMissing as e:
            return RowDraft(errors=[{'stage': 'rerank', 'category': 'upstream_missing', 'detail': str(e)}])
        cand = [a for a in up['order'][:self.n] if a in ctx.arts]
        res = ctx.openai(name='scores', schema=SCORE_SCHEMA, system=RERANK_SYSTEM,
                         user=prompt(case.query, ctx.arts, cand, self.chars), model=self.model, effort=self.effort,
                         max_completion_tokens=self.max_completion_tokens, arm=self.name, case=f'{case.id}#r{repeat}')
        tokens, usd, ids = _openai_numbers(res)
        base = dict(tokens=tokens, usd=usd, upstream={self.upstream_names[0]: up['key']},
                    model_ids={'requested': self.model, **ids}, order_keep=SCREEN_ORDER_KEEP)
        if res.payload is None:
            return RowDraft(order=list(up['order']), latency_ms={'rerank': res.latency_ms},
                            errors=[{'stage': 'rerank', **{k: v for k, v in e.items() if k != 'fatal'}} for e in res.errors],
                            notes={'degraded': 'rerank failed; upstream order kept'}, **base)
        probs: dict[str, float] = {}
        for row in res.payload.get('scores') or []:
            if isinstance(row, dict) and row.get('article') in cand and isinstance(row.get('probability'), (int, float)):
                probs.setdefault(row['article'], max(0.0, min(1.0, float(row['probability']))))
        scored = sorted(probs, key=lambda a: (-probs[a], cand.index(a)))
        unscored = [a for a in cand if a not in probs]                 # ids the model skipped keep upstream order, after
        order = append_rest(scored + unscored, up['order'])
        return RowDraft(order=order, probabilities=probs, latency_ms={'rerank': res.latency_ms},
                        notes={'scored': len(probs), 'candidates': len(cand), 'finish_reason': res.finish_reason},
                        **base)
