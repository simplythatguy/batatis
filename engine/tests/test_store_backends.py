"""File backend always. Postgres only when TEST_DATABASE_URL is set."""
import os
import threading
import uuid

import pytest

from engine.models import Case, Fact, Source
from engine.store import CaseStore, FileTooLarge, VersionConflict, open_store
from engine.uploads import PDF_MAX_BYTES

SRC = Source(type='user_text', ref='msg_1', quote='three storey rowhouse')


def _fact(field):
    return Fact(field=field, value=1, kind='pointed', source=SRC)


def _exercise(store, created: list | None = None):
    case = store.put(Case(title='Rowhouse'))
    if created is not None:
        created.append(case.id)
    version = store.get_version(case.id)
    assert version == 1
    case.title = 'Changed'
    store.put(case, expected_version=version)
    assert store.get_version(case.id) == 2
    with pytest.raises(VersionConflict):
        store.put(case, expected_version=version)
    stored = store.add_fact(case.id, _fact('storeys'))
    assert stored.facts[0].field == 'storeys'
    saved = store.put_file(case.id, 'note.pdf', b'%PDF-1.4 hello')
    assert saved['size'] == len(b'%PDF-1.4 hello')
    assert store.get_file(case.id, saved['id'])['data'] == b'%PDF-1.4 hello'
    with pytest.raises(FileTooLarge):
        store.put_file(case.id, 'big.pdf', b'x' * (PDF_MAX_BYTES + 1))
    store.put(Case(id=case.id, title='upserted'))
    assert store.get(case.id).title == 'upserted'
    assert store.get_version(case.id) >= 2


def test_file_backend_roundtrip_conflict_and_bytes(tmp_path):
    _exercise(CaseStore(tmp_path / 'cases.sqlite'))


def test_add_fact_retries_lost_updates(tmp_path):
    store = CaseStore(tmp_path / 'cases.sqlite')
    case = store.put(Case())
    barrier = threading.Barrier(2)

    def worker(name):
        barrier.wait()
        store.add_fact(case.id, _fact(name))

    threads = [threading.Thread(target=worker, args=(name,)) for name in ('a', 'b')]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert {fact.field for fact in store.get(case.id).facts} == {'a', 'b'}


def test_open_store_defaults_to_file(monkeypatch, tmp_path):
    monkeypatch.delenv('BATATIS_STORE', raising=False)
    monkeypatch.delenv('VERCEL', raising=False)
    monkeypatch.setenv('BATATIS_CASES', str(tmp_path / 'cases.sqlite'))
    store = open_store()
    assert isinstance(store, CaseStore)


def test_cases_older_than_seven_days_are_purged_with_files(tmp_path):
    from engine.tests.test_retention import assert_retention
    assert_retention(CaseStore(tmp_path / 'cases.sqlite'))


def test_vercel_refuses_an_unset_file_store(monkeypatch, tmp_path):
    monkeypatch.setenv('VERCEL', '1')
    monkeypatch.delenv('BATATIS_STORE', raising=False)
    monkeypatch.setenv('BATATIS_CASES', str(tmp_path / 'cases.sqlite'))
    with pytest.raises(RuntimeError, match='BATATIS_STORE is not postgres'):
        open_store()


def test_postgres_backend(monkeypatch):
    url = os.environ.get('TEST_DATABASE_URL')
    if not url:
        pytest.skip('TEST_DATABASE_URL is not set')
    monkeypatch.setenv('DATABASE_URL', url)
    from engine.store_postgres import PostgresCaseStore
    store = PostgresCaseStore(url)
    created = []
    try:
        first = store.put(Case(title='pg'))
        created.append(first.id)
        _exercise(store, created)
        shared = 'race_' + uuid.uuid4().hex
        created.append(shared)
        errors = []
        barrier = threading.Barrier(2)

        def worker(title):
            try:
                barrier.wait()
                store.put(Case(id=shared, title=title))
            except Exception as exc:
                errors.append(exc)

        threads = [threading.Thread(target=worker, args=(title,)) for title in ('left', 'right')]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        assert errors == []
        assert store.get_version(shared) == 2
        from engine.tests.test_retention import assert_retention
        assert_retention(store, created)
    finally:
        with store._conn() as con:
            for case_id in created:
                con.execute('DELETE FROM case_files WHERE case_id=%s', (case_id,))
                con.execute('DELETE FROM cases WHERE id=%s', (case_id,))
