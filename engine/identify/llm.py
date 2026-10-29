"""OpenAI rerank and verifier over a metered JSON transport.

Ported from PR #12 (engine/identify/llm.py). #12's `_openai_json` and `_anthropic_json` called the
provider directly; here every call goes through the transport from providers.py, which reserves and
settles through engine.llm_gate (or is the offline fake). The Anthropic verifier is verify.ClaudeVerifier.
Quote checking stays in verify.check_quotes. Ids the model returns that are not in the candidate list
are dropped; missing scores stay missing.
"""
from __future__ import annotations

import time

from .corpus import card
from .providers import OpenAIJson
from .verify import SYSTEM, Pick, Verification, check_quotes

_SCORE_SCHEMA = {
    'type': 'object', 'additionalProperties': False, 'required': ['scores'],
    'properties': {'scores': {'type': 'array', 'items': {
        'type': 'object', 'additionalProperties': False, 'required': ['article', 'probability'],
        'properties': {'article': {'type': 'string'}, 'probability': {'type': 'number'}}}}},
}
_PICK_SCHEMA = {
    'type': 'object', 'additionalProperties': False, 'required': ['picks'],
    'properties': {'picks': {'type': 'array', 'items': {
        'type': 'object', 'additionalProperties': False, 'required': ['article', 'quote', 'reason', 'confidence'],
        'properties': {'article': {'type': 'string'}, 'quote': {'type': 'string'},
                       'reason': {'type': 'string'}, 'confidence': {'type': 'number'}}}}},
}
RERANK_SYSTEM = ('Score each listed Division B article for whether the proposal must meet it, relies on it, '
                 'or departs from it. Return only article ids from the list. Do not judge compliance.')


def prompt(query: str, arts: dict, ids: list[str], chars: int | None) -> str:
    listed = '\n\n'.join(f'<article id="{a}">\n{card(arts[a], chars)}\n</article>' for a in ids if a in arts)
    return f'<proposal>\n{query}\n</proposal>\n\n<candidates>\n{listed}\n</candidates>'


def keep_scores(payload: dict, allowed: list[str]) -> list[tuple[str, float]]:
    ok, out, seen = set(allowed), [], set()
    for row in payload.get('scores') or []:
        if not isinstance(row, dict):
            continue
        art = row.get('article')
        if art not in ok or art in seen or not isinstance(row.get('probability'), (int, float)):
            continue
        seen.add(art)
        out.append((art, max(0.0, min(1.0, float(row['probability'])))))
    return out


def score_candidates(transport: OpenAIJson, query: str, arts: dict, ids: list[str], *, model: str,
                     chars: int | None = 700, effort: str | None = None) -> tuple[list[tuple[str, float]], dict]:
    """One request. Returns (scores for listed ids only, in the model's order; usage)."""
    ids = [a for a in ids if a in arts]
    payload, usage = transport('scores', _SCORE_SCHEMA, RERANK_SYSTEM, prompt(query, arts, ids, chars),
                               model=model, max_output_tokens=40 * len(ids) + 2000, effort=effort)
    return keep_scores(payload, ids), usage


class OpenAIVerifier:
    """Verifier contract (verify(query, candidates) -> Verification) over the OpenAI JSON transport."""

    def __init__(self, transport: OpenAIJson, arts: dict, *, model: str, chars: int | None = None,
                 effort: str | None = None, max_output_tokens: int = 8000):
        self.transport, self.arts, self.model, self.chars = transport, arts, model, chars
        self.max_output_tokens, self.effort = max_output_tokens, effort

    def verify(self, query: str, candidates: list[str]) -> Verification:
        candidates = [a for a in candidates if a in self.arts]
        t0 = time.monotonic()
        payload, usage = self.transport('picks', _PICK_SCHEMA, SYSTEM, prompt(query, self.arts, candidates, self.chars),
                                        model=self.model, max_output_tokens=self.max_output_tokens,
                                        effort=self.effort)
        picks = []
        for p in payload.get('picks') or []:
            if not isinstance(p, dict) or not isinstance(p.get('article'), str):
                continue
            try:
                confidence = max(0.0, min(1.0, float(p.get('confidence') or 0)))
            except (TypeError, ValueError):
                confidence = 0.0
            picks.append(Pick(article=p['article'], quote=str(p.get('quote') or ''), reason=str(p.get('reason') or ''),
                              confidence=confidence))
        keep, dropped = check_quotes(picks, candidates, self.arts)
        return Verification(keep, dropped, 'end_turn', {k: usage.get(k, 0) for k in ('input_tokens', 'output_tokens')},
                            time.monotonic() - t0)
