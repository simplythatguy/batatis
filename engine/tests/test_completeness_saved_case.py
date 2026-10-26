"""Synthetic public saved-case B regressions; no eval/held-out loaders or providers."""
import io
import json

import pytest
from fastapi.testclient import TestClient
from pypdf import PdfReader, PdfWriter

from engine.api import create_app
from engine.codes import Codes
from engine.export.scc import blockers, load_field_map
from engine.models import Case, Fact, Jurisdiction, Source
from engine.models import EvidenceItem
from engine.models import Gap
from engine.section_c import section_c_rows
from engine.section_d import section_d_plan
from engine.store import CaseStore


def fact(field, value, *, confirmed=True, kind='pointed', source_type='user_text', ref='SYNTHETIC applicant'):
    return Fact(field=field, value=value, kind=kind,
                status='confirmed' if confirmed else 'unconfirmed',
                source=Source(type=source_type, ref=ref, quote=str(value)))


@pytest.fixture
def context(tmp_path):
    store = CaseStore(tmp_path / 'saved.sqlite')
    codes = Codes()
    with TestClient(create_app(store, codes)) as client:
        yield client, store, codes


def elements(response):
    assert response.status_code == 200, response.text
    review = response.json()['reviews'][0]
    assert [section['section'] for section in review['sections']] == list('ABCD')
    return {entry['field']: entry for section in review['sections'] for entry in section['elements']}


@pytest.mark.parametrize('body', [None, {}, {'variant': 'B'}])
def test_actual_officer_default_route_returns_located_grouped_b_without_writes(context, body):
    client, store, codes = context
    case = store.put(Case(title='SYNTHETIC officer default B', facts=[
        fact('owner_name', 'SYNTHETIC owner'),
        fact('alternative_description', 'SYNTHETIC wall cladding departure'),
        fact('process.risk_assessment', 'low risk'),
        fact('process.mitigating_measures', 'standard measures'),
        fact('professional_status', 'not_engaged'),
    ]))
    uploaded = store.put_file(case.id, 'synthetic.pdf', b'%PDF-1.4\nSYNTHETIC presence bytes\n')
    before = store.get(case.id).model_dump()
    with store._connect() as con:
        raw_before = con.execute('SELECT json, version FROM cases WHERE id=?', (case.id,)).fetchone()
    response = client.post(f'/api/cases/{case.id}/completeness', **({} if body is None else {'json': body}))
    found = elements(response)
    payload = response.json()
    assert payload['schema_version'] == 'batatis.completeness.v1'
    assert payload['variant'] == 'B'
    assert payload['administrative_only'] is payload['not_a_compliance_determination'] is True
    assert 'administrative' in payload['notice']
    assert payload['reminder']['verdict'] == 'reminder'
    assert payload.get('llm') is None
    assert payload['case_id'] == case.id
    assert payload['case_version'] == before['version']
    assert found['owner_name']['verdict'] == 'present'
    assert found['owner_name']['quotes'][0]['source_ref'] == 'SYNTHETIC applicant'
    assert found['risk_assessment']['verdict'] == 'unclear'
    assert found['risk_assessment']['problem'] == 'generic'
    assert found['risk_assessment']['quotes'][0]['text'] == 'low risk'
    assert found['risk_assessment']['prompt']['field'] == 'process.risk_assessment'
    assert found['risk_assessment']['prompt']['question']
    assert found['mitigating_measures']['verdict'] == 'unclear'
    assert found['legal_description']['verdict'] == 'missing'
    assert found['legal_description']['form_fields']
    assert found['single_location']['verdict'] == 'unclear'
    assert found['section_c.edition']['verdict'] == 'unclear'
    assert payload['reviews'][0]['export_reasons'] == blockers(store.get(case.id), load_field_map(), codes)
    assert store.get(case.id).model_dump() == before
    assert store.get_file(case.id, uploaded['id'])['data'] == b'%PDF-1.4\nSYNTHETIC presence bytes\n'
    with store._connect() as con:
        assert con.execute('SELECT json, version FROM cases WHERE id=?', (case.id,)).fetchone() == raw_before
    assert response.headers['cache-control'] == 'no-store'
    assert response.headers['x-robots-tag'] == 'noindex, nofollow'
    assert payload['meta']['notice']


