"""Package review over HTTP: #48 reviewer roles, claim, information request, re-upload diff, access matrix."""
from __future__ import annotations

from contextlib import ExitStack
import io
import os
import uuid

import pytest
from fastapi.testclient import TestClient
from pypdf import PdfReader

from engine.api import create_app
from engine.codes import Codes
from engine.models import Case
from engine.store import CaseStore
from engine.tests.case_builder_fixtures import complete_case, fact, store_with_synthetic_files
from engine.tests.package_review_fixtures import (CLEAN_FORM, CLEAN_NARRATIVE, annotated_rationale_pdf,
                                                covered_scan_pdf, package, repeated_rationale_pdf, text_pdf)
from engine.tests.test_package_review_rationale import raster_rationale_pdf, split_rationale_pdf
from engine.tests.test_accounts import onboard, signup

NAMES = ['owner', 'other', 'reviewer', 'second', 'foreign', 'anonymous']


@pytest.mark.parametrize('kind,field', [('image', 'risk_assessment'), ('invisible', 'rationale'),
                                      ('Block', 'legal_description'), ('Objective', 'section_c.row1.pair')])
def test_upload_uncertainty_stays_out_of_the_http_applicant_request(scene, kind, field):
    from engine.tests.package_review_fixtures import CLEAN_FORM, fillable
    from engine.tests.test_package_review_logical_certainty import hidden_cell
    from engine.tests.test_package_review_passage_certainty import passage

    store, clients, _ = scene
    case = claimed(scene)
    before = store.get(case.id).model_dump()
    if kind in ('Block', 'Objective'):
        files = [('form.pdf', hidden_cell(kind))]
        source = 'form.pdf'
    else:
        heading = 'Rationale' if field == 'rationale' else 'Risk assessment'
        files = [('form.pdf', fillable(CLEAN_FORM)), ('answer.pdf', passage(kind, heading))]
        source = 'answer.pdf'
    response = clients['reviewer'].post(f'/review/{case.id}/package-review', files=multipart(files))
    assert response.status_code == 201, response.text
    body = response.json()
    finding = next(x for x in body['findings'] if x['field'] == field)
    assert finding['status'] == 'not_found'
    assert all(p['file'] == source and p['page'] == 1 for p in finding['pointers'])
    item = next(x for x in body['information_request']['items'] if x['finding_key'] == finding['key'])
    assert item['officer_check'] and not item['included']
    assert item['text'] not in body['information_request']['text']
    assert store.get(case.id).model_dump() == before


@pytest.fixture(scope='module')
def scene(tmp_path_factory):
    with pytest.MonkeyPatch.context() as patch, ExitStack() as stack:
        patch.delenv('VERCEL', raising=False)
        patch.setenv('BATATIS_REVIEWER_CODES', '{"edmonton":"officer-secret","calgary":"calgary-secret"}')
        patch.setenv('BATATIS_AUTH_RATE_LIMIT', '100')
        store = CaseStore(tmp_path_factory.mktemp('package-review') / 'cases.sqlite')
        app = create_app(store=store, codes=Codes())
        clients, users = {}, {}
        for name, role, authority in [('owner', 'applicant', 'edmonton'), ('other', 'applicant', 'edmonton'),
                                     ('reviewer', 'reviewer', 'edmonton'), ('second', 'reviewer', 'edmonton'),
                                     ('foreign', 'reviewer', 'calgary'), ('anonymous', None, None)]:
            clients[name] = stack.enter_context(TestClient(app, base_url='http://localhost'))
            if role:
                assert signup(clients[name], name + '@example.test', name.title()).status_code == 201
                users[name] = onboard(clients[name], role, authority)
        yield store, clients, users


def owned(scene, status='draft', complete=False):
    store, _, users = scene
    case = complete_case() if complete else Case(title='Package review matrix')
    case.owner_id, case.authority, case.status = users['owner']['id'], 'edmonton', status
    return store_with_synthetic_files(store, case) if complete else store.put(case)


def claimed(scene):
    store, clients, _ = scene
    case = owned(scene, 'submitted', complete=True)
    assert clients['reviewer'].post(f'/review/{case.id}/claim', json={}).status_code == 200
    return case


def multipart(files):
    return {'files': None} if not files else [('files', (name, data, 'application/pdf')) for name, data in files]


