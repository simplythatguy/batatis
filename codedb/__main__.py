"""python -m codedb: rebuild, query, and validate citations."""
from __future__ import annotations

import argparse
import json
import sqlite3
import sys

from . import children, lookup, search, validate


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--db', help='Read an alternate SQLite build')
    sub = ap.add_subparsers(dest='command', required=True)
    bp = sub.add_parser('build',help='Rebuild local SQLite and JSONL exports')
    bp.add_argument('--doc',choices=['NBC-AE'],action='append',help='NBC-AE is the verified scope')
    bp.add_argument('--json',action='store_true')
    for name in ('lookup','children','search'):
        p = sub.add_parser(name)
        p.add_argument('terms' if name=='search' else 'id', nargs='+' if name=='search' else None)
        p.add_argument('--doc', default='NBC-AE')
        p.add_argument('--division',choices=['A','B','C'])
        p.add_argument('--json',action='store_true',help='Structured JSON output (also the query default)')
        if name=='search':
            p.add_argument('--limit',type=int,default=20)
    vp = sub.add_parser('validate',help='Check Markdown/JSON/YAML citations; exit 1 on errors')
    vp.add_argument('paths',nargs='+')
    vp.add_argument('--doc',default='NBC-AE')
    vp.add_argument('--json',action='store_true')
    a = ap.parse_args(argv)
    try:
        if a.command=='build':
            if a.db:
                ap.error('--db is read-only; builds always write codedb/build/')
            from .build import build
            result = build(tuple(a.doc or ['NBC-AE']),log=lambda s:print(s,file=sys.stderr))
        elif a.command=='validate':
            result = validate(a.paths,doc=a.doc,db_path=a.db)
            if not a.json:
                for level in ('errors','warnings'):
                    for e in result[level]:
                        print(f'{e["path"]}:{e["line"]}:{e["column"]}: {level[:-1]} {e["code"]}: {e["message"]}')
                print(f'{result["files_checked"]} files; {result["citations_checked"]} citation tokens; '
                      f'{len(result["errors"])} errors; {len(result["warnings"])} warnings')
            else:
                print(json.dumps(result,indent=2,ensure_ascii=False))
            return 0 if result['ok'] else 1
        else:
            kwargs = {'doc':a.doc,'division':a.division,'db_path':a.db}
            if a.command=='lookup':
                result = lookup(a.id,**kwargs)
            elif a.command=='children':
                result = children(a.id,**kwargs)
            else:
                result = search(' '.join(a.terms),limit=a.limit,**kwargs)
        print(json.dumps(result,indent=2,ensure_ascii=False))
        return 1 if result is None else 0
    except (ValueError,OSError,sqlite3.Error) as exc:
        if getattr(a,'json',False):
            print(json.dumps({'ok':False,'errors':[{'code':'command_error','message':str(exc)}]}))
        else:
            print(f'codedb: {exc}',file=sys.stderr)
        return 2


if __name__=='__main__':
    raise SystemExit(main())