def test_latest_unconfirmed_revision_cannot_resurrect_older_answer(context):
    client, store, _ = context
    case = store.put(Case(facts=[fact('owner_name', 'SYNTHETIC old owner'),
                                fact('owner_name', 'SYNTHETIC changed owner', confirmed=False)]))
    found = elements(client.post(f'/cases/{case.id}/completeness', json={}))
    assert found['owner_name']['verdict'] == 'unclear'
    assert all(quote['text'] != 'SYNTHETIC old owner' for quote in found['owner_name']['quotes'])


def test_a_typed_answer_counts_as_given_but_a_reading_its_quote_does_not_support_does_not(context):
    client, store, _ = context
    typed = Fact(field='owner', value='SYNTHETIC Larkspur Row Homes', kind='pointed', status='confirmed',
                 source=Source(type='user_text', ref='Typed in Section A'))
    read = Fact(field='mailing_address', value='SYNTHETIC 100 Example Street', kind='pointed', status='confirmed',
                source=Source(type='file', ref='file_a', page=2, quote='SYNTHETIC 200 Other Road'))
    case = store.put(Case(facts=[typed, read]))
    found = elements(client.post(f'/cases/{case.id}/completeness', json={}))
    assert found['owner_name']['verdict'] == 'present'
    assert found['mailing_address']['verdict'] == 'unclear'


@pytest.mark.parametrize('body,status', [({'variant': 'C'}, 503), ({'variant': 'Z'}, 422),
                                        ({'documents': []}, 422), ({'anything_else': True}, 422)])
def test_unsupported_requests_fail_honestly_without_provider_work(context, body, status):
    client, store, _ = context
    case = store.put(Case(title='SYNTHETIC unsupported input'))
    before = store.get(case.id).model_dump()
    response = client.post(f'/cases/{case.id}/completeness', json=body)
    assert response.status_code == status, response.text
    assert store.get(case.id).model_dump() == before
    assert 'reviews' not in response.json()


def test_missing_case_checks_storage_before_corpus_or_variant_dependency(tmp_path):
    class NeverCodes:
        def __getattribute__(self, name):
            raise AssertionError(f'CodeDB touched for absent case: {name}')

    store = CaseStore(tmp_path / 'missing.sqlite')
    with TestClient(create_app(store, NeverCodes())) as client:
        for body in ({}, {'variant': 'C'}):
            response = client.post('/cases/case_SYNTHETIC_absent/completeness', json=body)
            assert response.status_code == 404, response.text
            assert response.json()['detail'] == 'case not found'
    with store._connect() as con:
        assert con.execute('SELECT count(*) FROM cases').fetchone()[0] == 0


def test_legacy_variant_names_consume_the_same_shared_policy(context):
    client, store, _ = context
    case = store.put(Case(facts=[
        fact('alternative_description', 'SYNTHETIC exterior cladding departure'),
        fact('process.risk_assessment', 'low risk'),
        fact('process.mitigating_measures', 'The interior stair handrail will be painted blue'),
        fact('process.assumptions_and_limits', 'The insulation capacity is stated as fact without a test'),
        fact('supporting_doc', 'brochure only'),
    ]))
    a = elements(client.post(f'/cases/{case.id}/completeness', json={'variant': 'A'}))
    b = elements(client.post(f'/cases/{case.id}/completeness', json={'variant': 'B'}))
    assert a == b
    assert a['risk_assessment']['verdict'] == 'unclear'
    assert b['risk_assessment']['problem'] == 'generic'
    assert b['mitigating_measures']['problem'] == 'unrelated'
    assert b['assumptions_and_limits']['problem'] == 'stated_as_fact'
    assert b['supporting_doc']['problem'] == 'brochure_only'
    assert b['section_b.consistency']['verdict'] == 'unclear'
    assert b['section_b.consistency']['lookup_skipped'] is True