@pytest.fixture(scope='module', params=['sqlite', 'postgres'])
def multi_source_scene(request, tmp_path_factory):
    if request.param == 'postgres':
        from engine.store_postgres import PostgresCaseStore
        url = os.environ.get('TEST_DATABASE_URL')
        if not url:
            pytest.skip('TEST_DATABASE_URL is not set')
        store = PostgresCaseStore(url)
    else:
        store = CaseStore(tmp_path_factory.mktemp('multi-source') / 'cases.sqlite')
    with pytest.MonkeyPatch.context() as patch, ExitStack() as stack:
        patch.delenv('VERCEL', raising=False)
        patch.setenv('BATATIS_REVIEWER_CODES', '{"edmonton":"officer-secret"}')
        patch.setenv('BATATIS_AUTH_RATE_LIMIT', '100')
        app = create_app(store=store, codes=Codes())
        clients, users = {}, {}
        for name, role in [('owner', 'applicant'), ('reviewer', 'reviewer')]:
            client = stack.enter_context(TestClient(app, base_url='http://localhost'))
            assert signup(client, f'{uuid.uuid4().hex}@example.test', name.title()).status_code == 201
            clients[name], users[name] = client, onboard(client, role, 'edmonton')
        yield store, clients, users


@pytest.mark.parametrize('status', ['draft', 'submitted', 'in_review', 'returned', 'accepted', 'refused'])
def test_read_access_matrix(scene, status):
    store, clients, _ = scene
    case = owned(scene, status)
    for name in NAMES:
        allowed = name in {'reviewer', 'second'} and status != 'draft'
        for suffix in ('', '/1'):
            response = clients[name].get(f'/review/{case.id}/package-review{suffix}')
            expected = (200 if not suffix else 404) if allowed else 404
            assert response.status_code == expected, (name, status, suffix, response.text)
        # Sent requests are readable by the owner and the authority's reviewers, never by others.
        response = clients[name].get(f'/cases/{case.id}/information-request')
        reader = name == 'owner' or allowed
        assert response.status_code == (200 if reader else 404), (name, status, response.text)
    store.delete(case.id)


def test_only_the_claimer_runs_edits_and_sends(scene):
    store, clients, _ = scene
    case = owned(scene, 'submitted', complete=True)
    for name in NAMES:
        response = clients[name].post(f'/review/{case.id}/package-review')
        assert response.status_code == (409 if name in {'reviewer', 'second'} else 404), (name, response.text)
    assert clients['reviewer'].post(f'/review/{case.id}/claim', json={}).status_code == 200
    for name in NAMES:
        if name == 'reviewer':
            continue
        response = clients[name].post(f'/review/{case.id}/package-review')
        assert response.status_code == (409 if name == 'second' else 404), (name, response.text)
    run = clients['reviewer'].post(f'/review/{case.id}/package-review')
    assert run.status_code == 201, run.text
    body = {'items': [{'text': 'Please confirm the owner name.', 'included': True}]}
    for name in NAMES:
        if name == 'reviewer':
            continue
        assert clients[name].put(f'/review/{case.id}/package-review/1/information-request',
                                 json=body).status_code in (404, 409), name
        assert clients[name].post(f'/review/{case.id}/package-review/1/information-request/send').status_code in (404, 409)
    store.delete(case.id)


def test_case_review_request_send_and_applicant_view(scene):
    store, clients, _ = scene
    case = claimed(scene)
    first = clients['reviewer'].post(f'/review/{case.id}/package-review')
    assert first.status_code == 201, first.text
    session = first.json()
    assert session['input_kind'] == 'case' and session['version'] == 1 and session['diff'] is None
    assert session['administrative_only'] is True and session['not_a_compliance_determination'] is True
    assert session['citations'] and all(check['exists'] for check in session['citations'])
    assert session['documents'], 'the documents panel lists the case attachments'
    # Drafts stay private until sent.
    assert clients['owner'].get(f'/cases/{case.id}/information-request').json()['requests'] == []
    items = [{'id': item['id'], 'text': item['text'], 'included': item['included']}
             for item in session['information_request']['items']]
    items.append({'text': 'Please send the stamped drawing set referenced in Section D.', 'included': True})
    edited = clients['reviewer'].put(f'/review/{case.id}/package-review/1/information-request',
                                     json={'items': items, 'intro': 'Officer intro.'})
    assert edited.status_code == 200, edited.text
    request = edited.json()['information_request']
    assert request['edited'] and request['intro'] == 'Officer intro.'
    assert request['items'][-1]['authored_by'] == 'officer'
    assert 'stamped drawing set' in request['text']
    bad = clients['reviewer'].put(f'/review/{case.id}/package-review/1/information-request',
                                  json={'items': [{'id': 'ir_nope', 'text': 'x'}]})
    assert bad.status_code == 422
    sent = clients['reviewer'].post(f'/review/{case.id}/package-review/1/information-request/send')
    assert sent.status_code == 200, sent.text
    assert sent.json()['information_request']['sent_at']
    assert clients['reviewer'].post(f'/review/{case.id}/package-review/1/information-request/send').status_code == 409
    assert clients['reviewer'].put(f'/review/{case.id}/package-review/1/information-request',
                                   json={'items': items}).status_code == 409
    view = clients['owner'].get(f'/cases/{case.id}/information-request').json()['requests']
    assert len(view) == 1 and 'stamped drawing set' in view[0]['text']
    thread = clients['owner'].get(f'/cases/{case.id}/messages').json()['messages']
    assert any('stamped drawing set' in message['body'] for message in thread)
    notifications = clients['owner'].get('/me/notifications').json()
    assert notifications['unread'] >= 1
    # The review never records a decision or moves the status.
    saved = store.get(case.id)
    assert saved.decision is None and saved.status == 'in_review'
    second = clients['reviewer'].post(f'/review/{case.id}/package-review').json()
    assert second['version'] == 2 and second['diff']['previous_version'] == 1
    assert second['diff']['statement'].startswith(f"0 of {second['diff']['previous_gaps']} gaps resolved")
    index = clients['second'].get(f'/review/{case.id}/package-review').json()
    assert [s['version'] for s in index['sessions']] == [1, 2] and index['latest']['version'] == 2
    store.delete(case.id)
    assert store.get(case.id) is None


