"""Artisty export/save contract, example stamps, officer after-fixes seed, and citation wording."""
from __future__ import annotations

import io
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from pypdf import PdfReader, PdfWriter
from reportlab.pdfgen import canvas

from engine.api import create_app
from engine.benchmark import IDENTIFY_RANKED, apply_identify_benchmark, resolve_div_b_benchmark
from engine.demo_seed import OFFICER_AFTER_ID, OFFICER_STORY, build_cases
from engine.export.appendix import (
    DRAFT_OPEN_GAPS, EXAMPLE_STAMP, build_appendix, stamp_draft, stamp_example, stamp_pages,
)
from engine.export.scc import export_metadata, facts_hash, load_field_map
from engine.models import Case, Fact, Gap, Jurisdiction, Source
from engine.store import CaseStore
from engine.wording import ACCEPTANCE, ALTERNATIVE_SOLUTION

REPO = Path(__file__).resolve().parents[2]
ENGINE = REPO / 'engine'
FORBIDDEN_REFS = (
    '1.2.1.1.(3)',
    '1.2.1.2.(1)',
    '1.2.1.3.(1)',
    '2.2.1.2.(1)',
    '2.2.3.1.(1)',
    '2.2.2.5.(1)',
    '2.4.2.1.(1)',
    'approximately equivalent or greater safety',
    'at least the same level of performance',
)


class _Codes:
    """Lookup stub. Returned citations are fixtures, not code text."""

    db_path = Path('/unused')

    def provision(self, provision_id, division=None):
        if division == 'B' and provision_id != '9.10.1.1.(1)':
            return None
        return {'id': provision_id, 'citation': 'fixture citation', 'article_title': 'Fixture', 'text': ''}

    def citation(self, provision_id, division=None):
        return 'fixture citation'


def _client(tmp_path):
    store = CaseStore(tmp_path / 'cases.sqlite')
    return TestClient(create_app(store, _Codes())), store


def _page() -> bytes:
    buf = io.BytesIO()
    sheet = canvas.Canvas(buf)
    sheet.drawString(72, 400, 'SYNTHETIC page')
    sheet.showPage()
    sheet.save()
    return buf.getvalue()


def _text(pdf: bytes) -> str:
    return '\n'.join(page.extract_text() or '' for page in PdfReader(io.BytesIO(pdf)).pages)


def test_export_409_returns_structured_reasons_and_the_string_list(tmp_path):
    client, _store = _client(tmp_path)
    case_id = client.post('/cases', json={'title': 'Empty'}).json()['id']
    blocked = client.post(f'/cases/{case_id}/export')
    assert blocked.status_code == 409
    body = blocked.json()
    assert set(body) == {'detail'}
    detail = body['detail']
    assert detail['message'] == 'export blocked; resolve these or export a draft'
    reasons = detail['reasons']
    assert reasons and all(isinstance(item, dict) for item in reasons)
    assert any(item['label'] == 'Section C has no provisions' for item in reasons)
    ids = []
    for item in reasons:
        assert item['section'] in ('A', 'B', 'C', 'D')
        assert item['gap_id'] and item['label'] and item['fix_hint']
        assert item['severity'] == 'blocking'
        assert 'fact_key' in item
        ids.append(item['gap_id'])
    again = client.post(f'/cases/{case_id}/export').json()['detail']['reasons']
    assert ids == [row['gap_id'] for row in again]
    assert 'section_c:empty' in ids
    empty = next(row for row in reasons if row['gap_id'] == 'section_c:empty')
    assert empty['fact_key'] is None and empty['section'] == 'C'
    jurisdiction = next(row for row in reasons if row['fact_key'] == 'jurisdiction')
    assert jurisdiction['section'] == 'B' and jurisdiction['gap_id'] == 'admin:jurisdiction'


def test_export_error_returns_fixed_text(tmp_path, monkeypatch):
    from engine.export.scc import ExportError

    client, _store = _client(tmp_path)
    case_id = client.post('/cases', json={'title': 'Empty'}).json()['id']

    def boom(*_args, **_kwargs):
        raise ExportError('secret path /var/forms/SCC-Variance-Form.pdf')

    monkeypatch.setattr('engine.api.export_case', boom)
    response = client.post(f'/cases/{case_id}/export')
    assert response.status_code == 500
    assert response.json() == {'detail': 'The SCC variance form could not be exported.'}
    assert 'secret path' not in response.text
    assert 'SCC-Variance-Form' not in response.text