def test_direct_c_and_document_entrypoints_fail_before_using_configured_dependencies():
    from engine.completeness_report import build_response
    from engine.completeness_variants import VariantUnavailable, run_variant
    from engine.review.ingest import IngestError, ingested_from_case, ingest_bytes, ingest_path

    class Forbidden:
        def __getattribute__(self, name):
            raise AssertionError(f'Unavailable entrypoint used dependency: {name}')

    with pytest.raises(VariantUnavailable, match='unavailable'):
        run_variant('C', ingested_from_case(Case()), Forbidden(), Forbidden())
    with pytest.raises(VariantUnavailable, match='unavailable'):
        build_response('C', [], case_id='SYNTHETIC', case_version=1, case_updated_at='SYNTHETIC')
    with pytest.raises(IngestError, match='unavailable'):
        ingest_bytes(b'SYNTHETIC document')
    with pytest.raises(IngestError, match='unavailable'):
        ingest_path(Forbidden())


@pytest.mark.parametrize('body,status', [({'variant': 'C'}, 503), ({'documents': []}, 422),
                                        ({'documents': [{'content_base64': 'a' * 2048}]}, 413)])
def test_public_unavailable_or_oversize_input_never_opens_codes(tmp_path, body, status):
    class Forbidden:
        def __getattribute__(self, name):
            raise AssertionError(f'Unavailable request touched CodeDB: {name}')

    store = CaseStore(tmp_path / 'closed.sqlite')
    case = store.put(Case())
    with TestClient(create_app(store, Forbidden())) as client:
        response = client.post(f'/cases/{case.id}/completeness', json=body)
    assert response.status_code == status, response.text
    assert response.headers['cache-control'] == 'no-store'


def test_chunked_oversize_request_is_bounded_before_json_decoding(context):
    client, store, _ = context
    case = store.put(Case())
    response = client.post(f'/cases/{case.id}/completeness',
                           content=iter([b'{"documents":"', b'a' * 1024, b'"}']))
    assert response.status_code == 413, response.text


def _selected_case(codes, provisions=('9.27.3.2.(1)', '9.27.3.3.(1)')):
    return Case(title='SYNTHETIC scoped attachment case', provisions=list(provisions),
                section_c=section_c_rows(list(provisions), codes), facts=[
                    fact('alternative_description', 'SYNTHETIC exterior cladding departure'),
                    fact('professional_status', 'not_engaged'),
                ])


def _scope_document(case, slot, item, file_id=None, *, auto_link=False):
    case.evidence.append(EvidenceItem(id=slot, description='SYNTHETIC applicant report',
                                     objective=item.objective, function=item.function, status='evidence_listed'))
    case.facts += [fact(f'evidence.{slot}.title', 'SYNTHETIC report title'),
                   fact(f'evidence.{slot}.responsible_party', 'SYNTHETIC organisation'),
                   fact(f'evidence.{slot}.date', 'SYNTHETIC revision'),
                   fact(f'evidence.{slot}.item_id', item.id),
                   fact(f'evidence.{slot}.provision_id', item.provision_id),
                   fact(f'evidence.{slot}.auto_link', auto_link)]
    if file_id:
        case.facts.append(fact(f'evidence.{slot}.file_ref', file_id, kind='exact', source_type='file', ref=file_id))


def test_scoped_text_listing_keeps_attachment_and_all_current_evidence_tasks(context):
    client, store, codes = context
    case = _selected_case(codes)
    items = section_d_plan(case, codes).items
    _scope_document(case, 'doc_text', items[0])
    case = store.put(case)
    response = client.post(f'/cases/{case.id}/completeness', json={})
    found = elements(response)
    assert found['evidence.doc_text.file_ref']['in_export_preflight'] is True
    assert found['evidence.doc_text.file_ref']['severity'] == 'blocking'
    groups = [entry for key, entry in found.items() if key in {f'evidence.{pid}' for pid in case.provisions}]
    assert len(groups) == 2  # one displayed task per sentence, not one row per pair
    assert set(field for group in groups for field in group['related_fields']) == {f'evidence.{item.id}' for item in items}
    assert all("doesn't review" in group['prompt']['question'] for group in groups)
    assert response.json()['reviews'][0]['export_reasons'] == blockers(store.get(case.id), load_field_map(), codes)


