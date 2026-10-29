"""Every place an applicant can name resolves to the office that reviews building work there, and every Alberta
place Batatis covers gets the same application as Calgary and Edmonton.

The expected office comes from the research inputs, not from the generated place files: the Safety Codes
Council accreditation snapshot of 2026-10-29 and the research table (docs/research/2026-10-28-every-jurisdiction).
Tests that export a PDF need the git-excluded code database and skip without it, as elsewhere in this suite.
"""
from __future__ import annotations

import csv
import io
import json
import re
import unicodedata
from contextlib import ExitStack

import pytest
from fastapi.testclient import TestClient
from pypdf import PdfReader

from engine.api import create_app
from engine.codes import Codes
from engine.export.sample import sample_case
from engine.identify.case_input import compose
from engine.jurisdictions import export_notice, notices_for, places_build, registry
from engine.models import Case, Fact, Jurisdiction, Source
from engine.store import CaseStore
from engine.tests._db_skip import require_repo_db
from engine.tests.case_builder_fixtures import store_with_synthetic_files
from engine.tests.test_accounts import onboard, signup

RESEARCH = places_build.RESEARCH
ROWS = list(csv.DictReader((RESEARCH / 'alberta-jurisdictions.csv').open(encoding='utf-8')))
SNAPSHOT = json.loads((RESEARCH / 'alberta-scc-snapshot.json').read_text(encoding='utf-8'))
A16 = json.loads(places_build.A16.read_text(encoding='utf-8'))


def norm(name: str) -> str:
    return unicodedata.normalize('NFKD', name).encode('ascii', 'ignore').decode().casefold()


HOLDS_BUILDING = {norm(o['organization']) for o in SNAPSHOT['municipalities'] if 'Building' in o['disciplines']}
# The Council sometimes names an organization differently from the population list (Special Areas No. 2-4,
# Kikino Métis Settlement); the A16 inventory recorded which Council names belong to each municipal code.
SCC_NAMES = {r['lg_code']: r.get('scc_organization_names') or []
             for r in A16['accredited_municipal_roster_all_330'] + A16['accredited_metis_settlements']}


def holds_building(row: dict) -> bool:
    return any(norm(n) in HOLDS_BUILDING for n in [row['legal_name'], *SCC_NAMES.get(row['lg_code'], [])])
PARK_CODES = {'0159', '0164', '0167', '0168', '0179', '0418'}       # five park districts and the Jasper townsite
UNCONFIRMED_CODES = {'0206', '0462'}                                # Lloydminster, Redwood Meadows
AIRPORTS = {'Calgary International Airport lands (Calgary Airport Authority)': 'City of Calgary',
            'Springbank Airport lands (Calgary Airport Authority)': 'Rocky View County',
            'Edmonton International Airport lands (Edmonton Regional Airports Authority)': 'Leduc County'}
LOCAL_PACKS = {'City of Calgary': 'calgary', 'City of Edmonton': 'edmonton'}
OUTSIDE = json.loads((places_build.OUT_DIR / 'outside-alberta.json').read_text(encoding='utf-8'))['places']
RESEARCH_CITIES = ['Vancouver', 'Surrey', 'Burnaby', 'Victoria', 'Winnipeg', 'Saskatoon', 'Regina', 'Toronto', 'Ottawa',
                   'Mississauga', 'Brampton', 'Hamilton', 'London', 'Markham', 'Vaughan', 'Kitchener', 'Windsor',
                   'Montréal', 'Québec City', 'Laval', 'Gatineau', 'Longueuil', 'Halifax', 'Fredericton', 'Moncton',
                   'Saint John', 'Charlottetown', "St. John's", 'Whitehorse', 'Yellowknife', 'Iqaluit']
PROVISION_ID = re.compile(r'\b\d{1,2}\.\d{1,2}\.\d{1,2}\.\d{1,2}\.(?:\(\d+\))?')


def expected(row: dict) -> tuple[str, str | None, bool]:
    """(authority kind, office or None, covered) for a research row, from the raw inputs."""
    name, code = row['legal_name'], row['lg_code']
    if row['type'] == 'Airport lands':
        return 'accredited_municipality', AIRPORTS[name], True
    if row['type'] == 'First Nation':
        return 'first_nation', name, False
    if code in PARK_CODES:
        return 'federal', 'Parks Canada', False
    if code in UNCONFIRMED_CODES:
        return 'unconfirmed', None, False
    if holds_building(row):
        return 'accredited_municipality', name, True
    return 'alberta_safety_codes_authority', 'Alberta Safety Codes Authority', True


