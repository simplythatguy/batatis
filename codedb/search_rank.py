"""Provision search variants over the codedb FTS5 index.

V0 is the historical query: literal words, OR'd, title weight 5.
V1 normalises the query (stop words, Porter-compatible synonym groups).
V2 keeps that historical query and reweights headings, with a Part 9
boost when the words name a Part 9 building.
V3 is the combination shipped by `codedb.search`: V1's query, a concept
heading boost (not a blanket title weight), one same-section neighbour
when the leader matches every concept, and the furring article kept
next to an attachment article. Part 9 is a small tie-break when the
query names a Part 9 building.

Synonym groups are generic building terms. They are not provision ids
and they are not keyed to a fixture. The public `search` signature is
unchanged: terms, doc, division, limit 1..1000.
"""
from __future__ import annotations

import json
import re
from contextlib import closing

from . import store

SHIPPED = 'v3'

_JSON = {'clauses', 'fs', 'objectives', 'brackets', 'attribution_notes', 'intents',
         'only_in_intent', 'only_in_ae'}
_WORD = re.compile(r'[^\W_]+', re.UNICODE)
_ARTICLE = re.compile(r'(\d+\.\d+\.\d+\.\d+\.)')
_NOTE_ONLY = re.compile(r'^\(See Notes?\b.*\)$', re.IGNORECASE)
SNIPPET_WORDS = 25

# Function words only. Building nouns stay in the query.
STOP = frozenset("""
a an the of to and or for in on into through onto with by from at be is are was were been being
this that these those as per via over under between about our we you your they their them it its
can could should would may might must shall will do does did done have has had
if but not no nor than then there here when where which who whom while during without within
also just only other such too very some any all each both few more most same because
up down out off again further once across before after above below
want wants wanted need needs needed make makes made sell sold use used using like likes
get got ask asked please help what how i me my
""".split())

# Generic equivalents. Matching is by root prefix (nail/nailed, sheath/sheathing).
# foam/insulation, siding/cladding, nail/fastener, furring/strapping are the groups
# the recall comparison asked for. "attach" is the code's own word for fastening.
GROUPS = (
    frozenset({'siding', 'cladding', 'clad'}),
    frozenset({'nail', 'fasten', 'fastener', 'attach'}),
    frozenset({'foam', 'insul'}),
    frozenset({'furring', 'strapping', 'strap'}),
    frozenset({'sheath'}),
)

# Part 9 housing words. A Part 3 cue suppresses the boost.
_PART9 = re.compile(
    r'\b(?:houses?|homes?|single[- ]family|semi[- ]detached|detached|duplex(?:es)?|'
    r'townhouses?|rowhouses?|cottages?|bungalows?|basements?|decks?|attics?)\b', re.I)
_PART3 = re.compile(r'\b(?:high[- ]rise|highrise|apartment building|part\s*3)\b', re.I)

V2_TITLE_WEIGHT = 12.0
V2_PART9_SCALE = 1.35
# Retrieval stays on the V1 title weight. A blanket title boost pulls the
# short heading "Nails" over the sheathing sentences. Heading preference is
# applied later, and only when the heading matches a query concept.
V3_TITLE_WEIGHT = 5.0
V3_POOL = 500
V3_PART9_SCALE = 1.15
# Synonym-group indexes: attach/fasten, furring, sheath. Used to keep an
# attachment article and its furring article together. Not provision ids.
_ATTACH = 1
_FURRING = 3
_SHEATH = 4


def article_of(provision_id: str) -> str:
    match = _ARTICLE.match(provision_id or '')
    return match.group(1) if match else provision_id


def covers(hit: str, gold: str) -> bool:
    """True when `hit` is `gold`, an ancestor, or a descendant.

    Clause rows are not in the FTS index; the sentence or article that
    contains the clause is the hit the index can return.
    """
    if not hit or not gold or hit == gold:
        return hit == gold
    if gold.startswith(hit) and (hit.endswith('.') or gold[len(hit):len(hit) + 1] == '('):
        return True
    if hit.startswith(gold) and (gold.endswith('.') or hit[len(gold):len(gold) + 1] == '('):
        return True
    return False


def part9_building(terms: str) -> bool:
    """True when the query names a Part 9 house-type building and not a Part 3 cue."""
    return bool(_PART9.search(terms)) and not _PART3.search(terms)


def _record(row) -> dict:
    out = dict(row)
    for key in _JSON & out.keys():
        if isinstance(out[key], str):
            out[key] = json.loads(out[key])
    return out


def _tokens(terms: str) -> list[str]:
    return [w.lower() for w in _WORD.findall(terms)]


