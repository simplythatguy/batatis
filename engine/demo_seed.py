"""Offline seed for the three fictional demo cases.

Reads ``evals/demo-cases/<case>/input/`` only. ``keys/``, ``expected/``, and ``presenter/``
are never opened. No model call, no socket, and no code database.

``confirmed`` on a seeded fact means the applicant's file states it. It is not a
verification, a professional opinion, or a finding that a design complies.
"""
from __future__ import annotations

import os
from pathlib import Path

from .benchmark import apply_identify_benchmark
from .models import Case, Fact, Jurisdiction, Source
from .store import CaseStore

STAMP = '2026-10-20T00:00:00+00:00'
OFFICER_AFTER_ID = 'demo-officer-after-fixes'
OFFICER_STORY = 'blocking gaps drop to only what a professional must supply'
REPO = Path(__file__).resolve().parents[1]
DEMO_ROOT = REPO / 'evals' / 'demo-cases'
FORBIDDEN = frozenset({'keys', 'expected', 'presenter'})

CASE_IDS = (
    'demo-a-manufacturer-nailbase',
    'demo-b-gc-firestop',
    'demo-c-homebuilder-infill',
)


class DemoSeedError(RuntimeError):
    pass


def demo_enabled() -> bool:
    """On only when the variable is exactly ``1``. Unset, empty, and ``true`` stay off."""
    return os.environ.get('BATATIS_DEMO') == '1'


def build_cases() -> list[Case]:
    """Canonical cases. The same call always returns the same documents."""
    specs = (_manufacturer(), _firestop(), _homebuilder())
    cases = [_case(spec) for spec in specs]
    cases.append(_officer_after_fixes())
    if tuple(case.id for case in cases[:3]) != CASE_IDS:
        raise DemoSeedError('demo case ids changed')
    if cases[3].id != OFFICER_AFTER_ID:
        raise DemoSeedError('officer after-fixes id changed')
    return cases


def seed_cases(store: CaseStore) -> list[Case]:
    """Write the canonical cases. A second call replaces any edit and returns the same documents."""
    return [store.put(case, keep_timestamps=True) for case in build_cases()]


def _manufacturer() -> dict:
    brief = 'input/project-brief.md'
    return {
        'id': CASE_IDS[0],
        'slug': 'a-manufacturer-nailbase-sheathing',
        'city': ('edmonton', 'Edmonton'),
        'facts': (
            _stated('representative', 'Mira Okafor', brief,
                    'Mira Okafor, Technical Director, Example Panel Works Ltd.'),
            _stated('municipalAddress', '0000 Example Way NW, Edmonton, AB *(fictional)*', brief,
                    '0000 Example Way NW, Edmonton, AB *(fictional)*'),
            _stated('brief_date', '2026-10-12', brief, '**Date:** 2026-10-12'),
            _stated('building.storeys', '2-storey', brief,
                    '2-storey single-family, about 190 m², unsprinklered, HRV planned'),
            _stated('alternative', 'Replaces 11 mm OSB on 2×6 walls at 400 mm o.c.', brief,
                    'Replaces 11 mm OSB on 2×6 walls at 400 mm o.c.'),
            _stated('project.description',
                    'Our panel is selling in two other provinces. We want **approval to sell it across Alberta** '
                    'and a first **pilot house** in Edmonton this spring. Builders love it because vinyl siding '
                    'nails **straight into the facer**, so there\'s no OSB and no strapping.',
                    brief,
                    'Our panel is selling in two other provinces. We want **approval to sell it across Alberta** '
                    'and a first **pilot house** in Edmonton this spring. Builders love it because vinyl siding '
                    'nails **straight into the facer**, so there\'s no OSB and no strapping.'),
            _stated('product.name', 'EPW NailBase CI-50', 'input/product-data-sheet.md',
                    'EPW NailBase CI-50: Product data sheet'),
            _stated('product.permeance', '"≈ 40 ng/(Pa·s·m²), breathable"', 'input/product-data-sheet.md',
                    '"≈ 40 ng/(Pa·s·m²), breathable"', status='unconfirmed'),
        ),
    }