def resolve(name: str, place_id: str | None = None):
    return registry().resolve(Jurisdiction(id=place_id or name, name=name))


def test_the_committed_place_files_are_what_the_research_builds():
    assert places_build.main(['--check']) == 0


def test_the_research_table_and_the_council_snapshot_agree():
    for row in ROWS:
        if row['type'] in {'City', 'Town', 'Village', 'Summer Village', 'Municipal District', 'Specialized Municipality',
                           'Improvement District', 'Special Areas', 'Metis Settlement'} and row['lg_code'] not in PARK_CODES | UNCONFIRMED_CODES:
            assert (row['building_accredited'] == 'true') == holds_building(row), row['legal_name']


@pytest.mark.parametrize('row', ROWS, ids=[r['legal_name'] for r in ROWS])
def test_every_alberta_place_names_the_office_that_reviews_building_work(row):
    kind, office, covered = expected(row)
    found = resolve(row['legal_name'])
    assert found is not None and found.matched_by in {'id', 'name'}, 'a named place never falls back'
    pack = found.pack
    assert pack.authority.kind == kind
    assert office is None or pack.authority.name == office
    assert (pack.coverage == 'full') is covered
    assert pack.authority.sources and all(s.url.startswith('https://') for s in pack.authority.sources)
    if row['legal_name'] in LOCAL_PACKS:
        assert pack.id == LOCAL_PACKS[row['legal_name']] and pack.authority.reviewer_code
    else:
        assert pack.id in registry().generated and pack.authority.reviewer_code is None


@pytest.mark.parametrize('place_id', sorted(registry().places), ids=sorted(registry().places))
def test_a_place_resolves_the_same_by_id_and_by_every_name(place_id):
    place = registry().places[place_id]
    target = registry().place_packs[place_id]
    assert resolve(place_id, place_id).pack.id == target
    for name in [place.name, *place.aliases]:
        assert resolve(name, 'x-unknown-id').pack.id == target, name


@pytest.mark.parametrize('name, office, kind, covered', [
    ('Lacombe County', 'Alberta Safety Codes Authority', 'alberta_safety_codes_authority', True),   # SCC M000374, Fire only
    ('City of Lacombe', 'City of Lacombe', 'accredited_municipality', True),                       # SCC M000373, Building
    ('Red Deer', 'City of Red Deer', 'accredited_municipality', True),
    ('Strathcona County', 'Strathcona County', 'accredited_municipality', True),
    ('Banff', 'Town of Banff', 'accredited_municipality', True),                                   # the town reviews its own
    ('Lake Louise', 'Parks Canada', 'federal', False),                                             # in Banff National Park
    ('Jasper', 'Parks Canada', 'federal', False),
    ("Tsuut'ina Nation", "Tsuut'ina Nation", 'first_nation', False),
    ('Kikino Metis Settlement', 'Kikino Metis Settlement', 'accredited_municipality', True),
    ('East Prairie Metis Settlement', 'Alberta Safety Codes Authority', 'alberta_safety_codes_authority', True),
    ('Calgary International Airport', 'City of Calgary', 'accredited_municipality', True),
    ('Lloydminster', 'City of Lloydminster', 'unconfirmed', False),
    ('Vancouver', 'City of Vancouver', 'outside_alberta', False),
    ('Montreal', 'Régie du bâtiment du Québec, or the City of Montréal for exempt buildings', 'outside_alberta', False),
])
def test_spot_checks_from_the_research(name, office, kind, covered):
    pack = resolve(name, 'x-unknown-id').pack
    assert (pack.authority.name, pack.authority.kind, pack.coverage == 'full') == (office, kind, covered)


def test_every_researched_city_outside_alberta_is_not_covered():
    names = {p['name'] for p in OUTSIDE}
    assert set(RESEARCH_CITIES) <= names
    for place in OUTSIDE:
        pack = resolve(place['name'], 'x-unknown-id').pack
        assert pack.province != 'AB' and pack.coverage == 'preview' and pack.authority.kind == 'outside_alberta'
        assert 'outside Alberta' in pack.summary and pack.code_edition != places_build.NBC_AE


