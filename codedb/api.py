"""Read-only public queries. Identifiers are scoped by document AND division."""
from __future__ import annotations

import json
from contextlib import closing
from pathlib import Path

from . import ids, store

_JSON = {'clauses', 'fs', 'objectives', 'brackets', 'attribution_notes', 'intents',
         'only_in_intent', 'only_in_ae'}


class AmbiguousProvisionError(ValueError):
    """The caller must select a division for an identifier shared by divisions."""


def record(row):
    out = dict(row)
    for key in _JSON & out.keys():
        if isinstance(out[key], str):
            out[key] = json.loads(out[key])
    return out


def resolve(con, provision_id, doc='NBC-AE', division=None):
    pid = ids.canon(provision_id)
    rows = con.execute('SELECT * FROM provisions WHERE doc=? AND id=?' +
                       (' AND division=?' if division else '') + ' ORDER BY division',
                       (doc, pid, division.upper()) if division else (doc, pid)).fetchall()
    if len(rows) > 1:
        raise AmbiguousProvisionError(f'{pid} occurs in divisions {", ".join(r["division"] for r in rows)}; specify division')
    return record(rows[0]) if rows else None


def attribution_rows(con, provision, *, inherited=True):
    """Return source rows, preserving application notes and the actual attributed target.

    Articles/sentences collect their descendants. Clause inheritance follows only an
    explicit parent row; exception-root heuristics are exposed separately, never implied.
    """
    if provision['division'] != 'B':
        return []
    pid, doc = provision['id'], provision['doc']
    rows = con.execute('SELECT * FROM attributions WHERE doc=? AND (provision_id=? OR provision_id LIKE ?) '
                       'ORDER BY pdf_page,seq', (doc, pid, pid + '(%')).fetchall()
    if not rows and inherited and provision['level'] in ('clause', 'subclause'):
        for parent in ids.parse(pid).ancestors():
            if parent.level not in ('sentence', 'clause'):
                break
            rows = con.execute('SELECT * FROM attributions WHERE doc=? AND provision_id=? ORDER BY seq',
                               (doc, str(parent))).fetchall()
            if rows:
                break
    return [record(r) for r in rows]


def lookup(provision_id: str, *, doc='NBC-AE', division=None, db_path: Path | str | None = None):
    """Return a provision with source rows, notes and explanatory intents; None if absent.

    Raise AmbiguousProvisionError when an unqualified id belongs to multiple divisions.
    National intent statements are explanatory only; their comparison is always included.
    """
    with closing(store.connect(db_path)) as con:
        out = resolve(con, provision_id, doc, division)
        if out is None:
            return None
        pid, div = out['id'], out['division']
        children_ = [record(r) for r in con.execute('SELECT * FROM provisions WHERE doc=? AND division=? '
                                                   'AND parent_id=? ORDER BY sort_key', (doc, div, pid))]
        out['children'] = children_
        if out['level'] == 'article':
            out['text'] = '\n'.join([out['text']] + [r['text'] for r in children_]).strip()
            out['pdf_page_end'] = max([out['pdf_page_end']] + [r['pdf_page_end'] for r in children_])
        out['attributions'] = attribution_rows(con, out)
        status = con.execute('SELECT * FROM attribution_status WHERE doc=? AND provision_id=?', (doc, pid)).fetchone()
        out['attribution_status'] = record(status) if status and div == 'B' else None
        out['notes'] = [record(r) for r in con.execute('SELECT DISTINCT n.* FROM notes n JOIN note_links l '
                      'ON n.doc=l.doc AND n.division=l.division AND n.note_id=l.note_id '
                      'WHERE l.doc=? AND l.division=? AND (l.provision_id=? OR l.provision_id LIKE ?) '
                      'ORDER BY n.pdf_page', (doc, div, pid, pid + '(%'))]
        out['intents'] = [record(r) for r in con.execute('SELECT * FROM intents WHERE code_doc=? '
                          'AND (provision_id=? OR provision_id LIKE ?) ORDER BY pdf_page,block_seq',
                          (doc, pid, pid + '(%'))] if div == 'B' else []
        out['intent_comparison'] = [record(r) for r in con.execute('SELECT * FROM intent_comparison WHERE code_doc=? '
                      'AND (provision_id=? OR provision_id LIKE ?)', (doc, pid, pid + '(%'))] if div == 'B' else []
        label = con.execute('SELECT label FROM docs WHERE doc=?', (doc,)).fetchone()[0]
        out['citation'] = f'{label}, Div {div}, {out["level"].title()} {pid} [PDF p.{out["pdf_page"]}]'
        return out


def children(provision_id: str, *, doc='NBC-AE', division=None, db_path=None):
    """Immediate children in code order. A missing parent has no children."""
    with closing(store.connect(db_path)) as con:
        parent = resolve(con, provision_id, doc, division)
        if not parent:
            return []
        return [record(r) for r in con.execute('SELECT * FROM provisions WHERE doc=? AND division=? AND parent_id=? '
                                              'ORDER BY sort_key', (doc, parent['division'], parent['id']))]


def search(terms: str, *, doc='NBC-AE', division=None, limit=20, db_path=None):
    """Ranked search of titles and sentences. Terms are words, not SQL/FTS syntax.

    The signature is unchanged: `limit` is still 1..1000, default 20. The
    engine route continues to clamp the caller's limit. Ranking is the
    shipped variant from the recall comparison (`codedb.search_rank`).
    """
    from .search_rank import SHIPPED, search_variant
    return search_variant(terms, SHIPPED, doc=doc, division=division, limit=limit, db_path=db_path)