def _firestop() -> dict:
    brief = 'input/project-brief.md'
    happened = (
        'Our firestop sub sealed the plumbing penetrations on L3 and L4 with **Example FireSeal 200** '
        '*(fictional)* and handed in listing **EX-FS-1234** *(fictional)*. The third-party firestop inspector '
        'says that listing only covers **metal pipes**. Ours are mostly **PVC drain pipe and bundles of PEX**, '
        'and some holes are bigger than the listing allows. L2 (copper) passed.'
    )
    return {
        'id': CASE_IDS[1],
        'slug': 'b-contractor-firestop-nonconformance',
        'city': ('calgary', 'Calgary'),
        'facts': (
            _stated('representative', 'Carlos Mendes', brief,
                    'Carlos Mendes, PM, Northgate Example Builders Ltd.'),
            _stated('owner', 'Example Commons Holdings Inc.', brief,
                    'Example Commons Holdings Inc. *(fictional)*'),
            _stated('municipalAddress', '0000 Example Avenue SW, Calgary, AB *(fictional)*', brief,
                    '0000 Example Avenue SW, Calgary, AB *(fictional)*'),
            _stated('legalDescription', 'Lot 0, Block 0, Plan 0000000 *(fictional placeholder)*', brief,
                    'Lot 0, Block 0, Plan 0000000 *(fictional placeholder)*', status='unconfirmed'),
            _stated('permit', 'BP-0000-00000', brief, 'BP-0000-00000 *(fictional)*, issued'),
            _stated('brief_date', '2026-10-15', brief, '**Date:** 2026-10-15'),
            _stated('building.storeys', '5 storeys', brief,
                    '5 storeys, sprinklered, retail at grade, 64 dwelling units above'),
            _stated('project.description', happened, brief, happened),
            _stated('alternative', 'Ideally "a variance so we don\'t have to rip it out"', brief,
                    'Ideally "a variance so we don\'t have to rip it out"'),
        ),
    }


def _homebuilder() -> dict:
    brief = 'input/project-brief.md'
    features = (
        '1. **No basement.** A slab-on-grade with in-floor hydronic heat. We want **R-7.5 rigid insulation** '
        'under the slab (the code table says more; we heard there\'s a STANDATA).\n'
        '2. **Flat-look roof** (low slope) with **no attic vents**. Closed-cell spray foam sprayed under the '
        'roof deck, with batts below.\n'
        '3. **Bedroom 3 "slot" window:** the client loves a tall, narrow casement on the street side. '
        'Clear opening per the supplier is **400 mm wide × 780 mm high**. It\'s the only window in that bedroom.'
    )
    return {
        'id': CASE_IDS[2],
        'slug': 'c-homebuilder-infill-house',
        'city': ('edmonton', 'Edmonton'),
        'facts': (
            _stated('representative', 'Priya Natarajan', brief,
                    'Priya Natarajan, Larkspur Example Homes'),
            _stated('owner', 'J. & R. Example', brief, 'J. & R. Example *(fictional)*'),
            _stated('municipalAddress', '0000 Example Crescent NW, Edmonton, AB *(fictional)*', brief,
                    '0000 Example Crescent NW, Edmonton, AB *(fictional)*'),
            _stated('legalDescription', 'Lot 0, Block 0, Plan 0000000 *(fictional placeholder)*', brief,
                    'Lot 0, Block 0, Plan 0000000 *(fictional placeholder)*', status='unconfirmed'),
            _stated('brief_date', '2026-10-16', brief, '**Date:** 2026-10-16'),
            _stated('building.storeys', '2 storeys', brief,
                    'Detached single-family, 2 storeys, ~210 m², no suite, **no sprinklers**'),
            _stated('project.description', features, brief, features),
            _stated('alternative', 'Clear opening per the supplier is **400 mm wide × 780 mm high**.', brief,
                    'Clear opening per the supplier is **400 mm wide × 780 mm high**.'),
        ),
    }


def _stated(field: str, value: str, file: str, quote: str, status: str = 'confirmed') -> dict:
    return {'field': field, 'value': value, 'file': file, 'quote': quote, 'status': status}


def _case(spec: dict) -> Case:
    slug = spec['slug']
    root = _input_dir(slug)
    brief = (root / 'project-brief.md').read_text(encoding='utf-8')
    title = _title(brief, slug)
    city_id, city_name = spec['city']
    address = next(row for row in spec['facts'] if row['field'] == 'municipalAddress')
    if city_name not in address['quote'] or city_name not in brief:
        raise DemoSeedError(f'{slug}: jurisdiction {city_name} is not in the brief')
    facts = [_quoted_fact(spec['id'], slug, root, row) for row in spec['facts']]
    facts.extend(_inventory(spec['id'], slug, root))
    fields = [fact.field for fact in facts]
    if len(fields) != len(set(fields)):
        raise DemoSeedError(f'{slug}: duplicate fact field')
    return Case(
        id=spec['id'], title=title, created_at=STAMP, updated_at=STAMP, version=1,
        provenance='example', example_id=spec['id'],
        jurisdiction=Jurisdiction(id=city_id, name=city_name, authority=None),
        facts=facts, provisions=[], section_c=[], evidence=[], gaps=[])


