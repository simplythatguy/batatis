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
from engine.jurisdictions import DRAFTS_ENV, export_notice, notices_for, places_build, registry
from engine.models import Case, Fact, Jurisdiction, Source
from engine.store import CaseStore
from engine.tests._db_skip import require_repo_db
from engine.tests.case_builder_fixtures import store_with_synthetic_files
from engine.tests.test_accounts import onboard, signup



@pytest.fixture(autouse=True, scope='module')
def draft_places():
    """These tests check the draft places, which the app leaves off (BATATIS_DRAFT_PLACES)."""
    mp = pytest.MonkeyPatch()
    mp.setenv(DRAFTS_ENV, '1')
    yield
    mp.undo()


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
    """(authority kind, office or None, covered) for a research row, from the raw inputs. Only an office whose own
    variance steps were checked by hand (Calgary, Edmonton) is covered."""
    name, code = row['legal_name'], row['lg_code']
    if row['type'] == 'Airport lands':
        return 'accredited_municipality', AIRPORTS[name], False
    if row['type'] == 'First Nation':
        return 'first_nation', name, False
    if code in PARK_CODES:
        return 'federal', 'Parks Canada', False
    if code in UNCONFIRMED_CODES:
        return 'unconfirmed', None, False
    if holds_building(row):
        return 'accredited_municipality', name, name in LOCAL_PACKS
    return 'alberta_safety_codes_authority', 'Alberta Safety Codes Authority', False


def resolve(name: str, place_id: str | None = None):
    return registry(drafts=True).resolve(Jurisdiction(id=place_id or name, name=name))


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
        assert pack.id in registry(drafts=True).generated and pack.authority.reviewer_code is None


@pytest.mark.parametrize('place_id', sorted(registry(drafts=True).places), ids=sorted(registry(drafts=True).places))
def test_a_place_resolves_the_same_by_id_and_by_every_name(place_id):
    place = registry(drafts=True).places[place_id]
    target = registry(drafts=True).place_packs[place_id]
    assert resolve(place_id, place_id).pack.id == target
    for name in [place.name, *place.aliases]:
        assert resolve(name, 'x-unknown-id').pack.id == target, name