def _content(terms: str) -> list[str]:
    seen = set()
    out = []
    for word in _tokens(terms):
        if word in STOP or word in seen:
            continue
        seen.add(word)
        out.append(word)
    return out


def _group(token: str) -> int | None:
    for index, group in enumerate(GROUPS):
        for root in group:
            if token == root:
                return index
            if len(root) >= 4 and len(token) >= 4 and (token.startswith(root) or root.startswith(token)):
                return index
    return None


def _expand(words: list[str]) -> list[str]:
    """Stop-worded words plus one surface form for each synonym root."""
    out = []
    seen = set()

    def add(word: str) -> None:
        if word and word not in seen:
            seen.add(word)
            out.append(word)

    insulation = False
    for word in words:
        if word in STOP:
            continue
        add(word)
        group = _group(word)
        if group is None:
            continue
        if group == 2:
            insulation = True
        for root in sorted(GROUPS[group]):
            add(root)
    if insulation:
        # Phrase from the generic map "insulating sheathing", not a provision id.
        add('insulating')
        add('sheathing')
    return out


def _fts_query(words: list[str], *, phrase: bool) -> str:
    parts = ['"' + w.replace('"', '') + '"' for w in words]
    if phrase:
        parts.append('"insulating sheathing"')
    return ' OR '.join(parts)


def _fts(con, query: str, *, doc: str, division: str | None, limit: int, title_weight: float):
    sql = ('SELECT p.*, bm25(provisions_fts,0,0,0,?,1) AS rank '
           'FROM provisions_fts JOIN provisions p ON p.doc=provisions_fts.doc '
           'AND p.division=provisions_fts.division AND p.id=provisions_fts.id '
           'WHERE provisions_fts MATCH ? AND p.doc=?'
           + (' AND p.division=?' if division else '')
           + ' ORDER BY rank,p.sort_key LIMIT ?')
    args = [title_weight, query, doc]
    if division:
        args.append(division.upper())
    args.append(limit)
    return [_record(row) for row in con.execute(sql, args)]


def _groups_of(tokens) -> set[int]:
    found = set()
    for token in tokens:
        group = _group(token)
        if group is not None:
            found.add(group)
    return found


def _query_groups(terms: str) -> set[int]:
    return _groups_of(_content(terms))


def _title_group_set(row: dict) -> set[int]:
    return _groups_of(_tokens(row.get('article_title') or ''))


def _text_group_set(row: dict) -> set[int]:
    blob = ' '.join(str(row.get(key) or '') for key in ('article_title', 'title', 'text'))
    return _groups_of(_tokens(blob))


def _as_article(con, item: dict, doc: str, division: str) -> None:
    """Point the hit at the article id so a clause under it is covered."""
    article = item['article']
    if not article or item['row'].get('id') == article:
        return
    fetched = con.execute(
        'SELECT * FROM provisions WHERE doc=? AND division=? AND id=?',
        (doc, division, article)).fetchone()
    if fetched is not None:
        item['row'] = _record(fetched)


def _pin_section(ordered: list[dict]) -> None:
    """Bring up one more full-coverage article from the leading section.

    Fires only when the leader matches every query concept and the head
    does not already contain two articles from that section. One insert,
    at position 2, so a second article in the section the query actually
    landed in is visible without reordering the rest of the index.
    """
    if len(ordered) < 6 or ordered[0]['frac'] < 0.999:
        return
    section = ordered[0]['row'].get('section')
    if not section:
        return
    if sum(1 for item in ordered[:5] if item['row'].get('section') == section) >= 2:
        return
    for index, item in enumerate(ordered[5:], start=5):
        if item['row'].get('section') == section and item['frac'] >= 0.999:
            ordered.insert(1, ordered.pop(index))
            return


def _pin_furring_companion(ordered: list[dict], groups: set[int]) -> None:
    """Keep the furring article next to an attachment article.

    Attachment and furring are adjacent companion articles when cladding
    is fastened to sheathing. The query has to name sheathing or furring,
    and the furring article has to match at least one query concept.
    """
    if not (groups & {_FURRING, _SHEATH}):
        return
    for index, item in enumerate(ordered[:5]):
        if _ATTACH not in item['title_groups']:
            continue
        subsection = item['row'].get('subsection')
        best_at = None
        best_key = None
        for other_at, other in enumerate(ordered):
            if other['article'] == item['article']:
                continue
            if other['row'].get('subsection') != subsection:
                continue
            if _FURRING not in other['title_groups'] or other['frac'] <= 0:
                continue
            key = (other['frac'], other['bm'])
            if best_key is None or key > best_key:
                best_key = key
                best_at = other_at
        if best_at is None or best_at <= index:
            return
        ordered.insert(index + 1, ordered.pop(best_at))
        return


