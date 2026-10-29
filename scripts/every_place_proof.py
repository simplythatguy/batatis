#!/usr/bin/env python
"""Prove, place by place, that Batatis works for every Alberta jurisdiction and says so where it does not.

    .venv/bin/python scripts/every_place_proof.py              # every place, about six minutes on eight workers
    .venv/bin/python scripts/every_place_proof.py --quick      # one place of every kind, about a minute
    .venv/bin/python scripts/every_place_proof.py --workers 4

Writes docs/verification/every-place/README.md and results.json, and prints a summary. Five checks:

1. Office: every one of the 390 Alberta places, by its legal name and every short name, names the office that
   reviews building work there. The expected office comes from the Safety Codes Council accreditation snapshot
   and the research table (docs/research/2026-10-28-every-jurisdiction), not from the generated place files.
2. Same application: the engine's synthetic sample application is exported for every covered Alberta place and
   compared with Calgary: the same code references in the final PDF and the same completeness findings.
3. Not covered: every place Batatis does not cover (outside Alberta, reserve land, national parks, places not
   confirmed) gets a blocking finding that names who to ask, and no final Alberta application.
4. No leaks: Calgary's and Edmonton's local items never reach another place.
5. Identification: the text code identification reads is the same whatever the place.

No model or network call is made. Needs the git-excluded code database at codedb/build/codedb.sqlite.
"""
from __future__ import annotations

import argparse
import io
import json
import os
import subprocess
import sys
import tempfile
import time
from collections import Counter, defaultdict
import multiprocessing
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
OUT = ROOT / 'docs' / 'verification' / 'every-place'

KIND_LABEL = {'accredited_municipality': 'Accredited municipality or settlement',
              'alberta_safety_codes_authority': 'Alberta Safety Codes Authority area',
              'first_nation': 'First Nation', 'federal': 'National park or Jasper townsite',
              'unconfirmed': 'Not confirmed (Lloydminster, Redwood Meadows)', 'outside_alberta': 'Outside Alberta'}

_W: dict = {}


def _env():
    os.environ.pop('VERCEL', None)
    os.environ['BATATIS_REVIEWER_CODES'] = '{"edmonton":"officer-secret","calgary":"calgary-secret"}'
    os.environ['BATATIS_AUTH_RATE_LIMIT'] = '100000'


def _worker_init():
    _env()
    from fastapi.testclient import TestClient
    from engine.api import create_app
    from engine.store import CaseStore
    from engine.tests.test_accounts import onboard, signup
    tmp = tempfile.mkdtemp(prefix='every-place-')
    store = CaseStore(Path(tmp) / 'cases.sqlite')
    client = TestClient(create_app(store=store), base_url='http://localhost')
    client.__enter__()
    assert signup(client, f'proof-{os.getpid()}@example.test', 'Proof').status_code == 201
    _W.update(client=client, store=store, owner=onboard(client))


def run_place(place_id: str) -> dict:
    """Export the sample application for one place. Covered: final PDF. Not covered: final (must refuse) and draft."""
    from pypdf import PdfReader
    from engine.codes import Codes
    from engine.export.sample import sample_case
    from engine.jurisdictions import registry
    from engine.models import Jurisdiction
    from engine.tests.case_builder_fixtures import store_with_synthetic_files
    from engine.tests.test_every_place import PROVISION_ID
    client, store, owner = _W['client'], _W['store'], _W['owner']
    reg = registry()
    pack = reg.get(reg.place_packs[place_id])
    started = time.perf_counter()
    case = sample_case(Codes())
    case.owner_id = owner['id']
    case.jurisdiction = Jurisdiction(id=place_id, name=reg.places[place_id].name)
    case.authority = pack.authority.reviewer_code
    case = store_with_synthetic_files(store, case)
    body = client.get(f'/cases/{case.id}/gaps').json()
    gaps = body['items'] if isinstance(body, dict) else body
    final = client.post(f'/cases/{case.id}/export', json={'draft': False})
    row = {'place': place_id, 'pack': pack.id, 'covered': pack.coverage == 'full', 'final_status': final.status_code,
           'core_gaps': sorted([g['id'], g['severity']] for g in gaps if g['severity'] != 'info'),
           'coverage_gap': next((g['message'] for g in gaps if g['id'] == 'coverage:jurisdiction'), None)}
    if final.status_code == 200:
        text = '\n'.join(p.extract_text() or '' for p in PdfReader(io.BytesIO(final.content)).pages)
        row.update(ids=sorted(set(PROVISION_ID.findall(text))), pages=len(PdfReader(io.BytesIO(final.content)).pages),
                   calgary_form_note='Request for Specific Variance' in text)
    else:
        row['final_reasons'] = (final.json().get('detail') or {}).get('reasons', [])
        draft = client.post(f'/cases/{case.id}/export', json={'draft': True})
        row['draft_status'] = draft.status_code
    submit = client.post(f'/cases/{case.id}/submit', json={'expected_version': client.get(f'/cases/{case.id}').json()['version']})
    row['submit_status'] = submit.status_code
    row['seconds'] = round(time.perf_counter() - started, 1)
    return row


