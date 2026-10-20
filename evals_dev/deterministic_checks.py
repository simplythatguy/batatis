"""Deterministic checks. No model grader and no human key.

Current evals are model-checked. The human key is unfilled. This report is
``grader: deterministic`` and is never mixed with model-graded scores.

    python evals_dev/deterministic_checks.py
    python evals_dev/deterministic_checks.py --json

Checks, each ``x of n`` with a Wilson 95% interval:

1. Citation resolution, system output and fixture gold reported separately.
2. Section C exactness of ``engine/section_c.py`` against codedb, including the
   ``validate_cases.py`` pair/status comparison for a gold Section C row.
3. Planted Part 1 A/B missing-field detection, plus false positives on clean controls.
4. Schema validity of case, identify, completeness, Section D and export metadata.
5. Appeal decisions, reported separately as ``label_source: appeals_weak``:
   citation resolution after mapping, the Section C anchor on decision 0015414,
   professional-involvement agreement on the 12 decisions where it comes up,
   and the 2022-06, 0015427, and 2024-06 / 0015432 anchors.

A check that needs codedb and does not find ``codedb/build/codedb.sqlite`` (or
``BATATIS_CODEDB``) reports n=0 and ``skipped: codedb missing``. The same path is
read again on the next run, so a database built by the identify-api fetch script
is picked up with no change here. Other branches plug in by dropping JSON in
``evals_dev/outputs/<kind>/`` (see ``output_adapters.py``).
"""
from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEV = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from evals_dev.appeals.checks import build_appeals_block, load_appeals  # noqa: E402
from evals_dev.jsoncheck import validate as schema_errors  # noqa: E402
from evals_dev.output_adapters import citations, discover  # noqa: E402
from evals_dev.stats import proportion  # noqa: E402

# Part 1 Section A/B fields the completeness checker treats as required.
# Keep this aligned with engine.completeness._CORE (the administrative rows).
AB_FIELDS = (
    'owner_name',
    'application_date',
    'civic_address',
    'legal_description',
    'representative',
    'mailing_address',
    'alternative_description',
    'scope',
)
SCHEMA_KINDS = ('case', 'identify', 'completeness', 'section_d', 'export')
NOTE = (
    'Deterministic checks only. Not mixed with model-graded scores. '
    'The human key is unfilled. Current evals are model-checked. This is not human verification.'
)
CODEDB_MISSING = 'skipped: codedb missing'


def find_codedb() -> Path | None:
    """Locate the database the identify-api fetch/build writes, if it is there now."""
    env = os.environ.get('BATATIS_CODEDB')
    candidates = [Path(env)] if env else []
    candidates.append(DEV.parent / 'codedb' / 'build' / 'codedb.sqlite')
    candidates.append(Path('/Users/aamia/.t3/projects/batatis/codedb/build/codedb.sqlite'))
    for path in candidates:
        if path.is_file():
            return path
    return None


def load_cases(path: Path) -> list[dict]:
    return [json.loads(p.read_text()) for p in sorted(path.glob('dev-*.json'))]


def load_manifests(path: Path) -> list[dict]:
    return [json.loads(p.read_text()) for p in sorted(path.glob('*.json'))]


def load_schemas(path: Path) -> dict[str, dict]:
    names = {
        'case': 'case.schema.json',
        'identify': 'identify.schema.json',
        'completeness': 'completeness.schema.json',
        'section_d': 'section_d.schema.json',
        'export': 'export_metadata.schema.json',
    }
    return {kind: json.loads((path / name).read_text()) for kind, name in names.items()}


def _connect(db_path: Path) -> sqlite3.Connection:
    con = sqlite3.connect(f'file:{db_path}?mode=ro', uri=True)
    con.row_factory = sqlite3.Row
    return con


def resolves(con: sqlite3.Connection, cite: dict) -> bool:
    provision = cite.get('provision')
    if not provision:
        return False
    try:
        from codedb.ids import canon
        provision = canon(provision)
    except (ImportError, ValueError):
        pass
    division = cite.get('division')
    if division:
        row = con.execute(
            "SELECT 1 FROM provisions WHERE doc='NBC-AE' AND division=? AND id=?",
            (division, provision)).fetchone()
        return row is not None
    row = con.execute(
        "SELECT 1 FROM provisions WHERE doc='NBC-AE' AND id=?", (provision,)).fetchone()
    return row is not None