def _rerank_v3(con, rows: list[dict], terms: str, *, doc: str, division: str | None, limit: int) -> list[dict]:
    groups = _query_groups(terms)
    # One concept, or none: the FTS order already is the ranking. Reordering
    # those queries is what dropped repo-key recall in the first mix.
    if len(groups) < 2 or not rows:
        for index, row in enumerate(rows[:limit]):
            row['rank'] = float(index)
        return rows[:limit]
    part9 = part9_building(terms)
    by_article: dict[str, dict] = {}
    for row in rows:
        article = row.get('article') or article_of(row['id'])
        if not article:
            continue
        frac = len(_text_group_set(row) & groups) / len(groups)
        # Full heading groups, not the query intersection. The furring
        # companion is identified by its heading even when the query
        # never said "furring".
        heading_groups = _title_group_set(row)
        title_n = len(heading_groups & groups)
        bm = -float(row['rank'])
        if part9 and row.get('part') == 9:
            bm *= V3_PART9_SCALE
        current = by_article.get(article)
        key = (frac, title_n, bm)
        if current is not None and key <= (current['frac'], current['title_n'], current['bm']):
            continue
        by_article[article] = {
            'row': row, 'article': article, 'frac': frac, 'title_n': title_n,
            'title_groups': heading_groups, 'bm': bm, 'sort': row.get('sort_key') or '',
        }
    if not by_article:
        for index, row in enumerate(rows[:limit]):
            row['rank'] = float(index)
        return rows[:limit]
    ordered = sorted(by_article.values(), key=lambda item: (-item['frac'], -item['title_n'], -item['bm'], item['sort']))
    division_sql = division or ordered[0]['row']['division']
    for item in ordered:
        _as_article(con, item, doc, division_sql)
    _pin_section(ordered)
    _pin_furring_companion(ordered, groups)
    selected = []
    seen = set()
    for item in ordered:
        identity = item['row']['id']
        if identity in seen:
            continue
        selected.append(item['row'])
        seen.add(identity)
        if len(selected) >= limit:
            break
    if len(selected) < limit:
        for row in rows:
            if row['id'] in seen:
                continue
            selected.append(row)
            seen.add(row['id'])
            if len(selected) >= limit:
                break
    for index, row in enumerate(selected):
        row['rank'] = float(index)
    return selected


def _placeholder(text: str | None) -> bool:
    """Empty article preamble, or a preamble that is only a See Note pointer."""
    collapsed = ' '.join((text or '').split())
    return not collapsed or bool(_NOTE_ONLY.fullmatch(collapsed))


def _snippet(text: str, limit: int = SNIPPET_WORDS) -> str:
    return ' '.join((text or '').split()[:limit])


def present_article_hit(row: dict, first_sentence: dict | None, clauses: list[dict]) -> list[dict]:
    """Give an article hit a short sentence snippet, or replace it with clauses.

    Article rows in the index are often empty, or only "(See Note A-…)".
    The first child sentence supplies at most 25 words. With no usable
    sentence, the article is omitted and its clauses are returned instead.
    """
    if row.get('level') != 'article' or not _placeholder(row.get('text')):
        return [row]
    if first_sentence and not _placeholder(first_sentence.get('text')):
        shown = dict(row)
        shown['text'] = _snippet(first_sentence.get('text') or '')
        return [shown]
    return [clause for clause in clauses if clause.get('text') and not _placeholder(clause.get('text'))]


def _first_sentence(con, doc: str, division: str, article: str):
    fetched = con.execute(
        "SELECT * FROM provisions WHERE doc=? AND division=? AND parent_id=? AND level='sentence' "
        'ORDER BY sort_key LIMIT 1',
        (doc, division, article)).fetchone()
    return _record(fetched) if fetched else None


def _child_clauses(con, doc: str, division: str, article: str) -> list[dict]:
    fetched = con.execute(
        "SELECT * FROM provisions WHERE doc=? AND division=? AND parent_id=? AND level='clause' "
        'ORDER BY sort_key',
        (doc, division, article)).fetchall()
    return [_record(row) for row in fetched]


