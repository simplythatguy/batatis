"""Farm-building intent rows share bare ids with Division C. They must not attach."""
import sqlite3

import pytest

from codedb import lookup
from codedb.tests.mini_db import build


@pytest.fixture
def db(tmp_path):
    path = tmp_path / 'mini.sqlite'
    build(path)
    return path


@pytest.mark.parametrize('pid,division', [
    ('2.3.1.1.(3)', 'C'),
    ('2.4.1.1.(1)', 'C'),
    ('1.2.1.1.(1)', 'A'),
])
def test_div_a_and_c_lookups_do_not_attach_bare_id_intents(db, pid, division):
    with sqlite3.connect(db) as con:
        stored = con.execute('SELECT intents FROM intents WHERE provision_id=?', (pid,)).fetchone()
    assert stored and 'SYNTHETIC farm intent must not attach' in stored[0]
    record = lookup(pid, division=division, db_path=db)
    assert record['division'] == division
    assert record['intents'] == []
    assert record['intent_comparison'] == []


def test_bare_id_lookup_of_a_division_c_sentence_stays_unattached(db):
    record = lookup('2.3.1.1.(3)', db_path=db)
    assert record['division'] == 'C'
    assert record['intents'] == []
    assert 'farm' not in record['text']


def test_provision_missing_in_ae_is_dropped_even_on_division_b(db):
    missing = lookup('9.1.1.1.(1)', division='B', db_path=db)
    assert missing['intents'] == []
    assert missing['intent_comparison'] == []
    kept = lookup('9.1.1.1.(2)', division='B', db_path=db)
    assert kept['intents'] and kept['intents'][0]['intents'] == ['SYNTHETIC division B intent may attach']
    assert kept['intent_comparison'][0]['status'] == 'match'