def score_citations(cites: list[dict], db_path: Path | None, *, empty_reason: str) -> dict:
    if not cites:
        return proportion(0, 0, skipped=empty_reason)
    if db_path is None:
        return proportion(0, 0, skipped=CODEDB_MISSING)
    con = _connect(db_path)
    try:
        hit = sum(1 for cite in cites if resolves(con, cite))
    finally:
        con.close()
    return proportion(hit, len(cites))


def gold_must_cite(cases: list[dict]) -> list[dict]:
    out = []
    for case in cases:
        for ref in (case.get('gold') or {}).get('must_cite') or []:
            if ref.get('provision'):
                out.append({'provision': ref['provision'], 'division': ref.get('division'),
                            'source': 'fixture_gold'})
    return out


def _pkey(pair: dict) -> tuple:
    return (pair['function'], pair['objective'], pair['bracket'], pair.get('application_note') or '')


def _ikey(intent: dict) -> tuple:
    return (intent.get('provision_id'), intent.get('objective'),
            tuple(intent.get('brackets') or []), tuple(intent.get('intents') or []))


def gold_row_matches(gold_row: dict | None, db_pairs: list[dict], db_status: dict) -> bool:
    """The validate_cases.py Section C comparison: brackets, conditions, status, root."""
    if gold_row is None:
        return True
    want_pairs = {p['bracket'] for p in db_pairs if not p.get('application_note')}
    want_cond = {(p['bracket'], p['application_note']) for p in db_pairs if p.get('application_note')}
    got_pairs = set(gold_row.get('pairs') or [])
    got_cond = {(item['pair'], item['when']) for item in gold_row.get('conditional') or []}
    return (got_pairs == want_pairs and got_cond == want_cond
            and (gold_row.get('status'), gold_row.get('root_provision'))
            == (db_status.get('status'), db_status.get('root_provision')))


def _cmp_key(comparison: dict | None):
    if not comparison:
        return None

    def seq(value):
        items = list(value or [])
        if all(isinstance(item, str) for item in items):
            return tuple(sorted(items))
        return tuple(repr(item) for item in items)

    return (comparison.get('status'), seq(comparison.get('only_in_intent')), seq(comparison.get('only_in_ae')))


def engine_matches(engine: dict, db: dict) -> bool:
    """Objective/function pairs and intent blocks equal the codedb rows."""
    if {_pkey(p) for p in engine['pairs']} != {_pkey(p) for p in db['pairs']}:
        return False
    if {_ikey(i) for i in engine['intents']} != {_ikey(i) for i in db['intents']}:
        return False
    return _cmp_key(engine.get('comparison')) == _cmp_key(db.get('comparison'))


def provision_exact(engine: dict | None, db: dict, gold_row: dict | None) -> bool:
    if engine is None:
        return False
    return engine_matches(engine, db) and gold_row_matches(gold_row, db['pairs'], db['status'])


def confirmed_provisions(case: dict) -> list[str]:
    rows = (case.get('gold') or {}).get('section_c') or []
    if rows:
        return [row['provision'] for row in rows if row.get('provision')]
    return [ref['provision'] for ref in (case.get('gold') or {}).get('must_cite') or []
            if ref.get('division') == 'B' and ref.get('provision')]


