#!/usr/bin/env python
"""Gate G4: at least 50 committed Part 9 picks with at most 1 error on the validation fold. Exits 1 unless it passes.

    python scripts/gate_g4.py [--pipeline V15f-R5]

Reads the result rows and engine/identify/calibration.json. With no calibrated threshold the gate is NOT RUN, which is a failure:
this script never fits a threshold and never writes calibration.json.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from evals_dev.accuracy.gates import evaluate_g4, passed  # noqa: E402
from evals_dev.identify_bench.analysis import analyse  # noqa: E402

CALIBRATION = Path(__file__).resolve().parents[1] / 'engine' / 'identify' / 'calibration.json'


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--pipeline')
    args = ap.parse_args(argv)
    an = analyse()
    pipeline = args.pipeline or (an.decision.winner if an.decision else None)
    calibration = json.loads(CALIBRATION.read_text()) if CALIBRATION.is_file() else None
    checks = evaluate_g4(an, pipeline, calibration)
    for c in checks:
        print(f'{c.id}  {c.status:7s}  {c.text}')
    ok = passed(checks)
    print('G4', 'PASS' if ok else 'FAIL')
    return 0 if ok else 1


if __name__ == '__main__':
    raise SystemExit(main())
