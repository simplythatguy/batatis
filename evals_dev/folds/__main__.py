"""Command line for the frozen folds file. See ``evals_dev/folds/__init__.py``."""
from __future__ import annotations

import argparse
import json
import sys

from evals_dev.identify_bench.datasets import FOLDS_FILE, load_all

from . import core


def items() -> list[core.Item]:
    return [core.Item(c.id, c.dataset, c.stratum) for c in load_all(with_folds=False)]


def write(doc: dict) -> None:
    FOLDS_FILE.write_text(json.dumps(doc, indent=1, sort_keys=True, ensure_ascii=True) + '\n')


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog='python -m evals_dev.folds', description=__doc__.split('\n')[0])
    ap.add_argument('command', choices=['build', 'extend', 'verify', 'show'])
    args = ap.parse_args(argv)
    if args.command == 'build':
        if FOLDS_FILE.exists():
            print(f'{FOLDS_FILE} exists; folds are frozen. Use extend, or write folds-v2.json.', file=sys.stderr)
            return 2
        write(core.build(items()))
        print(f'wrote {FOLDS_FILE}')
        return 0
    doc = json.loads(FOLDS_FILE.read_text())
    if args.command == 'extend':
        out = core.extend(doc, items())
        if out is doc:
            print('nothing to add')
            return 0
        write(out)
        print(f"added {out['generations'][-1]['added']} case(s) as generation {out['generations'][-1]['generation']}")
        return 0
    if args.command == 'verify':
        problems = core.verify(doc, items())
        for p in problems:
            print(p, file=sys.stderr)
        print('folds verify: ' + ('OK' if not problems else f'{len(problems)} problem(s)'))
        return 1 if problems else 0
    print(f"seed {doc['seed']}  calibration share {doc['calibration_share']}  sha256 {doc['sha256'][:16]}")
    for fold, rows in doc['counts'].items():
        print(f"{fold}: {sum(rows.values())}")
        for key, n in rows.items():
            print(f'  {key}: {n}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