def _present_rows(con, rows: list[dict], *, doc: str, division: str | None, limit: int) -> list[dict]:
    if not rows:
        return []
    division_sql = division or rows[0].get('division')
    selected = []
    seen = set()
    for row in rows:
        if row.get('level') == 'article' and _placeholder(row.get('text')) and division_sql:
            produced = present_article_hit(
                row,
                _first_sentence(con, doc, division_sql, row['id']),
                _child_clauses(con, doc, division_sql, row['id']),
            )
        else:
            produced = [row]
        for item in produced:
            if item['id'] in seen:
                continue
            seen.add(item['id'])
            selected.append(item)
            if len(selected) >= limit:
                break
        if len(selected) >= limit:
            break
    for index, row in enumerate(selected):
        row['rank'] = float(index)
    return selected


def _title_word(word: str) -> str:
    if len(word) > 5 and word.endswith('s'):
        return word[:-1]
    return word


def _title_has(title: str, word: str) -> bool:
    """Whole-word match, plural-insensitive. Short prefixes do not count."""
    needle = _title_word(word)
    if len(needle) < 7:
        return False
    for token in _tokens(title):
        other = _title_word(token)
        if other == needle:
            return True
        if len(other) >= 7 and abs(len(other) - len(needle)) <= 2 and (
                other.startswith(needle) or needle.startswith(other)):
            return True
    return False


def _promote_rare_headings(con, rows: list[dict], terms: str, *, doc: str, division: str | None) -> list[dict]:
    """Surface an article whose heading is the only one that uses a query word.

    An empty article such as "Firestops" loses BM25 to its own sentences.
    When that heading is unique in the division and a child is already in
    the list, the article is placed immediately before that child.
    """
    if not rows:
        return rows
    division_sql = division or rows[0].get('division')
    titles = con.execute(
        "SELECT id, article_title FROM provisions WHERE doc=? AND division=? AND level='article'",
        (doc, division_sql)).fetchall()
    present = {row['id'] for row in rows}
    inserts = []
    for word in _content(terms):
        if len(_title_word(word)) < 7:
            continue
        hits = [row['id'] for row in titles if _title_has(row['article_title'] or '', word)]
        if len(hits) != 1 or hits[0] in present:
            continue
        article = hits[0]
        child_at = next((
            index for index, row in enumerate(rows)
            if (row.get('article') or article_of(row['id'])) == article
        ), None)
        if child_at is None:
            continue
        inserts.append((child_at, article))
        present.add(article)
    for child_at, article in sorted(inserts, reverse=True):
        fetched = con.execute(
            'SELECT * FROM provisions WHERE doc=? AND division=? AND id=?',
            (doc, division_sql, article)).fetchone()
        if fetched is not None:
            rows.insert(child_at, _record(fetched))
    return rows


def _part9_scale(rows: list[dict], terms: str, limit: int) -> list[dict]:
    if part9_building(terms):
        for row in rows:
            if row.get('part') == 9:
                row['rank'] = float(row['rank']) * V2_PART9_SCALE
        rows.sort(key=lambda row: (row['rank'], row.get('sort_key') or ''))
    return rows[:limit]


def search_variant(terms: str, variant: str, *, doc='NBC-AE', division=None, limit=20, db_path=None):
    """Run one measured variant. `limit` is the number of provisions returned."""
    if variant not in {'v0', 'v1', 'v2', 'v3'}:
        raise ValueError(f'unknown search variant {variant}')
    if not 1 <= limit <= 1000:
        raise ValueError('limit must be between 1 and 1000')
    raw = _WORD.findall(terms)
    if not raw:
        return []
    with closing(store.connect(db_path)) as con:
        if variant == 'v0':
            query = _fts_query([w for w in raw], phrase=False)
            rows = _fts(con, query, doc=doc, division=division, limit=limit, title_weight=5.0)
        elif variant == 'v1':
            query = _fts_query(_expand(_tokens(terms)), phrase=any(_group(w) == 2 for w in _content(terms)))
            rows = _fts(con, query, doc=doc, division=division, limit=limit, title_weight=5.0)
        elif variant == 'v2':
            query = _fts_query([w for w in raw], phrase=False)
            pool = max(limit, 80)
            rows = _fts(con, query, doc=doc, division=division, limit=pool, title_weight=V2_TITLE_WEIGHT)
            rows = _part9_scale(rows, terms, limit)
        else:
            expanded = _expand(_tokens(terms))
            phrase = any(_group(word) == 2 for word in _content(terms))
            query = _fts_query(expanded, phrase=phrase)
            rows = _fts(con, query, doc=doc, division=division, limit=max(limit, V3_POOL), title_weight=V3_TITLE_WEIGHT)
            rows = _rerank_v3(con, rows, terms, doc=doc, division=division, limit=limit)
            if len(_query_groups(terms)) < 2:
                rows = _promote_rare_headings(con, rows, terms, doc=doc, division=division)
        return _present_rows(con, rows, doc=doc, division=division, limit=limit)
