"""Does Batatis give other places the same results as Calgary and Edmonton? Two tests on the real engine.

Test 1 (routing): for every row of alberta-jurisdictions.csv and 31 cities outside Alberta, which jurisdiction
pack the engine resolves, and whether that answer names the right reviewing office (see `verdict`).

Test 2 (same application, different place): the engine's SYNTHETIC sample application (5 Division B provisions,
complete facts, synthetic attachments) is stored once per place with only the place changed. For each place it
records the resolved pack, the completeness gaps, the exported draft and final PDFs (pages, provision ids in the
text), and whether in-app submission to an officer works. Every result is compared with Calgary and Edmonton.

No model or network call is made. Needs the git-excluded code database at codedb/build/codedb.sqlite.
Run from the repository root:  .venv/bin/python docs/research/2026-10-28-every-jurisdiction/evidence/place_parity.py
"""
from __future__ import annotations

import csv
import hashlib
import io
import json
import os
import re
import sys
import tempfile
from collections import Counter
from contextlib import ExitStack
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
sys.path.insert(0, str(ROOT))
os.environ.pop('VERCEL', None)
os.environ['BATATIS_REVIEWER_CODES'] = '{"edmonton":"officer-secret","calgary":"calgary-secret"}'
os.environ['BATATIS_AUTH_RATE_LIMIT'] = '1000'

from fastapi.testclient import TestClient  # noqa: E402
from pypdf import PdfReader  # noqa: E402

from engine.api import create_app  # noqa: E402
from engine.codes import Codes  # noqa: E402
from engine.export.sample import PROVISIONS, sample_case  # noqa: E402
from engine.jurisdictions import registry  # noqa: E402
from engine.models import Jurisdiction  # noqa: E402
from engine.section_c import section_c_rows  # noqa: E402
from engine.store import CaseStore  # noqa: E402
from engine.tests.case_builder_fixtures import store_with_synthetic_files  # noqa: E402
from engine.tests.test_accounts import onboard, signup  # noqa: E402

CSV = HERE.parent / 'alberta-jurisdictions.csv'
PLACE_NAMES = json.loads((ROOT / 'engine/data/jurisdictions/place_names.json').read_text())['places']

# Outside Alberta: the cities the research covered (ontario-quebec.md, rest-of-canada.md).
CITIES = [('Vancouver', 'BC'), ('Surrey', 'BC'), ('Burnaby', 'BC'), ('Victoria', 'BC'), ('Winnipeg', 'MB'),
          ('Saskatoon', 'SK'), ('Regina', 'SK'), ('Toronto', 'ON'), ('Ottawa', 'ON'), ('Mississauga', 'ON'),
          ('Brampton', 'ON'), ('Hamilton', 'ON'), ('London', 'ON'), ('Markham', 'ON'), ('Vaughan', 'ON'),
          ('Kitchener', 'ON'), ('Windsor', 'ON'), ('Montréal', 'QC'), ('Québec', 'QC'), ('Laval', 'QC'),
          ('Gatineau', 'QC'), ('Longueuil', 'QC'), ('Halifax', 'NS'), ('Fredericton', 'NB'), ('Moncton', 'NB'),
          ('Saint John', 'NB'), ('Charlottetown', 'PE'), ("St. John's", 'NL'), ('Whitehorse', 'YT'),
          ('Yellowknife', 'NT'), ('Iqaluit', 'NU')]

# Test 2 sample: one place of every kind, plus outside-Alberta cities. Names are what an applicant would type.
SAMPLE = [('City of Calgary', 'accredited_municipality'), ('City of Edmonton', 'accredited_municipality'),
          ('City of Red Deer', 'accredited_municipality'), ('City of Lethbridge', 'accredited_municipality'),
          ('Strathcona County', 'accredited_municipality'), ('Town of Tofield', 'accredited_municipality'),
          ('Lacombe County', 'asca'), ('Kikino Metis Settlement', 'metis_settlement'),
          ('East Prairie Metis Settlement', 'asca'), ('Tsuut\'ina Nation', 'first_nation'),
          ('Municipality of Jasper', 'federal'), ('City of Lloydminster', 'other'),
          ('Vancouver', 'outside_alberta'), ('Toronto', 'outside_alberta'), ('Ottawa', 'outside_alberta'),
          ('Montréal', 'outside_alberta'), ('Winnipeg', 'outside_alberta'), ('Iqaluit', 'outside_alberta')]