@pytest.mark.parametrize('name, office, kind, covered', [
    ('Calgary', 'City of Calgary', 'accredited_municipality', True),                               # its own steps are checked
    ('Edmonton', 'City of Edmonton', 'accredited_municipality', True),
    ('Lacombe County', 'Alberta Safety Codes Authority', 'alberta_safety_codes_authority', False),  # SCC M000374, Fire only
    ('City of Lacombe', 'City of Lacombe', 'accredited_municipality', False),                      # SCC M000373, Building
    ('Red Deer', 'City of Red Deer', 'accredited_municipality', False),
    ('Strathcona County', 'Strathcona County', 'accredited_municipality', False),
    ('Banff', 'Town of Banff', 'accredited_municipality', False),                                  # the town reviews its own
    ('Lake Louise', 'Parks Canada', 'federal', False),                                             # in Banff National Park
    ('Jasper', 'Parks Canada', 'federal', False),
    ("Tsuut'ina Nation", "Tsuut'ina Nation", 'first_nation', False),
    ('Kikino Metis Settlement', 'Kikino Metis Settlement', 'accredited_municipality', False),
    ('East Prairie Metis Settlement', 'Alberta Safety Codes Authority', 'alberta_safety_codes_authority', False),
    ('Calgary International Airport', 'City of Calgary', 'accredited_municipality', False),
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
    ('Kikino Métis Settlement', 'accredited_municipality', False, 'Kikino Metis Settlement'),   # the Council's spelling
    ('Red Deer, AB', 'accredited_municipality', False, 'City of Red Deer'),
    ('Fort McMurray', 'accredited_municipality', False, 'Regional Municipality of Wood Buffalo'),
    ('Sherwood Park', 'accredited_municipality', False, 'Strathcona County'),
    ('Cold Lake', 'accredited_municipality', False, 'City of Cold Lake'),          # not Cold Lake First Nations
    ('Calgary, AB', 'accredited_municipality', True, 'City of Calgary'),
    ('Lake Louise', 'federal', False, 'Parks Canada'),
    ('St. Johns', 'outside_alberta', False, "City of St. John's"),                 # a period and no apostrophe
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
    assert found.matched_by == 'fallback' and found.pack.id == 'alberta-other' and found.pack.coverage == 'preview'


def test_only_offices_whose_own_steps_were_checked_prepare_applications():
    assert sorted(p.id for p in registry(drafts=True).packs.values() if p.coverage == 'full') == sorted(LOCAL_PACKS.values())
    assert all(not place.covered for pid, place in registry(drafts=True).places.items() if pid not in LOCAL_PACKS.values())


def test_local_items_never_leak_to_another_place():
    for place_id, pack_id in registry(drafts=True).place_packs.items():
        case = Case(title='SYNTHETIC leak check', jurisdiction=Jurisdiction(id=place_id, name=registry(drafts=True).places[place_id].name))
        local = notices_for(case, 'gaps') + notices_for(case, 'export_appendix')
        pack = registry(drafts=True).get(pack_id)
        if pack_id in LOCAL_PACKS.values():
            continue
        assert local == [] and export_notice(case) is None, place_id
        assert pack.standing_packages == [] and pack.guides == [] and pack.forms == [], place_id


# Where the Safety Codes Act does not decide, or Batatis has not confirmed who does (written out, not read from the code).
NOT_UNDER_THE_ACT = {'first_nation', 'federal', 'outside_alberta', 'unconfirmed'}


def test_alberta_process_items_reach_only_places_under_the_act():
    reg = registry(drafts=True)
    shared = reg.provinces['AB']
    everything = ([n.id for n in shared.process_notes], [f.id for f in shared.forms], shared.bulletins)
    for pack in reg.packs.values():
        detail = reg.detail(pack)
        province = ([n.id for n in detail.process_notes if n.scope == 'province'],
                    [f.id for f in detail.forms if f.scope == 'province'], [b for b in detail.bulletins if b in shared.bulletins])
        if pack.authority.kind in NOT_UNDER_THE_ACT:
            assert province == ([], [], []), pack.id
        elif pack.province == 'AB':
            assert province == everything, pack.id


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

COVERED = sorted({pid for pid, pack in registry(drafts=True).place_packs.items()
                  if registry(drafts=True).get(pack).coverage == 'full' and registry(drafts=True).get(pack).province == 'AB'})
NOT_COVERED = sorted(pid for pid, pack in registry(drafts=True).place_packs.items() if registry(drafts=True).get(pack).coverage != 'full')
KINDS = {}
for pid in COVERED + NOT_COVERED:
    KINDS.setdefault(registry(drafts=True).get(registry(drafts=True).place_packs[pid]).authority.kind, pid)
# One place of every kind here; scripts/every_place_proof.py runs every place (about six minutes on eight workers).
SAMPLE_COVERED = sorted(set(COVERED) - {'calgary'})
SAMPLE_NOT_COVERED = sorted({p for p in KINDS.values() if p in NOT_COVERED} | {'red-deer', 'lacombe-county', 'kikino-metis-settlement',
                            'calgary-international-airport', 'vancouver', 'tsuutina-nation', 'jasper'})


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


def run_application(engine_client, place_id, *, draft=True, name=None):
    client, store, owner = engine_client
    jurisdiction = Jurisdiction(id=place_id, name=name or registry(drafts=True).places[place_id].name)
    case = sample_case(Codes())
    case.owner_id = owner['id']
    case.jurisdiction = jurisdiction
    case.authority = registry(drafts=True).resolve(jurisdiction).pack.authority.reviewer_code
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
    pack = registry(drafts=True).get(registry(drafts=True).place_packs[place_id])
    blocker = [g for g in run['gaps'] if g['id'] == 'coverage:jurisdiction']
    assert blocker and blocker[0]['severity'] == 'blocking' and pack.name in blocker[0]['message']
    assert run['final'].status_code == 409
    assert any('does not prepare applications' in reason for reason in run['final'].json()['detail']['reasons'])
    assert run['draft'].status_code == 200          # the applicant can still read what they wrote


def test_a_name_batatis_does_not_know_blocks_the_final_application(engine_client):
    run = run_application(engine_client, 'example-hamlet', name='Example Hamlet')
    blocker = [g for g in run['gaps'] if g['id'] == 'coverage:jurisdiction']
    assert blocker and blocker[0]['severity'] == 'blocking' and 'Rest of Alberta' in blocker[0]['message']
    assert run['final'].status_code == 409 and run['draft'].status_code == 200