def test_upload_on_queue_case_and_reupload_diff(scene):
    store, clients, _ = scene
    case = claimed(scene)
    planted = dict(CLEAN_FORM, Owner='', **{'Date of Reqeuest': '', 'Name Responsible': ''})
    first = clients['reviewer'].post(f'/review/{case.id}/package-review', files=multipart(package(planted)))
    assert first.status_code == 201, first.text
    keys = {f['key'] for f in first.json()['findings'] if f['status'] != 'not_found'}
    assert {'owner_name:presence', 'application_date:presence', 'supporting_doc:no_responsible'} <= keys
    fixed = dict(CLEAN_FORM, **{'Date of Reqeuest': '', 'Lot': 'TBD'})
    second = clients['reviewer'].post(f'/review/{case.id}/package-review', files=multipart(package(fixed, flat=True)))
    assert second.status_code == 201, second.text
    diff = second.json()['diff']
    assert diff['previous_gaps'] == 3
    assert {e['key'] for e in diff['resolved']} == {'owner_name:presence', 'supporting_doc:no_responsible'}
    assert {e['key'] for e in diff['still_open']} == {'application_date:presence'}
    assert {e['key'] for e in diff['new']} == {'legal_description:presence'}
    assert diff['statement'] == '2 of 3 gaps resolved, 1 still open, 1 new'
    store.delete(case.id)


@pytest.mark.parametrize('standalone', [False, True], ids=['case-upload', 'standalone-upload'])
@pytest.mark.parametrize('input_kind', ['blank', 'split', 'raster'])
def test_uploaded_rationale_gap_and_reupload_resolution(scene, standalone, input_kind):
    store, clients, _ = scene
    case = None if standalone else claimed(scene)
    before = store.get(case.id).model_dump(mode='json') if case else None
    path = '/package-review' if standalone else f'/review/{case.id}/package-review'
    uploads = package(narrative=dict(CLEAN_NARRATIVE, Rationale='')) if input_kind == 'blank' else (
        package(drop=('Rationale',)) + [('rationale.pdf',
            split_rationale_pdf() if input_kind == 'split' else raster_rationale_pdf())])
    first = clients['reviewer'].post(path, files=multipart(uploads))
    assert first.status_code == 201, first.text
    session = first.json()
    assert session['administrative_only'] and session['not_a_compliance_determination']
    finding = next(f for f in session['findings'] if f['field'] == 'rationale')
    assert finding['status'] == ('blank' if input_kind == 'blank' else 'not_found')
    assert finding['severity'] == 'blocking'
    if input_kind == 'split':
        assert {p['page'] for p in finding['pointers'] if p['file'] == 'rationale.pdf'} >= {1, 2}
    item = next(i for i in session['information_request']['items'] if i['finding_key'] == finding['key'])
    assert item['included'] is (input_kind == 'blank')
    assert item['officer_check'] is (input_kind != 'blank')
    assert (item['text'] in session['information_request']['text']) is (input_kind == 'blank')
    reupload_path = f'/package-review/{session["package_id"]}' if standalone else path
    fixed = clients['reviewer'].post(reupload_path, files=multipart(package(flat=True)))
    assert fixed.status_code == 201, fixed.text
    assert not any(f['field'] == 'rationale' for f in fixed.json()['findings'])
    assert {e['key'] for e in fixed.json()['diff']['resolved']} == (
        {finding['key']} if input_kind == 'blank' else set())
    assert fixed.json()['diff']['previous_gaps'] == (1 if input_kind == 'blank' else 0)
    if case:
        assert store.get(case.id).model_dump(mode='json') == before
        store.delete(case.id)


