"""Intent-supplement attribution brackets survive PDF letter spacing.

Source receipt: NBC 2020 Intent Statements PDF p.608, Provision 3.4.2.1.(1), Objective OS3,
attribution extracted as "[ F 1 0 ,F 1 2 ,F 0 5 ,F 0 6 - O S 3 . 7 ]".
"""
import pytest

from codedb import lookup, store
from codedb.intents import Block, parse_attribution_bracket


@pytest.mark.parametrize('raw,expected', [
    ('[ F 1 0 ,F 1 2 ,F 0 5 ,F 0 6 - O S 3 . 7 ]', '[F10,F12,F05,F06-OS3.7]'),
    ('[ F 5 0 ,F 5 1 ,F 5 2 , F54, F63-OH1.2, OH1.3]', '[F50,F51,F52,F54,F63-OH1.2,OH1.3]'),
    ('[F20, F80-OH 4]', '[F20,F80-OH4]'),
    ('[F6 3-OS2.3]', '[F63-OS2.3]'),
    ('[F02, F03, F04-OP1.2, OP1 .3]', '[F02,F03,F04-OP1.2,OP1.3]'),
    ('[F01, F02, F03-O P1.1, OP1.2]', '[F01,F02,F03-OP1.1,OP1.2]'),
    ('[F10-OS3.7]', '[F10-OS3.7]'),
])
def test_spaced_brackets_parse(raw, expected):
    assert parse_attribution_bracket(raw).raw == expected


def test_quoted_code_words_are_not_attributions_and_stay_in_the_note():
    b = Block('OP1', ['3.2.2.74.(2)(a) [F03-OP1.2] Applies to portion of Code text: "... [ noncombustible] floor'])
    assert [x.raw for x in b.brackets] == ['[F03-OP1.2]']
    assert b.attribution_notes == ['3.2.2.74.(2)(a)  Applies to portion of Code text: "... [ noncombustible] floor']


def test_bracket_continued_on_next_line():
    b = Block('OH1', ['6.2.1.1.(1)(h) [ F 5 0 ,F 5 1 ,F 5 2 , F54, F63-OH1.2, OH1.3]'])
    assert b.brackets[0].pairs[0] == ('F50', 'OH1.2') and len(b.brackets[0].pairs) == 10
    assert b.attribution_notes == ['6.2.1.1.(1)(h)']


def test_3_4_2_1_1_os3_intent_has_its_bracket():
    r = lookup('3.4.2.1.(1)', division='B')
    os3 = [i for i in r['intents'] if i['objective'] == 'OS3']
    assert os3 and os3[0]['pdf_page'] == 608
    assert os3[0]['brackets'] == ['[F10,F12,F05,F06-OS3.7]']


def test_no_objective_block_has_empty_brackets():
    con = store.connect()
    try:
        empty = con.execute("SELECT provision_id, objective FROM intents "
                            "WHERE objective IS NOT NULL AND brackets='[]'").fetchall()
    finally:
        con.close()
    assert [tuple(r) for r in empty] == []
