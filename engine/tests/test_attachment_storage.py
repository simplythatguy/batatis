"""Attachment proof and legacy abstention on SQLite and an explicitly configured test PG."""
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from engine.api import create_app
from engine.models import Case, Source
from engine.store import InvalidAttachment
from engine.tests.case_builder_fixtures import fact
from engine.tests.test_privacy_interleavings import raw_rows, store  # noqa: F401 - backend fixture


def attachment(reference):
    return fact('evidence.test.file_ref', reference,
                source=Source(type='file', ref=reference, quote='SYNTHETIC storage-only input'))


def test_confirmed_attachment_must_belong_to_the_same_case_transaction(store):
    first, second = store.put(Case()), store.put(Case())
    version = store.get_version(first.id)
    with pytest.raises(InvalidAttachment):
        store.add_fact(first.id, attachment('SYNTHETIC absent'))
    assert store.get_version(first.id) == version and store.get(first.id).facts == []
    saved = store.put_file(first.id, 'SYNTHETIC.pdf', b'%PDF-1.4 SYNTHETIC storage bytes')
    assert store.add_fact(first.id, attachment(saved['id'])).facts[-1].status == 'confirmed'
    with pytest.raises(InvalidAttachment):
        store.add_fact(second.id, attachment(saved['id']))
    assert store.get(second.id).facts == []
    mismatched = attachment(saved['id']).model_copy(update={'value': 'different'})
    with pytest.raises(InvalidAttachment):
        store.add_fact(first.id, mismatched)
    assert store.get(first.id).facts[-1].value == saved['id']


def test_legacy_attachment_is_a_listing_until_owned_bytes_exist(store):
    source = store.put(Case())
    saved = store.put_file(source.id, 'SYNTHETIC.pdf', b'%PDF-1.4 SYNTHETIC storage bytes')
    legacy = store.put(Case(facts=[attachment(saved['id'])]))
    loaded, version = store.get_snapshot(legacy.id)
    assert loaded.facts[0].value == saved['id'] and loaded.facts[0].status == 'unconfirmed'
    assert version == store.get_version(legacy.id)
    client = TestClient(create_app(store, object()))
    bad = client.post(f'/cases/{legacy.id}/facts', json=attachment(saved['id']).model_dump())
    assert bad.status_code == 422
    own = store.put_file(legacy.id, 'SYNTHETIC-own.pdf', b'%PDF-1.4 SYNTHETIC own storage bytes')
    valid = client.post(f'/cases/{legacy.id}/facts', json=attachment(own['id']).model_dump())
    assert valid.status_code == 200
    assert store.get(legacy.id).facts[-1].status == 'confirmed'


@pytest.mark.parametrize('ending', ['delete', 'expiry'])
def test_attachment_write_cannot_resurrect_a_deleted_or_expired_case(store, monkeypatch, ending):
    case = store.put(Case())
    saved = store.put_file(case.id, 'SYNTHETIC.pdf', b'%PDF-1.4 SYNTHETIC storage bytes')
    if ending == 'delete':
        assert store.delete(case.id)
    else:
        future = (datetime.now(timezone.utc) + timedelta(days=1)).isoformat()
        monkeypatch.setattr('engine.store.retention_cutoff', lambda: future)
        monkeypatch.setattr('engine.store_postgres.retention_cutoff', lambda: future)
    client = TestClient(create_app(store, object()))
    assert client.post(f'/cases/{case.id}/facts', json=attachment(saved['id']).model_dump()).status_code == 404
    assert raw_rows(store, case.id) == (None, None, 0)