def test_version_advances_on_writes_and_failures_are_not_200(tmp_path):
    client, store = _client(tmp_path)
    created = client.post('/cases', json={'title': 'Versioned', 'jurisdiction': {
        'id': 'edmonton', 'name': 'Edmonton', 'authority': None}})
    assert created.status_code == 201
    body = created.json()
    assert body['version'] == 1
    fact = {'field': 'project.description', 'value': 'A garden suite.', 'kind': 'pointed', 'status': 'confirmed',
            'source': {'type': 'user_text', 'ref': 'applicant', 'quote': 'A garden suite.'}}
    added = client.post(f"/cases/{body['id']}/facts", json=fact)
    assert added.status_code == 200 and added.json()['version'] == 2
    missing = client.post('/cases/missing-case/facts', json=fact)
    assert missing.status_code == 404 and 'id' not in missing.json()
    invalid = client.post(f"/cases/{body['id']}/facts", json={**fact, 'kind': 'proposed', 'status': 'confirmed'})
    assert invalid.status_code == 422 and invalid.status_code != 200
    assert store.get(body['id']).version == 2

    gap = {'id': 'gap_stable', 'section': 'D', 'field': 'note', 'message': 'A note.', 'severity': 'warning'}
    stored = client.post(f"/cases/{body['id']}/gaps", json=gap)
    assert stored.status_code == 200 and stored.json()['version'] == 3
    assert client.post('/cases/missing-case/gaps', json=gap).status_code == 404
    bad_gap = client.post(f"/cases/{body['id']}/gaps", json={**gap, 'section': 'Z'})
    assert bad_gap.status_code == 422
    assert store.get(body['id']).version == 3

    stale = client.post(f"/cases/{body['id']}/export", json={'expected_version': 1})
    assert stale.status_code == 409
    assert stale.json() == {'code': 'version_conflict', 'current_version': 3}
    current = client.post(f"/cases/{body['id']}/export", json={'expected_version': 3})
    assert current.status_code == 409
    assert current.json()['detail']['reasons'] and 'code' not in current.json()


def test_patch_updates_jurisdiction_and_authority(tmp_path):
    client, _store = _client(tmp_path)
    created = client.post('/cases').json()
    assert created['version'] == 1
    untouched = client.patch(f"/cases/{created['id']}", json={})
    assert untouched.status_code == 200 and untouched.json()['version'] == 1
    missing_authority = client.patch(f"/cases/{created['id']}", json={'authority': 'County of Example'})
    assert missing_authority.status_code == 422
    assert client.get(f"/cases/{created['id']}").json()['version'] == 1
    patched = client.patch(f"/cases/{created['id']}", json={
        'jurisdiction': {'id': 'county-of-example', 'name': 'County of Example', 'authority': None}})
    assert patched.status_code == 200 and patched.json()['version'] == 2
    authority = client.patch(f"/cases/{created['id']}", json={'authority': 'County of Example'})
    assert authority.status_code == 200
    assert authority.json()['jurisdiction']['authority'] == 'County of Example'
    assert authority.json()['version'] == 3
    assert client.patch(f"/cases/{created['id']}", json={'title': 'no'}).status_code == 422


def test_metadata_records_version_and_facts_hash():
    case = Case(title='Meta', version=4, facts=[
        Fact(field='scope', value='site', kind='pointed', status='confirmed',
             source=Source(type='user_text', ref='m', quote='site'))])
    meta = export_metadata(case, draft=False, field_map='scc_2026-10')
    assert meta['/BatatisCaseVersion'] == '4'
    assert meta['/BatatisFactsHash'] == facts_hash(case)
    case.facts[0].value = 'other'
    assert export_metadata(case, draft=True, field_map='scc_2026-10')['/BatatisFactsHash'] != meta['/BatatisFactsHash']
    assert export_metadata(case, draft=True, field_map='scc_2026-10')['/Keywords'] == DRAFT_OPEN_GAPS


