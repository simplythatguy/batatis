"""AC6.1 and AC6.4: every pack file validates against the schema, unknown keys fail, every claim is sourced."""
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
from pathlib import Path
from typing import get_args

import pytest

from engine.account_models import Authority
from engine.jurisdictions import DATA_DIR, PackError, Registry
from engine.jurisdictions import schema as pack_schema
from engine.models_jurisdictions import PackSource

ROOT = Path(__file__).resolve().parents[2]
REFERENCE = Path(os.environ.get('BATATIS_REFERENCE_DIR') or ROOT / 'reference')   # git-excluded


@pytest.fixture(scope='module')
def reg() -> Registry:
    return Registry.load(DATA_DIR)


def _sources(node):
    """Every PackSource-shaped dict anywhere in a pack file."""
    if isinstance(node, dict):
        if {'url', 'retrieved', 'title'} <= set(node):
            yield node
        for value in node.values():
            yield from _sources(value)
    elif isinstance(node, list):
        for item in node:
            yield from _sources(item)


def _files():
    return sorted(DATA_DIR.glob('packs/*.json')) + sorted(DATA_DIR.glob('provinces/*.json'))


def test_committed_schema_is_generated_from_the_models():
    assert pack_schema.main(['--check']) == 0


def test_every_schema_object_rejects_unknown_keys():
    schema = json.loads((DATA_DIR / 'pack.schema.json').read_text())
    objects = [d for d in schema['$defs'].values() if d.get('type') == 'object' and 'properties' in d]
    assert len(objects) >= 10
    assert all(d.get('additionalProperties') is False for d in objects), \
        [d['title'] for d in objects if d.get('additionalProperties') is not False]


def test_all_packs_load(reg):
    assert {'calgary', 'edmonton', 'alberta-other'} <= set(reg.packs)
    assert reg.fallbacks == {'AB': 'alberta-other'}


@pytest.mark.parametrize('where', [(), ('authority',), ('process_notes', 0), ('process_notes', 0, 'sources', 0)])
def test_an_unknown_key_anywhere_fails_validation(tmp_path, where):
    root = tmp_path / 'packs-copy'
    shutil.copytree(DATA_DIR, root)
    path = root / 'packs' / 'calgary.json'
    data = json.loads(path.read_text())
    node = data
    for step in where:
        node = node[step]
    node['surprise'] = True
    path.write_text(json.dumps(data))
    with pytest.raises(PackError, match='calgary.json'):
        Registry.load(root)


def test_every_process_claim_cites_a_url_and_a_retrieval_date(reg):
    for pack in reg.packs.values():
        for note in reg.detail(pack).process_notes:
            assert note.sources, note.id
            for source in note.sources:
                assert source.url.startswith('https://') and re.fullmatch(r'\d{4}-\d{2}-\d{2}', source.retrieved)


def test_every_source_in_every_file_is_complete_and_unverified_ones_say_why():
    count = 0
    for path in _files():
        for raw in _sources(json.loads(path.read_text())):
            source = PackSource.model_validate(raw)
            count += 1
            if source.status == 'unverified':
                assert source.note, f'{path.name}: unverified source without a note: {source.title}'
    assert count >= 30


def test_standing_packages_are_metadata_and_b14_01_is_historical(reg):
    packages = {p.code: p for pack in reg.packs.values() for p in pack.standing_packages}
    assert {'SPV-001', 'SPV-006', 'B23-01', 'B14-01'} <= set(packages)
    for code in ('SPV-001', 'SPV-006', 'B23-01'):
        assert packages[code].status == 'current' and packages[code].checklist is None
    b14 = packages['B14-01']
    assert b14.status == 'historical' and '2014' in b14.edition and b14.historical_reason
    assert 'superseded' in b14.historical_reason
    for package in packages.values():
        assert package.status == 'historical' or package.historical_reason is None


def test_edmonton_point_access_block_guide_is_listed(reg):
    guides = {g.id: g for g in reg.get('edmonton').guides}
    guide = guides['edmonton-point-access-block']
    assert guide.topic == 'single_exit_stair' and guide.requires_professional is True
    assert guide.issued == '2025-02-28' and guide.source.sha256


def test_the_province_form_matches_the_export_field_map(reg):
    form = next(f for f in reg.forms(reg.get('calgary')) if f.id == 'scc-variance')
    assert form.scope == 'province' and form.export == 'supported'
    field_map = json.loads((ROOT / form.field_map).read_text())
    assert form.sha256 == field_map['sha256'] and form.field_count == field_map['field_count']


def test_the_same_form_or_document_has_one_hash_everywhere():
    by_url: dict[str, set[str]] = {}
    for path in _files():
        for raw in _sources(json.loads(path.read_text())):
            if raw.get('sha256'):
                by_url.setdefault(raw['url'], set()).add(raw['sha256'])
    assert by_url and all(len(hashes) == 1 for hashes in by_url.values()), \
        {url: hashes for url, hashes in by_url.items() if len(hashes) > 1}


def test_local_reference_copies_match_the_recorded_hash(reg):
    checked = 0
    for pack in reg.packs.values():
        for form in reg.forms(pack):
            if not form.local_path:
                continue
            local = REFERENCE / Path(form.local_path).relative_to('reference')
            if local.is_file():
                assert hashlib.sha256(local.read_bytes()).hexdigest() == form.sha256, form.id
                checked += 1
    if not checked:
        pytest.skip('reference/ is git-excluded and not present here')


def test_notices_are_info_text_safe_for_an_http_header(reg):
    for pack in reg.packs.values():
        for notice in pack.notices:
            notice.message.encode('ascii')
            assert 'complies' not in notice.message.lower() and 'approved' not in notice.message.lower()


def test_coverage_labels_every_province_and_territory(reg):
    regions = {r.id: r for r in reg.coverage.regions}
    assert set(regions) == {'AB', 'BC', 'SK', 'MB', 'ON', 'QC', 'NB', 'NS', 'PE', 'NL', 'YT', 'NT', 'NU'}
    assert regions['AB'].coverage == 'full'
    assert set(reg.coverage.levels) == {'full', 'code_only', 'preview'}
    for region in regions.values():
        assert region.coverage in reg.coverage.levels and region.note


def test_reviewer_codes_line_up_with_account_authorities(reg):
    assert {p.authority.reviewer_code for p in reg.reviewing_packs()} == set(get_args(Authority))


def test_a_second_fallback_for_the_same_province_is_rejected(tmp_path):
    root = tmp_path / 'packs-copy'
    shutil.copytree(DATA_DIR, root)
    path = root / 'packs' / 'edmonton.json'
    data = json.loads(path.read_text())
    data['fallback'] = True
    path.write_text(json.dumps(data))
    with pytest.raises(PackError, match='fallback'):
        Registry.load(root)


def test_a_name_claimed_by_two_packs_is_rejected(tmp_path):
    root = tmp_path / 'packs-copy'
    shutil.copytree(DATA_DIR, root)
    path = root / 'packs' / 'edmonton.json'
    data = json.loads(path.read_text())
    data['match']['names'].append('City of Calgary')
    path.write_text(json.dumps(data))
    with pytest.raises(PackError, match='also matches'):
        Registry.load(root)