def _view_from_record(rec: dict) -> dict:
    """Codedb lookup record in the same shape as an engine Section C row."""
    pid = rec['id']
    pairs = []
    for attr in rec.get('attributions') or []:
        note = attr.get('application_note') or ''
        for function in attr.get('fs') or []:
            for objective in attr.get('objectives') or []:
                pairs.append({'function': function, 'objective': objective, 'bracket': attr.get('bracket'),
                              'application_note': note})
    intents = []
    for intent in rec.get('intents') or []:
        intent_id = intent.get('provision_id')
        if intent_id != pid and not (isinstance(intent_id, str) and intent_id.startswith(pid + '(')):
            continue
        intents.append({'provision_id': intent_id, 'objective': intent.get('objective'),
                        'brackets': list(intent.get('brackets') or []),
                        'intents': list(intent.get('intents') or [])})
    comp = next((item for item in rec.get('intent_comparison') or [] if item.get('provision_id') == pid), None)
    comparison = None if comp is None else {
        'status': comp.get('status'),
        'only_in_intent': list(comp.get('only_in_intent') or []),
        'only_in_ae': list(comp.get('only_in_ae') or []),
    }
    status = rec.get('attribution_status') or {}
    return {
        'pairs': pairs,
        'intents': intents,
        'status': {'status': status.get('status'), 'root_provision': status.get('root_provision')},
        'comparison': comparison,
    }


def _engine_view(row) -> dict:
    return {
        'pairs': [{'function': p.function, 'objective': p.objective, 'bracket': p.bracket,
                   'application_note': p.application_note or ''} for p in row.pairs],
        'intents': [{'provision_id': i.provision_id, 'objective': i.objective,
                     'brackets': list(i.brackets), 'intents': list(i.intents)} for i in row.intents],
        'comparison': None if row.intent_comparison is None else {
            'status': row.intent_comparison,
            'only_in_intent': list(row.only_in_intent),
            'only_in_ae': list(row.only_in_ae),
        },
    }


def section_c_exactness(cases: list[dict], db_path: Path | None) -> dict:
    if db_path is None:
        return proportion(0, 0, skipped=CODEDB_MISSING)
    try:
        from engine.codes import Codes
        from engine.section_c import section_c_rows
    except ImportError as exc:
        return proportion(0, 0, skipped=f'skipped: engine unavailable ({type(exc).__name__})')
    codes = Codes(db_path)
    hit = 0
    n = 0
    for case in cases:
        gold_rows = {row.get('provision'): row for row in (case.get('gold') or {}).get('section_c') or []}
        for pid in confirmed_provisions(case):
            n += 1
            try:
                looked = section_c_rows([pid], codes)
            except (KeyError, ValueError):
                continue
            ok = bool(looked)
            for row in looked:
                rec = codes.provision(row.provision_id, 'B')
                gold = gold_rows.get(row.provision_id)
                if rec is None or not provision_exact(_engine_view(row), _view_from_record(rec), gold):
                    ok = False
            if ok:
                hit += 1
    return proportion(hit, n)


def score_planted(manifests: list[dict], checker) -> tuple[dict, dict]:
    """``checker(facts)`` returns the field names flagged missing. It must not be shown removed_fields."""
    detected = slots = fp = fp_n = 0
    for manifest in manifests:
        flagged = set(checker(manifest['facts']))
        if manifest['role'] == 'clean-control':
            for field in AB_FIELDS:
                fp_n += 1
                if field in flagged:
                    fp += 1
        else:
            for field in manifest['removed_fields']:
                slots += 1
                if field in flagged:
                    detected += 1
    return proportion(detected, slots), proportion(fp, fp_n)


def engine_planted_checker(db_path: Path):
    from engine.codes import Codes
    from engine.completeness import check_completeness
    from engine.tests.case_builder_fixtures import complete_case
    codes = Codes(db_path)

    def checker(facts: dict) -> set[str]:
        case = complete_case()
        absent = [field for field in AB_FIELDS if field not in facts]
        case.facts = [fact for fact in case.facts if fact.field not in absent]
        return {gap.field for gap in check_completeness(case, codes)}

    return checker


def score_schemas(documents: dict[str, list], schemas: dict[str, dict], skip: dict[str, str | None]) -> dict:
    by_kind = {}
    for kind in SCHEMA_KINDS:
        docs = documents.get(kind) or []
        if not docs:
            by_kind[kind] = proportion(0, 0, skipped=skip.get(kind) or 'no system output')
            continue
        valid = sum(1 for doc in docs if not schema_errors(doc, schemas[kind]))
        by_kind[kind] = proportion(valid, len(docs))
    active = [row for row in by_kind.values() if not row['skipped']]
    if not active:
        reasons = sorted({row['skipped'] for row in by_kind.values()})
        overall = proportion(0, 0, skipped=reasons[0] if len(reasons) == 1 else '; '.join(reasons))
    else:
        overall = proportion(sum(row['x'] for row in active), sum(row['n'] for row in active))
    return {'overall': overall, 'by_kind': by_kind}