def test_owned_attachment_closes_only_its_explicit_item_not_another_provisions_pair(context):
    client, store, codes = context
    case = _selected_case(codes)
    items = section_d_plan(case, codes).items
    target = next(item for item in items if item.provision_id == case.provisions[0]
                  and any(other.provision_id != item.provision_id and (other.function, other.objective) ==
                          (item.function, item.objective) for other in items))
    shared_pair_elsewhere = next(item for item in items if item.provision_id != target.provision_id
                                 and (item.function, item.objective) == (target.function, target.objective))
    case = store.put(case)
    uploaded = store.put_file(case.id, 'synthetic.pdf', b'%PDF-1.4\nSYNTHETIC presence\n')
    _scope_document(case, 'doc_scoped', target, uploaded['id'])
    case = store.put(case, expected_version=case.version)
    found = elements(client.post(f'/cases/{case.id}/completeness', json={}))
    fields = {field for entry in found.values() for field in entry['related_fields']}
    assert f'evidence.{target.id}' not in fields
    assert f'evidence.{shared_pair_elsewhere.id}' in fields
    assert store.get_file(case.id, uploaded['id'])['data'] == b'%PDF-1.4\nSYNTHETIC presence\n'


@pytest.mark.parametrize('foreign', [False, True])
def test_phantom_or_foreign_file_never_closes_attachment_or_scope(context, foreign):
    client, store, codes = context
    case = _selected_case(codes, ('9.27.3.2.(1)',))
    item = section_d_plan(case, codes).items[0]
    file_id = 'file_SYNTHETIC_phantom'
    if foreign:
        other = store.put(Case(title='SYNTHETIC other owner'))
        file_id = store.put_file(other.id, 'foreign.pdf', b'%PDF SYNTHETIC foreign bytes')['id']
    _scope_document(case, 'doc_unowned', item, file_id)
    case.facts += [fact('professional_status', 'engaged'),
                   fact('ahj_requires_professional', True, source_type='officer', ref='SYNTHETIC internal direction'),
                   fact('professional.role', 'SYNTHETIC engineer'),
                   fact('professional.registration_number', 'SYNTHETIC registration'),
                   fact('professional_name', 'SYNTHETIC person'),
                   fact('evidence.doc_unowned.professional_seal', 'SYNTHETIC file authentication metadata')]
    case = store.put(case)
    before = store.get(case.id).model_dump()
    response = client.post(f'/cases/{case.id}/completeness', json={})
    found = elements(response)
    assert found['evidence.doc_unowned.file_ref']['severity'] == 'blocking'
    assert found['professional_authentication']['severity'] == 'blocking'
    assert f'evidence.{item.id}' in found[f'evidence.{item.provision_id}']['related_fields']
    assert any('unconfirmed exact fact' in reason for reason in response.json()['reviews'][0]['export_reasons'])
    assert store.get(case.id).model_dump() == before
    if foreign:
        assert store.get_file(other.id, file_id)['data'] == b'%PDF SYNTHETIC foreign bytes'


def test_reference_withdrawal_and_reselection_never_restore_document_scope(context):
    client, store, codes = context
    case = _selected_case(codes, ('9.27.3.2.(1)',))
    item = section_d_plan(case, codes).items[0]
    case = store.put(case)
    upload = store.put_file(case.id, 'synthetic.pdf', b'%PDF SYNTHETIC kept bytes')
    _scope_document(case, item.id, item, upload['id'], auto_link=True)
    case = store.put(case, expected_version=case.version)
    found = elements(client.post(f'/cases/{case.id}/completeness', json={}))
    assert f'evidence.{item.id}' not in found[f'evidence.{item.provision_id}']['related_fields']
    cleared = client.post(f'/cases/{case.id}/section-d', json={'provisions': [], 'expected_version': case.version})
    assert cleared.status_code == 200, cleared.text
    restored = client.post(f'/cases/{case.id}/section-d', json={
        'provisions': ['9.27.3.2.(1)'], 'expected_version': cleared.json()['case_version'],
    })
    assert restored.status_code == 200, restored.text
    found = elements(client.post(f'/cases/{case.id}/completeness', json={}))
    assert f'evidence.{item.id}' in found[f'evidence.{item.provision_id}']['related_fields']
    assert store.get_file(case.id, upload['id'])['data'] == b'%PDF SYNTHETIC kept bytes'


