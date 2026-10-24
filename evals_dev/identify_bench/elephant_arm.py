"""Elephant pool-scoring arm: score a small candidate pool in as few requests as possible.

The free tier allows 50 requests a day, so Elephant scores only a candidate pool (~30-60 articles),
packed greedily in pool order up to the engine's own context bound (elephant_runtime.request_bytes).
A card is never truncated to fit more; an article whose request cannot fit even alone is an error.

Variants (names are stable; combine with '+', e.g. `focused-500+compact`):
  production   byte-identical to engine.identify.screen.Judge for method='elephant' (700-char cards,
               GOVERN noul per article, same greedy batching).
  focused-N    heading path + the article's sentences ordered by lexical overlap with the description,
               cut at N characters on a sentence boundary when possible; a scope sentence stays first.
  criteria     production cards + noul criteria defining governs vs merely related.
  compact      the decision rule once in state['rule'], short per-question instructions.

Packing bounds (`bound=`):
  engine       elephant_runtime.request_bytes, 1 token per UTF-8 byte (default; what the app admits).
  calibrated   measured on the live route (3.42 bytes per token; 1 output token per noul answer):
               bytes / 3.0 + 512 framing + 8 per question <= 15,000. Requests above the engine bound go
               through live.elephant_ask_unbounded (benchmark probe only; the app would reject them).

  .venv/bin/python -m evals_dev.identify_bench.elephant_arm plan      # dry-run request table, no network
"""
from __future__ import annotations

import json
import re
import sys
from contextlib import closing
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any, Callable, Mapping

from engine.identify.corpus import STOP, articles, bm25_rank, card
from engine.identify.elephant_runtime import ROUTING, ElephantError, request_bytes
from engine.identify.screen import ELEPHANT_MODEL, GOVERN, noul

DB = Path(__file__).resolve().parents[2] / 'codedb' / 'build' / 'codedb.sqlite'
PRODUCTION_CHARS = 700           # IdentifyConfig.card_chars
TIMEOUT = 60
BOUNDS = ('engine', 'calibrated')
CAL_BYTES_PER_TOKEN, CAL_FRAMING, CAL_PER_QUESTION, CAL_LIMIT = 3.0, 512, 8, 15_000

CRITERIA = {
    'true': ('The proposal must meet, relies on, or departs from a requirement this article states, so a complete '
             'variance application for the proposal must cite this article.'),
    'false': ('The article addresses a different subject, or only shares words, materials or building elements with '
              'the proposal without stating a requirement the proposal must meet, relies on, or departs from.'),
}
RULE = ('For one article in `articles`, decide whether it states a requirement that directly governs the situation '
        'described in `proposal`: the proposal must meet that requirement, relies on it, or departs from it, so a '
        'complete variance application must cite the article. An article on a different subject, or one that only '
        'shares words with the proposal, does not govern it.')
COMPACT_QUESTION = 'Apply `rule` to article {L}.'

# ask(state, questions, timeout) -> {"answers": {name: {"noul": p}}, ...}: the engine's Ask seam.
Ask = Callable[[Any, Mapping[str, Mapping[str, Any]], float], Mapping[str, Any]]


@dataclass(frozen=True)
class Variant:
    name: str
    focus_chars: int | None = None       # None: production card(a, 700)
    criteria: bool = False
    compact: bool = False

    def card(self, article: str, description: str, db_path: Path = DB) -> str:
        arts = articles(Path(db_path))
        if self.focus_chars is None:
            return card(arts[article], PRODUCTION_CHARS)
        return focused_card(arts[article], sentences(article, Path(db_path)), description, self.focus_chars)

    def payload(self, description: str, batch: list[tuple[str, str]]) -> tuple[dict, dict]:
        """(state, questions) for one request. For `production` this is Judge._payload exactly."""
        state: dict = {'proposal': description}
        if self.compact:
            state['rule'] = RULE
        state['articles'] = {f'A{i}': text for i, (_, text) in enumerate(batch)}
        questions = {}
        for i in range(len(batch)):
            q = noul((COMPACT_QUESTION if self.compact else GOVERN).format(L=f'A{i}'))
            if self.criteria:
                q['criteria'] = dict(CRITERIA)
            questions[f'q{i}'] = q
        return state, questions


