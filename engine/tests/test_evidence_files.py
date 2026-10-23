"""Real uploaded synthetic PDFs, ledger binding, retention and role-scoped delivery."""
from datetime import datetime, timedelta, timezone
from hashlib import sha256
from io import BytesIO

import pytest
from fastapi import HTTPException
from reportlab.pdfgen import canvas

from engine.access import AccessContext, current_access
from engine.account_models import User
from engine.models import Case
from engine.process_fields import confirmed_value
from engine.section_d import section_d_plan, supporting_documents
from engine.codes import Codes
from engine.tests.test_evidence_ledger import ledger, payload, post  # noqa: F401 - real adapter fixture
from engine.tests.test_review import scene, owned  # noqa: F401 - real account sessions


def synthetic_pdf(revision='A'):
    stream = BytesIO()
    pdf = canvas.Canvas(stream)
    pdf.drawString(72, 720, f'SYNTHETIC attachment fixture {revision}. No professional finding.')
    pdf.save()
    return stream.getvalue()


def upload(client, case_id, name='SYNTHETIC source.pdf', data=None):
    data = synthetic_pdf() if data is None else data
    response = client.post(f'/cases/{case_id}/files', files={'file': (name, data, 'application/pdf')})
    assert response.status_code == 201, response.text
    return response.json(), data


def test_upload_bind_scope_and_download_deliver_the_same_pdf_bytes(ledger):
    store, create, client = ledger
    case = create(provisions=['9.27.3.2.(1)'])
    target = section_d_plan(case, Codes()).items[0]
    file, data = upload(client, case.id)
    inventory = client.get(f'/cases/{case.id}/files').json()['items']
    assert inventory == [{key: file[key] for key in ('id', 'name', 'size', 'content_type')}]
    assert store.get_version(case.id) == case.version, 'upload bytes do not acknowledge a content edit'
    response = post(client, case.id, payload(file_ref=file['id'], scope={'item_id': target.id}))
    assert response.status_code == 200, response.text
    assert response.json()['case_version'] == case.version + 1
    assert response.json()['evidence']['kind'] == 'file'
    saved = store.get(case.id)
    source = next(f for f in reversed(saved.facts) if f.field == 'evidence.doc_wall.file_ref')
    assert source.value == source.source.ref == file['id']
    assert source.source.type == 'file' and source.source.quote == file['name']
    assert confirmed_value(saved, f'evidence.doc_wall.covers.{target.id}') is True
    assert [item.id for item in section_d_plan(saved, Codes()).items if item.attachments] == [target.id]
    assert supporting_documents(saved)[0].file.ref == file['id']
    assert not any(g['field'] == 'evidence.doc_wall.file_ref'
                   for g in client.get(f'/cases/{case.id}/gaps').json()['items'])
    got = client.get(f'/cases/{case.id}/files/{file["id"]}')
    assert got.status_code == 200
    assert got.content == data and sha256(got.content).digest() == sha256(data).digest()
    assert got.headers['content-type'] == 'application/pdf'
    assert got.headers['cache-control'] == 'no-store'
    assert got.headers['x-content-type-options'] == 'nosniff'
    assert got.headers['content-disposition'].startswith('attachment;')
    assert got.headers['content-security-policy'].startswith('sandbox;')
    assert store.get_version(case.id) == response.json()['case_version'], 'reads do not change the content revision'


def test_title_and_unowned_ids_cannot_close_attachment_gaps(ledger):
    store, create, client = ledger
    case, other = create(), create()
    foreign, _ = upload(client, other.id)
    assert post(client, case.id, payload()).status_code == 200
    assert store.get(case.id).evidence[0].kind == 'text'
    before = store.get(case.id)
    for file_id in ('file_copied_arbitrary_id', foreign['id']):
        response = post(client, case.id, payload(before.version, operation='update', file_ref=file_id))
        assert response.status_code == 422, response.text
        assert store.get(case.id) == before
        assert client.get(f'/cases/{case.id}/files/{file_id}').status_code == 404
    assert client.get(f'/cases/{case.id}/files').json()['items'] == []


def test_replace_unbind_and_remove_preserve_sources_other_slots_and_cas(ledger):
    store, create, client = ledger
    case = create()
    first, data_a = upload(client, case.id)
    second, data_b = upload(client, case.id, 'SYNTHETIC revision B.pdf', synthetic_pdf('B'))
    assert post(client, case.id, payload(file_ref=first['id'])).status_code == 200
    assert post(client, case.id, payload(2, evidence_id='doc_other', file_ref=first['id'])).status_code == 200
    before = store.get(case.id)
    # Every binding change is CAS protected. A stale replacement cannot change either slot.
    assert post(client, case.id, payload(2, operation='update', file_ref=second['id'])).status_code == 409
    assert store.get(case.id) == before
    replaced = post(client, case.id, payload(3, operation='update', file_ref=second['id']))
    assert replaced.status_code == 200
    assert replaced.json()['evidence']['kind'] == 'file'
    assert confirmed_value(store.get(case.id), 'evidence.doc_wall.file_ref') == second['id']
    removed = post(client, case.id, payload(4, operation='update', file_ref=None))
    assert removed.status_code == 200 and removed.json()['evidence']['kind'] == 'text'
    saved = store.get(case.id)
    assert {doc.id for doc in supporting_documents(saved)} == {'doc_other'}
    assert confirmed_value(saved, 'evidence.doc_other.file_ref') == first['id']
    # Original source facts remain inspectable after replacement and unbinding.
    assert [f.value for f in saved.facts if f.field == 'evidence.doc_wall.file_ref'] == [first['id'], second['id'], None]
    deleted = client.request('DELETE', f'/cases/{case.id}/evidence/doc_wall', json={'expected_version': 5})
    assert deleted.status_code == 200
    assert [item.id for item in store.get(case.id).evidence] == ['doc_other']
    assert {f['id'] for f in client.get(f'/cases/{case.id}/files').json()['items']} == {first['id'], second['id']}
    assert client.get(f'/cases/{case.id}/files/{first["id"]}').content == data_a
    assert client.get(f'/cases/{case.id}/files/{second["id"]}').content == data_b
    # A stale binding update cannot resurrect a deleted evidence slot.
    assert post(client, case.id, payload(5, operation='update', file_ref=first['id'])).status_code == 409
    assert post(client, case.id, payload(6, operation='update', file_ref=first['id'])).status_code == 404


