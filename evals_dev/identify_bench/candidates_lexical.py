"""Offline lexical candidate generation for code identification: BM25 arms plus a cross-reference graph.

  .venv/bin/python -m evals_dev.identify_bench.candidates_lexical          # tune fold, writes results/lexical.*
  .venv/bin/python -m evals_dev.identify_bench.candidates_lexical --test   # also the test fold, recommended recipe only

Arms return ranked Division B article ids (only ids in engine.identify.corpus.articles). The graph is parsed
from the code database text (Division B sentences, clauses and subclauses, plus appendix note text attached
to a provision through note_links). Edges are typed:

  article     "Article 9.10.9.6.", "Sentence 9.10.15.4.(2)", "Clause ...(1)(b)", "Subclause ...", ranges
  table       "Table 9.10.14.4.-A" -> the article that carries the table (when it exists)
  note        a reference made in the appendix note of the source article (any of the forms above)
  subsection  "Subsection 9.10.8." (kept on its own; expanded to member articles on request)
  section     "Section 9.20." (kept on its own; too broad to expand by default)

References followed by "of Division A/C" and same-article relative references ("Sentence (2)") are dropped.
"""
from __future__ import annotations

import json
import re
import sys
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor
from contextlib import closing
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Iterable, Sequence

from codedb import store
from engine.identify import corpus, search_rank

ROOT = Path(__file__).resolve().parents[2]
DB = ROOT / 'codedb' / 'build' / 'codedb.sqlite'
RESULTS = Path(__file__).resolve().parent / 'results'

EDGE_TYPES = ('article', 'table', 'note', 'subsection', 'section')
EDGE_PRIORITY = {t: i for i, t in enumerate(EDGE_TYPES)}
ARTICLE_EDGES = ('article', 'table', 'note')

_KEYWORD = r'(?P<kw>Articles?|Sentences?|Clauses?|Subclauses?|Subsections?|Sections?|Tables?)'
_NUM = r'\d+(?:\.\d+)*\.(?:-[A-Z]+)?(?:\(\d+\))*(?:\([a-z]+\))*(?:\([ivx]+\))*'
_REL = r'(?:\(\d+\))+(?:\([a-z]+\))*(?:\([ivx]+\))*|(?:\([a-z]+\))+(?:\([ivx]+\))*'
_ITEM = rf'(?:{_NUM}|{_REL})'
_SEP = r'(?:\s*,\s*(?:and\s+|or\s+)?|\s+(?:and|or|to)\s+)'
REF = re.compile(rf'\b{_KEYWORD}\s+(?P<list>{_NUM}(?:{_SEP}{_ITEM})*)')
_TOKENS = re.compile(rf'{_NUM}|{_REL}|\bto\b')
_OTHER_DIVISION = re.compile(r'\s*,?\s*(?:of|in)\s+Division\s+[AC]\b')
_DOTTED = re.compile(r'^(\d+(?:\.\d+)*\.)')
_ARTICLE_ID = re.compile(r'(\d+\.\d+\.\d+\.\d+\.)')


@dataclass(frozen=True)
class Ref:
    """One parsed reference: kind is the keyword family, target the dotted number (article, subsection...)."""
    kind: str            # 'article' | 'table' | 'subsection' | 'section'
    target: str          # dotted id: '9.10.9.6.' (article/table), '9.10.8.' (subsection), '9.20.' (section)
    range_to: str | None = None


def _dotted(token: str) -> str | None:
    m = _DOTTED.match(token)
    return m.group(1) if m else None


def _level(dotted: str) -> str:
    return {2: 'section', 3: 'subsection', 4: 'article'}.get(dotted.count('.'), 'other')


def parse_refs(text: str) -> list[Ref]:
    """Cross-references in one provision text, in order. Relative ("Sentence (2)") and Division A/C refs dropped.

    Each dotted number is classified by its depth (4 parts: article, 3: subsection, 2: section); a Table
    reference becomes kind 'table' pointing at its article number. "X to Y" yields one Ref with range_to=Y
    (when Y is a full number; "9.10.14.1.(1) to (4)" stays inside one article and needs no range).
    """
    out: list[Ref] = []
    for m in REF.finditer(text or ''):
        if _OTHER_DIVISION.match(text, m.end()):
            continue
        is_table = m.group('kw').startswith('Table')
        tokens = _TOKENS.findall(m.group('list'))
        pending_range = False
        for tok in tokens:
            if tok == 'to':
                pending_range = True
                continue
            dotted = _dotted(tok)
            if dotted is None:          # relative item: same article/sentence as the previous one
                pending_range = False
                continue
            level = _level(dotted)
            if level == 'other':
                pending_range = False
                continue
            kind = 'table' if is_table and level == 'article' else level
            if pending_range and out and out[-1].kind == kind and out[-1].range_to is None and out[-1].target != dotted:
                out[-1] = Ref(kind, out[-1].target, dotted)
            else:
                out.append(Ref(kind, dotted))
            pending_range = False
    return out