PREFIX = re.compile(r'^(City|Town|Village|Summer Village|County|Municipal District|Municipality|Regional Municipality) of ',
                    re.I)
PROVISION_ID = re.compile(r'\b\d{1,2}\.\d{1,2}\.\d{1,2}\.\d{1,2}\.(?:\(\d+\))?')


def slug(text: str) -> str:
    return re.sub(r'[^a-z0-9]+', '-', text.lower()).strip('-')


def short(name: str) -> str:
    return PREFIX.sub('', name).strip()


def what_the_app_sends(name: str) -> tuple[Jurisdiction, str | None]:
    """Mirror web/src/config.ts resolveOffice: a local pack's id and reviewer code, else the typed place."""
    reg = registry()
    hit = reg.resolve(Jurisdiction(id=slug(name), name=name))
    if hit and not hit.pack.fallback:
        return Jurisdiction(id=hit.pack.id, name=name), hit.pack.authority.reviewer_code
    return Jurisdiction(id=slug(name), name=name), None


def verdict(kind: str, pack) -> str:
    if not pack:
        return 'no answer'
    if not pack.fallback:
        return 'names the office'
    if kind in ('accredited_municipality', 'asca', 'metis_settlement'):
        return 'right rules, office not named'
    return 'wrong office type'   # First Nation, federal land, Lloydminster, or outside Alberta


def routing_test() -> dict:
    rows = list(csv.DictReader(CSV.open(encoding='utf-8')))
    out, places = [], {p.lower() for p in PLACE_NAMES}
    for row in rows:
        for typed in sorted({row['legal_name'], short(row['legal_name'])}):
            jur, code = what_the_app_sends(typed)
            res = registry().resolve(jur, code)
            out.append({'place': row['legal_name'], 'typed': typed, 'kind': row['building_ahj_kind'],
                        'true_office': row['building_ahj'], 'pack': res.pack.id if res else None,
                        'matched_by': res.matched_by if res else None,
                        'app_says': res.pack.authority.name if res else None,
                        'in_picker_list': typed.lower() in places, 'verdict': verdict(row['building_ahj_kind'], res and res.pack)})
    for city, prov in CITIES:
        jur, code = what_the_app_sends(city)
        res = registry().resolve(jur, code)
        out.append({'place': f'{city}, {prov}', 'typed': city, 'kind': 'outside_alberta', 'true_office': f'{city} ({prov})',
                    'pack': res.pack.id if res else None, 'matched_by': res.matched_by if res else None,
                    'app_says': res.pack.authority.name if res else None, 'in_picker_list': city.lower() in places,
                    'verdict': verdict('outside_alberta', res and res.pack)})
    return {'rows': out}


def pdf_facts(data: bytes) -> dict:
    reader = PdfReader(io.BytesIO(data))
    text = '\n'.join(page.extract_text() or '' for page in reader.pages)
    return {'pages': len(reader.pages), 'provision_ids': sorted(set(PROVISION_ID.findall(text))), 'text': text}