def _live_documents(db_path: Path) -> tuple[dict[str, list], str | None]:
    try:
        from engine.codes import Codes
        from engine.completeness import check_completeness
        from engine.section_d import section_d_plan
        from engine.tests.case_builder_fixtures import complete_case
    except ImportError as exc:
        return {}, f'skipped: engine unavailable ({type(exc).__name__})'
    codes = Codes(db_path)
    case = complete_case()
    docs = {
        'case': [json.loads(case.model_dump_json())],
        'completeness': [[json.loads(gap.model_dump_json()) for gap in check_completeness(case, codes)]],
        'section_d': [json.loads(section_d_plan(case, codes).model_dump_json())],
        'export': [],
    }
    try:
        from engine.export import ExportError, export_case
        result = export_case(case, draft=True, codes=codes)
        docs['export'].append({
            'field_map': result.field_map,
            'form_pages': result.form_pages,
            'appendix_pages': result.appendix_pages,
            'draft': result.draft,
            'blank_fields': list(result.blank_fields),
            'open_items': list(result.open_items),
        })
    except (ImportError, ExportError, OSError):
        docs['export'] = []
    return docs, None


def build_report(*, root: Path, db_path: Path | None, cases: list[dict], manifests: list[dict],
                 schemas: dict[str, dict], planted_checker=None, documents: dict | None = None,
                 appeals: list[dict] | None = None, professional_flagger=None) -> dict:
    found = documents if documents is not None else discover(root)
    system = {
        'identify': citations('identify', found.get('identify') or []),
        'section_c': citations('section_c', found.get('section_c') or []),
        'section_d': citations('section_d', found.get('section_d') or []),
    }
    system_scores = {
        kind: score_citations(rows, db_path, empty_reason='no system output')
        for kind, rows in system.items()
    }
    pooled = [cite for rows in system.values() for cite in rows]
    if not pooled:
        system_total = proportion(0, 0, skipped='no system output')
    else:
        system_total = score_citations(pooled, db_path, empty_reason='no system output')
    gold = score_citations(gold_must_cite(cases), db_path, empty_reason='no fixture must_cite entries')

    if planted_checker is not None:
        detection, false_positives = score_planted(manifests, planted_checker)
    elif db_path is None:
        detection = proportion(0, 0, skipped=CODEDB_MISSING)
        false_positives = proportion(0, 0, skipped=CODEDB_MISSING)
    else:
        try:
            detection, false_positives = score_planted(manifests, engine_planted_checker(db_path))
        except ImportError as exc:
            reason = f'skipped: engine unavailable ({type(exc).__name__})'
            detection = proportion(0, 0, skipped=reason)
            false_positives = proportion(0, 0, skipped=reason)

    skip = {kind: None for kind in SCHEMA_KINDS}
    docs = {kind: list(found.get(kind) or []) for kind in SCHEMA_KINDS}
    if db_path is None:
        for kind in ('case', 'completeness', 'section_d', 'export'):
            if not docs[kind]:
                skip[kind] = CODEDB_MISSING
    else:
        live, err = _live_documents(db_path)
        for kind in ('case', 'completeness', 'section_d', 'export'):
            extra = live.get(kind) or []
            if extra:
                docs[kind].extend(extra)
            elif not docs[kind]:
                skip[kind] = err or 'no system output'
    if not docs['identify']:
        skip['identify'] = 'no system output'

    return {
        'grader': 'deterministic',
        'evals': 'model-checked',
        'human_key': 'unfilled',
        'note': NOTE,
        'codedb': str(db_path) if db_path else None,
        'checks': {
            'citation_resolution': {
                'system': system_total,
                'system_by_source': system_scores,
                'fixture_gold': gold,
            },
            'section_c_exactness': section_c_exactness(cases, db_path),
            'planted_missing_fields': {
                'detection': detection,
                'false_positives': false_positives,
            },
            'schema_validity': score_schemas(docs, schemas, skip),
            'appeals': build_appeals_block(
                [] if appeals is None else appeals, db_path, score_citations,
                professional_flagger=professional_flagger,
            ),
        },
    }