def _officer_after_fixes() -> Case:
    """Fictional officer package after the applicant's stated fixes.

    Quotes come from the tester-sample bundle and the Hartley brief. ``keys/`` is not read.
    Professional facts stay the label ``needs professional``. The Division B benchmark is
    whatever ``identify.ranked`` the code database can resolve, which is empty in this seed.
    """
    bundle = _tester_html('03-sco-submission-bundle.html')
    brief = _tester_html('01-hartley-garden-suite-brief.html')
    bundle_ref = 'evals/demo-cases/tester-samples/03-sco-submission-bundle.html'
    brief_ref = 'evals/demo-cases/tester-samples/01-hartley-garden-suite-brief.html'
    address = _slice(bundle, '0000 Example Avenue NW', ' (fictional address)')
    address_quote = address + ' (fictional address)'
    scope_quote = 'A small one-bedroom garden suite at the back of my lot for my mother.'
    description = '60 m² garden suite, 300 mm hempcrete walls, no polyethylene vapour barrier (no poly).'
    facts = [
        _file_fact(OFFICER_AFTER_ID, 'authority', 'County of Example', bundle_ref, 'County of Example'),
        _file_fact(OFFICER_AFTER_ID, 'jurisdiction', 'County of Example', bundle_ref, 'County of Example'),
        _file_fact(OFFICER_AFTER_ID, 'municipalAddress', address, bundle_ref, address_quote),
        _file_fact(OFFICER_AFTER_ID, 'representative', 'D. Hartley', bundle_ref, 'Rep: D. Hartley'),
        _file_fact(OFFICER_AFTER_ID, 'alternative', description, bundle_ref, description),
        _file_fact(OFFICER_AFTER_ID, 'owner', 'Dana Hartley', brief_ref, 'Dana Hartley (owner / builder)'),
        _file_fact(OFFICER_AFTER_ID, 'date', '2026-10-14', brief_ref, '2026-10-14'),
        _file_fact(OFFICER_AFTER_ID, 'scope', 'at the back of my lot', brief_ref, scope_quote),
        _file_fact(OFFICER_AFTER_ID, 'identify.query', description, bundle_ref, description),
        _identify_ranked(OFFICER_AFTER_ID),
        _story_fact(OFFICER_AFTER_ID),
        _needs_professional(OFFICER_AFTER_ID, 'responsible_professional', brief_ref),
        _needs_professional(OFFICER_AFTER_ID, 'professional_qualifications', brief_ref),
        _needs_professional(OFFICER_AFTER_ID, 'professional_seal', brief_ref),
    ]
    case = Case(
        id=OFFICER_AFTER_ID, title='Officer review, after fixes',
        created_at=STAMP, updated_at=STAMP, version=1,
        provenance='example', example_id=OFFICER_AFTER_ID,
        jurisdiction=Jurisdiction(id='county-of-example', name='County of Example',
                                  authority='County of Example'),
        facts=facts, provisions=[], section_c=[], evidence=[], gaps=[])
    apply_identify_benchmark(case, _Unresolved())
    return case


class _Unresolved:
    """Seed-time stand-in. It resolves no provision, so the seed cannot invent a benchmark."""

    def provision(self, provision_id, division=None):
        return None


def _tester_html(name: str) -> str:
    path = (DEMO_ROOT / 'tester-samples' / name).resolve()
    demo = DEMO_ROOT.resolve()
    if demo not in path.parents or path.parent.name != 'tester-samples':
        raise DemoSeedError(f'{name}: left the tester-samples directory')
    if FORBIDDEN & set(path.parts):
        raise DemoSeedError(f'{name}: refusing a key path')
    if not path.is_file():
        raise DemoSeedError(f'{name}: missing tester sample')
    return path.read_text(encoding='utf-8')


def _slice(text: str, start: str, end: str) -> str:
    at = text.find(start)
    if at < 0:
        raise DemoSeedError(f'missing {start!r}')
    stop = text.find(end, at)
    if stop < 0:
        raise DemoSeedError(f'missing {end!r}')
    return text[at:stop]


def _file_fact(case_id: str, field: str, value: str, ref: str, quote: str) -> Fact:
    path = REPO / ref
    text = path.read_text(encoding='utf-8')
    if quote not in text or value not in quote:
        raise DemoSeedError(f'{case_id}: {field} is not in {ref}')
    if any(part in FORBIDDEN for part in Path(ref).parts):
        raise DemoSeedError(f'refusing {ref}')
    return _fact(case_id, field, value, 'confirmed', ref, quote)


