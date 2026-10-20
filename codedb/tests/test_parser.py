import pytest
from codedb import ids
from codedb.provisions import TreeParser


def test_table_cells_do_not_become_sentence_text():
    p=TreeParser('B',9,set())
    p.feed([(1,t) for t in ['Section 9.1. Scope','9.1.1. General','9.1.1.1. Application',
        '1) This sentence introduces a table.','Table 9.1.1.1.','Some numeric cells 123 456',
        'Notes to Table 9.1.1.1.:','(1) A table footnote.','2) This is the next sentence.']])
    first=p.nodes[ids.parse('9.1.1.1.(1)')]
    assert first.text=='1) This sentence introduces a table.'
    assert p.nodes[ids.parse('9.1.1.1.(2)')].text=='2) This is the next sentence.'


@pytest.mark.parametrize('bad',['9.9.10.1. rubbish','9.9.10.1.(1)(a)tail','9.9.(1)','0.2.3.4.'])
def test_identifier_parser_rejects_partial_matches(bad):
    with pytest.raises(ValueError): ids.parse(bad)


def test_identifier_normalizes_spaces():
    assert ids.canon('9.9.10.1 (1) (a) (ii)')=='9.9.10.1.(1)(a)(ii)'