# What applicants actually type, with the answer written by hand from the research (not read from the place files).
EVERYDAY = [
    ('Siksika', 'first_nation', False, 'Siksika Nation'),
    ('Tsuut\u2019ina Nation', 'first_nation', False, "Tsuut'ina Nation"),        # a curly apostrophe
    ("Tsuut'ina", 'first_nation', False, "Tsuut'ina Nation"),
    ('Enoch', 'first_nation', False, 'Enoch Cree Nation #440'),
    ('Kainai', 'first_nation', False, 'Blood Tribe'),
    ('Stoney Nakoda', 'first_nation', False, None),
    ('Maskwacis', 'first_nation', False, None),
    ('Redwood Meadows', 'unconfirmed', False, None),
    ('Lloydminster, SK', 'unconfirmed', False, 'City of Lloydminster'),
    ('Toronto, ON', 'outside_alberta', False, None),
    ('Montreal', 'outside_alberta', False, None),
    ('Kikino Métis Settlement', 'accredited_municipality', True, 'Kikino Metis Settlement'),   # the Council's spelling
    ('Red Deer, AB', 'accredited_municipality', True, 'City of Red Deer'),
    ('Fort McMurray', 'accredited_municipality', True, 'Regional Municipality of Wood Buffalo'),
    ('Sherwood Park', 'accredited_municipality', True, 'Strathcona County'),
    ('Cold Lake', 'accredited_municipality', True, 'City of Cold Lake'),           # not Cold Lake First Nations
    ('Lake Louise', 'federal', False, 'Parks Canada'),
]


@pytest.mark.parametrize('typed, kind, covered, office', EVERYDAY, ids=[e[0] for e in EVERYDAY])
def test_what_applicants_actually_type(typed, kind, covered, office):
    pack = resolve(typed, 'x-typed').pack
    assert (pack.authority.kind, pack.coverage == 'full') == (kind, covered)
    assert office is None or pack.authority.name == office


# The code in force outside Alberta, as the research read it (ontario-quebec.md, rest-of-canada.md).
CODE_IN_FORCE = [('Vancouver', 'Vancouver Building By-law'), ('Surrey', 'BC Building Code 2024'), ('Winnipeg', 'M.R. 78/2023'),
                 ('Regina', 'Saskatchewan'), ('Toronto', 'O. Reg. 163/24'), ('Ottawa', 'O. Reg. 163/24'),
                 ('Montréal', 'Chapter I'), ('Halifax', 'N.S. Reg. 198/2024'), ('Fredericton', '2021-2'),
                 ("St. John's", '2025'), ('Iqaluit', '2015'), ('Whitehorse', 'Yukon')]


@pytest.mark.parametrize('city, code', CODE_IN_FORCE, ids=[c[0] for c in CODE_IN_FORCE])
def test_outside_alberta_names_the_code_the_research_found(city, code):
    pack = resolve(city, 'x-typed').pack
    assert pack.authority.kind == 'outside_alberta' and code in pack.code_edition and code in pack.summary
    assert pack.coverage == 'preview'


@pytest.mark.parametrize('name', ['Example Hamlet', 'Taber'])
def test_an_unknown_or_ambiguous_name_keeps_the_generic_alberta_answer(name):
    found = resolve(name)
    assert found.matched_by == 'fallback' and found.pack.id == 'alberta-other'


def test_local_items_never_leak_to_another_place():
    for place_id, pack_id in registry().place_packs.items():
        case = Case(title='SYNTHETIC leak check', jurisdiction=Jurisdiction(id=place_id, name=registry().places[place_id].name))
        local = notices_for(case, 'gaps') + notices_for(case, 'export_appendix')
        pack = registry().get(pack_id)
        if pack_id in LOCAL_PACKS.values():
            continue
        assert local == [] and export_notice(case) is None, place_id
        assert pack.standing_packages == [] and pack.guides == [] and pack.forms == [], place_id


def test_identification_reads_the_same_text_whatever_the_place():
    said = 'SYNTHETIC: continuous exterior insulation under fibre-cement cladding on a Part 9 house.'
    fact = Fact(field='project.description', value=said, kind='pointed', status='confirmed',
                source=Source(type='user_text', ref='synthetic-test-fixture:applicant', quote=said))
    texts = set()
    for place_id in ['calgary', 'edmonton', 'red-deer', 'lacombe-county', 'tsuutina-nation', 'vancouver']:
        case = Case(title='SYNTHETIC', facts=[fact], jurisdiction=Jurisdiction(id=place_id, name=place_id))
        texts.add(compose(case).text)
    assert len(texts) == 1 and said in next(iter(texts))


