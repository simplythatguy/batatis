"""File backend always. Postgres only when TEST_DATABASE_URL is set."""
import os
import threading

import pytest

from engine.models import Case, Fact, Source
from engine.store import CaseStore, FileTooLarge, VersionConflict, open_store
from engine.uploads import PDF_MAX_BYTES

SRC = Source(type='user_text', ref='msg_1', quote='three storey rowhouse')


def _fact(field):
    return Fact(field=field, value=1, kind='pointed', source=SRC)


def _exercise(store):
    case = store.put(Case(title='Rowhouse'))
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
    monkeypatch.setenv('BATATIS_CASES', str(tmp_path / 'cases.sqlite'))
    store = open_store()
    assert isinstance(store, CaseStore)


def test_postgres_backend(monkeypatch):
    url = os.environ.get('TEST_DATABASE_URL')
    if not url:
        pytest.skip('TEST_DATABASE_URL is not set')
    monkeypatch.setenv('DATABASE_URL', url)
    from engine.store_postgres import PostgresCaseStore
    store = PostgresCaseStore(url)
    case = store.put(Case(title='pg'))
    try:
        _exercise(store)
    finally:
        with store._conn() as con:
            con.execute('DELETE FROM case_files WHERE case_id=%s', (case.id,))
            con.execute('DELETE FROM cases WHERE id=%s', (case.id,))
