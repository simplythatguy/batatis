"""The BM25 floor as a judge SUT: rank Division B articles by BM25 over the code database and commit nothing.

Reads the applicant's words on stdin and prints one JSON object (the ``engine/cli_sut.py`` contract). It is the
"BM25 floor" arm of the held-out run: a pipeline that cannot beat it has not earned its model cost.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from engine.codes import default_db  # noqa: E402
from engine.identify import articles, bm25_rank  # noqa: E402

TOP_K = 10


def main() -> int:
    prose = sys.stdin.read().strip()
    if not prose:
        print('bm25_floor: no prose on stdin', file=sys.stderr)
        return 2
    db = default_db()
    arts = articles(db)
    ranked = [a for a in bm25_rank(prose, db) if a in arts][:TOP_K]
    print(json.dumps({
        'articles': [{'provision': a, 'division': 'B', 'committed': False, 'title': arts[a]['title'],
                      'part': arts[a]['part'], 'probability': None} for a in ranked],
        'section_c': [],
        'engineering_required': 'depends',
        'intake_action': 'ask',
        'questions': [],
        'trace': {'ranker': 'bm25 floor', 'commits': 'none by design'},
    }))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