def get_variant(name: str | Variant) -> Variant:
    """Parse a variant name: 'production' or '+'-joined parts from focused-N, criteria, compact."""
    if isinstance(name, Variant):
        return name
    if name == 'production':
        return Variant('production')
    focus, criteria, compact = None, False, False
    for part in name.split('+'):
        m = re.fullmatch(r'focused-(\d+)', part)
        if m and focus is None and int(m.group(1)) > 0:
            focus = int(m.group(1))
        elif part == 'criteria' and not criteria:
            criteria = True
        elif part == 'compact' and not compact:
            compact = True
        else:
            raise ValueError(f'unknown Elephant variant: {name!r}')
    return Variant(name, focus, criteria, compact)


VARIANTS = {n: get_variant(n) for n in ('production', 'focused-350', 'focused-500', 'focused-700', 'criteria',
                                    'compact', 'focused-350+compact', 'focused-500+compact',
                                    'focused-500+criteria')}


# --- focused cards ---------------------------------------------------------------------------------

_WORD = re.compile(r'[a-z][a-z0-9-]{2,}')                       # corpus.bm25_rank tokenization
_SCOPE = re.compile(r'\b(?:appl(?:y|ies) (?:only )?to|this (?:article|subsection|section|part) (?:is|does|shall))\b',
                    re.I)


def words(text: str) -> set[str]:
    return {w for w in _WORD.findall(text.lower()) if w not in STOP}


@lru_cache(maxsize=4096)
def sentences(article: str, db_path: Path = DB) -> tuple[str, ...]:
    """The article's sentences in code order, each with its clauses, de-duplicated as corpus.articles does."""
    from codedb import store
    units: dict[str, list[str]] = {}
    last = None
    with closing(store.connect(db_path)) as c:
        rows = c.execute("select id, text from provisions where doc='NBC-AE' and division='B' and article=? "
                         "and level in ('sentence','clause','subclause') order by sort_key", (article,)).fetchall()
    for r in rows:
        if not r['text']:
            continue
        t = re.sub(r'\s+', ' ', r['text']).strip()
        if last is not None and t in last:
            continue
        m = re.match(re.escape(article) + r'(\(\d+\))', r['id'])
        key = m.group(1) if m else r['id']
        units.setdefault(key, []).append(t)
        last = t
    return tuple(' '.join(parts) for parts in units.values())


def focused_card(a: dict, sents: tuple[str, ...], description: str, n: int) -> str:
    """Heading path + sentences by overlap with the description (stable on ties), cut at n body chars."""
    head = f"{a['title']} (Part {a['part']} > {a['section']} > {a['subsection']})"
    if not sents:
        return card(a, n)
    want = words(description)
    order = list(range(len(sents)))
    scope = [0] if sents and _SCOPE.search(sents[0]) else []
    rest = sorted((i for i in order if i not in scope), key=lambda i: -len(want & words(sents[i])))
    chosen, size, cut = [], 0, False
    for i in scope + rest:
        s = sents[i]
        extra = len(s) + (1 if chosen else 0)
        if size + extra <= n:
            chosen.append(s)
            size += extra
        elif not chosen:                    # the best sentence alone is too long: cut it at n characters
            chosen.append(s[:n])
            size, cut = n, True
            break
        # else skip it: a shorter later sentence may still fit
    body = ' '.join(chosen) + (' ...' if cut or len(chosen) < len(sents) else '')
    return f'{head}: {body}'


# --- packing and scoring ---------------------------------------------------------------------------

def calibrated_tokens(state, questions) -> float:
    """Estimated provider tokens for the exact body the engine would send."""
    body = json.dumps({'model': ELEPHANT_MODEL, 'state': state, 'questions': questions, 'provider': ROUTING},
                      ensure_ascii=False, allow_nan=False, separators=(',', ':')).encode('utf-8')
    return len(body) / CAL_BYTES_PER_TOKEN + CAL_FRAMING + CAL_PER_QUESTION * len(questions)


def admit(state, questions, bound: str = 'engine') -> int:
    """Request size in bytes when the bound admits it; ElephantError('request_too_large') otherwise."""
    if bound == 'engine':
        return len(request_bytes(state, questions, model=ELEPHANT_MODEL))
    if bound != 'calibrated':
        raise ValueError(f'unknown bound: {bound!r}')
    if calibrated_tokens(state, questions) > CAL_LIMIT:
        raise ElephantError('request_too_large', dispatched=False)
    return len(json.dumps({'model': ELEPHANT_MODEL, 'state': state, 'questions': questions, 'provider': ROUTING},
                          ensure_ascii=False, separators=(',', ':')).encode('utf-8'))