@pytest.mark.parametrize('withhold', [False, True])
def test_not_engaged_never_hides_a_mandatory_duty_or_independent_source_failure(context, withhold):
    client, store, codes = context
    if withhold:
        original = codes.provision
        codes.provision = lambda pid, division='B': None if (division, pid) == ('B', '9.15.3.3.(2)') else original(pid, division)
    case = store.put(Case(facts=[fact('professional_status', 'not_engaged'), fact('supported_joist_span_m', 5.2)]))
    response = client.post(f'/cases/{case.id}/completeness', json={})
    found = elements(response)
    if withhold:
        assert found['professional_requirement']['severity'] == 'blocking'
    else:
        assert found['professional_confirmation']['severity'] == 'blocking'
    assert ('professional_source' in found) is withhold
    if withhold:
        assert found['professional_source']['in_export_preflight'] is True
        assert '9.15.3.3.(2)' in found['professional_source']['reason']
        assert any('professional_source' in reason for reason in response.json()['reviews'][0]['export_reasons'])


def test_each_independent_failed_source_identity_survives_grouping(context):
    client, store, codes = context
    original = codes.provision
    failed = {'9.15.3.3.(2)', '9.23.3.5.(4)'}
    codes.provision = lambda pid, division='B': None if division == 'B' and pid in failed else original(pid, division)
    case = store.put(Case(facts=[fact('professional_status', 'not_engaged'),
                                fact('supported_joist_span_m', 5.2), fact('hourly_wind_pressure_1in50_kPa', 1.25)]))
    found = elements(client.post(f'/cases/{case.id}/completeness', json={}))
    assert all(pid in found['professional_source']['reason'] for pid in failed)
    assert found['professional_source']['severity'] == 'blocking'


def test_no_attribution_and_missing_benchmark_remain_honest_located_findings(context):
    client, store, codes = context
    case = _selected_case(codes, ('3.1.9.1.(4)',))
    case.provisions.append('99.99.99.99.(1)')  # deliberately invalid synthetic applicant reference
    case = store.put(case)
    found = elements(client.post(f'/cases/{case.id}/completeness', json={}))
    scope = [entry for entry in found.values() if entry['field'].endswith('.scope')]
    assert len(scope) == 1 and scope[0]['severity'] == 'warning'
    assert 'no row' in scope[0]['prompt']['question']
    assert found['provisions.99.99.99.99.(1)']['severity'] == 'blocking'
    assert found['section_c.provision_found']['verdict'] == 'missing'
    assert '99.99.99.99.(1)' in found['section_c.provision_found']['reason']


def test_distinct_saved_blocker_messages_on_same_field_are_not_silently_dropped(context):
    client, store, _ = context
    case = store.put(Case(gaps=[
        Gap(id='synthetic-source-one', section='D', field='review_source', message='SYNTHETIC missing source ONE'),
        Gap(id='synthetic-source-two', section='D', field='review_source', message='SYNTHETIC missing source TWO'),
    ]))
    found = elements(client.post(f'/cases/{case.id}/completeness', json={}))
    assert 'SYNTHETIC missing source ONE' in found['review_source']['reason']
    assert 'SYNTHETIC missing source TWO' in found['review_source']['reason']


def test_saved_source_page_bbox_and_applicant_quote_are_preserved_without_code_attribution(context):
    client, store, _ = context
    answer = fact('owner_name', 'SYNTHETIC drawing owner', source_type='drawing', ref='SYNTHETIC drawing')
    answer.source.page, answer.source.bbox = 2, (1, 2, 3, 4)
    case = store.put(Case(facts=[answer]))
    found = elements(client.post(f'/cases/{case.id}/completeness', json={}))
    source = found['owner_name']['sources'][0]
    assert source == answer.source.model_dump(mode='json')
    assert found['owner_name']['quotes'][0]['text'] == 'SYNTHETIC drawing owner'
    assert 'url' not in found['owner_name']['quotes'][0]


