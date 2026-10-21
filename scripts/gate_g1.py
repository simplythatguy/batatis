#!/usr/bin/env python
"""Gate G1: Code ID re-measure. Prints each check against its threshold; exits 1 unless every check passes.

    python scripts/gate_g1.py [--verifier V15f-R5]

Reads the result rows in evals_dev/identify_bench/results (nothing is run, nothing is paid for). A check with no data prints
NOT RUN and the gate fails: a missing run is never a pass.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from evals_dev.accuracy.gates import evaluate_g1, passed  # noqa: E402
from evals_dev.identify_bench.analysis import analyse  # noqa: E402
from evals_dev.identify_bench.live import db_path  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--verifier')
    args = ap.parse_args(argv)
    arts = None
    try:
        from engine.identify.corpus import articles
        arts = articles(db_path())
    except Exception:                                    # noqa: BLE001 - the integrity recheck is skipped without a database
        pass
    checks = evaluate_g1(analyse(arts=arts), args.verifier)
    for c in checks:
        print(f'{c.id}  {c.status:7s}  {c.text}')
    ok = passed(checks)
    print('G1', 'PASS' if ok else 'FAIL')
    return 0 if ok else 1


if __name__ == '__main__':
    raise SystemExit(main())
