#!/usr/bin/env python3
"""Record live identify results for the three offline demo cases.

Requires OPENAI_API_KEY and a built code database. When the key is missing the
script exits without writing, so it cannot invent a citation. Unset
BATATIS_OFFLINE before running; this process deletes that variable for itself.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from engine.identify.demo_cache import DEMO_CASE_IDS, cache_key, reset_cache  # noqa: E402
from engine.identify.pipeline import run  # noqa: E402

CACHE = ROOT / 'engine' / 'identify' / 'demo_cache.json'
CASES = ROOT / 'evals_dev' / 'cases'


def main() -> int:
    os.environ.pop('BATATIS_OFFLINE', None)
    if not (os.environ.get('OPENAI_API_KEY') or '').strip():
        print('OPENAI_API_KEY is not set; refusing to write a demo cache.', file=sys.stderr)
        return 2
    rows = []
    for case_id in DEMO_CASE_IDS:
        case = json.loads((CASES / f'{case_id}.json').read_text())
        prose = case['description']
        result = run(prose)
        if result.get('mode') == 'bm25_fallback' or not result.get('articles'):
            print(f'{case_id}: live identify did not return a model result; cache not written.', file=sys.stderr)
            return 1
        result['source'] = 'live'
        result['persisted'] = False
        candidates = [{
            'provision': article['provision'],
            'title': article.get('title') or '',
            'text': article.get('quote') or '',
            'part': article.get('part'),
        } for article in result['articles']]
        rows.append({
            'id': case_id,
            'description': prose,
            'description_sha256': cache_key(prose),
            'candidates': candidates,
            'payload': result,
        })
    CACHE.write_text(json.dumps(rows, indent=2) + '\n')
    reset_cache()
    print(f'wrote {len(rows)} demo cases to {CACHE.relative_to(ROOT)}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
