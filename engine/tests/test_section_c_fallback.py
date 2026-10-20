"""Section C inherits clause, then sentence, then article rows, and does not invent pairs."""
import pytest

from codedb.tests.mini_db import build
from engine.codes import Codes
from engine.section_c import section_c_rows


@pytest.fixture
def codes(tmp_path):
    path = tmp_path / 'mini.sqlite'
    build(path)
    return Codes(path)


@pytest.mark.parametrize('pid,root', [
    ('9.8.8.1.(5)', '9.8.8.1.(4)'),
    ('3.1.9.4.(1)', None),
    ('3.1.9.4.(2)', None),
    ('3.1.9.4.(4)', None),
    ('3.1.9.1.(4)', '3.1.9.1.(1)'),
    ('9.25.5.1.(1)', '9.25.5.1.(2)'),
])
def test_sentence_without_an_article_row_stays_a_gap(codes, pid, root):
    [row] = section_c_rows([pid], codes)
    assert row.pairs == []
    assert row.attribution_status == 'no row in the attribution table'
    assert row.attributed_via is None
    assert row.related_root == root
    assert 'compli' not in row.citation.casefold()


def test_sentence_attributed_only_at_clause_a_inherits_that_clause(codes):
    [row] = section_c_rows(['3.1.8.1.(1)'], codes)
    assert row.attribution_status == 'inherited from parent'
    assert row.attributed_via == '3.1.8.1.(1)(a)'
    assert sorted((pair.function, pair.objective) for pair in row.pairs) == [('F03', 'OP1.2'), ('F03', 'OS1.2')]


def test_clause_without_rows_does_not_take_a_sibling_clause(codes):
    [row] = section_c_rows(['3.1.8.1.(1)(b)'], codes)
    assert row.pairs == []
    assert row.attributed_via is None
    assert row.attribution_status == 'no row in the attribution table'


def test_clause_inherits_its_sentence_not_a_made_up_pair(codes):
    [row] = section_c_rows(['3.1.4.2.(1)(a)'], codes)
    assert row.attribution_status == 'inherited from parent'
    assert row.attributed_via == '3.1.4.2.(1)'
    assert [(pair.function, pair.objective) for pair in row.pairs] == [('F02', 'OS1.2')]


def test_sentence_falls_back_to_an_article_row(codes):
    [row] = section_c_rows(['8.1.1.1.(1)'], codes)
    assert row.attribution_status == 'inherited from parent'
    assert row.attributed_via == '8.1.1.1.'
    assert [(pair.function, pair.objective) for pair in row.pairs] == [('F10', 'OS3.7')]


def test_division_c_sentence_is_not_a_section_c_row(codes):
    with pytest.raises(KeyError):
        section_c_rows(['2.3.1.1.(3)'], codes)