def test_saved_rationale_gap_blocks_acceptance_until_applicant_supplies_it(scene):
    store, clients, _ = scene
    case = claimed(scene)
    saved = store.get(case.id)
    saved.facts = [f for f in saved.facts if f.field != 'rationale']
    store.put(saved)
    path = f'/review/{case.id}'
    first = clients['reviewer'].post(f'{path}/package-review')
    assert first.status_code == 201, first.text
    finding = next(f for f in first.json()['findings'] if f['field'] == 'rationale')
    assert finding['status'] == 'blank' and finding['severity'] == 'blocking'
    blocked = clients['reviewer'].post(f'{path}/decision', json={'outcome': 'accept'})
    assert blocked.status_code == 409, blocked.text
    assert any(g['field'] == 'rationale' for g in blocked.json()['detail']['gaps'])
    assert store.get(case.id).status == 'in_review' and store.get(case.id).decision is None
    saved = store.get(case.id)
    saved.facts.append(fact('process.rationale', 'SYNTHETIC applicant rationale: the existing assembly rating is '
                           'unknown, so we propose a separately documented alternative.'))
    store.put(saved)
    second = clients['reviewer'].post(f'{path}/package-review')
    assert second.status_code == 201, second.text
    assert not any(f['field'] == 'rationale' for f in second.json()['findings'])
    assert finding['key'] in {e['key'] for e in second.json()['diff']['resolved']}
    accepted = clients['reviewer'].post(f'{path}/decision', json={'outcome': 'accept'})
    assert accepted.status_code == 200, accepted.text
    assert accepted.json()['decision']['message'] == (
        'Accepted as administratively complete. Technical review remains the responsibility of the authority.')
    store.delete(case.id)


@pytest.mark.parametrize('path', ['standalone', 'case-upload', 'http-export'])
@pytest.mark.parametrize('later_paragraph', [False, True], ids=['initial', 'later-paragraph'])
def test_nbc_prose_rationale_survives_upload_and_http_export(scene, path, later_paragraph):
    store, clients, _ = scene
    rationale = ('NBC(AE) defines the benchmark; our proposed departure is described here.'
                 if not later_paragraph else 'SYNTHETIC applicant introduction.\n\n'
                 'NBC(AE) defines the benchmark; the applicant supplies this second paragraph.\n'
                 'SYNTHETIC final words belonging to the rationale.')
    expected = ' '.join(rationale.split())
    case = claimed(scene) if path == 'case-upload' else None
    route = f'/review/{case.id}/package-review' if case else '/package-review'
    if path == 'http-export':
        case = owned(scene, complete=True)
        saved = store.get(case.id)
        saved.facts = [f for f in saved.facts if f.field != 'rationale'] + [fact('process.rationale', rationale)]
        store.put(saved)
        exported = clients['owner'].post(f'/cases/{case.id}/export')
        assert exported.status_code == 200, exported.text
        uploads = [('official-prose.pdf', exported.content)]
        source = 'official-prose.pdf'
    else:
        source = 'applicant-rationale.pdf'
        uploads = package(drop=('Rationale',)) + [(source, text_pdf([
            'Rationale', *rationale.split('\n'), 'Risk assessment', 'SYNTHETIC next process field.']))]
    response = clients['reviewer'].post(route, files=multipart(uploads))
    assert response.status_code == 201, response.text
    session = response.json()
    reading = next(f for f in session['fields'] if f['field'] == 'rationale')
    assert reading['status'] == 'present' and reading['value'] == expected, reading
    assert reading['pointer']['file'] == source and reading['pointer']['page']
    assert reading['pointer']['quote'] == expected
    assert not any(f['field'] == 'rationale' for f in session['findings'])
    assert not any(i['field'] == 'rationale' for i in session['information_request']['items'])
    assert session['administrative_only'] and session['not_a_compliance_determination']
    if case:
        store.delete(case.id)