@dataclass
class Graph:
    order: list[str]                                     # Division B articles in code order
    refs_out: dict[str, dict[str, str]] = field(default_factory=dict)   # src -> {dst: best edge type}
    refs_in: dict[str, dict[str, str]] = field(default_factory=dict)    # dst -> {src: best edge type}
    container_out: dict[str, dict[str, str]] = field(default_factory=dict)  # src -> {subsection/section id: type}
    same_subsection: dict[str, list[str]] = field(default_factory=dict)     # article -> siblings (code order)
    pos: dict[str, int] = field(default_factory=dict)                       # article -> code-order index
    subsection_members: dict[str, list[str]] = field(default_factory=dict)  # '9.10.8.' -> articles
    section_members: dict[str, list[str]] = field(default_factory=dict)     # '9.10.' -> articles


@lru_cache(maxsize=4)
def _members(order: tuple[str, ...], depth: int) -> dict[str, list[str]]:
    out: dict[str, list[str]] = defaultdict(list)
    for a in order:
        out['.'.join(a.split('.')[:depth]) + '.'].append(a)
    return dict(out)


def _add(edges: dict, src: str, dst: str, kind: str) -> None:
    cur = edges.setdefault(src, {}).get(dst)
    if cur is None or EDGE_PRIORITY[kind] < EDGE_PRIORITY[cur]:
        edges[src][dst] = kind


def _resolve(ref: Ref, index: dict[str, int], order: list[str]) -> list[str]:
    """Article ids a Ref names (ranges enumerate in code order, capped at 60 articles)."""
    if ref.range_to is None:
        return [ref.target] if ref.target in index else []
    if ref.kind in ('subsection', 'section'):
        return []
    lo, hi = index.get(ref.target), index.get(ref.range_to)
    if lo is None or hi is None or hi < lo or hi - lo > 60:
        return [a for a in (ref.target, ref.range_to) if a in index]
    return order[lo:hi + 1]


def _containers(ref: Ref, order: list[str]) -> list[str]:
    if ref.range_to is None:
        return [ref.target]
    depth = ref.target.count('.')
    known = sorted({'.'.join(a.split('.')[:depth]) + '.' for a in order}, key=lambda d: [int(x) for x in d[:-1].split('.')])
    try:
        lo, hi = known.index(ref.target), known.index(ref.range_to)
    except ValueError:
        return [ref.target, ref.range_to]
    return known[lo:hi + 1] if 0 <= hi - lo <= 20 else [ref.target, ref.range_to]


@lru_cache(maxsize=2)
def build_graph(db_path: Path = DB) -> Graph:
    order = list(corpus.articles(db_path))
    index = {a: i for i, a in enumerate(order)}
    g = Graph(order=order, pos=index, subsection_members=_members(tuple(order), 3),
              section_members=_members(tuple(order), 2))

    def add_text(src: str, text: str, note: bool) -> None:
        for ref in parse_refs(text):
            if ref.kind in ('subsection', 'section'):
                for cid in _containers(ref, order):
                    _add(g.container_out, src, cid, ref.kind)
                continue
            for dst in _resolve(ref, index, order):
                if dst != src:
                    _add(g.refs_out, src, dst, 'note' if note else ref.kind)

    with closing(store.connect(db_path)) as c:
        for r in c.execute("select article, text from provisions where doc='NBC-AE' and division='B' "
                           "and level in ('sentence','clause','subclause') order by sort_key"):
            if r['article'] in index:
                add_text(r['article'], r['text'] or '', note=False)
        for r in c.execute("select distinct l.provision_id as pid, n.text as text from note_links l join notes n "
                           "on n.doc=l.doc and n.division=l.division and n.note_id=l.note_id "
                           "where l.doc='NBC-AE' and l.division='B'"):
            m = _ARTICLE_ID.match(r['pid'] or '')
            src = m.group(1) if m else None
            if src in index:
                add_text(src, r['text'] or '', note=True)
    for src, dsts in g.refs_out.items():
        for dst, kind in dsts.items():
            _add(g.refs_in, dst, src, kind)
    for members in _members(tuple(order), 3).values():
        for a in members:
            g.same_subsection[a] = [b for b in members if b != a]
    return g


