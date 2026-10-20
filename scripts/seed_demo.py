#!/usr/bin/env python3
"""Write the fictional demo cases into the local case store.

Offline. No API key and no network. Reads evals/demo-cases/<case>/input/ only.

    BATATIS_DEMO=1 python scripts/seed_demo.py

Without BATATIS_DEMO=1 the script exits 2 and writes nothing. Leave that variable
unset in production. See docs/demo/seed.md.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from engine.demo_seed import demo_enabled, seed_cases
from engine.store import CaseStore


def main() -> int:
    if not demo_enabled():
        print('Demo seed is off. Set BATATIS_DEMO=1. It stays off in production.', file=sys.stderr)
        return 2
    cases = seed_cases(CaseStore())
    json.dump([case.model_dump() for case in cases], sys.stdout, indent=2, ensure_ascii=False)
    sys.stdout.write('\n')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