# Same application, place changed. Needs the code database.

COVERED = sorted({pid for pid, pack in registry().place_packs.items()
                  if registry().get(pack).coverage == 'full' and registry().get(pack).province == 'AB'})
NOT_COVERED = sorted(pid for pid, pack in registry().place_packs.items() if registry().get(pack).coverage != 'full')
KINDS = {}
for pid in COVERED + NOT_COVERED:
    KINDS.setdefault(registry().get(registry().place_packs[pid]).authority.kind, pid)
# One place of every kind here; scripts/every_place_proof.py runs every place (about six minutes on eight workers).
SAMPLE_COVERED = sorted({p for p in KINDS.values() if p in COVERED} | {'edmonton', 'red-deer', 'lacombe-county',
                                                                      'calgary-international-airport'})
SAMPLE_NOT_COVERED = sorted({p for p in KINDS.values() if p in NOT_COVERED} | {'vancouver', 'tsuutina-nation', 'jasper'})


@pytest.fixture(scope='module')
def engine_client(tmp_path_factory, monkeypatch_module):
    require_repo_db()
    store = CaseStore(tmp_path_factory.mktemp('places') / 'cases.sqlite')
    with ExitStack() as stack:
        client = stack.enter_context(TestClient(create_app(store=store), base_url='http://localhost'))
        assert signup(client, 'places@example.test', 'Places').status_code == 201
        owner = onboard(client)
        yield client, store, owner


@pytest.fixture(scope='module')
def monkeypatch_module():
    mp = pytest.MonkeyPatch()
    mp.delenv('VERCEL', raising=False)
    mp.setenv('BATATIS_REVIEWER_CODES', '{"edmonton":"officer-secret","calgary":"calgary-secret"}')
    mp.setenv('BATATIS_AUTH_RATE_LIMIT', '1000')
    yield mp
    mp.undo()


def run_application(engine_client, place_id, *, draft=True):
    client, store, owner = engine_client
    pack = registry().get(registry().place_packs[place_id])
    case = sample_case(Codes())
    case.owner_id = owner['id']
    case.jurisdiction = Jurisdiction(id=place_id, name=registry().places[place_id].name)
    case.authority = pack.authority.reviewer_code
    case = store_with_synthetic_files(store, case)
    body = client.get(f'/cases/{case.id}/gaps').json()
    gaps = body['items'] if isinstance(body, dict) else body
    final = client.post(f'/cases/{case.id}/export', json={'draft': False})
    draft = client.post(f'/cases/{case.id}/export', json={'draft': True}) if draft else None
    text = ''
    if final.status_code == 200:
        text = '\n'.join(p.extract_text() or '' for p in PdfReader(io.BytesIO(final.content)).pages)
    return {'gaps': gaps, 'final': final, 'draft': draft, 'ids': sorted(set(PROVISION_ID.findall(text))), 'text': text}


@pytest.fixture(scope='module')
def calgary_run(engine_client):
    return run_application(engine_client, 'calgary', draft=False)


@pytest.mark.parametrize('place_id', SAMPLE_COVERED)
def test_a_covered_place_gets_the_same_application_as_calgary(engine_client, calgary_run, place_id):
    run = run_application(engine_client, place_id, draft=False)
    assert run['final'].status_code == 200
    assert run['ids'] == calgary_run['ids'] and len(run['ids']) > 20
    core = lambda gaps: sorted((g['id'], g['severity']) for g in gaps if g['severity'] != 'info')
    assert core(run['gaps']) == core(calgary_run['gaps'])
    assert not any(g['id'] == 'coverage:jurisdiction' for g in run['gaps'])
    if place_id != 'calgary':
        assert 'Request for Specific Variance' not in run['text']     # Calgary's local form note stays in Calgary


@pytest.mark.parametrize('place_id', SAMPLE_NOT_COVERED)
def test_a_place_batatis_does_not_cover_blocks_the_final_application(engine_client, place_id):
    run = run_application(engine_client, place_id)
    pack = registry().get(registry().place_packs[place_id])
    blocker = [g for g in run['gaps'] if g['id'] == 'coverage:jurisdiction']
    assert blocker and blocker[0]['severity'] == 'blocking' and pack.name in blocker[0]['message']
    assert run['final'].status_code == 409
    assert any('does not prepare applications' in reason for reason in run['final'].json()['detail']['reasons'])
    assert run['draft'].status_code == 200          # the applicant can still read what they wrote
