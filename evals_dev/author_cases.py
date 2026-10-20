"""Check deterministic Section C values; committed JSON is the sole authoring source.

No narratives, semantic labels or authoring receipts are generated. Only Division B
benchmarks already listed in each case's gold.must_cite are looked up, read-only.

    .venv/bin/python evals_dev/author_cases.py [--db PATH] [--cases DIR] [--check | --write]

The default is read-only. --write refreshes only gold.section_c after validating
the complete batch. Exit 0 when current/refreshed, 1 for drift in check mode,
or 2 for invalid input or an I/O error.
"""
import argparse
from contextlib import closing
import json
import pathlib
import sqlite3
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT.parent))
from codedb import lookup  # noqa: E402
from evals_dev.validate_cases import DEFAULT_DB, validate  # noqa: E402

REVIEWED_IDS = tuple(f'dev-{n:03}' for n in range(1, 61))


def section_c_row(pid, db):
    result = lookup(pid, division='B', db_path=db)
    if result is None:
        raise ValueError(f'unknown Division B benchmark {pid}')
    status = result['attribution_status']
    if not status:
        raise ValueError(f'no attribution status for Division B benchmark {pid}')
    pairs = sorted({r['bracket'] for r in result['attributions'] if not r['application_note']})
    conditional = sorted({(r['bracket'], r['application_note']) for r in result['attributions']
                          if r['application_note']})
    return {'provision': result['id'], 'status': status['status'], 'root_provision': status['root_provision'],
            'pairs': pairs, 'conditional': [{'pair': p, 'when': w} for p, w in conditional]}


def plan_refresh(case_dir, db):
    if not case_dir.is_dir():
        raise ValueError(f'case directory does not exist: {case_dir}')
    paths = {p.stem: p for p in case_dir.glob('*.json')}
    missing, unexpected = set(REVIEWED_IDS) - paths.keys(), paths.keys() - set(REVIEWED_IDS)
    if missing or unexpected:
        raise ValueError(f'expected dev-001 through dev-060; missing={sorted(missing)}, unexpected={sorted(unexpected)}')

    cases, changes = [], []
    for cid in REVIEWED_IDS:
        path = paths[cid]
        original = path.read_bytes()
        case = json.loads(original)
        if not isinstance(case, dict) or case.get('id') != cid:
            raise ValueError(f'{path.name}: id must match filename {cid}')
        gold = case.get('gold')
        if not isinstance(gold, dict) or not isinstance(gold.get('must_cite'), list):
            raise ValueError(f'{cid}: gold.must_cite must be a list')
        if not isinstance(gold.get('section_c'), list):
            raise ValueError(f'{cid}: gold.section_c must be a list')
        benchmarks = []
        for ref in gold['must_cite']:
            if (not isinstance(ref, dict) or ref.get('division') not in {'A', 'B', 'C'}
                    or ref.get('role') not in {'benchmark', 'scope'} or not isinstance(ref.get('provision'), str)):
                raise ValueError(f'{cid}: invalid gold.must_cite reference')
            if ref['division'] == 'B' and ref['role'] == 'benchmark':
                if ref['provision'] in benchmarks:
                    raise ValueError(f'{cid}: duplicate benchmark {ref["provision"]}')
                benchmarks.append(ref['provision'])
        try:
            rows = [section_c_row(pid, db) for pid in benchmarks]
        except ValueError as error:
            raise ValueError(f'{cid}: {error}') from error
        updated = {**case, 'gold': {**gold, 'section_c': rows}}
        cases.append(updated)
        if gold['section_c'] != rows:
            changes.append((path, original, updated))

    # Validate the complete projected batch before any file may be written. Old
    # Section C drift is repairable; invalid narrative/semantic data is not changed.
    with closing(sqlite3.connect(pathlib.Path(db).resolve().as_uri() + '?mode=ro', uri=True)) as con:
        errors, counts = validate(cases, con)
    if errors:
        raise ValueError('\n'.join(errors))
    return changes, counts


def write_changes(changes):
    staged = []
    try:
        # Prepare every replacement before changing any source file.
        for path, _, case in changes:
            with tempfile.NamedTemporaryFile(mode='w', encoding='utf8', dir=path.parent,
                                             prefix=f'.{path.name}.', suffix='.tmp', delete=False) as file:
                replacement = pathlib.Path(file.name)
                staged.append((path, replacement))
                json.dump(case, file, indent=2, ensure_ascii=False)
                file.write('\n')
            replacement.chmod(path.stat().st_mode & 0o777)
        for path, original, _ in changes:
            if path.read_bytes() != original:
                raise ValueError(f'{path.name}: changed during refresh; no files written')
        for path, replacement in staged:
            replacement.replace(path)
    finally:
        for _, replacement in staged:
            replacement.unlink(missing_ok=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--db', default=DEFAULT_DB)
    parser.add_argument('--cases', type=pathlib.Path, default=ROOT / 'cases')
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument('--check', action='store_true', help='read-only check (the default)')
    mode.add_argument('--write', action='store_true', help='refresh only deterministic gold.section_c values')
    args = parser.parse_args()
    try:
        changes, counts = plan_refresh(args.cases, args.db)
        if args.write:
            write_changes(changes)
    except (ValueError, OSError, sqlite3.Error, KeyError, TypeError, AttributeError) as error:
        print(json.dumps({'ok': False, 'error': str(error)}), file=sys.stderr)
        return 2
    print(json.dumps({'ok': args.write or not changes, 'mode': 'write' if args.write else 'check', 'cases': counts['cases'],
                      'section_c_rows': counts['section_c_rows'],
                      'changed_cases': [case['id'] for _, _, case in changes]}, indent=2))
    return 1 if changes and not args.write else 0


if __name__ == '__main__':
    sys.exit(main())
