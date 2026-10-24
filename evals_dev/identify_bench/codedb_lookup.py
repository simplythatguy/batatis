"""Read-only NBC(AE) 2023 2nd printing lookups for verifying researched citations.

  .venv/bin/python -m evals_dev.identify_bench.codedb_lookup article 9.10.15.5.
  .venv/bin/python -m evals_dev.identify_bench.codedb_lookup text 9.10.15.5.
  .venv/bin/python -m evals_dev.identify_bench.codedb_lookup search "limiting distance soffit"
  .venv/bin/python -m evals_dev.identify_bench.codedb_lookup subsection 9.10.15.
"""
from __future__ import annotations

import re
import sqlite3
import sys
from pathlib import Path

DB = Path(__file__).resolve().parents[2] / 'codedb' / 'build' / 'codedb.sqlite'


def connect():
    return sqlite3.connect(f'file:{DB}?mode=ro', uri=True)


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print(__doc__)
        return 2
    cmd, arg = argv[0], ' '.join(argv[1:])
    con = connect()
    if cmd == 'article':
        rows = con.execute("select id, part, title from provisions where doc='NBC-AE' and division='B' "
                           "and level='article' and id=?", (arg,)).fetchall()
        print(rows[0] if rows else f'{arg}: not a Division B article')
    elif cmd == 'text':
        title = con.execute("select title from provisions where doc='NBC-AE' and division='B' and level='article' "
                            "and id=?", (arg,)).fetchone()
        if not title:
            print(f'{arg}: not a Division B article')
            return 1
        print(f'{arg} {title[0]}')
        for pid, text in con.execute("select id, text from provisions where doc='NBC-AE' and division='B' "
                                     "and article=? and level in ('sentence','clause','subclause') "
                                     "order by sort_key", (arg,)):
            print(f'  {pid} {re.sub(chr(92) + "s+", " ", text or "").strip()}')
    elif cmd == 'subsection':
        for row in con.execute("select id, title from provisions where doc='NBC-AE' and division='B' "
                               "and level='article' and id like ? order by sort_key", (arg + '%',)):
            print(row)
    elif cmd == 'search':
        words = [w for w in re.findall(r'[A-Za-z][A-Za-z0-9-]{2,}', arg)]
        query = ' AND '.join('"%s"' % w for w in words)
        seen = []
        for (pid,) in con.execute("select id from provisions_fts where provisions_fts match ? and doc='NBC-AE' "
                                  "and division='B' order by bm25(provisions_fts) limit 200", (query,)):
            m = re.match(r'(\d+\.\d+\.\d+\.\d+\.)', pid)
            if m and m.group(1) not in seen:
                seen.append(m.group(1))
        for art in seen[:25]:
            t = con.execute("select title from provisions where doc='NBC-AE' and division='B' and level='article' "
                            "and id=?", (art,)).fetchone()
            print(art, t[0] if t else '')
        if not seen:
            print('no matches')
    else:
        print(__doc__)
        return 2
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