def _complete_package(store, codes):
    case = _selected_case(codes, ('3.1.8.1.(1)',))
    case.jurisdiction = Jurisdiction(id='synthetic-ahj', name='SYNTHETIC reviewing jurisdiction')
    case.facts += [fact(field, value) for field, value in {
        'owner_name': 'SYNTHETIC owner', 'request_date': '2026-10-21',
        'owner_rep_name': 'SYNTHETIC representative', 'mailing_address': 'SYNTHETIC mailing address',
        'municipal_address': 'SYNTHETIC project address', 'legal_description': 'SYNTHETIC lot block plan',
        'scope': 'site-specific', 'pathway': 'alternative',
        'process.rationale': 'SYNTHETIC applicant proposes a cladding departure using a comparison method.',
        'process.risk_assessment': 'SYNTHETIC cladding departure could affect occupants during a fire scenario.',
        'process.mitigating_measures': 'SYNTHETIC cladding departure measures address the fire scenario in the comparison.',
        'process.assumptions_and_limits': 'SYNTHETIC assumptions limit the cladding installation to this project configuration.',
        'process.maintenance_operation': 'SYNTHETIC applicant identifies inspection intervals and the responsible organisation.',
        'process.qualifications': 'SYNTHETIC applicant records the responsible designer and analysis scope.',
    }.items()]
    case = store.put(case)
    pdf = PdfWriter()
    pdf.add_blank_page(width=200, height=200)
    data = io.BytesIO()
    pdf.write(data)
    uploaded = store.put_file(case.id, 'synthetic-presence-only.pdf', data.getvalue())
    for index, item in enumerate(section_d_plan(case, codes).items):
        _scope_document(case, f'doc_presence_{index}', item, uploaded['id'])
    case = store.put(case, expected_version=case.version)
    return case, uploaded


@pytest.mark.parametrize('condition', ['unresolved_requirement', 'failed_source', 'missing_risk'])
def test_report_reasons_match_official_export_while_professional_handoff_is_unresolved(context, tmp_path, condition):
    client, store, codes = context
    case, upload = _complete_package(store, codes)
    if condition == 'failed_source':
        case = store.add_fact(case.id, fact('supported_joist_span_m', 5.2))
        original = codes.provision
        codes.provision = lambda pid, division='B': None if (division, pid) == ('B', '9.15.3.3.(2)') else original(pid, division)
    elif condition == 'missing_risk':
        case = store.add_fact(case.id, fact('process.risk_assessment', ''))
    before, bytes_before = store.get(case.id).model_dump(), store.get_file(case.id, upload['id'])['data']
    reviewed = client.post(f'/api/cases/{case.id}/completeness', json={})
    found = elements(reviewed)
    reasons = reviewed.json()['reviews'][0]['export_reasons']
    assert found['professional_requirement']['severity'] == 'blocking'
    official = client.post(f'/api/cases/{case.id}/export', json={'draft': False})
    assert official.status_code == 409, official.text
    assert official.json()['detail']['reasons'] == reasons
    assert reasons
    if condition == 'failed_source':
        assert found['professional_source']['severity'] == 'blocking'
        draft = client.post(f'/api/cases/{case.id}/export', json={'draft': True})
        assert draft.status_code == 200
        # The unresolved reference and reviewer action are the review's reasons; the draft document is not
        # a to-do list, so it does not print them.
        assert any('9.15.3.3.(2)' in reason for reason in reasons)
        assert any('professional' in reason.casefold() for reason in reasons)
        text = ' '.join(' '.join(page.extract_text().split()) for page in PdfReader(io.BytesIO(draft.content)).pages)
        assert not any(' '.join(reason.split())[:60] in text for reason in reasons)
        (tmp_path / 'failed-source-draft.pdf').write_bytes(draft.content)
    assert store.get(case.id).model_dump() == before
    assert store.get_file(case.id, upload['id'])['data'] == bytes_before
    (tmp_path / 'report.json').write_text(json.dumps(reviewed.json(), indent=2))