@pytest.mark.parametrize('linked', [False, True], ids=['standalone', 'case-linked'])
@pytest.mark.parametrize('reverse', [False, True], ids=['blank-first', 'supplied-first'])
def test_official_blank_draft_cannot_mask_supplied_rationale(multi_source_scene, linked, reverse):
    store, clients, _ = multi_source_scene
    case = owned(multi_source_scene, complete=True)
    saved = store.get(case.id)
    saved.facts = [f for f in saved.facts if f.field not in ('rationale', 'process.rationale')]
    store.put(saved)
    exported = clients['owner'].post(f'/cases/{case.id}/export', json={'draft': True})
    assert exported.status_code == 200, exported.text
    saved = store.get(case.id)
    saved.status = 'submitted'
    store.put(saved)
    assert clients['reviewer'].post(f'/review/{case.id}/claim', json={}).status_code == 200
    before = store.get(case.id).model_dump(mode='json')
    rationale = 'NBC(AE) defines the benchmark; our proposed departure is described here.'
    uploads = [('official-blank-draft.pdf', exported.content), ('supplied-rationale.pdf', text_pdf([
        'Rationale', rationale, 'Risk assessment', 'SYNTHETIC following process field.']))]
    if reverse:
        uploads.reverse()
    route = f'/review/{case.id}/package-review' if linked else '/package-review'
    response = clients['reviewer'].post(route, files=multipart(uploads))
    assert response.status_code == 201, response.text
    session = response.json()
    reading = next(f for f in session['fields'] if f['field'] == 'rationale')
    assert reading['status'] == 'not_found' and reading['value'] is None, reading
    finding = next(f for f in session['findings'] if f['field'] == 'rationale')
    assert finding['status'] == 'not_found'
    assert {p['file'] for p in finding['pointers']} == {'official-blank-draft.pdf', 'supplied-rationale.pdf'}
    assert any(p['file'] == 'supplied-rationale.pdf' and p['quote'] == rationale for p in finding['pointers'])
    assert any(p['file'] == 'official-blank-draft.pdf' and 'No answer has been supplied by Batatis.' in p['quote']
               for p in finding['pointers'])
    item = next(i for i in session['information_request']['items'] if i['field'] == 'rationale')
    assert item['officer_check'] and not item['included']
    assert item['text'] not in session['information_request']['text']
    # Once only the supplied passage remains, no rationale request survives the re-upload.
    reupload = route if linked else f'/package-review/{session["package_id"]}'
    supplied = [upload for upload in uploads if upload[0] == 'supplied-rationale.pdf']
    resolved = clients['reviewer'].post(reupload, files=multipart(supplied))
    assert resolved.status_code == 201, resolved.text
    assert next(f for f in resolved.json()['fields'] if f['field'] == 'rationale')['value'] == rationale
    assert not any(i['field'] == 'rationale' for i in resolved.json()['information_request']['items'])
    assert store.get(case.id).model_dump(mode='json') == before
    store.delete(case.id)


@pytest.mark.parametrize('linked', [False, True], ids=['standalone', 'case-linked'])
@pytest.mark.parametrize('reverse', [False, True], ids=['blank-first', 'supplement-first'])
@pytest.mark.parametrize('supplement', [
    'repeated-raster', 'unique-heading-raster', 'repeated-vector', 'reversed-boundaries',
    'covered-scan', 'same-page-scan', 'scan-control'])
def test_official_blank_draft_retains_graphics_and_page_uncertainty(
        multi_source_scene, linked, reverse, supplement):
    import hashlib
    store, clients, _ = multi_source_scene
    case = owned(multi_source_scene, complete=True)
    saved = store.get(case.id)
    saved.facts = [f for f in saved.facts if f.field not in ('rationale', 'process.rationale')]
    store.put(saved)
    exported = clients['owner'].post(f'/cases/{case.id}/export', json={'draft': True})
    assert exported.status_code == 200, exported.text
    saved = store.get(case.id)
    saved.status = 'submitted'
    store.put(saved)
    assert clients['reviewer'].post(f'/review/{case.id}/claim', json={}).status_code == 200
    before = store.get(case.id).model_dump(mode='json')
    if supplement in ('covered-scan', 'same-page-scan', 'scan-control'):
        cover = {'covered-scan': 'separate', 'same-page-scan': 'same-page', 'scan-control': 'none'}[supplement]
        data = covered_scan_pdf(cover)
        expected_sources = [(2 if cover == 'separate' else 1, None)]
    else:
        unique = supplement in ('unique-heading-raster', 'reversed-boundaries')
        data = repeated_rationale_pdf('vector' if supplement == 'repeated-vector' else 'raster',
                                      unique_heading=unique, reversed_stop=supplement == 'reversed-boundaries')
        expected_sources = [(1, 'Rationale'), (1, 'Rationale for variance' if unique else 'Rationale')]
    uploads = [('official-blank-draft.pdf', exported.content), ('supplement.pdf', data)]
    if reverse:
        uploads.reverse()
    route = f'/review/{case.id}/package-review' if linked else '/package-review'
    response = clients['reviewer'].post(route, files=multipart(uploads))
    assert response.status_code == 201, response.text
    session = response.json()
    reading = next(f for f in session['fields'] if f['field'] == 'rationale')
    finding = next(f for f in session['findings'] if f['field'] == 'rationale')
    assert reading['status'] == finding['status'] == 'not_found', reading
    assert reading['value'] is None
    assert [(p['page'], p['quote']) for p in finding['pointers'] if p['file'] == 'supplement.pdf'] == expected_sources
    appendix_page = int(PdfReader(io.BytesIO(exported.content)).metadata['/BatatisFormPages']) + 1
    assert any(p['file'] == 'official-blank-draft.pdf' and p['page'] == appendix_page
               and p['quote'] == '(Not provided or not confirmed. No answer has been supplied by Batatis.)'
               for p in finding['pointers'])
    assert next(f for f in session['files'] if f['name'] == 'supplement.pdf')['sha256'] == hashlib.sha256(data).hexdigest()
    item = next(i for i in session['information_request']['items'] if i['field'] == 'rationale')
    assert item['officer_check'] and not item['included']
    assert item['text'] not in session['information_request']['text']
    assert session['administrative_only'] and session['not_a_compliance_determination']
    # A later readable applicant passage resolves the uncertainty without changing the saved case.
    reupload = route if linked else f'/package-review/{session["package_id"]}'
    passage = 'SYNTHETIC supplied readable rationale, with unknown existing conditions.'
    resolved = clients['reviewer'].post(reupload, files=multipart([
        ('readable.pdf', text_pdf(['Rationale', passage, 'Risk assessment']))]))
    assert resolved.status_code == 201, resolved.text
    assert next(f for f in resolved.json()['fields'] if f['field'] == 'rationale')['value'] == passage
    assert not any(i['field'] == 'rationale' for i in resolved.json()['information_request']['items'])
    assert store.get(case.id).model_dump(mode='json') == before
    store.delete(case.id)