def office_check() -> list[dict]:
    from engine.jurisdictions import registry
    from engine.models import Jurisdiction
    from engine.tests.test_every_place import LOCAL_PACKS, OUTSIDE, ROWS, expected
    reg = registry()
    out = []
    for row in ROWS:
        kind, office, covered = expected(row)
        place_id = next(pid for pid, p in reg.places.items() if p.name == row['legal_name'])
        place = reg.places[place_id]
        for typed in [row['legal_name'], *place.aliases, place_id]:
            found = reg.resolve(Jurisdiction(id=typed if typed == place_id else 'x-typed', name=typed))
            pack = found.pack
            ok = (found.matched_by in {'id', 'name'} and pack.authority.kind == kind and (pack.coverage == 'full') is covered
                  and (office is None or pack.authority.name == office)
                  and (pack.id == LOCAL_PACKS.get(row['legal_name'], pack.id)))
            out.append({'place': row['legal_name'], 'typed': typed, 'kind': kind, 'expected_office': office,
                        'office': pack.authority.name, 'covered': pack.coverage == 'full', 'ok': ok})
    from engine.tests.test_every_place import EVERYDAY
    for typed, kind, covered, office in EVERYDAY:   # what applicants type, answers written by hand
        pack = reg.resolve(Jurisdiction(id='x-typed', name=typed)).pack
        ok = pack.authority.kind == kind and (pack.coverage == 'full') is covered and (office is None or pack.authority.name == office)
        out.append({'place': typed, 'typed': typed, 'kind': kind, 'expected_office': office, 'everyday': True,
                    'office': pack.authority.name, 'covered': pack.coverage == 'full', 'ok': ok})
    for p in OUTSIDE:
        for typed in [p['name'], *p['aliases']]:
            pack = reg.resolve(Jurisdiction(id='x-typed', name=typed)).pack
            ok = pack.coverage == 'preview' and pack.authority.kind == 'outside_alberta' and pack.province != 'AB'
            out.append({'place': p['name'], 'typed': typed, 'kind': 'outside_alberta', 'expected_office': p['office'],
                        'office': pack.authority.name, 'covered': pack.coverage == 'full', 'ok': ok})
    return out


def leak_check() -> list[str]:
    from engine.jurisdictions import export_notice, notices_for, registry
    from engine.models import Case, Jurisdiction
    from engine.tests.test_every_place import LOCAL_PACKS
    reg, bad = registry(), []
    for place_id, pack_id in reg.place_packs.items():
        if pack_id in LOCAL_PACKS.values():
            continue
        case = Case(title='SYNTHETIC', jurisdiction=Jurisdiction(id=place_id, name=reg.places[place_id].name))
        pack = reg.get(pack_id)
        if notices_for(case, 'gaps') or export_notice(case) or pack.standing_packages or pack.guides or pack.forms:
            bad.append(place_id)
    return bad


def identification_check() -> int:
    from engine.identify.case_input import compose
    from engine.jurisdictions import registry
    from engine.models import Case, Fact, Jurisdiction, Source
    said = 'SYNTHETIC: continuous exterior insulation under fibre-cement cladding on a Part 9 house.'
    fact = Fact(field='project.description', value=said, kind='pointed', status='confirmed',
                source=Source(type='user_text', ref='synthetic-proof:applicant', quote=said))
    texts = {compose(Case(title='SYNTHETIC', facts=[fact], jurisdiction=Jurisdiction(id=pid, name=pid))).text
             for pid in registry().places}
    return len(texts)


