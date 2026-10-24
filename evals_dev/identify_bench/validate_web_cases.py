"""Validate researched precedent cases before they join the identify benchmark.

  .venv/bin/python -I -m evals_dev.identify_bench.validate_web_cases FILE.json [--db codedb/build/codedb.sqlite]

A case is usable only when every gold and context id is an NBC(AE) 2023 2nd printing Division B article
in the code database, the description carries no article/sentence numbers, and the source is cited.
"""
from __future__ import annotations

import argparse
import json
import re
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ARTICLE = re.compile(r'^\d{1,2}\.\d{1,2}\.\d{1,2}\.\d{1,2}\.$')
NUMBERED = re.compile(r'\b\d{1,2}\.\d{1,2}\.\d{1,2}(\.\d{1,2})?\b')
REQUIRED = ('id', 'source', 'description', 'gold')
SOURCE_KEYS = ('url', 'title', 'issuer', 'edition_cited', 'excerpt')


def division_b_articles(db: Path) -> dict[str, str]:
    con = sqlite3.connect(f'file:{db}?mode=ro', uri=True)
    try:
        return dict(con.execute("select id, title from provisions where doc='NBC-AE' and division='B' "
                                "and level='article'").fetchall())
    finally:
        con.close()


def problems(cases: list, arts: dict[str, str]) -> list[str]:
    out, seen = [], set()
    for n, case in enumerate(cases):
        where = f'case {n} ({case.get("id", "?") if isinstance(case, dict) else "?"})'
        if not isinstance(case, dict):
            out.append(f'{where}: not an object')
            continue
        for key in REQUIRED:
            if not case.get(key):
                out.append(f'{where}: missing {key}')
        if case.get('id') in seen:
            out.append(f'{where}: duplicate id')
        seen.add(case.get('id'))
        source = case.get('source') or {}
        for key in SOURCE_KEYS:
            if not isinstance(source, dict) or not source.get(key):
                out.append(f'{where}: source.{key} missing')
        text = case.get('description') or ''
        if NUMBERED.search(text):
            out.append(f'{where}: description contains a code number ({NUMBERED.search(text).group(0)})')
        if len(text.split()) < 25:
            out.append(f'{where}: description under 25 words')
        for field in ('gold', 'context'):
            for art in case.get(field) or []:
                if not isinstance(art, str) or not ARTICLE.match(art):
                    out.append(f'{where}: {field} id {art!r} is not an article id like 9.10.15.5.')
                elif art not in arts:
                    out.append(f'{where}: {field} {art} is not a Division B article in the code database')
        mapped = {m.get('article') for m in case.get('mapping') or [] if isinstance(m, dict)}
        for art in case.get('gold') or []:
            if art not in mapped:
                out.append(f'{where}: gold {art} has no mapping entry (as-cited number, edition, verification)')
        if set(case.get('gold') or []) & set(case.get('context') or []):
            out.append(f'{where}: an article is in both gold and context')
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('file')
    ap.add_argument('--db', default=str(ROOT / 'codedb' / 'build' / 'codedb.sqlite'))
    a = ap.parse_args(argv)
    cases = json.loads(Path(a.file).read_text())
    if not isinstance(cases, list):
        print('top level must be a JSON list of cases')
        return 1
    found = problems(cases, division_b_articles(Path(a.db)))
    for line in found:
        print(line)
    print(f'{len(cases)} cases, {len(found)} problems')
    return 1 if found else 0


if __name__ == '__main__':
    sys.exit(main())