# ---------------------------------------------------------------- arms


def _known(ids: Iterable[str], db_path: Path) -> list[str]:
    arts = corpus.articles(db_path)
    return [a for a in dict.fromkeys(ids) if a in arts]


def bm25(text: str, k: int = 200, db_path: Path = DB) -> list[str]:
    return _known(corpus.bm25_rank(text, db_path), db_path)[:k]


def bm25_v3(text: str, k: int = 200, db_path: Path = DB) -> list[str]:
    return _known(search_rank.rank_articles(text, db_path, limit=k), db_path)[:k]


def rrf(*rankings: Sequence[str], c: int = 60) -> list[str]:
    """Reciprocal-rank fusion; ties keep first-seen order."""
    score: dict[str, float] = defaultdict(float)
    for ranking in rankings:
        for i, a in enumerate(ranking):
            score[a] += 1 / (c + i + 1)
    return sorted(score, key=lambda a: -score[a])


def interleave(*rankings: Sequence[str]) -> list[str]:
    out: dict[str, None] = {}
    for i in range(max((len(r) for r in rankings), default=0)):
        for r in rankings:
            if i < len(r):
                out.setdefault(r[i])
    return list(out)


# ---------------------------------------------------------------- expansion


def neighbours(article: str, g: Graph, mode: str = 'out', types: tuple[str, ...] = ARTICLE_EDGES) -> dict[str, str]:
    """{neighbour: edge type}. 'subsection' in types expands Subsection references to their member articles."""
    out: dict[str, str] = {}
    if mode in ('out', 'both'):
        for dst, kind in g.refs_out.get(article, {}).items():
            if kind in types:
                out.setdefault(dst, kind)
        for cid, kind in g.container_out.get(article, {}).items():
            if kind in types:
                members = (g.subsection_members if kind == 'subsection' else g.section_members).get(cid, [])
                for dst in members:
                    if dst != article:
                        out.setdefault(dst, kind)
    if mode in ('in', 'both'):
        for src, kind in g.refs_in.get(article, {}).items():
            if kind in types and (src not in out or EDGE_PRIORITY[kind] < EDGE_PRIORITY[out[src]]):
                out[src] = kind
    return out


def expand(seed_ranked: Sequence[str], hops: int = 1, mode: str = 'out', max_new: int | None = None, *,
           top: int | None = None, types: tuple[str, ...] = ARTICLE_EDGES, g: Graph | None = None) -> list[str]:
    """Seed order kept; neighbours of the first `top` seeds appended, ranked by (hop, best seed rank, edge type,
    code order). Only Division B article ids in the code database are emitted."""
    g = g or build_graph()
    pos = g.pos
    seeds = [a for a in dict.fromkeys(seed_ranked) if a in pos]
    out = list(seeds)
    seen = set(out)
    frontier = [(i, a) for i, a in enumerate(seeds[:top] if top else seeds)]
    added = 0
    for hop in range(hops):
        best: dict[str, tuple[int, int, int]] = {}
        for rank, a in frontier:
            for n, kind in neighbours(a, g, mode, types).items():
                if n in seen or n not in pos:
                    continue
                key = (rank, EDGE_PRIORITY[kind], pos[n])
                if n not in best or key < best[n]:
                    best[n] = key
        new = sorted(best, key=best.get)
        if max_new is not None:
            new = new[:max(0, max_new - added)]
        out.extend(new)
        seen.update(new)
        added += len(new)
        frontier = [(best[n][0], n) for n in new]
        if not frontier:
            break
    return out


def subsection_complete(seed_ranked: Sequence[str], top: int = 5, g: Graph | None = None) -> list[str]:
    """Seed order kept; then the subsection siblings of the top seeds, by seed rank then code order."""
    g = g or build_graph()
    seeds = [a for a in dict.fromkeys(seed_ranked) if a in g.same_subsection]
    out, seen = list(seeds), set(seeds)
    for a in seeds[:top]:
        for s in g.same_subsection[a]:
            if s not in seen:
                out.append(s)
                seen.add(s)
    return out


def pool(base: Sequence[str], size: int, *, seeds: int, mode: str = 'out', types: tuple[str, ...] = ARTICLE_EDGES,
         sibling_top: int = 0, g: Graph | None = None) -> list[str]:
    """A fixed-size pool: the top `seeds` of base, their graph neighbours (and subsection siblings of the top
    `sibling_top`), then the rest of base. Truncated to `size`."""
    g = g or build_graph()
    head = list(base[:seeds])
    grown = expand(head, 1, mode, types=types, g=g) if mode else head
    if sibling_top:
        sib = subsection_complete(head, top=sibling_top, g=g)[len(head):]
        grown = grown + [a for a in sib if a not in set(grown)]
    out = list(dict.fromkeys(list(grown) + list(base)))
    return out[:size]


