#!/usr/bin/env python3
"""Record an offline BM25 identify run for the three seeded demo cases.

The script does not call a model. It unsets provider keys for this process,
runs BM25 against the code database, and refuses to write when a snippet is
longer than 25 words or a whole article would be stored.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

CACHE = ROOT / 'engine' / 'identify' / 'demo_cache.json'


def main() -> int:
    os.environ.pop('OPENAI_API_KEY', None)
    os.environ.pop('ANTHROPIC_API_KEY', None)
    os.environ.pop('BATATIS_LIVE', None)
    try:
        from engine.identify.demo_record import build_rows
        rows = build_rows()
    except FileNotFoundError as exc:
        print(f'{exc}; refusing to write a demo cache.', file=sys.stderr)
        return 2
    except (RuntimeError, ValueError) as exc:
        print(f'{exc}; cache not written.', file=sys.stderr)
        return 1
    CACHE.write_text(json.dumps(rows, indent=2) + '\n')
    from engine.identify.demo_cache import reset_cache
    reset_cache()
    print(f'wrote {len(rows)} offline demo cases to {CACHE.relative_to(ROOT)}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
