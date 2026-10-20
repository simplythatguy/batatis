"""Literal receipts checked with tools/codesearch.py page NBC-AE (1-based PDF pages)."""
import pytest
from codedb import AmbiguousProvisionError, children, lookup, search


def test_bedroom_egress_literal_source_receipt():
    r = lookup('9.9.10.1.(1)')
    assert (r['division'],r['pdf_page'],r['volume']) == ('B',873,2)
    assert r['article_title'] == 'Egress Windows or Doors for Bedrooms'
    assert [(a['bracket'],a['pdf_page']) for a in r['attributions']] == [('[F10-OS3.7]',1126)]


def test_part_three_and_unattributed_exception():
    # Body p.179; Table 3.10.1.1 at p.326. No attribution exists for sentence (1).
    root = lookup('3.2.2.20.(2)',division='B')
    assert root['pdf_page'] == 179
    assert ('[F02-OS1.2]',326) in [(a['bracket'],a['pdf_page']) for a in root['attributions']]
    r = lookup('3.2.2.20.(1)',division='B')
    assert r['attributions'] == []
    assert r['attribution_status']['status'] == 'none'


def test_division_c_documentation():
    r = lookup('2.3.1.1.',division='C')
    assert (r['title'],r['pdf_page']) == ('Documentation',739)
    assert [c['id'] for c in r['children']] == [f'2.3.1.1.({i})' for i in range(1,7)]
    assert 'analytical methods' in r['text']
    assert r['attributions'] == []
    assert r['intents'] == []


def test_ambiguity_is_not_silently_division_b():
    with pytest.raises(AmbiguousProvisionError,match='divisions A, B, C'):
        lookup('1.2.1.1.(1)')
    assert lookup('1.2.1.1.(1)',division='A')['pdf_page'] == 38


def test_children_and_search():
    assert len(children('9.9.10.1.')) == 6
    rows = search('egress bedrooms',limit=10)
    assert any(r['id']=='9.9.10.1.' for r in rows)
    assert rows == sorted(rows,key=lambda r:r['rank'])
    assert search('') == []
    assert lookup('9.99.99.99.') is None


def test_exception_root_is_same_article_requirement():
    status = lookup('3.2.2.20.(1)',division='B')['attribution_status']
    assert (status['status'],status['root_provision'],status['root_method']) == (
        'none','3.2.2.20.(2)','referenced_sentence_same_article')


def test_table_and_figure_text_is_separate_from_sentences():
    assert 'Notes to Table' not in lookup('4.1.3.4.(6)')['text_raw']
    r = lookup('4.1.7.6.(11)')
    assert r['pdf_page_end']==459
    assert '\nFigure ' not in r['text_raw']


def test_definitions_literal_source_receipts():
    # Div A definition text independently checked on PDF p.80 and p.69.
    from contextlib import closing
    from codedb.store import connect
    with closing(connect()) as con:
        fs=con.execute("select * from definitions where doc='NBC-AE' and code='F10'").fetchone()
        obj=con.execute("select * from definitions where doc='NBC-AE' and code='OS3.7'").fetchone()
    assert (fs['pdf_page'],fs['text'])==(80,'To facilitate the timely movement of persons to a safe place in an emergency.')
    assert (obj['pdf_page'],obj['parent'])==(69,'OS3')
    assert 'delayed in or impeded from moving to a safe place' in obj['text']
