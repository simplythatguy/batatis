"""Print a provision's sentences with their Section C rows (authoring aid for development cases).

Usage: python evals_dev/show.py 9.10.15.5. [--div B] [--chars 400]
"""
import argparse
import os
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
from codedb import children, lookup  # noqa: E402

DB = os.environ.get('BATATIS_CODEDB') or str(pathlib.Path(__file__).resolve().parents[1] / 'codedb' / 'build' / 'codedb.sqlite')

ap = argparse.ArgumentParser()
ap.add_argument('ids', nargs='+')
ap.add_argument('--div', default='B')
ap.add_argument('--chars', type=int, default=400)
ap.add_argument('--db', default=DB)
a = ap.parse_args()
for pid in a.ids:
    r = lookup(pid, division=a.div, db_path=a.db)
    if not r:
        print('MISSING', pid)
        continue
    print(f"===== {r['citation']}  {r['article_title']}")
    for s in [r] if r['level'] != 'article' else children(pid, division=a.div, db_path=a.db):
        full = lookup(s['id'], division=a.div, db_path=a.db)
        st = full['attribution_status'] or {}
        pairs = ' '.join(x['bracket'] + ('*' if x['application_note'] else '') for x in full['attributions'])
        print(f"  {s['id']} p.{s['pdf_page']} [{st.get('status')}{' root=' + str(st.get('root_provision')) if st.get('root_provision') else ''}] {pairs}")
        print('     ' + s['text'][:a.chars].replace('\n', ' '))
