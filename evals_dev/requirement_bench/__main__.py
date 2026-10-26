"""Stdlib-only offline CLI. Exit 0: valid captures, 1: capture failures, 2: invalid dataset/command."""
from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from pathlib import Path

from .manifest import export_inputs, seal, snapshot_catalog
from .protocol import Invalid, write_json
from .score import evaluate, key_template


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description='Offline requirement-reference coverage evaluator; no provider calls.')
    sub = parser.add_subparsers(dest='command', required=True)
    p = sub.add_parser('seal', help='Hash opaque keys and input files; enforce split/leakage controls.')
    p.add_argument('--plan', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True)
    p = sub.add_parser('export', help='Export only predictor inputs, config and source catalog.')
    p.add_argument('--manifest', type=Path, required=True)
    p.add_argument('--split', choices=('train', 'dev', 'holdout'), required=True)
    p.add_argument('--run-id', required=True)
    p.add_argument('--out', type=Path, required=True)
    p = sub.add_parser('score', help='Score captured JSONL, loading answer keys only in this process.')
    p.add_argument('--manifest', type=Path, required=True)
    p.add_argument('--predictions', type=Path, required=True)
    p.add_argument('--split', choices=('train', 'dev', 'holdout'), required=True)
    p.add_argument('--run-id', required=True)
    p.add_argument('--out', type=Path, required=True)
    p = sub.add_parser('catalog', help='Snapshot NBC(AE) 2023 p2 identities from a local codedb; no prose exported.')
    p.add_argument('--db', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True)
    p = sub.add_parser('key-template', help='Create an empty, unreviewed, unknown-coverage key.')
    p.add_argument('--case-id', required=True)
    p.add_argument('--out', type=Path, required=True)
    p = sub.add_parser('synthetic-demo', help='Generate and score synthetic captures; never expert gold.')
    p.add_argument('--out', type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        code = 0
        if args.command == 'seal':
            m = seal(args.plan, args.out)
            result = {'seal_sha256': m['seal_sha256'], 'planned_cases': len(m['cases'])}
        elif args.command == 'export':
            result = export_inputs(args.manifest, args.split, args.run_id, args.out)
        elif args.command in ('score', 'synthetic-demo'):
            if args.command == 'score':
                result = evaluate(args.manifest, args.predictions, args.split, args.run_id)
                write_json(args.out, result)
            else:
                from .synthetic import run_demo
                result = run_demo(args.out)
            code = int(not result['capture_integrity_valid'] or any(
                row['prediction_status'] != 'ok' or any(s['status'] != 'ok' for s in row['layers'].values())
                for row in result['cases']))
            result = {'planned_cases': result['diagnostics_all_planned']['planned_cases'],
                      'prediction_status_counts': result['diagnostics_all_planned']['prediction_status_counts'],
                      'expert_eligible_cases': result['expert_headline']['eligible_cases'],
                      'expert_metrics': result['expert_headline']['metrics'],
                      'this_offline_evaluation': result['this_offline_evaluation'],
                      'report': str(args.out if args.command == 'score' else args.out / 'report.json')}
        elif args.command == 'catalog':
            catalog = snapshot_catalog(args.db)
            write_json(args.out, catalog)
            result = {'references': len(catalog['references']), 'kind': catalog['kind']}
        else:
            write_json(args.out, key_template(args.case_id))
            result = {'review': 'unreviewed', 'coverage': 'unknown', 'requirements': 0}
        print(json.dumps(result, sort_keys=True, allow_nan=False))
        return code
    except (Invalid, OSError, sqlite3.Error) as error:
        print(json.dumps({'error': str(error), 'provider_calls': 0}), file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