@pytest.mark.parametrize('linked', [False, True], ids=['standalone', 'case-linked'])
@pytest.mark.parametrize('reverse', [False, True], ids=['forward', 'reverse'])
@pytest.mark.parametrize('variant', ['stamp-text', 'stamp-vector', 'selected-state', 'free-text', 'cover-page',
    'hidden', 'unselected-state', 'outside-present', 'wrapped-label', 'wrapped-body', 'wrapped-limits'])
def test_annotation_and_wrapped_boundaries_over_http(multi_source_scene, linked, reverse, variant):
    import hashlib
    store, clients, _ = multi_source_scene
    case = owned(multi_source_scene, complete=True)
    saved = store.get(case.id)
    saved.facts = [f for f in saved.facts if f.field not in ('rationale', 'process.rationale')]
    store.put(saved)
    exported = clients['owner'].post(f'/cases/{case.id}/export', json={'draft': True})
    assert exported.status_code == 200, exported.text
    saved = store.get(case.id)
    saved.status = 'submitted'
    store.put(saved)
    assert clients['reviewer'].post(f'/review/{case.id}/claim', json={}).status_code == 200
    before = store.get(case.id).model_dump(mode='json')
    passage = 'SYNTHETIC readable applicant rationale, with unknown existing conditions.'
    expected, page, quote = 'not_found', 1, 'Rationale'
    other = ('official-blank.pdf', exported.content)
    if variant.startswith('wrapped'):
        heading = ['Assumptions', 'and limits:'] if variant == 'wrapped-limits' else ['Risk', 'assessment:']
        data = text_pdf(['Rationale', *heading,
                         '' if variant == 'wrapped-label' else 'SYNTHETIC neighboring field body.', 'Commissioning'])
        other = ('cover.pdf', text_pdf(['SYNTHETIC readable cover.']))
    else:
        options = {'stamp-text': {}, 'stamp-vector': {'kind': 'vector'}, 'selected-state': {'appearance': 'state'},
                   'free-text': {'subtype': '/FreeText'}, 'cover-page': {'layout': 'cover-page'},
                   'hidden': {'flags': 6}, 'unselected-state': {'appearance': 'unselected-state'},
                   'outside-present': {'layout': 'outside', 'passage': passage}}[variant]
        data = annotated_rationale_pdf(**options)
        if variant == 'cover-page':
            page, quote = 2, None
        elif variant in ('hidden', 'unselected-state'):
            expected = 'blank'
        elif variant == 'outside-present':
            expected, quote = 'present', passage
            other = ('cover.pdf', text_pdf(['SYNTHETIC readable cover.']))
    uploads = [other, ('supplement.pdf', data)]
    if reverse:
        uploads.reverse()
    route = f'/review/{case.id}/package-review' if linked else '/package-review'
    response = clients['reviewer'].post(route, files=multipart(uploads))
    assert response.status_code == 201, response.text
    session = response.json()
    reading = next(f for f in session['fields'] if f['field'] == 'rationale')
    assert reading['status'] == expected, reading
    findings = [f for f in session['findings'] if f['field'] == 'rationale']
    items = [i for i in session['information_request']['items'] if i['field'] == 'rationale']
    if expected == 'present':
        assert reading['value'] == reading['pointer']['quote'] == passage and not findings and not items
    else:
        assert reading['value'] is None and findings[0]['status'] == expected
        assert any((p['file'], p['page'], p['quote']) == ('supplement.pdf', page, quote)
                   for p in findings[0]['pointers'])
        assert items[0]['included'] == (expected == 'blank')
        assert items[0]['officer_check'] == (expected == 'not_found')
        if expected == 'not_found':
            assert items[0]['text'] not in session['information_request']['text']
    assert session['administrative_only'] and session['not_a_compliance_determination']
    assert {f['name']: f['sha256'] for f in session['files']} == {
        name: hashlib.sha256(content).hexdigest() for name, content in uploads}
    reupload = route if linked else f'/package-review/{session["package_id"]}'
    resolved = clients['reviewer'].post(reupload, files=multipart([
        ('readable.pdf', text_pdf(['Rationale', passage, 'Risk assessment']))]))
    assert resolved.status_code == 201, resolved.text
    assert next(f for f in resolved.json()['fields'] if f['field'] == 'rationale')['value'] == passage
    assert not any(i['field'] == 'rationale' for i in resolved.json()['information_request']['items'])
    assert store.get(case.id).model_dump(mode='json') == before
    store.delete(case.id)


