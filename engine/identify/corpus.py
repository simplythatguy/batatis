"""Division B article corpus and BM25 article ranking over codedb (read-only).

Ported from docs/research/2026-10-20-vision/jev-benchmark/scripts/corpus.py; behaviour unchanged except
that the database path is a parameter.
"""
from __future__ import annotations

import re
from contextlib import closing
from functools import lru_cache
from pathlib import Path

from codedb import store

STOP = set("""a an and are as at be been but by can for from has have if in into is it its may must not of on or
our shall should such than that the their then there these this those to under was were when where which while
who will with within without would per via any all each other also only more most than some same apply applies
applied ref allows allow accepts accept explains describes requirements requirement buildings building""".split())


@lru_cache(maxsize=4)
def articles(db_path: Path) -> dict[str, dict]:
    """{article id: {id, part, title, section, subsection, text}} in code order, for all Division B articles.

    text = the article's sentences, clauses and subclauses, whitespace-collapsed, de-duplicated."""
    with closing(store.connect(db_path)) as c:
        titles = {r['id']: r['title'] for r in c.execute(
            "select id, title from provisions where doc='NBC-AE' and division='B' and level in ('section','subsection')")}
        arts = {}
        for r in c.execute("select id, part, section, subsection, title from provisions where doc='NBC-AE' "
                           "and division='B' and level='article' order by sort_key"):
            arts[r['id']] = dict(id=r['id'], part=r['part'], title=r['title'], section=titles.get(r['section'], ''),
                                 subsection=titles.get(r['subsection'], ''), parts=[])
        for r in c.execute("select article, level, text from provisions where doc='NBC-AE' and division='B' "
                           "and level in ('sentence','clause','subclause') order by sort_key"):
            a = arts.get(r['article'])
            if a is None or not r['text']:
                continue
            t = re.sub(r'\s+', ' ', r['text']).strip()
            if a['parts'] and t in a['parts'][-1]:
                continue
            a['parts'].append(t)
    for a in arts.values():
        a['text'] = ' '.join(a.pop('parts'))
    return arts


def card(a: dict, n: int | None = 700) -> str:
    """Heading path plus the first n characters of the article text (n=None: full text)."""
    head = f"{a['title']} (Part {a['part']} > {a['section']} > {a['subsection']})"
    body = a['text'] if n is None or len(a['text']) <= n else a['text'][:n] + '...'
    return f'{head}: {body}'


def bm25_rank(query: str, db_path: Path, limit: int = 3000) -> list[str]:
    """Article ids ranked by their best provision's FTS5 BM25 score."""
    words = [w for w in re.findall(r'[a-z][a-z0-9-]{2,}', query.lower()) if w not in STOP]
    if not words:
        return []
    q = ' OR '.join('"%s"' % w.replace('"', '') for w in dict.fromkeys(words))
    best: dict[str, float] = {}
    with closing(store.connect(db_path)) as c:
        for r in c.execute("select id, bm25(provisions_fts, 0, 0, 0, 4.0, 1.0) as s from provisions_fts where "
                           "provisions_fts match ? and doc='NBC-AE' and division='B' order by s limit ?", (q, limit)):
            m = re.match(r'(\d+\.\d+\.\d+\.\d+\.)', r['id'])
            if not m:
                continue
            art = m.group(1)
            if art not in best or r['s'] < best[art]:
                best[art] = r['s']
    return [a for a, _ in sorted(best.items(), key=lambda kv: kv[1])]