# ---------------------------------------------------------------- evaluation


POOLS = (20, 40, 60, 100, 150, 200)


def _rank_of(ranked: Sequence[str], a: str) -> int | None:
    try:
        return ranked.index(a) + 1
    except ValueError:
        return None


def evaluate(fold: str = 'tune', recipes: dict | None = None) -> dict:
    from evals_dev.identify_bench import cases as C, metrics as M

    g = build_graph()
    arts = corpus.articles(DB)
    chosen = C.select(C.all_cases(), fold=fold)
    # bm25_v3 at the pipeline's limit (300) takes ~35 s per long description, so fan it out over processes.
    with ProcessPoolExecutor(max_workers=8) as ex:
        v3 = dict(zip([c.id for c in chosen], ex.map(bm25_v3, [c.description for c in chosen], [300] * len(chosen))))
    base = {c.id: {'bm25': bm25(c.description, 400), 'bm25_v3': v3[c.id]} for c in chosen}
    for c in chosen:
        b = base[c.id]
        b['rrf'] = rrf(b['bm25'], b['bm25_v3'])
        b['interleave'] = interleave(b['bm25_v3'], b['bm25'])
    unreachable = {c.id: [a for a in c.gold if a not in arts] for c in chosen}

    def summary(fn) -> dict:
        return M.ranking_summary([(fn(c), c.gold) for c in chosen], ks=(10, 20, 40, 60, 100, 150, 200))

    arms = {name: summary(lambda c, n=name: base[c.id][n]) for name in ('bm25', 'bm25_v3', 'rrf', 'interleave')}

    expansions = {}
    for arm in ('bm25', 'bm25_v3', 'rrf'):
        for seeds in (5, 10, 20):
            for mode in ('out', 'in', 'both'):
                expansions[f'{arm}|expand-{mode}|seeds{seeds}'] = summary(
                    lambda c, a=arm, s=seeds, m=mode: expand(base[c.id][a][:s], 1, m, g=g))
            expansions[f'{arm}|expand-out+sub|seeds{seeds}'] = summary(
                lambda c, a=arm, s=seeds: expand(base[c.id][a][:s], 1, 'out', types=ARTICLE_EDGES + ('subsection',), g=g))
            expansions[f'{arm}|expand-out|hops2|seeds{seeds}'] = summary(
                lambda c, a=arm, s=seeds: expand(base[c.id][a][:s], 2, 'out', g=g))
            expansions[f'{arm}|siblings|seeds{seeds}'] = summary(
                lambda c, a=arm, s=seeds: subsection_complete(base[c.id][a][:s], top=s, g=g))

    # Pool recipes: complete recall at each pool size.
    recipes = recipes or {}
    if not recipes:
        for arm in ('bm25', 'bm25_v3', 'rrf', 'interleave'):
            recipes[f'{arm}'] = dict(arm=arm, seeds=0, mode=None)
            for seeds in (3, 5, 8, 10, 15, 20):
                for mode in ('out', 'both'):
                    recipes[f'{arm}+{mode}@{seeds}'] = dict(arm=arm, seeds=seeds, mode=mode)
                recipes[f'{arm}+out+sub@{seeds}'] = dict(arm=arm, seeds=seeds, mode='out',
                                                         types=ARTICLE_EDGES + ('subsection',))
                for sib in (1, 3, 5):
                    if sib <= seeds:
                        recipes[f'{arm}+out@{seeds}+sib{sib}'] = dict(arm=arm, seeds=seeds, mode='out', sibling_top=sib)
                        recipes[f'{arm}+sib{sib}@{seeds}'] = dict(arm=arm, seeds=seeds, mode=None, sibling_top=sib)

    def build(c, r, size):
        b = base[c.id][r['arm']]
        if not r['seeds']:
            return b[:size]
        return pool(b, size, seeds=r['seeds'], mode=r.get('mode'), types=r.get('types', ARTICLE_EDGES),
                    sibling_top=r.get('sibling_top', 0), g=g)

    curve = {}
    for name, r in recipes.items():
        row = {}
        for size in POOLS:
            lists = [build(c, r, size) for c in chosen]
            assert all(len(x) <= size and all(a in arts for a in x) for x in lists)
            row[str(size)] = round(sum(M.complete_at(x, c.gold) for x, c in zip(lists, chosen)) / len(chosen), 4)
            row[f'recall{size}'] = round(sum(len(set(c.gold) & set(x)) for x, c in zip(lists, chosen))
                                         / sum(len(c.gold) for c in chosen), 4)
        curve[name] = row
    return dict(fold=fold, cases=len(chosen), sources=sorted({c.source for c in chosen}),
                gold_articles=sum(len(c.gold) for c in chosen),
                unreachable_gold={k: v for k, v in unreachable.items() if v},
                arms=arms, expansions=expansions, curve=curve,
                _build=build, _chosen=chosen, _base=base)