def test_standalone_upload_review_is_reviewer_and_authority_scoped(scene):
    _, clients, _ = scene
    files = package(dict(CLEAN_FORM, Owner=''))
    assert clients['anonymous'].post('/package-review', files=multipart(files)).status_code == 401
    assert clients['owner'].post('/package-review', files=multipart(files)).status_code == 403
    created = clients['reviewer'].post('/package-review', files=multipart(files))
    assert created.status_code == 201, created.text
    package_id = created.json()['package_id']
    assert created.json()['case_id'] is None
    assert clients['second'].get(f'/package-review/{package_id}').status_code == 200
    assert clients['foreign'].get(f'/package-review/{package_id}').status_code == 404
    assert clients['foreign'].post(f'/package-review/{package_id}', files=multipart(files)).status_code == 404
    assert clients['owner'].get(f'/package-review/{package_id}').status_code == 403
    again = clients['second'].post(f'/package-review/{package_id}', files=multipart(package()))
    assert again.status_code == 201
    assert again.json()['diff']['statement'].startswith('1 of 1 gaps resolved')
    assert clients['reviewer'].get(f'/package-review/{package_id}/2').json()['version'] == 2


def test_upload_input_errors(scene):
    _, clients, _ = scene
    assert clients['reviewer'].post('/package-review', content=b'%PDF-1.4',
                                    headers={'content-type': 'application/pdf'}).status_code == 415
    response = clients['reviewer'].post('/package-review', files=[('files', ('notes.txt', b'hello', 'text/plain'))])
    assert response.status_code == 201
    session = response.json()
    assert session['files'][0]['role'] == 'unreadable'
    assert {f['key'] for f in session['findings']} >= {'form:presence', 'file:notes.txt:unreadable'}
    big = [('files', ('big.pdf', b'%PDF' + b'0' * (4 * 1024 * 1024), 'application/pdf'))]
    assert clients['reviewer'].post('/package-review', files=big).status_code == 413


@pytest.mark.parametrize('outcome', ['accept', 'refuse'])
def test_close_out_after_decision_with_record_package(scene, outcome):
    store, clients, _ = scene
    case = claimed(scene)
    reviewed = clients['reviewer'].post(f'/review/{case.id}/package-review')
    assert reviewed.status_code == 201
    source_version = reviewed.json()['case_version']
    assert clients['reviewer'].get(f'/review/{case.id}/close-out').status_code == 404   # no decision yet
    decided = clients['reviewer'].post(f'/review/{case.id}/decision',
                                      json={'outcome': outcome, 'message': 'Officer recorded the written reason.',
                                            'expected_version': source_version})
    assert decided.status_code == 200, decided.text
    close = clients['second'].get(f'/review/{case.id}/close-out')
    assert close.status_code == 200, close.text
    body = close.json()
    assert body['outcome'] == outcome
    assert body['decided_at'] == decided.json()['decision']['at']
    decided_case = store.get(case.id).model_dump()
    # Decision/close-out writes never rewrite the review's saved source version or applicant evidence.
    for path, payload in [('/package-review', None),
                          ('/package-review/1/information-request', {'items': []}),
                          ('/package-review/1/information-request/send', None)]:
        method = 'put' if payload is not None else 'post'
        assert clients['reviewer'].request(method, f'/review/{case.id}' + path, json=payload).status_code == 409
    from datetime import datetime, timedelta, timezone
    decided_at = datetime.fromisoformat(body['decided_at']).date()
    assert body['due_date'] == (decided_at + timedelta(days=10)).isoformat()
    assert body['days_remaining'] == (decided_at + timedelta(days=10) - datetime.now(timezone.utc).date()).days
    assert body['sent'] is False and body['overdue'] is False
    package_ = body['record_package']
    assert package_['send_to_council'][0]['label'] == 'Copy of the variance as decided'
    assert {item['label'] for item in package_['retain_on_file']} >= {'Supporting documents',
                                                                      'Section C code references and attributions'}
    assert 'IB-2025-11-18' in package_['basis'][0]
    assert 'never' not in body['notice'] or 'does not send' in body['notice']
    index = clients['reviewer'].get(f'/review/{case.id}/package-review').json()
    assert index['close_out']['due_date'] == body['due_date']
    assert index['close_out']['outcome'] == outcome
    assert index['latest']['case_version'] == source_version
    for name in ['owner', 'other', 'foreign', 'anonymous']:
        assert clients[name].post(f'/review/{case.id}/close-out/sent').status_code == 404, name
    assert clients['second'].post(f'/review/{case.id}/close-out/sent').status_code == 409
    sent = clients['reviewer'].post(f'/review/{case.id}/close-out/sent')
    assert sent.status_code == 200 and sent.json()['sent'] and sent.json()['sent_by_name'] == 'Reviewer'
    assert clients['reviewer'].post(f'/review/{case.id}/close-out/sent').status_code == 409
    assert clients['second'].get(f'/review/{case.id}/close-out').json()['sent']
    assert store.get(case.id).model_dump() == decided_case
    store.delete(case.id)


