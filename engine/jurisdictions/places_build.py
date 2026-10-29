"""Build the place files from the 2026-10-28 jurisdiction research. Data only; no network.

    python -m engine.jurisdictions.places_build          # write the files below
    python -m engine.jurisdictions.places_build --check  # exit 1 when a committed file differs

Writes `places/alberta.json` and `places/outside-alberta.json` (PlacesFile, loaded by the registry) and
`place_index.json` (the compact list the web picker reads). Inputs: the research table
`alberta-jurisdictions.csv` (390 rows: municipalities, Metis settlements, First Nations, national parks,
airport lands), its hand-checked overrides and Safety Codes Council snapshot, and `place_inputs.json`
(parks, airports and places outside Alberta, with code names and links from the same research folder).

A place never says a design complies. It says who reviews building work there, from a source.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import sys
import unicodedata
from pathlib import Path

from ..models_jurisdictions import PlacesFile
from . import DATA_DIR

ROOT = DATA_DIR.parents[2]
RESEARCH = ROOT / 'docs' / 'research' / '2026-10-28-every-jurisdiction'
CSV_IN = RESEARCH / 'alberta-jurisdictions.csv'
OVERRIDES = RESEARCH / 'alberta-jurisdiction-overrides.json'
SNAPSHOT = RESEARCH / 'alberta-scc-snapshot.json'
A16 = ROOT / 'Data Prompts' / 'Alberta Jurisdiction Sources.json'
OUT_DIR = DATA_DIR / 'places'
INDEX = DATA_DIR / 'place_index.json'
RETRIEVED = '2026-10-29'
NBC_AE = 'NBC(AE) 2023, 2nd printing'

SCC_SEARCH = {'title': 'Safety Codes Council, Accreditation Search',
              'url': 'https://councilconnect.safetycodes.ab.ca/eWeb/DynamicPage.aspx?Site=scc&WebKey=d1d96198-3866-4673-9cec-a787f71f89f5',
              'retrieved': RETRIEVED}
MAPL = {'title': 'Alberta Municipal Affairs Population List 2025',
        'url': 'https://open.alberta.ca/opendata/alberta-municipal-affairs-population-list', 'retrieved': RETRIEVED}
ASCA_ORDER = {'title': 'Alberta Safety Codes Authority Order, AR 29/2016, s.4(1)',
              'url': 'https://www.qp.alberta.ca/documents/Regs/2016_029.pdf', 'retrieved': RETRIEVED}
ASCA_AGENCIES = {'title': 'Safety Codes Council, Alberta Safety Codes Authority agencies',
                 'url': 'https://safetycodes.ab.ca/municipalities-corporations-and-agencies/asca-agencies/',
                 'retrieved': RETRIEVED}
SCA = {'title': 'Safety Codes Act, RSA 2000 c S-1 (Metis settlement is a municipality, s.1(1)(u))',
       'url': 'https://www.qp.alberta.ca/documents/Acts/S01.pdf', 'retrieved': RETRIEVED}
INDIAN_ACT = {'title': 'Indian Act, s.81(1)(h): band by-laws on the construction and use of buildings',
              'url': 'https://laws-lois.justice.gc.ca/eng/acts/I-5/section-81.html', 'retrieved': RETRIEVED}
PARKS_POLICY = {'title': 'Parks Canada, land use planning in national parks',
                'url': 'https://parks.canada.ca/agence-agency/bib-lib/politiques-policies/amenagement-du-territoire-land-use-planning',
                'retrieved': RETRIEVED}
CBHCC = {'title': 'Canadian Board for Harmonized Construction Codes, provincial and territorial adoption',
         'url': 'https://cbhcc-cchcc.ca/en/provincial-territorial-adoption/', 'retrieved': '2026-10-28'}

PREFIX = re.compile(r'^(City|Town|Village|Summer Village|County|Municipal District|Municipality|Regional Municipality)'
                    r' of ', re.I)

INPUTS = DATA_DIR / 'place_inputs.json'   # parks, airports and places outside Alberta, entered by hand


def inputs() -> dict:
    return json.loads(INPUTS.read_text(encoding='utf-8'))


def slug(text: str) -> str:
    ascii_text = unicodedata.normalize('NFKD', text).encode('ascii', 'ignore').decode()
    return re.sub(r'[^a-z0-9]+', '-', ascii_text.lower().replace("'", '')).strip('-')


def short(name: str) -> str:
    return PREFIX.sub('', name).strip()


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def source(base: dict, note: str | None = None, status: str = 'verified') -> dict:
    out = {**base, 'status': status}
    if note:
        out['note'] = note
    return out


def building_accreditations() -> tuple[dict[str, list[str]], dict[str, list[str]]]:
    """Accreditation numbers that hold Building: by organization name (SCC snapshot of 2026-10-29) and,
    as a fallback, by municipal code (A16 inventory of 2026-10-25; the research found no difference)."""
    snap = json.loads(SNAPSHOT.read_text(encoding='utf-8'))
    by_name: dict[str, list[str]] = {}
    for org in snap['municipalities']:
        if 'Building' in org['disciplines']:
            by_name.setdefault(fold(org['organization']), []).append(org['accreditation_number'])
    a16 = json.loads(A16.read_text(encoding='utf-8'))
    by_code = {r['lg_code']: r['scc_accreditation_numbers'] for r in a16['accredited_municipal_roster_all_330']
               if r.get('building_accredited')}
    by_code |= {r['lg_code']: r['scc_accreditation_numbers'] for r in a16['accredited_metis_settlements']
                if r.get('building_accredited')}
    return by_name, by_code


def alberta_place(row: dict, overrides: dict, numbers: tuple[dict, dict], hand: dict) -> dict:
    name, kind, lg = row['legal_name'], row['building_ahj_kind'], row['lg_code'] or None
    by_name, by_code = numbers
    accreditation = sorted(set(by_name.get(fold(name)) or by_code.get(lg or '', [])))
    base = {'name': name, 'province': 'AB', 'lg_code': lg, 'type': row['type'], 'aliases': [],
            'accreditation': accreditation, 'climate_location': row['table_c2_location'] or None,
            'code_edition': NBC_AE}
    if row['type'] == 'Airport lands':
        airport = hand['airports'][name]
        pid, aliases, office, caveat = airport['id'], airport['aliases'], airport['office'], airport.get('caveat')
        url = next(iter(re.findall(r'https://\S+', row['source'])), None)
        note = f'The airport authority authorizes the project first; then {office} reviews building work.'
        return {**base, 'id': pid, 'aliases': aliases, 'kind': 'accredited_municipality', 'office': office, 'covered': True,
                'note': f'{note} {caveat}' if caveat else note,
                'ask': f'Ask the airport authority for its letter of authorization, then {office}.',
                'sources': [source({'title': f'{name}: who reviews building work', 'url': url, 'retrieved': RETRIEVED},
                                   caveat, 'unverified' if caveat else 'verified')]}
    if kind == 'accredited_municipality' or kind == 'metis_settlement':
        number = f' ({", ".join(accreditation)})' if accreditation else ''
        return {**base, 'id': slug(short(name)), 'aliases': [short(name)] if short(name) != name else [],
                'kind': 'accredited_municipality', 'office': name, 'covered': True,
                'note': f'{name} is accredited for building under the Safety Codes Act{number}, so it reviews building work here.',
                'ask': f'Ask {name} about its intake steps and fees.',
                'sources': [source(SCC_SEARCH), source(MAPL)] + ([source(SCA)] if kind == 'metis_settlement' else [])}
    if kind == 'asca':
        return {**base, 'id': slug(short(name)), 'aliases': [short(name)] if short(name) != name else [],
                'kind': 'alberta_safety_codes_authority', 'office': 'Alberta Safety Codes Authority', 'covered': True,
                'note': (f'{name} is not accredited for building, so the Alberta Safety Codes Authority oversees building '
                         'permits here. The owner picks one of its contracted agencies; the fees are the same.'),
                'ask': 'Ask the Alberta Safety Codes Authority or one of its contracted agencies.',
                'sources': [source(SCC_SEARCH, 'No Building accreditation under this name on the search date.'),
                            source(ASCA_ORDER, 'Areas with no accredited organization go to the Authority; applying the rule to this place is an inference.'),
                            source(ASCA_AGENCIES), source(MAPL)]}
    if kind == 'first_nation':
        return {**base, 'id': slug(name), 'aliases': hand['first_nation_aliases'].get(name, []), 'kind': 'first_nation',
                'office': name, 'covered': False, 'code_edition': 'Set by the Nation',
                'note': ('This is reserve land. The Nation may set its own building rules (Indian Act s.81(1)(h)); '
                         'Batatis does not prepare applications here.'),
                'ask': f'Ask {name} which building rules apply and who reviews them.',
                'sources': [source(INDIAN_ACT, 'Supports that a band council may make building by-laws.'),
                            source(SCC_SEARCH, 'No accreditation under this name on the search date.')]}
    if kind == 'federal':
        parks = overrides['national_park_improvement_districts']
        hit = parks.get(lg) if lg else None
        url = hit['source'] if hit else next(iter(re.findall(r'https://\S+', row['source'] + ' ' + row['notes'])), PARKS_POLICY['url'])
        park = hand['parks'].get(lg or '', {})
        pid, label, aliases = park.get('id', ''), park.get('label', ''), park.get('aliases', [])
        if not pid:   # Municipality of Jasper and districts without a nicer name keep a slug of the legal name
            pid, label = slug(short(name)), short(name)
        return {**base, 'id': pid, 'aliases': sorted({label, *aliases} - {name}), 'kind': 'federal',
                'office': 'Parks Canada', 'covered': False,
                'code_edition': 'Set by the Parks Canada permit (a provincial or national code)',
                'note': 'Parks Canada issues the building permit here. Batatis does not prepare applications in national parks.',
                'ask': 'Ask Parks Canada, realty and development, for this park.',
                'sources': [source({'title': f'Parks Canada: building permits, {label or name}', 'url': url,
                                    'retrieved': RETRIEVED}), source(PARKS_POLICY)]}
    # other: Lloydminster (own charter) and Redwood Meadows (not determined)
    special = overrides['special_rows'].get(lg or '', {})
    url = special.get('source') if str(special.get('source', '')).startswith('https://') else MAPL['url']
    known_office = bool(special.get('ahj'))
    office = name if known_office else 'Not confirmed'
    note = (f'{name} reviews building work under its own bylaw, and Batatis has not confirmed which code that bylaw '
            'adopts, so it does not prepare applications here.' if known_office else
            f'Batatis has not confirmed who reviews building work in {short(name)}, so it does not prepare applications here.')
    return {**base, 'id': slug(short(name)), 'aliases': [short(name)] if short(name) != name else [],
            'kind': 'unconfirmed', 'office': office, 'covered': False,
            'code_edition': 'Not confirmed', 'note': note,
            'ask': f'Ask {name if known_office else "the townsite administration"} which building code applies and who reviews it.',
            'sources': [source({'title': f'{name}: what the research could confirm', 'url': url, 'retrieved': RETRIEVED},
                               special.get('note') or 'Building authority not determined.', 'unverified')]}


def outside_places(hand: dict) -> list[dict]:
    by_province = {p['province']: p for p in hand['provinces']}
    out = []
    for p in hand['provinces']:
        prov, name, aliases, code, src = p['province'], p['name'], p['aliases'], p['code'], p['source']
        out.append({'id': slug(name), 'name': name, 'aliases': aliases, 'province': prov, 'lg_code': None,
                    'type': 'Province or territory', 'kind': 'outside_alberta', 'office': f'the local building authority in {name}',
                    'accreditation': [], 'covered': False, 'code_edition': code, 'climate_location': None,
                    'note': f'{name} is outside Alberta and uses the {code}. Batatis does not prepare applications outside Alberta.',
                    'ask': f'Ask the building authority where the project is.',
                    'sources': [source(src)]})
    for c in hand['cities']:
        prov, name, aliases, office, code, src = c['province'], c['name'], c['aliases'], c['office'], c['code'], c['source']
        pname, pcode, psrc = by_province[prov]['name'], by_province[prov]['code'], by_province[prov]['source']
        code, src = code or pcode, src or psrc
        out.append({'id': slug(name), 'name': name, 'aliases': aliases, 'province': prov, 'lg_code': None,
                    'type': 'City outside Alberta', 'kind': 'outside_alberta', 'office': office,
                    'accreditation': [], 'covered': False, 'code_edition': code, 'climate_location': None,
                    'note': f'{name} is outside Alberta ({pname}) and uses the {code}. Batatis does not prepare applications outside Alberta.',
                    'ask': f'Ask {office}.',
                    'sources': [source(src)]})
    return out


MUNICIPAL = {'accredited_municipality', 'alberta_safety_codes_authority'}


def group_places(hand: dict, alberta: list[dict]) -> list[dict]:
    """Names several Nations share (Maskwacis, Stoney Nakoda): not covered, like each member."""
    by_name = {p['name']: p for p in alberta}
    out = []
    for g in hand['first_nation_groups']:
        members = [m for m in g['members'] if m in by_name]
        out.append({'id': g['id'], 'name': g['name'], 'aliases': g['aliases'], 'province': 'AB', 'lg_code': None,
                    'type': 'First Nations', 'kind': 'first_nation', 'office': ' or '.join(members), 'accreditation': [],
                    'covered': False, 'code_edition': 'Set by each Nation', 'climate_location': None,
                    'note': (f'This is reserve land of {", ".join(members[:-1])} and {members[-1]}. Each Nation may set its own '
                             'building rules (Indian Act s.81(1)(h)); Batatis does not prepare applications here.'),
                    'ask': 'Ask the Nation where the project is which building rules apply and who reviews them.',
                    'sources': [source(INDIAN_ACT, 'Supports that a band council may make building by-laws.'),
                                source(MAPL, 'The members are population-list rows; grouping them under one name is ours.',
                                       'unverified')]})
    return out


def add_community_aliases(hand: dict, alberta: list[dict]) -> None:
    by_name = {p['name']: p for p in alberta}
    for alias, name in hand['community_aliases']['aliases'].items():
        by_name[name]['aliases'] = [*by_name[name]['aliases'], alias]


def fold(name: str) -> str:
    """Case-, accent- and apostrophe-free, so 'Kikino Métis Settlement' matches 'Kikino Metis Settlement'."""
    text = unicodedata.normalize('NFKD', name.replace('\u2019', "'").replace('\u2018', "'")).encode('ascii', 'ignore').decode()
    return ' '.join(text.split()).casefold()


def dedupe_aliases(places: list[dict]) -> list[str]:
    """An alias two places share stays with the municipality when exactly one place is a municipality (so
    "Cold Lake" stays the City of Cold Lake); otherwise it is dropped from all of them. Returns what was dropped."""
    seen: dict[str, set[str]] = {}
    for p in places:
        for n in [p['name'], *p['aliases']]:
            seen.setdefault(fold(n), set()).add(p['id'])
    kinds = {p['id']: p['kind'] for p in places}
    dropped = []
    for p in places:
        keep = []
        for a in p['aliases']:
            owners = seen[fold(a)]
            municipal = [o for o in owners if kinds[o] in MUNICIPAL]
            if len(owners) == 1 or (len(municipal) == 1 and municipal[0] == p['id']):
                keep.append(a)
            else:
                dropped.append(f'{p["id"]}: {a}')
        p['aliases'] = keep
    return dropped


def build() -> dict[Path, str]:
    rows = list(csv.DictReader(CSV_IN.open(encoding='utf-8')))
    overrides = json.loads(OVERRIDES.read_text(encoding='utf-8'))
    numbers = building_accreditations()
    hand = inputs()
    alberta = [alberta_place(r, overrides, numbers, hand) for r in rows]
    add_community_aliases(hand, alberta)
    alberta += group_places(hand, alberta)
    outside = outside_places(hand)
    ids = [p['id'] for p in alberta + outside]
    dup = {i for i in ids if ids.count(i) > 1}
    for p in alberta:
        if p['id'] in dup and p['lg_code']:
            p['id'] = f"{p['id']}-{p['lg_code']}"
    ids = [p['id'] for p in alberta + outside]
    if len(ids) != len(set(ids)):
        raise SystemExit(f'duplicate place ids: {sorted({i for i in ids if ids.count(i) > 1})}')
    dropped = dedupe_aliases(alberta + outside)
    hashes = {CSV_IN.name: sha256(CSV_IN), OVERRIDES.name: sha256(OVERRIDES), SNAPSHOT.name: sha256(SNAPSHOT),
              A16.name: sha256(A16), INPUTS.name: sha256(INPUTS)}
    files = {}
    for group, places in (('alberta', alberta), ('outside-alberta', outside)):
        doc = {'schema_version': 1, 'group': group, 'generated_by': 'python -m engine.jurisdictions.places_build',
               'inputs': hashes, 'places': sorted(places, key=lambda p: p['id'])}
        PlacesFile.model_validate(doc)
        files[OUT_DIR / f'{group}.json'] = json.dumps(doc, indent=1, ensure_ascii=False) + '\n'
    index = [{'id': p['id'], 'name': p['name'], 'aliases': p['aliases'], 'province': p['province'],
              'kind': p['kind'], 'covered': p['covered'], 'office': p['office']}
             for p in sorted(alberta + outside, key=lambda p: (p['province'] != 'AB', p['name'].casefold()))]
    files[INDEX] = json.dumps({'note': 'Generated by python -m engine.jurisdictions.places_build. Do not edit.',
                               'places': index}, indent=1, ensure_ascii=False) + '\n'
    if dropped:
        print(f'aliases dropped because two places share them: {len(dropped)}', file=sys.stderr)
    return files


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--check', action='store_true')
    args = ap.parse_args(argv)
    files = build()
    if args.check:
        stale = [p for p, text in files.items() if not p.is_file() or p.read_text(encoding='utf-8') != text]
        for p in stale:
            print(f'{p} is stale; run python -m engine.jurisdictions.places_build', file=sys.stderr)
        return 1 if stale else 0
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for p, text in files.items():
        p.write_text(text, encoding='utf-8')
        print(f'wrote {p.relative_to(ROOT)}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