def commit() -> str:
    try:
        sha = subprocess.run(['git', 'rev-parse', '--short', 'HEAD'], cwd=ROOT, capture_output=True, text=True).stdout.strip()
        dirty = subprocess.run(['git', 'status', '--porcelain', '--', 'engine'], cwd=ROOT, capture_output=True, text=True).stdout.strip()
        return sha + (' with uncommitted engine changes' if dirty else '')
    except OSError:
        return 'unknown'


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--quick', action='store_true', help='one place of every kind instead of every place')
    ap.add_argument('--workers', type=int, default=min(8, os.cpu_count() or 2))
    args = ap.parse_args(argv)
    _env()
    from engine.jurisdictions import registry
    from engine.tests._db_skip import REPO_DB
    from engine.tests.test_every_place import COVERED, NOT_COVERED, SAMPLE_COVERED, SAMPLE_NOT_COVERED
    if not REPO_DB.is_file() and not os.environ.get('BATATIS_CODEDB'):
        print('The code database is missing (codedb/build/codedb.sqlite); the export checks need it.', file=sys.stderr)
        return 2
    t0 = time.perf_counter()
    reg = registry()
    offices = office_check()
    leaks = leak_check()
    texts = identification_check()
    covered = SAMPLE_COVERED if args.quick else COVERED
    not_covered = SAMPLE_NOT_COVERED if args.quick else NOT_COVERED
    places = ['calgary'] + [p for p in covered + not_covered if p != 'calgary']
    # Workers keep the test client's threads alive, so the pool is terminated, not joined, once results are in.
    pool = multiprocessing.get_context('spawn').Pool(args.workers, initializer=_worker_init)
    try:
        runs = {}
        for i, r in enumerate(pool.imap_unordered(run_place, places), 1):
            runs[r['place']] = r
            if i % 25 == 0 or i == len(places):
                print(f'  {i}/{len(places)} applications exported', file=sys.stderr, flush=True)
    finally:
        pool.terminate()
        pool.join()
    base = runs['calgary']
    same, refused = [], []
    for pid in covered:
        r = runs[pid]
        ok = (r['final_status'] == 200 and r['ids'] == base['ids'] and r['core_gaps'] == base['core_gaps']
              and r['coverage_gap'] is None and (pid == 'calgary' or not r['calgary_form_note'])
              and (r['submit_status'] == 200) == bool(reg.get(r['pack']).authority.reviewer_code))
        same.append({**r, 'ok': ok})
    for pid in not_covered:
        r = runs[pid]
        ok = (r['final_status'] == 409 and r['draft_status'] == 200 and bool(r['coverage_gap'])
              and any('does not prepare applications' in x for x in r['final_reasons']) and r['submit_status'] != 200)
        refused.append({**r, 'ok': ok})
    seconds = round(time.perf_counter() - t0)
    kind_of = {pid: reg.get(reg.place_packs[pid]).authority.kind for pid in reg.places}
    table = defaultdict(lambda: Counter())
    for r in same:
        table[kind_of[r['place']]]['same_runs'] += 1
        table[kind_of[r['place']]]['same_ok'] += r['ok']
    for r in refused:
        table[kind_of[r['place']]]['refused_runs'] += 1
        table[kind_of[r['place']]]['refused_ok'] += r['ok']
    by_place = defaultdict(list)
    everyday = [o for o in offices if o.get('everyday')]
    for o in offices:
        if not o.get('everyday'):
            by_place[o['place']].append(o['ok'])
    for name, oks in by_place.items():
        kind = next(o['kind'] for o in offices if o['place'] == name and not o.get('everyday'))
        table[kind]['places'] += 1
        table[kind]['office_ok'] += all(oks)
    failures = ([f"office: {o['typed']} -> {o['office']} (expected {o['expected_office']})" for o in offices if not o['ok']]
                + [f"same application: {r['place']}" for r in same if not r['ok']]
                + [f"not covered: {r['place']}" for r in refused if not r['ok']]
                + [f'leak: {p}' for p in leaks] + ([f'identification text differs across places ({texts} texts)'] if texts != 1 else []))
    result = {'generated_at': datetime.now(timezone.utc).isoformat(timespec='seconds'), 'commit': commit(),
              'mode': 'quick' if args.quick else 'every place', 'workers': args.workers, 'seconds': seconds,
              'names_checked': len(offices), 'places': len(by_place), 'covered_runs': len(same), 'not_covered_runs': len(refused),
              'everyday_names': {'checked': len(everyday), 'ok': sum(o['ok'] for o in everyday),
                                 'examples': [o['typed'] for o in everyday]},
              'calgary_baseline': {'code_references': len(base['ids']), 'pdf_pages': base['pages'],
                                   'findings': len(base['core_gaps'])},
              'identification_texts': texts, 'leaks': leaks, 'failures': failures,
              'by_kind': {k: dict(v) for k, v in table.items()}, 'covered': same, 'not_covered': refused}
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / 'results.json').write_text(json.dumps(result, indent=1, ensure_ascii=False) + '\n', encoding='utf-8')
    (OUT / 'README.md').write_text(render(result), encoding='utf-8')
    print(render(result).split('## How the checks work')[0])
    return 1 if failures else 0


