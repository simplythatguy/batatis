"""Section C rows equal the attribution table rows in the code database.

Expected literals were read from codedb (Table 9.38.1.1., NBC(AE) 2023 p2) on 2026-10-20; each test also
re-derives the pairs straight from the attributions table so the row cannot drift from the source.
"""
import json
from contextlib import closing

import pytest

from codedb import store
from engine.codes import Codes
from engine.models import INTENT_LABEL
from engine.section_c import section_c_rows


@pytest.fixture(scope='module')
def codes():
    return Codes()


def table_pairs(codes, pid):
    with closing(store.connect(codes.db_path)) as con:
        rows = con.execute("SELECT fs, objectives FROM attributions WHERE doc='NBC-AE' AND "
                           "(provision_id=? OR provision_id LIKE ?)", (pid, pid + '(%')).fetchall()
    return sorted((f, o) for r in rows for f in json.loads(r['fs']) for o in json.loads(r['objectives']))


@pytest.mark.parametrize('pid,pairs,page', [
    ('9.10.11.2.(2)', [('F03', 'OP3.1'), ('F03', 'OS1.2')], 1128),
    ('9.10.15.5.(8)', [('F03', 'OP3.1')], 1130),
    ('9.10.13.13.(1)', [('F03', 'OP1.2'), ('F03', 'OS1.2')], 1129),
])
def test_most_varied_part9_sentences(codes, pid, pairs, page):
    [row] = section_c_rows([pid], codes)
    assert row.attribution_status == 'direct'
    got = sorted((p.function, p.objective) for p in row.pairs)
    assert got == pairs == table_pairs(codes, pid)
    assert {p.table for p in row.pairs} == {'Table 9.38.1.1.'} and {p.pdf_page for p in row.pairs} == {page}
    assert row.citation == codes.provision(pid)['citation']
    assert row.citation.startswith('NBC(AE) 2023 p2, Div B, Sentence ' + pid)
    assert all(p.function_text and p.objective_text for p in row.pairs)
    assert row.intents and all(i.label == INTENT_LABEL for i in row.intents)
    assert row.intent_comparison == 'match' and row.differs is False


def test_article_without_table_row_says_so(codes):
    rows = section_c_rows(['9.10.14.2.'], codes)
    assert [r.provision_id for r in rows] == ['9.10.14.2.(1)', '9.10.14.2.(2)', '9.10.14.2.(3)']
    for r in rows:
        assert r.attribution_status == 'no row in the attribution table'
        assert r.pairs == [] and table_pairs(codes, r.provision_id) == []


def test_clause_inherits_its_sentence_row(codes):
    [row] = section_c_rows(['3.1.4.2.(1)(a)'], codes)
    assert row.attribution_status == 'inherited from parent'
    assert row.attributed_via == '3.1.4.2.(1)'
    assert sorted((p.function, p.objective) for p in row.pairs) == table_pairs(codes, '3.1.4.2.(1)')


def test_differs_flag_comes_from_intent_comparison(codes):
    [row] = section_c_rows(['9.32.1.3.(2)'], codes)
    assert row.differs is True and row.intent_comparison == 'differs'
    assert '[F01-OS1.1]' in row.only_in_ae


def test_unknown_provision_is_an_error(codes):
    with pytest.raises(KeyError):
        section_c_rows(['9.99.99.99.(1)'], codes)