def pack(description: str, pool_ids: list[str], v: Variant, db_path: Path = DB, *,
         bound: str = 'engine') -> list[list[tuple[str, str]]]:
    """Greedy, in pool order: each request holds as many whole cards as the bound admits.

    With bound='engine' this is the algorithm of screen.Judge.batches for method='elephant'."""
    out, cur = [], []
    for article in pool_ids:
        candidate = (article, v.card(article, description, db_path))
        trial = [*cur, candidate]
        try:
            admit(*v.payload(description, trial), bound)
        except ElephantError as error:
            if error.code != 'request_too_large' or not cur:
                raise
            out.append(cur)
            cur = [candidate]
            admit(*v.payload(description, cur), bound)
        else:
            cur = trial
    if cur:
        out.append(cur)
    return out


def live_ask(budget=None, tag: str = '', bound: str = 'engine') -> Ask:
    """The harness transport, cached by request bytes; budget=None means cache-only."""
    from . import live

    def ask(state, questions, timeout):
        if bound == 'calibrated':
            if budget is None:
                # elephant_ask_unbounded requires a budget and loads the credential before spending it;
                # cache-only reads its store directly (same key) so no credential is touched.
                from .cache import request_key
                body = json.dumps({'model': ELEPHANT_MODEL, 'state': state, 'questions': questions,
                                   'provider': ROUTING}, ensure_ascii=False, allow_nan=False,
                                  separators=(',', ':'))
                hit = live._stores()[0].get(request_key('elephant-unbounded', body))
                if hit is None:
                    raise live.BudgetExhausted('cache miss and live Elephant calls are off')
                return hit
            return live.elephant_ask_unbounded(state, questions, budget=budget, timeout=timeout, tag=tag)
        return live.elephant_ask(state, questions, budget=budget, timeout=timeout, tag=tag)
    return ask


def score_pool(description: str, pool_ids: list[str], *, variant: str | Variant, ask: Ask | None = None,
               budget=None, tag: str = '', bound: str = 'engine', db_path: Path = DB) -> tuple[dict[str, float], dict]:
    """({article: probability}, {requests, questions, bytes, ...}). Requests run in order; any failure stops."""
    v = get_variant(variant)
    if len(set(pool_ids)) != len(pool_ids):
        raise ValueError('pool has duplicate articles')
    ask = ask or live_ask(budget, tag or f'{v.name}/{bound}', bound)
    scores: dict[str, float] = {}
    sizes, estimated = [], []
    batches = pack(description, pool_ids, v, db_path, bound=bound)
    for batch in batches:
        state, questions = v.payload(description, batch)
        sizes.append(admit(state, questions, bound))
        estimated.append(round(calibrated_tokens(state, questions)))
        reply = ask(state, questions, TIMEOUT)
        for i, (article, _) in enumerate(batch):
            scores[article] = float(reply['answers'][f'q{i}']['noul'])
    return {a: scores[a] for a in pool_ids}, {'variant': v.name, 'bound': bound, 'requests': len(batches),
                                              'questions': len(pool_ids), 'bytes': sizes,
                                              'estimated_tokens': estimated}


def plan_requests(cases_with_pools, variant: str | Variant, db_path: Path = DB, *, bound: str = 'engine') -> dict:
    """Dry run, no network: requests per case and in total. cases_with_pools: [(case id, description, pool)]."""
    v = get_variant(variant)
    per_case = {cid: len(pack(desc, list(pool), v, db_path, bound=bound)) for cid, desc, pool in cases_with_pools}
    return {'variant': v.name, 'bound': bound, 'per_case': per_case, 'total': sum(per_case.values()),
            'max': max(per_case.values(), default=0)}


def bm25_pools(cases, k: int, db_path: Path = DB):
    return [(c.id, c.description, bm25_rank(c.description, db_path)[:k]) for c in cases]


def main(argv: list[str]) -> int:
    if argv[:1] != ['plan']:
        print(__doc__)
        return 2
    from .cases import all_cases, select
    tune = select(all_cases(), fold='tune')
    sizes = (20, 30, 40, 60)
    pools = {k: bm25_pools(tune, k) for k in sizes}
    print(f'tune fold: {len(tune)} cases; bm25 top-k pools; cell = mean requests per case [max], total')
    print(f"{'variant':24}{'bound':12}" + ''.join(f'{"pool " + str(k):>20}' for k in sizes))
    for name, v in VARIANTS.items():
        for bound in BOUNDS:
            row = []
            for k in sizes:
                p = plan_requests(pools[k], v, bound=bound)
                row.append(f"{p['total'] / max(1, len(tune)):.2f} [{p['max']}] {p['total']:>4}")
            print(f'{name:24}{bound:12}' + ''.join(f'{cell:>20}' for cell in row))
    return 0


if __name__ == '__main__':
    raise SystemExit(main(sys.argv[1:]))
