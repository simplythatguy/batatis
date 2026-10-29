"""AC6.2 and AC6.3: a fourth pack added as data changes behaviour with zero code edits."""
from __future__ import annotations

import io
import json
import shutil

import pytest
from fastapi.testclient import TestClient
from pypdf import PdfReader

from engine import jurisdictions
from engine.api import create_app
from engine.export.appendix import build_appendix
from engine.jurisdictions import DATA_DIR, export_notice, notices_for, registry
from engine.models import Case, Jurisdiction
from engine.store import CaseStore

SYNTHETIC_NOTICE = ('SYNTHETIC: Example Town also asks for its own intake sheet. '
                    'Keep the SCC form; ask the officer whether they want both.')
SOURCE = {'title': 'SYNTHETIC test source', 'url': 'https://example.invalid/synthetic', 'retrieved': '2026-10-21',
          'status': 'unverified', 'note': 'Test fixture only; not a real office.'}
FOURTH = {
    'schema_version': 1, 'id': 'example-town', 'name': 'Town of Example (SYNTHETIC)', 'province': 'AB',
    'coverage': 'full', 'code_edition': 'NBC(AE) 2023, 2nd printing',
    'summary': 'SYNTHETIC fourth pack used only by the portability test.',
    'authority': {'name': 'Town of Example (SYNTHETIC)', 'kind': 'accredited_municipality', 'reviewer_code': None,
                  'sources': [SOURCE]},
    'match': {'ids': ['example-town'], 'names': ['Example Town']},
    'process_notes': [{'id': 'ex-intake', 'topic': 'submission', 'text': 'SYNTHETIC intake note.', 'sources': [SOURCE]}],
    'standing_packages': [{
        'id': 'example-sp-1', 'code': 'EX-1', 'kind': 'policy', 'title': 'SYNTHETIC standing package',
        'issued': '2026-01-01', 'edition': 'NBC(AE) 2023', 'status': 'current', 'applies_to': 'Nothing real.',
        'source': SOURCE}],
    'notices': [{'id': 'example_town_form', 'surfaces': ['gaps', 'export_header', 'export_appendix'],
                 'section': 'B', 'heading': 'Local intake sheet', 'message': SYNTHETIC_NOTICE,
                 'fix_hint': 'Ask the officer.', 'sources': [SOURCE]}],
}


@pytest.fixture
def four_packs(tmp_path, monkeypatch):
    root = tmp_path / 'jurisdictions'
    shutil.copytree(DATA_DIR, root)
    (root / 'packs' / 'example-town.json').write_text(json.dumps(FOURTH))
    monkeypatch.setenv(jurisdictions.ENV_DIR, str(root))
    jurisdictions.clear_cache()
    yield root
    jurisdictions.clear_cache()


def _case(jid='example-town', name='Example Town'):
    return Case(title='SYNTHETIC portability fixture', jurisdiction=Jurisdiction(id=jid, name=name))


class _Plan:
    overflow: list = []


def _appendix_text(case):
    pdf = build_appendix(case, _Plan(), {}, {'version': 'test'}, codes=None)
    if pdf is None:                         # nothing real to print: no appendix
        return ''
    return ' '.join(' '.join((p.extract_text() or '') for p in PdfReader(io.BytesIO(pdf)).pages).split())


def test_without_the_fourth_pack_an_unknown_town_falls_back_with_no_notice():
    jurisdictions.clear_cache()
    found = registry().resolve(Jurisdiction(id='example-town', name='Example Town'))
    assert found.pack.id == 'alberta-other' and found.matched_by == 'fallback'
    assert notices_for(_case(), 'gaps') == [] and export_notice(_case()) is None


def test_the_fourth_pack_resolves_and_drives_every_surface(four_packs):
    assert registry().resolve(_case().jurisdiction).pack.id == 'example-town'
    assert registry().resolve(Jurisdiction(id='x', name='EXAMPLE   town')).matched_by == 'name'
    assert [n.id for n in notices_for(_case(), 'gaps')] == ['example_town_form']
    assert export_notice(_case()) == SYNTHETIC_NOTICE
    text = _appendix_text(_case())
    assert 'Local intake sheet' in text and ' '.join(SYNTHETIC_NOTICE.split()) in text


def test_the_fourth_pack_is_served_by_the_routes(four_packs, tmp_path):
    client = TestClient(create_app(store=CaseStore(tmp_path / 'cases.sqlite')))
    listed = client.get('/jurisdictions').json()['jurisdictions']
    assert 'example-town' in {row['id'] for row in listed}
    detail = client.get('/jurisdictions/example-town').json()
    assert [p['code'] for p in detail['standing_packages']] == ['EX-1']
    assert {f['id'] for f in detail['forms']} == {'scc-variance'}       # the province form comes along
    case = client.post('/cases', json={'jurisdiction': {'id': 'example-town', 'name': 'Example Town'}}).json()
    resolved = client.get(f'/cases/{case["id"]}/jurisdiction/pack').json()
    assert resolved['matched_by'] == 'id' and resolved['pack']['id'] == 'example-town'


def test_completeness_reads_the_fourth_pack(four_packs):
    from engine.codes import CodeDbMissing, Codes
    from engine.completeness import check_completeness
    try:
        codes = Codes()
    except (CodeDbMissing, FileNotFoundError):
        pytest.skip('code database not built')
    gaps = {g.id: g for g in check_completeness(_case(), codes)}
    assert gaps['info:example_town_form'].severity == 'info'
    assert gaps['info:example_town_form'].message == SYNTHETIC_NOTICE
    other = {g.id for g in check_completeness(_case('edmonton', 'City of Edmonton'), codes)}
    assert not any(gap.startswith('info:') for gap in other)


def test_removing_a_pack_file_removes_its_behaviour(tmp_path, monkeypatch):
    root = tmp_path / 'jurisdictions'
    shutil.copytree(DATA_DIR, root)
    city = registry().get('calgary')
    calgary_case = _case('calgary', city.name)
    assert export_notice(calgary_case)
    (root / 'packs' / 'calgary.json').unlink()
    monkeypatch.setenv(jurisdictions.ENV_DIR, str(root))
    jurisdictions.clear_cache()
    try:
        found = registry().resolve_case(calgary_case)
        # The place still names its office, from the generated place file; the local items are gone.
        assert found.pack.id in registry().generated and found.matched_by == 'id'
        assert found.pack.coverage == 'preview'          # without its checked pack, Batatis stops preparing it
        assert found.pack.standing_packages == [] and found.pack.notices == []
        assert export_notice(calgary_case) is None
    finally:
        jurisdictions.clear_cache()
