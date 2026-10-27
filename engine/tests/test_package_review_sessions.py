"""Session storage on both case-store backends, retention with the case, and the official-export round trip."""
from __future__ import annotations

import os
import uuid

import pytest

from engine.models import Case
from engine.models_review import InformationRequest, ReviewSession
from engine.review.sessions import SessionConflict, Sessions
from engine.store import CaseStore


def _session(package_id, version, case_id=None, created_at='2099-01-01T00:00:00+00:00'):
    return ReviewSession(package_id=package_id, case_id=case_id, authority='edmonton', version=version,
                         created_at=created_at, created_by_name='Reviewer', input_kind='upload',
                         information_request=InformationRequest(intro='i', items=[]))


def _exercise(store):
    sessions = Sessions(store)
    case = store.put(Case(title='sessions'))
    sessions.add(_session(case.id, 1, case.id))
    sessions.add(_session(case.id, 2, case.id))
    with pytest.raises(SessionConflict):
        sessions.add(_session(case.id, 2, case.id))
    assert [s.version for s in sessions.list(case.id)] == [1, 2]
    current, raw = sessions.get(case.id, 2)
    sessions.replace(current.model_copy(update={'created_by_name': 'Edited'}), raw)
    with pytest.raises(SessionConflict):
        sessions.replace(current, raw)   # stale write
    assert sessions.get(case.id, 2)[0].created_by_name == 'Edited'
    # Standalone packages follow creation-based retention; case packages go with the case.
    standalone = 'pkg_' + uuid.uuid4().hex[:8]
    sessions.add(_session(standalone, 1, None, created_at='2000-01-01T00:00:00+00:00'))
    sessions.record_closeout(case.id, '2026-10-21T00:00:00+00:00', '2026-10-22T00:00:00+00:00', 'Reviewer')
    with pytest.raises(SessionConflict):
        sessions.record_closeout(case.id, '2026-10-21T00:00:00+00:00', '2026-10-23T00:00:00+00:00', 'Reviewer')
    assert sessions.closeout(case.id)[2] == 'Reviewer'
    store.delete(case.id)
    assert sessions.list(case.id) == []
    assert sessions.closeout(case.id) is None
    assert sessions.list(standalone) == []


def test_sqlite_sessions(tmp_path):
    _exercise(CaseStore(tmp_path / 'cases.sqlite'))


def test_retention_purge_removes_reviews_without_a_review_request(tmp_path):
    """The 7-day promise covers package reviews: the cron purge drops them with their case."""
    import sqlite3
    from engine.retention import purge_now
    store = CaseStore(tmp_path / 'cases.sqlite')
    sessions = Sessions(store)
    old = store.put(Case(title='expired', created_at='2000-01-01T00:00:00+00:00'))
    from engine.tests.test_retention import _set_last_activity
    _set_last_activity(store, old.id, '2000-01-01T00:00:00+00:00')
    sessions.add(_session(old.id, 1, old.id))
    sessions.record_closeout(old.id, '2000-01-02T00:00:00+00:00', '2000-01-03T00:00:00+00:00', 'Reviewer')
    sessions.add(_session('pkg_old', 1, None, created_at='2000-01-01T00:00:00+00:00'))
    assert purge_now(store) == 1
    with sqlite3.connect(tmp_path / 'cases.sqlite') as con:   # read the tables directly: no sweep on read
        assert con.execute('SELECT COUNT(*) FROM package_review_sessions').fetchone()[0] == 0
        assert con.execute('SELECT COUNT(*) FROM package_review_closeouts').fetchone()[0] == 0


def test_postgres_sessions(monkeypatch):
    url = os.environ.get('TEST_DATABASE_URL')
    if not url:
        pytest.skip('TEST_DATABASE_URL is not set')
    monkeypatch.setenv('DATABASE_URL', url)
    from engine.store_postgres import PostgresCaseStore
    _exercise(PostgresCaseStore(url))


def test_official_export_reads_back_as_present_fields():
    """A flattened SCC form produced by Batatis's own export reads back field for field."""
    from engine.codes import Codes
    from engine.export import export_case
    from engine.export.sample import sample_case
    from engine.review.pdf_reader import read_pdf
    from engine.tests.package_review_fixtures import blank_form
    blank_form()   # skip without the form
    codes = Codes()
    result = export_case(sample_case(codes), codes=codes)
    read = read_pdf(result.pdf, 'export.pdf')
    assert read.role == 'scc_form_flattened' and read.form_version == result.field_map
    for placement in result.placements:
        state = read.fields[placement.field]
        assert state.status == 'present', placement.field
        assert placement.lines[0].strip()[:20] in state.value, (placement.field, state.value)
    assert read.text_pages, 'the appendix pages are read as text'