def same_application_test() -> dict:
    codes = Codes()
    sc_reference = [r.model_dump() for r in section_c_rows(list(PROVISIONS), codes)]
    sc_hash = hashlib.sha256(json.dumps(sc_reference, sort_keys=True).encode()).hexdigest()[:12]
    results = []
    with tempfile.TemporaryDirectory() as tmp, ExitStack() as stack:
        store = CaseStore(Path(tmp) / 'cases.sqlite')
        client = stack.enter_context(TestClient(create_app(store=store), base_url='http://localhost'))
        assert signup(client, 'parity@example.test', 'Parity').status_code == 201
        owner = onboard(client)
        for name, kind in SAMPLE:
            jur, code = what_the_app_sends(name)
            case = sample_case(codes)
            case.owner_id, case.jurisdiction, case.authority = owner['id'], jur, code
            case = store_with_synthetic_files(store, case)
            pack = client.get(f'/cases/{case.id}/jurisdiction/pack').json()
            body = client.get(f'/cases/{case.id}/gaps').json()
            gaps = body['items'] if isinstance(body, dict) else body
            exports = {}
            for draft in (True, False):
                r = client.post(f'/cases/{case.id}/export', json={'draft': draft})
                facts = pdf_facts(r.content) if r.status_code == 200 and r.content.startswith(b'%PDF') else {}
                exports['draft' if draft else 'final'] = {
                    'status': r.status_code, 'pages': facts.get('pages'), 'provision_ids': facts.get('provision_ids'),
                    'place_named_in_pdf': bool(facts) and short(name).lower() in facts['text'].lower(),
                    'jurisdiction_notice_header': r.headers.get('x-batatis-jurisdiction-notice')}
            current = client.get(f'/cases/{case.id}').json()
            submit = client.post(f'/cases/{case.id}/submit', json={'expected_version': current['version']})
            results.append({
                'place': name, 'kind': kind, 'sent_jurisdiction': jur.model_dump(), 'sent_reviewer_code': code,
                'pack': pack['pack']['id'] if pack['pack'] else None, 'matched_by': pack['matched_by'],
                'app_says_office': pack['pack']['authority']['name'] if pack['pack'] else None,
                'local_items': {k: len(pack['pack'][k]) for k in ('standing_packages', 'guides', 'notices')}
                if pack['pack'] else None,
                'gaps': sorted((g['id'], g['severity'], bool(g.get('submission_blocking'))) for g in gaps),
                'section_c_hash': sc_hash,
                'export': exports,
                'submit_status': submit.status_code,
                'submit_detail': (submit.json().get('detail') if submit.status_code != 200 else 'submitted'),
            })
    return {'provisions': list(PROVISIONS), 'section_c_rows': len(sc_reference), 'section_c_hash': sc_hash,
            'results': results}


def compare(test2: dict) -> list[dict]:
    """Each place against Calgary and Edmonton: what is identical and what differs."""
    by = {r['place']: r for r in test2['results']}
    base = [by['City of Calgary'], by['City of Edmonton']]

    def core_gaps(r):   # info notices come from local packs; everything else is the application itself
        return sorted(g for g in r['gaps'] if g[1] != 'info')

    rows = []
    for r in test2['results']:
        rows.append({
            'place': r['place'], 'kind': r['kind'],
            'same_blocking_and_admin_gaps': all(core_gaps(r) == core_gaps(b) for b in base),
            'same_section_b_ids_in_final_pdf': all(r['export']['final']['provision_ids'] == b['export']['final']['provision_ids'] for b in base),
            'same_section_c': True,   # section_c_rows takes only provision ids and the code database
            'final_pdf_exports': r['export']['final']['status'] == 200,
            'final_pdf_pages': r['export']['final']['pages'],
            'office_named': r['pack'] in ('calgary', 'edmonton'),
            'in_app_officer_review': r['submit_status'] == 200,
            'local_pack_items': r['local_items'],
            'info_notices': [g[0] for g in r['gaps'] if g[1] == 'info'],
        })
    return rows


def main() -> None:
    t1 = routing_test()
    t2 = same_application_test()
    cmp_rows = compare(t2)
    for r in t2['results']:
        for e in r['export'].values():
            e.pop('text', None)
    out = {'routing': t1, 'same_application': t2, 'comparison': cmp_rows,
           'counts': {'routing_rows': len(t1['rows']),
                      'routing_verdicts_by_kind': {k: dict(Counter(x['verdict'] for x in t1['rows'] if x['kind'] == k))
                                                   for k in sorted({x['kind'] for x in t1['rows']})}}}
    (HERE / 'place_parity.json').write_text(json.dumps(out, indent=1, ensure_ascii=False) + '\n', encoding='utf-8')
    print(json.dumps(out['counts'], indent=1))
    for row in cmp_rows:
        print(row)


if __name__ == '__main__':
    main()