def test_example_provenance_survives_description_edits_and_stamps(tmp_path):
    client, _store = _client(tmp_path)
    created = client.post('/cases', json={'title': 'Sample', 'example_id': 'demo-sample'})
    assert created.status_code == 201
    body = created.json()
    assert body['provenance'] == 'example' and body['example_id'] == 'demo-sample'
    edited = client.post(f"/cases/{body['id']}/facts", json={
        'field': 'project.description', 'value': 'Edited description.', 'kind': 'pointed',
        'status': 'confirmed', 'source': {'type': 'user_text', 'ref': 'edit', 'quote': 'Edited description.'}})
    assert edited.json()['provenance'] == 'example'
    assert edited.json()['example_id'] == 'demo-sample'
    assert edited.json()['version'] == 2

    writer = PdfWriter(clone_from=io.BytesIO(_page()))
    stamp_pages(writer, example=True, draft=True)
    case = Case(provenance='example', example_id='demo-sample', version=2)
    writer.add_metadata(export_metadata(case, draft=True, field_map='scc_2026-10'))
    buf = io.BytesIO()
    writer.write(buf)
    text = _text(buf.getvalue())
    assert EXAMPLE_STAMP in text
    assert DRAFT_OPEN_GAPS in text
    info = PdfReader(io.BytesIO(buf.getvalue())).metadata
    assert EXAMPLE_STAMP in (info.get('/Subject') or '')
    assert (info.get('/Keywords') or '') == DRAFT_OPEN_GAPS
    assert info.get('/BatatisCaseVersion') == '2'
    assert info.get('/BatatisFactsHash') == facts_hash(case)

    plain = PdfWriter(clone_from=io.BytesIO(_page()))
    stamp_example(plain)
    out = io.BytesIO()
    plain.write(out)
    assert EXAMPLE_STAMP in _text(out.getvalue())
    draft_only = PdfWriter(clone_from=io.BytesIO(_page()))
    stamp_draft(draft_only)
    draft_buf = io.BytesIO()
    draft_only.write(draft_buf)
    draft_text = _text(draft_buf.getvalue())
    assert DRAFT_OPEN_GAPS in draft_text and EXAMPLE_STAMP not in draft_text


def test_officer_after_fixes_package():
    case = next(item for item in build_cases() if item.id == OFFICER_AFTER_ID)
    assert case.provenance == 'example' and case.example_id == OFFICER_AFTER_ID
    assert case.jurisdiction is not None
    assert case.jurisdiction.authority == 'County of Example'
    authority = next(fact for fact in case.facts if fact.field == 'authority')
    assert authority.value == 'County of Example'
    assert authority.source.quote in (REPO / authority.source.ref).read_text(encoding='utf-8')
    story = next(fact for fact in case.facts if fact.field == 'package.story')
    assert story.value == OFFICER_STORY
    professional = [fact for fact in case.facts if fact.value == 'needs professional']
    assert {fact.field for fact in professional} == {
        'responsible_professional', 'professional_qualifications', 'professional_seal'}
    assert all(fact.status == 'unconfirmed' for fact in professional)
    assert all('engineer' not in str(fact.value).lower() or fact.value == 'needs professional' for fact in case.facts)
    assert case.provisions == [] and case.section_c == []
    assert all('/keys/' not in fact.source.ref and '/expected/' not in fact.source.ref for fact in case.facts)
    ranked = next(fact for fact in case.facts if fact.field == IDENTIFY_RANKED)
    assert ranked.value == '[]'

    class _Db:
        def provision(self, provision_id, division=None):
            if division == 'B' and provision_id == '9.10.1.1.(1)':
                return {'id': provision_id}
            return None

    resolved = case.model_copy(deep=True)
    resolved.facts = [fact.model_copy(update={'value': '["[ARTICLE-X]", "9.10.1.1.(1)"]'})
                      if fact.field == IDENTIFY_RANKED else fact for fact in resolved.facts]
    assert resolve_div_b_benchmark(resolved, _Db()) == ['9.10.1.1.(1)']
    assert apply_identify_benchmark(resolved, _Db()) == ['9.10.1.1.(1)']
    dropped = case.model_copy(deep=True)
    dropped.facts = [fact.model_copy(update={'value': '["[ARTICLE-X]"]'})
                     if fact.field == IDENTIFY_RANKED else fact for fact in dropped.facts]
    assert resolve_div_b_benchmark(dropped, _Db()) == []


def test_template_wording_uses_the_real_sources_only():
    assert '1.2.1.1.(1)(b)' in ALTERNATIVE_SOLUTION
    assert 'IB-2026-10-01' in ACCEPTANCE
    assert '1.4.1.2' not in ALTERNATIVE_SOLUTION
    for path in ENGINE.rglob('*'):
        if 'tests' in path.parts or path.suffix not in {'.py', '.json'}:
            continue
        text = path.read_text(encoding='utf-8')
        for banned in FORBIDDEN_REFS:
            assert banned not in text, f'{path.relative_to(REPO)} contains {banned}'
    plan = type('Plan', (), {'overflow': [], 'rows_in_form': 0, 'docs_in_form': 0})()
    pdf = build_appendix(Case(title='Wording'), plan, {}, load_field_map(), codes=None, open_items=[])
    text = _text(pdf)
    assert ALTERNATIVE_SOLUTION in text and ACCEPTANCE in text


def test_user_case_metadata_has_no_example_stamp():
    case = Case(provenance='user', version=1)
    meta = export_metadata(case, draft=False, field_map='scc_2026-10')
    assert '/Subject' not in meta and '/Keywords' not in meta
    assert json.dumps(meta).find(EXAMPLE_STAMP) < 0
