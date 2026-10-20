"""Check evals_dev/cases/*.json against SCHEMA.md and the code database.

Queries SQLite directly (read-only), independently of the codedb.lookup path the author script used.
Exit 0 when every case passes; 1 otherwise.

    .venv/bin/python evals_dev/validate_cases.py [--db PATH] [--cases DIR]
"""
import argparse
import collections
import json
import os
import pathlib
import re
import sqlite3
import sys

ROOT = pathlib.Path(__file__).resolve().parent
REPO = ROOT.parent
DEFAULT_DB = str(REPO / 'codedb' / 'build' / 'codedb.sqlite')


def database_path() -> pathlib.Path:
    """Repo build, or BATATIS_CODEDB when that variable is set."""
    return pathlib.Path(os.environ['BATATIS_CODEDB']) if os.environ.get('BATATIS_CODEDB') else pathlib.Path(DEFAULT_DB)
APPLICANTS = {'manufacturer', 'homebuilder', 'contractor', 'architect-engineer', 'owner'}
TOPICS = {'part9-spatial-separation', 'part9-fire-separations', 'envelope-insulation-sheathing', 'cladding',
          'engineered-walls', 'single-exit', 'part3-fire-protection', 'part4-structural', 'out-of-scope'}
ENG = {'yes', 'no', 'depends'}
ACTIONS = {'ask', 'proceed_conditionally', 'redirect'}
ARTICLE_NO = re.compile(r'\b\d{1,2}\.\d{1,2}\.\d{1,2}\.\d{1,2}\.?')


def validate(cases, con):
    errors = []
    counts = collections.Counter()

    def err(cid, msg):
        errors.append(f'{cid}: {msg}')

    def exists(cid, div, pid, where):
        if con.execute("SELECT 1 FROM provisions WHERE doc='NBC-AE' AND division=? AND id=?", (div, pid)).fetchone() is None:
            err(cid, f'{where}: Div {div} {pid} not in database')
            return False
        return True

    seen = set()
    for c in cases:
        cid = c.get('id', '?')
        for key in ['id', 'applicant_type', 'topic', 'code_part', 'jurisdiction', 'seed_provision', 'description',
                    'known_facts', 'missing_info', 'gold', 'authoring']:
            if key not in c:
                err(cid, f'missing {key}')
        if not re.fullmatch(r'dev-\d{3}', cid) or cid in seen:
            err(cid, 'id must be unique dev-NNN')
        seen.add(cid)
        if c.get('applicant_type') not in APPLICANTS:
            err(cid, 'applicant_type')
        if c.get('topic') not in TOPICS:
            err(cid, 'topic')
        if ARTICLE_NO.search(c.get('description', '')):
            err(cid, 'description contains an article number')
        if c.get('authoring', {}).get('source') != 'codedb':
            err(cid, 'authoring.source must be codedb')
        for m in c.get('missing_info', []):
            if m.get('priority') not in ('critical', 'administrative') or not m.get('field') or not m.get('why'):
                err(cid, f'missing_info entry malformed: {m.get("field")}')
        exists(cid, 'B', c.get('seed_provision', ''), 'seed_provision')

        g = c.get('gold', {})
        for key in ['departure', 'must_cite', 'should_cite', 'must_not_cite', 'section_c', 'engineering_required',
                    'engineering_reason', 'engineering_citations', 'intake_action', 'out_of_scope', 'redirect_to']:
            if key not in g:
                err(cid, f'missing gold.{key}')
        for field in ['must_cite', 'should_cite', 'must_not_cite', 'engineering_citations']:
            for ref in g.get(field, []):
                if exists(cid, ref.get('division'), ref.get('provision'), field):
                    counts['citations_checked'] += 1
        if g.get('engineering_required') not in ENG:
            err(cid, 'engineering_required')
        if not g.get('engineering_citations'):
            err(cid, 'engineering decision has no citation')
        action = g.get('intake_action')
        if action not in ACTIONS:
            err(cid, 'intake_action')
        if action == 'ask':
            if g.get('must_cite'):
                err(cid, 'ask case must leave must_cite empty')
            if not any(m['priority'] == 'critical' for m in c.get('missing_info', [])):
                err(cid, 'ask case needs a critical missing field')
        if action == 'redirect' and not (g.get('out_of_scope') is True and g.get('redirect_to')):
            err(cid, 'redirect case needs out_of_scope true and redirect_to')
        if action != 'redirect' and g.get('out_of_scope'):
            err(cid, 'out_of_scope only for redirect')
        if action == 'proceed_conditionally':
            if not g.get('must_cite') or not g.get('departure'):
                err(cid, 'proceed case needs must_cite and departure')
            bench = {r['provision'] for r in g.get('must_cite', []) if r.get('division') == 'B' and r.get('role') == 'benchmark'}
            if not bench <= {r['provision'] for r in g.get('section_c', [])}:
                err(cid, 'every Div B benchmark needs a section_c row')

        # Section C rows equal the attribution table rows in the database
        for row in g.get('section_c', []):
            pid = row['provision']
            if not exists(cid, 'B', pid, 'section_c'):
                continue
            db_rows = con.execute("SELECT provision_id, bracket, application_note FROM attributions WHERE doc='NBC-AE' "
                                  "AND (provision_id=? OR provision_id LIKE ?)", (pid, pid + '(%')).fetchall()
            want_pairs = {b for _, b, n in db_rows if not n}
            want_cond = {(b, n) for _, b, n in db_rows if n}
            got_pairs = set(row.get('pairs', []))
            got_cond = {(x['pair'], x['when']) for x in row.get('conditional', [])}
            if got_pairs != want_pairs:
                err(cid, f'section_c {pid}: pairs {sorted(got_pairs ^ want_pairs)} differ from the table')
            if got_cond != want_cond:
                err(cid, f'section_c {pid}: conditional rows differ from the table')
            st = con.execute("SELECT status, root_provision FROM attribution_status WHERE doc='NBC-AE' AND provision_id=?",
                             (pid,)).fetchone()
            if (row.get('status'), row.get('root_provision')) != (tuple(st) if st else (None, None)):
                err(cid, f'section_c {pid}: status/root differs from the database')
            if not want_pairs and not want_cond and row.get('status') != 'none':
                err(cid, f'section_c {pid}: no table row but status is not none')
            counts['section_c_rows'] += 1
            counts['pairs_checked'] += len(got_pairs) + len(got_cond)
            counts['no_row_sentences'] += not (want_pairs or want_cond)

        counts['cases'] += 1
        counts['applicant_' + c.get('applicant_type', '?')] += 1
        counts['action_' + str(action)] += 1
        counts['topic_' + c.get('topic', '?')] += 1
        counts[f"part_{c.get('code_part')}"] += 1
    return errors, counts


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--db', default=str(database_path()))
    ap.add_argument('--cases', default=str(ROOT / 'cases'))
    a = ap.parse_args()
    con = sqlite3.connect(f'file:{a.db}?mode=ro', uri=True)
    cases = [json.loads(p.read_text()) for p in sorted(pathlib.Path(a.cases).glob('*.json'))]
    errors, counts = validate(cases, con)
    print(json.dumps({'ok': not errors, 'errors': errors, 'counts': dict(sorted(counts.items()))}, indent=2))
    sys.exit(1 if errors else 0)


if __name__ == '__main__':
    main()