def test_send_claims_the_session_before_posting_and_releases_it_on_failure(scene, monkeypatch):
    """Nothing reaches the applicant unless the send is claimed; a failed post leaves the request unsent."""
    import engine.routes_package_review as routes
    from engine.review.sessions import Sessions
    store, clients, _ = scene
    case = claimed(scene)
    assert clients['reviewer'].post(f'/review/{case.id}/package-review').status_code == 201
    real = routes.mutate
    seen = []

    def failing(*args, **kwargs):
        seen.append(Sessions(store).get(case.id, 1)[0].information_request.sent_at)
        raise RuntimeError('thread write failed')

    monkeypatch.setattr(routes, 'mutate', failing)
    with pytest.raises(RuntimeError):
        clients['reviewer'].post(f'/review/{case.id}/package-review/1/information-request/send')
    assert seen and seen[0], 'the claim is stored before the message is posted'
    assert Sessions(store).get(case.id, 1)[0].information_request.sent_at is None
    monkeypatch.setattr(routes, 'mutate', real)
    sent = clients['reviewer'].post(f'/review/{case.id}/package-review/1/information-request/send')
    assert sent.status_code == 200, sent.text
    assert sent.json()['information_request']['message_id']
    assert len(clients['owner'].get(f'/cases/{case.id}/information-request').json()['requests']) == 1


def test_send_rechecks_the_claim_on_the_written_case(scene, monkeypatch):
    """A take-over between the route check and the post stops the send; the claim is released."""
    import engine.routes_package_review as routes
    from engine.review.sessions import Sessions
    store, clients, _ = scene
    case = claimed(scene)
    assert clients['reviewer'].post(f'/review/{case.id}/package-review').status_code == 201
    real = routes.mutate

    def taken_over(backend, case_id, user, change):
        current = store.get(case_id)
        current.claim = current.claim.model_copy(update={'reviewer_id': 'someone-else'})
        return change(current)

    monkeypatch.setattr(routes, 'mutate', taken_over)
    refused = clients['reviewer'].post(f'/review/{case.id}/package-review/1/information-request/send')
    assert refused.status_code == 409
    request = Sessions(store).get(case.id, 1)[0].information_request
    assert request.sent_at is None and request.message_id is None
    assert clients['owner'].get(f'/cases/{case.id}/information-request').json()['requests'] == []
    monkeypatch.setattr(routes, 'mutate', real)


def test_a_stuck_claim_keeps_the_original_error_is_hidden_and_expires(scene, monkeypatch):
    import engine.routes_package_review as routes
    from engine.review.sessions import Sessions
    store, clients, _ = scene
    case = claimed(scene)
    assert clients['reviewer'].post(f'/review/{case.id}/package-review').status_code == 201
    real_mutate, real_replace = routes.mutate, Sessions.replace
    calls = []

    def replace_then_fail(self, session, expected):
        calls.append(session.information_request.sent_at)
        if len(calls) > 1:
            raise OSError('store unavailable')
        return real_replace(self, session, expected)

    def outage(*_args, **_kwargs):
        raise RuntimeError('thread write failed')

    monkeypatch.setattr(routes, 'mutate', outage)
    monkeypatch.setattr(Sessions, 'replace', replace_then_fail)
    with pytest.raises(RuntimeError, match='thread write failed'):   # not the release's OSError
        clients['reviewer'].post(f'/review/{case.id}/package-review/1/information-request/send')
    monkeypatch.setattr(Sessions, 'replace', real_replace)
    stuck = Sessions(store).get(case.id, 1)[0].information_request
    assert stuck.sent_at and stuck.message_id is None
    assert clients['owner'].get(f'/cases/{case.id}/information-request').json()['requests'] == []
    busy = clients['reviewer'].post(f'/review/{case.id}/package-review/1/information-request/send')
    assert busy.status_code == 409 and busy.headers['retry-after']
    monkeypatch.setattr(routes, 'SEND_CLAIM_TTL', routes.timedelta(0))   # the claim has expired
    monkeypatch.setattr(routes, 'mutate', real_mutate)
    sent = clients['reviewer'].post(f'/review/{case.id}/package-review/1/information-request/send')
    assert sent.status_code == 200, sent.text
    assert len(clients['owner'].get(f'/cases/{case.id}/information-request').json()['requests']) == 1
