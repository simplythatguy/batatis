"""Full evaluator outputs for every vector, the file both evaluators must reproduce exactly.

    python -m engine.rules.golden            # write evals_dev/rules/outputs.json
    python -m engine.rules.golden --check    # exit 1 when it is stale

The TypeScript test (`web/src/rules/rules.test.ts`) deep-compares its own outputs with this file, so any
difference between the two evaluators fails CI.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .evaluator import evaluate, load_index, load_rule

ROOT = Path(__file__).resolve().parents[2]
VECTORS = ROOT / 'evals_dev' / 'rules' / 'vectors.json'
OUTPUTS = ROOT / 'evals_dev' / 'rules' / 'outputs.json'


def outputs() -> dict:
    index = load_index()
    vectors = json.loads(VECTORS.read_text(encoding='utf-8'))['vectors']
    return {v['id']: evaluate(load_rule(v['rule']), v['inputs'], index) for v in vectors}


def text() -> str:
    return json.dumps({'generated_by': 'python -m engine.rules.golden', 'outputs': outputs()},
                      indent=1, ensure_ascii=False) + '\n'


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    if args.check:
        stale = not OUTPUTS.exists() or OUTPUTS.read_text(encoding='utf-8') != text()
        if stale:
            print('evals_dev/rules/outputs.json is stale: run python -m engine.rules.golden', file=sys.stderr)
        return 1 if stale else 0
    OUTPUTS.write_text(text(), encoding='utf-8')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