def render(r: dict) -> str:
    order = ['accredited_municipality', 'alberta_safety_codes_authority', 'first_nation', 'federal', 'unconfirmed',
             'outside_alberta']
    rows = []
    for k in order:
        v = r['by_kind'].get(k, {})
        office = f"{v.get('office_ok', 0)} / {v.get('places', 0)}"
        same = f"{v.get('same_ok', 0)} / {v.get('same_runs', 0)}" if v.get('same_runs') else '-'
        refused = f"{v.get('refused_ok', 0)} / {v.get('refused_runs', 0)}" if v.get('refused_runs') else '-'
        rows.append(f'| {KIND_LABEL[k]} | {office} | {same} | {refused} |')
    totals = {key: sum(v.get(key, 0) for v in r['by_kind'].values())
              for key in ('places', 'office_ok', 'same_runs', 'same_ok', 'refused_runs', 'refused_ok')}
    rows.append(f"| **All places** | **{totals['office_ok']} / {totals['places']}** | **{totals['same_ok']} / {totals['same_runs']}**"
                f" | **{totals['refused_ok']} / {totals['refused_runs']}** |")
    fail = '\n'.join(f'- {f}' for f in r['failures']) or 'None.'
    base = r['calgary_baseline']
    slow = sorted(r['covered'] + r['not_covered'], key=lambda x: -x['seconds'])[:1]
    return f"""# Every place: does Batatis work outside Calgary and Edmonton?

Run {r['generated_at']} on commit `{r['commit']}` ({r['mode']}, {r['workers']} workers, {r['seconds']} s). Generated by
`scripts/every_place_proof.py`; do not edit by hand.

| Kind of place | Names the right office | Same application as Calgary | Not covered, says so, no Alberta PDF |
|---|---:|---:|---:|
{chr(10).join(rows)}

- **Office**: {r['names_checked']} names typed ({r['places']} places, by legal name, every short name and id); the
  expected office comes from the Safety Codes Council accreditation snapshot and the research table.
- **What people type**: {r['everyday_names']['ok']} / {r['everyday_names']['checked']} everyday names answered as written
  by hand from the research, for example {', '.join(r['everyday_names']['examples'][:6])}.
- **Same application**: the sample application exported for each covered Alberta place has the same
  {base['code_references']} code references as Calgary's ({base['pdf_pages']} pages), the same {base['findings']}
  completeness findings, and no Calgary-only form note. Only Calgary and Edmonton can send it to an officer
  inside Batatis; everywhere else the applicant exports the PDF.
- **Not covered**: each place gets a blocking finding that names who to ask; the final application is refused
  and the draft still opens.
- **No leaks**: {len(r['leaks'])} places received Calgary or Edmonton local items.
- **Identification**: {r['identification_texts']} distinct input text across {r['places'] + 0} places (1 means the place
  never changes what code identification reads).

Failures: {fail}

## How the checks work

The engine runs in-process through its real API routes (`/gaps`, `/export`, `/submit`), the same code the app
calls. The application is the engine's synthetic sample (`engine/export/sample.py`: continuous exterior
insulation on a Part 9 house, five Division B provisions, synthetic attachments). Only the place changes.
`engine/tests/test_every_place.py` runs one place of every kind on every engine test run; this script runs all.

Sources of truth: `docs/research/2026-10-28-every-jurisdiction/alberta-scc-snapshot.json` (Safety Codes Council
accreditation search, 2026-10-29) and `alberta-jurisdictions.csv` (390 places with their sources). The place files the
app reads are generated from them by `python -m engine.jurisdictions.places_build`, and a test fails if they drift.

## What this does not show

- Code identification accuracy itself. The place cannot change it (check 5), and the research measured it on 653 real
  cases by place: `docs/research/2026-10-28-every-jurisdiction/evidence/evidence.md`.
- Local intake steps and fees outside Calgary and Edmonton. Batatis names the office and links its sources; the
  applicant confirms the steps with that office.
- Hamlets and unlisted localities. A name Batatis does not know keeps the general Alberta answer
  (accredited municipality, or the Alberta Safety Codes Authority) and asks the applicant to confirm.
"""


if __name__ == '__main__':
    raise SystemExit(main())
