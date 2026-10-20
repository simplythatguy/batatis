"""Score system output against the human key.

The committed key is unfilled, so a run with no verified keys reports n=0.
Current evals are model-checked. This script does not claim human verification.

Per-field accuracy uses only keys with ``status: verified``. Model-grader agreement
(the development-case gold labels versus a filled key) is a separate block and is
never added into the accuracy counts.

``--calibrate`` reports committed-pick precision at probability thresholds 0.50–0.95
(step 0.05) so the engine's 0.75 auto-commit threshold can be set once a key is filled.

    python evals_dev/human_key/score.py
    python evals_dev/human_key/score.py --system outputs.json --calibrate
    python evals_dev/human_key/score.py --run-engine --calibrate
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
KEY_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from evals_dev.stats import proportion  # noqa: E402

FIELDS = (
    'section_ab_required_fields',
    'expected_top_articles',
    'benchmark_acceptable_solution',
    'engineer_needed',
    'intake_action',
)
THRESHOLDS = [i / 100 for i in range(50, 100, 5)]
NOTE = (
    'The human key is unfilled. Current evals are model-checked. '
    'These figures are not human verification.'
)


def _norm(text: str) -> str:
    """Normalize spacing, case and a terminal period for prose equality comparisons."""
    return re.sub(r'\s+', ' ', text).strip().casefold().rstrip('.')


def _canon_field(text: str) -> str | None:
    """Map engine names and form labels to the human-key administrative vocabulary."""
    t = re.sub(r'[_\-]+', ' ', text.casefold())
    if 'mailing' in t:
        return 'mailing_address'
    if 'civic' in t or 'municipal' in t:
        return 'municipal_address'
    if 'legal' in t or t.strip() in {'lot', 'block', 'plan'}:
        return 'legal_description'
    if 'permit' in t:
        return 'permit_number'
    if 'jurisdiction' in t or t.strip() == 'scope':
        return 'jurisdiction_wide'
    if 'representative' in t or 'owner rep' in t:
        return 'representative'
    if 'owner' in t:
        return 'owner'
    if re.search(r'\bdate\b', t):
        return 'date_of_request'
    if 'alternative' in t:
        return 'alternative_description'
    return None


def _articles(value) -> set[tuple[str, str]] | None:
    """Normalize article strings or records to a set of division/id pairs."""
    if value is None:
        return None
    out = set()
    for art in value:
        if isinstance(art, str):
            out.add(('B', art))
            continue
        provision = art.get('provision') or art.get('provision_id')
        if not provision:
            continue
        out.add((art.get('division') or 'B', provision))
    return out


def _system_articles(system: dict) -> set[tuple[str, str]] | None:
    """Prefer explicitly committed article picks when the system supplies them."""
    arts = system.get('articles', system.get('expected_top_articles'))
    if arts is None:
        return None
    committed = [a for a in arts if isinstance(a, dict) and a.get('committed') is True]
    return _articles(committed if committed else arts)


def field_match(field: str, key: dict, system: dict) -> bool | None:
    """True/false when both sides have a value. None when the key has no value."""
    expected = key.get(field)
    if expected is None:
        return None
    if field == 'section_ab_required_fields':
        got = system.get(field)
        if got is None:
            return False
        return set(expected) == {_canon_field(x) or x for x in got}
    if field == 'expected_top_articles':
        got = _system_articles(system)
        if got is None:
            return False
        return _articles(expected) == got
    if field == 'benchmark_acceptable_solution':
        got = system.get(field)
        if not isinstance(got, str):
            return False
        return _norm(expected) == _norm(got)
    if field == 'engineer_needed':
        got = system['engineer_needed'] if 'engineer_needed' in system else system.get('engineering_required')
        return got == expected
    return system.get(field) == expected


def agreement_match(field: str, key: dict, gold: dict, case: dict) -> bool | None:
    """Compare one verified-key field with development gold, independently of system accuracy."""
    expected = key.get(field)
    if expected is None:
        return None
    if field == 'intake_action':
        return expected == gold.get('intake_action')
    if field == 'engineer_needed':
        return expected == gold.get('engineering_required')
    if field == 'benchmark_acceptable_solution':
        return isinstance(gold.get('departure'), str) and _norm(expected) == _norm(gold['departure'])
    if field == 'expected_top_articles':
        gold_arts = {(ref.get('division') or 'B', ref['provision'])
                     for ref in gold.get('must_cite', []) if ref.get('provision')}
        return _articles(expected) == gold_arts
    if field == 'section_ab_required_fields':
        mapped = {c for m in case.get('missing_info', []) if (c := _canon_field(m.get('field', '')))}
        return set(expected) == mapped
    return None


def _tally(pairs: list[bool | None]) -> dict:
    """Count true matches while excluding key fields with no answer."""
    judged = [p for p in pairs if p is not None]
    return proportion(sum(bool(p) for p in judged), len(judged))


def score_keys(keys: list[dict], systems: dict[str, dict], cases: dict[str, dict]) -> dict:
    """Score verified keys only, separating system accuracy from model-gold agreement."""
    verified = [k for k in keys if k.get('status') == 'verified']
    accuracy = {}
    agreement = {}
    for field in FIELDS:
        acc, agr = [], []
        for key in verified:
            system = systems.get(key['case_id'], {})
            case = cases.get(key['case_id'], {})
            acc.append(field_match(field, key, system))
            agr.append(agreement_match(field, key, case.get('gold') or {}, case))
        accuracy[field] = _tally(acc)
        agreement[field] = _tally(agr)
    unfilled = len(verified) == 0
    return {
        'evals': 'model-checked' if unfilled else 'human-key-filled',
        'human_key': 'unfilled' if unfilled else 'filled',
        'subset': 'human-key',
        'n': len(verified),
        'note': NOTE if unfilled else 'Counts use keys with status verified only. This is not a code-compliance finding.',
        'accuracy': accuracy,
        'model_grader_agreement': agreement,
    }


def calibrate(keys: list[dict], systems: dict[str, dict], thresholds: list[float] = None) -> dict:
    """Committed-pick precision. A pick at threshold t has probability >= t.

    It counts as a hit when its provision is in the verified key's expected articles.
    The 0.75 row is the engine's current auto-commit placeholder.
    """
    thresholds = list(THRESHOLDS if thresholds is None else thresholds)
    verified = {k['case_id']: k for k in keys
                if k.get('status') == 'verified' and k.get('expected_top_articles') is not None}
    rows = []
    for threshold in thresholds:
        hits = 0
        picks = 0
        for cid, key in verified.items():
            expected = _articles(key['expected_top_articles']) or set()
            for art in systems.get(cid, {}).get('articles') or []:
                prob = art.get('probability') if isinstance(art, dict) else None
                if prob is None or prob < threshold:
                    continue
                picks += 1
                ident = ((art.get('division') or 'B'), art.get('provision') or art.get('provision_id'))
                if ident[1] and ident in expected:
                    hits += 1
        row = proportion(hits, picks)
        row['threshold'] = threshold
        row['auto_commit_placeholder'] = threshold == 0.75
        rows.append(row)
    return {
        'human_key': 'unfilled' if not verified else 'filled',
        'n_cases': len(verified),
        'definition': 'precision of articles whose probability is at least the threshold, against expected_top_articles',
        'thresholds': rows,
    }


def _engine_systems(cases: dict[str, dict], ids: list[str]) -> dict[str, dict]:
    """Run identification for selected scenarios and retain only supported scored fields."""
    from engine.cli_sut import run
    systems = {}
    for cid in ids:
        out = run(cases[cid]['description'])
        systems[cid] = {
            'case_id': cid,
            'articles': out.get('articles') or [],
            'engineer_needed': out.get('engineering_required'),
            'intake_action': out.get('intake_action'),
        }
    return systems


def load_system(path: Path) -> dict[str, dict]:
    """Read list, cases-wrapper or case-id-map system outputs into a case-id index."""
    data = json.loads(path.read_text())
    rows = data['cases'] if isinstance(data, dict) and 'cases' in data else data
    if isinstance(rows, dict):
        return {cid: dict(row, case_id=cid) for cid, row in rows.items()}
    return {row['case_id']: row for row in rows}


def render(report: dict, calibration: dict | None) -> str:
    """Render separate accuracy and agreement metrics plus optional threshold calibration."""
    lines = [
        'human key',
        f"evals: {report['evals']}",
        f"human key: {report['human_key']}",
        report['note'],
        f"verified keys: {report['n']}",
        '',
        'accuracy (verified keys only; model gold is not in these counts)',
    ]
    for field, row in report['accuracy'].items():
        lines.append(_line(field, row))
    lines.append('')
    lines.append('model-grader agreement (separate from accuracy; not a human verification)')
    for field, row in report['model_grader_agreement'].items():
        lines.append(_line(field, row))
    if calibration is not None:
        lines.append('')
        lines.append('commit-threshold calibration (verified keys only)')
        if calibration['n_cases'] == 0:
            lines.append('0 cases — human key is unfilled, so 0.75 is not calibrated')
        for row in calibration['thresholds']:
            mark = '  <- current placeholder' if row['auto_commit_placeholder'] else ''
            lines.append(f"  {row['threshold']:.2f}: {row['label']}{_wilson(row)}{mark}")
    payload = dict(report)
    if calibration is not None:
        payload['calibration'] = calibration
    lines.extend(['', '--- json ---', json.dumps(payload, indent=2)])
    return '\n'.join(lines) + '\n'


def _line(field: str, row: dict) -> str:
    """Format a field score with its Wilson interval when available."""
    return f"  {field}: {row['label']}{_wilson(row)}"


def _wilson(row: dict) -> str:
    """Format an available Wilson interval, or an empty suffix for no observations."""
    span = row['wilson_95']
    if not span:
        return ''
    return f'  Wilson 95% [{span[0]:.3f}, {span[1]:.3f}]'


def main(argv: list[str] | None = None) -> int:
    """Load keys and optional system outputs, then print scores and requested calibration."""
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--keys', type=Path, default=KEY_DIR)
    ap.add_argument('--cases', type=Path, default=ROOT / 'evals_dev' / 'cases')
    ap.add_argument('--system', type=Path, help='system output JSON')
    ap.add_argument('--run-engine', action='store_true', help='run engine identify/intake on the 15 cases')
    ap.add_argument('--calibrate', action='store_true')
    ap.add_argument('--json', action='store_true', help='print the JSON block only')
    args = ap.parse_args(argv)
    keys = [json.loads(p.read_text()) for p in sorted(args.keys.glob('dev-*.json'))]
    cases = {c['id']: c for p in sorted(args.cases.glob('dev-*.json')) for c in [json.loads(p.read_text())]}
    if args.system and args.run_engine:
        print('pass either --system or --run-engine', file=sys.stderr)
        return 2
    if args.run_engine:
        systems = _engine_systems(cases, [k['case_id'] for k in keys])
    elif args.system:
        systems = load_system(args.system)
    else:
        systems = {}
    report = score_keys(keys, systems, cases)
    calibration = calibrate(keys, systems) if args.calibrate else None
    text = render(report, calibration)
    if args.json:
        payload = json.loads(text.split('--- json ---', 1)[1])
        print(json.dumps(payload, indent=2))
    else:
        print(text, end='')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
