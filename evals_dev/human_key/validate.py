"""Validate human-key files. Blank unverified keys pass.

A key with ``status: verified``, or with any answer filled in, is rejected when the
verifier name or the verification date is missing. When ``codedb/build/codedb.sqlite``
(or ``BATATIS_CODEDB``) exists, cited articles are checked against it. A missing article
or an implausible page is a warning and does not fail the run.

    python evals_dev/human_key/validate.py
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
KEY_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from evals_dev.jsoncheck import validate as schema_errors  # noqa: E402
from evals_dev.human_key.select import ANSWER_FIELDS, persona_of  # noqa: E402

SCHEMA = json.loads((KEY_DIR / 'schema.json').read_text())
FILLED = [name for name in ANSWER_FIELDS if name not in ('verifier_name', 'date_verified', 'source_page_refs', 'notes')]


def codedb_path() -> Path | None:
    """Locate an existing explicitly configured or repository-built code database."""
    env = os.environ.get('BATATIS_CODEDB')
    candidates = [Path(env)] if env else []
    candidates.append(ROOT / 'codedb' / 'build' / 'codedb.sqlite')
    for path in candidates:
        if path.is_file():
            return path
    return None


def _date_ok(value: str) -> bool:
    """Check whether a verification date parses as an ISO calendar date."""
    try:
        dt.date.fromisoformat(value)
    except ValueError:
        return False
    return True


def key_errors(data: dict, case: dict | None) -> list[str]:
    """Validate key shape, verifier requirements and consistency with the source scenario."""
    cid = data.get('case_id', '?')
    errors = [f'{cid}: {msg}' for msg in schema_errors(data, SCHEMA)]
    status = data.get('status')
    name = data.get('verifier_name')
    date = data.get('date_verified')
    filled = any(data.get(field) is not None for field in FILLED)
    needs_verifier = status == 'verified' or filled
    if needs_verifier and not (isinstance(name, str) and name.strip()):
        errors.append(f'{cid}: missing verifier name')
    if needs_verifier and not (isinstance(date, str) and _date_ok(date)):
        errors.append(f'{cid}: missing verifier date')
    if isinstance(name, str) and name.strip() and status != 'verified':
        errors.append(f'{cid}: verifier name set but status is not verified')
    if case is not None:
        if data.get('scenario') != case.get('description'):
            errors.append(f'{cid}: scenario is not the case description')
        if data.get('persona') != persona_of(case):
            errors.append(f'{cid}: persona does not match applicant_type')
        if data.get('variance_kind') != case.get('topic'):
            errors.append(f'{cid}: variance_kind does not match topic')
        for banned in ('gold', 'must_cite', 'seed_provision', 'authoring'):
            if banned in data:
                errors.append(f'{cid}: key must not carry {banned}')
    return errors


def page_warnings(data: dict, con: sqlite3.Connection) -> list[str]:
    """Warn when a cited provision or claimed source page does not match codedb."""
    cid = data.get('case_id', '?')
    warnings = []
    articles = data.get('expected_top_articles') or []
    for art in articles:
        if not isinstance(art, dict):
            continue
        provision = art.get('provision')
        division = art.get('division') or 'B'
        if not provision:
            continue
        row = con.execute(
            "SELECT pdf_page, pdf_page_end FROM provisions WHERE doc='NBC-AE' AND division=? AND id=?",
            (division, provision)).fetchone()
        if row is None:
            warnings.append(f'{cid}: cited {division} {provision} is not in codedb')
            continue
        page = art.get('page')
        start, end = row[0], row[1] if row[1] is not None else row[0]
        if isinstance(page, int) and not start <= page <= end:
            warnings.append(
                f'{cid}: page {page} for {provision} is outside codedb pages {start}-{end} (warning)')
    return warnings


def validate_keys(keys: list[tuple[Path, dict]], cases: dict[str, dict], db: Path | None) -> tuple[list[str], list[str]]:
    """Collect key errors and optional citation warnings using a read-only database."""
    errors, warnings = [], []
    con = sqlite3.connect(f'file:{db}?mode=ro', uri=True) if db else None
    try:
        for path, data in keys:
            case = cases.get(data.get('case_id'))
            errors.extend(key_errors(data, case))
            if con is not None:
                warnings.extend(page_warnings(data, con))
    finally:
        if con is not None:
            con.close()
    return errors, warnings


def main() -> int:
    """Validate the selected key files and print errors, warnings and verification status."""
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--keys', type=Path, default=KEY_DIR)
    ap.add_argument('--cases', type=Path, default=ROOT / 'evals_dev' / 'cases')
    ap.add_argument('--db', type=Path, default=None)
    args = ap.parse_args()
    paths = sorted(p for p in args.keys.glob('dev-*.json'))
    keys = [(p, json.loads(p.read_text())) for p in paths]
    cases = {c['id']: c for p in sorted(args.cases.glob('dev-*.json')) for c in [json.loads(p.read_text())]}
    db = args.db if args.db else codedb_path()
    errors, warnings = validate_keys(keys, cases, db if db and Path(db).is_file() else None)
    report = {
        'ok': not errors,
        'keys': len(keys),
        'errors': errors,
        'warnings': warnings,
        'codedb': str(db) if db and Path(db).is_file() else None,
        'human_key': 'unfilled' if all(k.get('status') == 'unverified' for _, k in keys) else 'filled',
        'evals': 'model-checked',
    }
    print(json.dumps(report, indent=2))
    return 1 if errors else 0


if __name__ == '__main__':
    raise SystemExit(main())