def _identify_ranked(case_id: str) -> Fact:
    return Fact(
        id=f'fact_{case_id}_identify_ranked', field='identify.ranked', value='[]',
        kind='computed', status='confirmed', formula='identify.ranked',
        source=Source(type='user_text', ref='identify-output', quote='[]'))


def _story_fact(case_id: str) -> Fact:
    return Fact(
        id=f'fact_{case_id}_package_story', field='package.story', value=OFFICER_STORY,
        kind='pointed', status='confirmed',
        source=Source(type='user_text', ref='demo-seed:officer-after-fixes', quote=OFFICER_STORY))


def _needs_professional(case_id: str, field: str, ref: str) -> Fact:
    quote = 'No lab tests, no engineer yet'
    if quote not in (REPO / ref).read_text(encoding='utf-8'):
        raise DemoSeedError(f'{case_id}: professional basis is not in {ref}')
    token = ''.join(ch if ch.isalnum() else '_' for ch in field)
    return Fact(
        id=f'fact_{case_id}_{token}', field=field, value='needs professional',
        kind='pointed', status='unconfirmed',
        source=Source(type='file', ref=ref, quote=quote))


def _input_dir(slug: str) -> Path:
    root = (DEMO_ROOT / slug / 'input').resolve()
    demo = DEMO_ROOT.resolve()
    if demo not in root.parents or root.name != 'input':
        raise DemoSeedError(f'{slug}: input path left the demo input directory')
    if not root.is_dir():
        raise DemoSeedError(f'{slug}: input directory is missing')
    if FORBIDDEN & set(root.parts):
        raise DemoSeedError(f'{slug}: refusing a key path')
    return root


def _title(text: str, slug: str) -> str:
    first = text.splitlines()[0].strip()
    prefix = '# Project brief: '
    if not first.startswith(prefix):
        raise DemoSeedError(f'{slug}: project brief title is missing')
    return first[len(prefix):]


def _quoted_fact(case_id: str, slug: str, root: Path, row: dict) -> Fact:
    path = _file_in_input(root, row['file'], slug)
    text = path.read_text(encoding='utf-8')
    if row['quote'] not in text:
        raise DemoSeedError(f'{slug}: quote for {row["field"]} is not in {row["file"]}')
    if row['value'] not in row['quote']:
        raise DemoSeedError(f'{slug}: value for {row["field"]} is not inside its quote')
    return _fact(case_id, row['field'], row['value'], row['status'], _ref(slug, path, root), row['quote'])


def _inventory(case_id: str, slug: str, root: Path) -> list[Fact]:
    facts = []
    for path in sorted(p for p in root.rglob('*') if p.is_file()):
        if FORBIDDEN & set(path.parts):
            raise DemoSeedError(f'{slug}: refusing a key path')
        rel = path.relative_to(root).as_posix()
        quote = _banner(path)
        facts.append(_fact(case_id, f'input_file.{rel}', path.name, 'confirmed', _ref(slug, path, root), quote))
    if not facts:
        raise DemoSeedError(f'{slug}: input directory has no files')
    return facts


def _file_in_input(root: Path, rel: str, slug: str) -> Path:
    if rel.startswith('/') or '..' in Path(rel).parts or not rel.startswith('input/'):
        raise DemoSeedError(f'{slug}: fact file is outside input/')
    path = (root.parent / rel).resolve()
    if root not in path.parents and path != root:
        raise DemoSeedError(f'{slug}: fact file left input/')
    if not path.is_file():
        raise DemoSeedError(f'{slug}: missing {rel}')
    return path


def _ref(slug: str, path: Path, root: Path) -> str:
    rel = path.resolve().relative_to(root).as_posix()
    ref = f'evals/demo-cases/{slug}/input/{rel}'
    if any(part in FORBIDDEN for part in Path(ref).parts):
        raise DemoSeedError(f'refusing {ref}')
    return ref


def _banner(path: Path) -> str | None:
    if path.suffix.lower() not in {'.md', '.txt', '.html'}:
        return None
    lines = [line.strip() for line in path.read_text(encoding='utf-8').splitlines() if line.strip()]
    for line in lines:
        if 'EXAMPLE' in line or 'DRAFT' in line:
            return line
    for line in lines:
        if line.startswith('# '):
            return line
    return lines[0] if lines else None


def _fact(case_id: str, field: str, value: str, status: str, ref: str, quote: str | None) -> Fact:
    token = ''.join(ch if ch.isalnum() else '_' for ch in field)
    return Fact(
        id=f'fact_{case_id}_{token}',
        field=field, value=value, kind='pointed', status=status,
        source=Source(type='file', ref=ref, quote=quote))