def test_binding_commit_does_not_overwrite_an_interleaved_content_edit(ledger, monkeypatch):
    store, create, client = ledger
    case = create()
    file, _ = upload(client, case.id)
    put = store.put
    ran = []

    def interleave(candidate, *, expected_version=None):
        if not ran:
            ran.append(True)
            live = store.get(case.id)
            live.title = 'SYNTHETIC concurrent content'
            put(live, expected_version=live.version)
        return put(candidate, expected_version=expected_version)

    monkeypatch.setattr(store, 'put', interleave)
    response = post(client, case.id, payload(file_ref=file['id']))
    assert response.status_code == 409
    assert store.get(case.id).title == 'SYNTHETIC concurrent content'
    assert store.get(case.id).evidence == []
    assert store.get_file(case.id, file['id']) is not None


@pytest.mark.parametrize('ending', ['deleted', 'expired'])
def test_removed_case_has_no_inventory_download_or_binding(ledger, ending):
    store, create, client = ledger
    case = create()
    file, _ = upload(client, case.id)
    if ending == 'deleted':
        store.delete(case.id)
    else:
        saved = store.get(case.id)
        saved.created_at = (datetime.now(timezone.utc) - timedelta(days=8)).isoformat()
        store.put(saved, expected_version=saved.version)
    for suffix in ('/files', f'/files/{file["id"]}'):
        assert client.get(f'/cases/{case.id}' + suffix).status_code == 404
    assert post(client, case.id, payload(file_ref=file['id'])).status_code == 404
    assert store.get_file(case.id, file['id']) is None


def test_download_filename_is_metadata_not_a_header_or_path(ledger):
    store, create, client = ledger
    case = create()
    file = store.put_file(case.id, '../folder/évil"\r\nX-Injected: yes.pdf', synthetic_pdf())
    response = client.get(f'/cases/{case.id}/files/{file["id"]}')
    assert response.status_code == 200
    disposition = response.headers['content-disposition']
    assert '\r' not in disposition and '\n' not in disposition
    assert '../' not in disposition and 'folder/' not in disposition
    assert 'filename*=UTF-8\'\'%C3%A9vil%22X-Injected%3A%20yes.pdf' in disposition
    assert 'x-injected' not in response.headers


@pytest.mark.parametrize('status', ['draft', 'submitted', 'in_review', 'returned', 'accepted', 'refused', 'withdrawn'])
def test_inventory_download_and_binding_authorization_for_both_roles(scene, status):
    store, clients, _ = scene
    case = owned(scene)
    file, data = upload(clients['owner'], case.id)
    saved = store.get(case.id)
    saved.status = status
    store.put(saved, expected_version=saved.version)
    for name, client in clients.items():
        readable = name == 'owner' or name in {'reviewer', 'second'} and status in {'submitted', 'in_review', 'returned', 'accepted', 'refused'}
        for suffix in ('/files', f'/files/{file["id"]}'):
            response = client.get(f'/cases/{case.id}' + suffix)
            assert response.status_code == (200 if readable else 404), (name, status, suffix)
            assert response.headers['cache-control'] == 'no-store'
            if readable and suffix.endswith(file['id']):
                assert response.content == data
        version = store.get_version(case.id)
        response = post(client, case.id, payload(version, file_ref=file['id']))
        expected = 200 if name == 'owner' and status in {'draft', 'returned'} else 409 if name == 'owner' else 404
        assert response.status_code == expected, (name, status, response.text)
    store.delete(case.id)


def test_storage_rechecks_authority_even_after_route_authorization(ledger):
    store, create, _ = ledger
    case = create(owner_id='synthetic-owner', authority='calgary', status='submitted')
    file = store.put_file(case.id, 'SYNTHETIC.pdf', synthetic_pdf())
    reviewer = User(email='synthetic@example.test', name='Synthetic officer', role='reviewer', authority='edmonton')
    token = current_access.set(AccessContext(reviewer, 'read'))
    try:
        for read in (lambda: store.get_file(case.id, file['id']), lambda: store.list_files(case.id)):
            with pytest.raises(HTTPException) as error:
                read()
            assert error.value.status_code == 404
    finally:
        current_access.reset(token)
    store.delete(case.id)