def _line(label: str, row: dict) -> str:
    if row.get('skipped'):
        return f"  {label}: {row['label']} ({row['skipped']})"
    span = row['wilson_95']
    interval = f"  Wilson 95% [{span[0]:.3f}, {span[1]:.3f}]" if span else ''
    return f"  {label}: {row['label']}{interval}"


def render(report: dict) -> str:
    checks = report['checks']
    cite = checks['citation_resolution']
    planted = checks['planted_missing_fields']
    schema = checks['schema_validity']
    lines = [
        'deterministic checks',
        'grader: deterministic',
        f"evals: {report['evals']}",
        f"human key: {report['human_key']}",
        report['note'],
        '',
        'Citation resolution',
        _line('system', cite['system']),
    ]
    for kind, row in cite['system_by_source'].items():
        lines.append(_line(f'system {kind}', row))
    lines.append(_line('fixture gold must_cite', cite['fixture_gold']))
    lines.append('')
    lines.append('Section C exactness')
    lines.append(_line('confirmed provisions', checks['section_c_exactness']))
    lines.append('')
    lines.append('Planted missing-field detection')
    lines.append(_line('removed fields flagged', planted['detection']))
    lines.append(_line('false positives on clean controls', planted['false_positives']))
    lines.append('')
    lines.append('Schema validity')
    lines.append(_line('overall', schema['overall']))
    for kind, row in schema['by_kind'].items():
        lines.append(_line(kind, row))
    appeals = checks.get('appeals') or {}
    lines.extend(['', 'Appeals (weak labels)', appeals.get('note') or ''])
    cite_row = appeals.get('citation_resolution') or {}
    if 'label' in cite_row:
        lines.append(_line('citation resolution after mapping', cite_row))
    anchor = appeals.get('section_c_anchor') or {}
    if isinstance(anchor, dict) and 'quote_recorded' in anchor:
        lines.append(_line('0015414 Section C quote recorded', anchor['quote_recorded']))
        lines.append(_line('0015414 Section C engine probe', anchor['engine_flags_missing_section_c']))
    prof = appeals.get('professional_involvement') or {}
    if isinstance(prof, dict) and 'agreement' in prof:
        lines.append(_line('professional-involvement agreement', prof['agreement']))
    extra = appeals.get('anchors') or {}
    if isinstance(extra, dict) and 'insufficient_information_2022_06' in extra:
        lines.append(_line('2022-06 insufficient information', extra['insufficient_information_2022_06']['recorded']))
        lines.append(_line('0015427 accepted with a condition', extra['accepted_with_condition_0015427']['recorded']))
        lines.append(_line('2024-06 vs 0015432 deference opposed', extra['officer_deference_opposed']['recorded']))
    lines.extend(['', '--- json ---', json.dumps(report, indent=2)])
    return '\n'.join(lines) + '\n'


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--root', type=Path, default=DEV)
    ap.add_argument('--db', type=Path, default=None)
    ap.add_argument('--json', action='store_true')
    args = ap.parse_args(argv)
    db = args.db if args.db else find_codedb()
    if db is not None and not Path(db).is_file():
        db = None
    report = build_report(
        root=args.root,
        db_path=db,
        cases=load_cases(args.root / 'cases'),
        manifests=load_manifests(args.root / 'planted' / 'ab_minimal'),
        schemas=load_schemas(args.root / 'schemas'),
        appeals=load_appeals(args.root / 'appeals' / 'cases'),
    )
    text = render(report)
    if args.json:
        print(json.dumps(json.loads(text.split('--- json ---', 1)[1]), indent=2))
    else:
        print(text, end='')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