def _best(curve: dict, size: int) -> list[tuple[str, float, float]]:
    rows = [(n, r[str(size)], r[f'recall{size}']) for n, r in curve.items()]
    return sorted(rows, key=lambda x: (-x[1], -x[2], len(x[0])))


def graph_stats(g: Graph) -> dict:
    by_type: dict[str, int] = defaultdict(int)
    for dsts in g.refs_out.values():
        for kind in dsts.values():
            by_type[kind] += 1
    for cs in g.container_out.values():
        for kind in cs.values():
            by_type[kind] += 1
    return dict(articles=len(g.order), with_out_refs=len(g.refs_out), with_in_refs=len(g.refs_in),
                edges=dict(by_type))


def main(argv: list[str]) -> int:
    RESULTS.mkdir(exist_ok=True)
    g = build_graph()
    tune = evaluate('tune')
    best40, best60 = _best(tune['curve'], 40), _best(tune['curve'], 60)
    # Recommend the recipe that is best at 60 among those tied-best at 40 when possible.
    top40 = {n for n, v, _ in best40 if v == best40[0][1]}
    pick = next((n for n, v, _ in best60 if n in top40 and v == best60[0][1]), best60[0][0])
    misses = []
    for c in tune['_chosen']:
        for size in (60,):
            lst = tune['_build'](c, _recipe_of(pick), size)
            missing = [a for a in c.gold if a not in lst]
            if missing:
                wide = tune['_build'](c, _recipe_of(pick), 400)
                misses.append(dict(case=c.id, source=c.source,
                                   gold={a: {'rank': _rank_of(wide, a), 'missed': a in missing,
                                             'in_codedb': a in corpus.articles(DB)} for a in c.gold},
                                   description=c.description[:160]))
    out = dict(graph=graph_stats(g), tune={k: v for k, v in tune.items() if not k.startswith('_')},
               recommended=pick, recommended_recipe=_recipe_of(pick),
               best_at_40=best40[:10], best_at_60=best60[:10], misses_at_60=misses)
    if '--test' in argv:
        test = evaluate('test', recipes={pick: _recipe_of(pick), 'rrf': _recipe_of('rrf'), 'bm25': _recipe_of('bm25'),
                                         'bm25_v3': _recipe_of('bm25_v3')})
        out['test'] = {k: v for k, v in test.items() if not k.startswith('_')}
    (RESULTS / 'lexical.json').write_text(json.dumps(out, indent=1, default=list))
    print(json.dumps({'recommended': pick, 'tune': tune['curve'][pick],
                      'test': out.get('test', {}).get('curve', {}).get(pick)}, indent=1))
    return 0


def _recipe_of(name: str) -> dict:
    """Parse a recipe name produced by evaluate() back into its settings."""
    m = re.fullmatch(r'(?P<arm>[a-z0-9_]+)(?:\+(?P<rest>.*))?', name)
    arm, rest = m.group('arm'), m.group('rest')
    if not rest:
        return dict(arm=arm, seeds=0, mode=None)
    if (s := re.fullmatch(r'(out|both)@(\d+)', rest)):
        return dict(arm=arm, seeds=int(s.group(2)), mode=s.group(1))
    if (s := re.fullmatch(r'out\+sub@(\d+)', rest)):
        return dict(arm=arm, seeds=int(s.group(1)), mode='out', types=ARTICLE_EDGES + ('subsection',))
    if (s := re.fullmatch(r'out@(\d+)\+sib(\d+)', rest)):
        return dict(arm=arm, seeds=int(s.group(1)), mode='out', sibling_top=int(s.group(2)))
    if (s := re.fullmatch(r'sib(\d+)@(\d+)', rest)):
        return dict(arm=arm, seeds=int(s.group(2)), mode=None, sibling_top=int(s.group(1)))
    raise ValueError(name)


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
