"""Tiny code database for lookup tests. Text is synthetic; it is not the NBC."""
from __future__ import annotations

import json
import sqlite3

from codedb import store


def build(path) -> None:
    con = sqlite3.connect(path)
    con.executescript(store.SCHEMA)
    con.execute("INSERT INTO docs VALUES ('NBC-AE','NBC(AE) 2023 p2','code',1,'','','')")

    def prov(division, pid, level, parent=None):
        con.execute(
            'INSERT INTO provisions (doc, division, id, level, parent_id, text, text_raw, '
            'pdf_page, pdf_page_end, sort_key) VALUES (?,?,?,?,?,?,?,?,?,?)',
            ('NBC-AE', division, pid, level, parent, 'synthetic fixture', 'synthetic fixture', 1, 1, pid))

    def attr(pid, function, objective, seq=1, page=1, table='Table synthetic'):
        con.execute(
            'INSERT INTO attributions VALUES (?,?,?,?,?,?,?,?,?,?,?,?)',
            ('NBC-AE', table, pid, pid.split('(')[0], None, '[]', seq,
             f'[{function}-{objective}]', json.dumps([function]), json.dumps([objective]), None, page))

    def status(pid, name, root=None, how=None):
        con.execute('INSERT INTO attribution_status VALUES (?,?,?,?,?)',
                    ('NBC-AE', pid, name, root, how))

    def intent(pid, text, comparison, objective='OS9'):
        con.execute('INSERT INTO intents VALUES (?,?,?,?,?,?,?,?,?,?)',
                    ('NBC-2020-IS', 'NBC-AE', pid, 0, objective, '[]', '[]', json.dumps([text]), 1, 1))
        con.execute('INSERT INTO intent_comparison VALUES (?,?,?,?,?,?,?)',
                    ('NBC-2020-IS', 'NBC-AE', pid, int(comparison != 'provision_missing_in_ae'),
                     comparison, None, None))

    prov('B', '9.8.8.1.', 'article')
    prov('B', '9.8.8.1.(4)', 'sentence', '9.8.8.1.')
    prov('B', '9.8.8.1.(5)', 'sentence', '9.8.8.1.')
    attr('9.8.8.1.(4)', 'F30', 'OS3.1')
    status('9.8.8.1.(4)', 'direct')
    status('9.8.8.1.(5)', 'none', '9.8.8.1.(4)', 'exception_root')

    prov('B', '3.1.9.4.', 'article')
    for sentence in ('1', '2'):
        prov('B', f'3.1.9.4.({sentence})', 'sentence', '3.1.9.4.')
        status(f'3.1.9.4.({sentence})', 'none')
    # Codedb attribution_status for (4) is none. No root is stored here.
    prov('B', '3.1.9.4.(4)', 'sentence', '3.1.9.4.')
    status('3.1.9.4.(4)', 'none')
    prov('B', '3.1.9.4.(3)', 'sentence', '3.1.9.4.')
    attr('3.1.9.4.(3)', 'F03', 'OS1.2')
    status('3.1.9.4.(3)', 'direct')
    # (7) is a later-added sentence with its own table row. It is not copied onto (4).
    prov('B', '3.1.9.4.(7)', 'sentence', '3.1.9.4.')
    attr('3.1.9.4.(7)', 'F03', 'OS1.2')
    status('3.1.9.4.(7)', 'direct')

    prov('B', '3.1.9.1.', 'article')
    # Shaped like Table 3.10.1.1.: rows for sentences 1, 2, 3, 6 and 7.
    # Sentences (4) and (5) are the sprinkler and fire-damper exemptions and have no row.
    # Sibling pairs are fixture stand-ins so those sentences count as having a row.
    # They are not a claim about the printed brackets. Sentence (1) keeps the real control.
    for sentence in ('1', '2', '3', '4', '5', '6', '7'):
        prov('B', f'3.1.9.1.({sentence})', 'sentence', '3.1.9.1.')
    for seq, (function, objective) in enumerate(
            (('F03', 'OS1.2'), ('F04', 'OS1.3'), ('F03', 'OP1.2'), ('F04', 'OP1.3')), start=1):
        attr('3.1.9.1.(1)', function, objective, seq, page=323, table='Table 3.10.1.1.')
    status('3.1.9.1.(1)', 'direct')
    for sentence in ('2', '3', '6', '7'):
        attr(f'3.1.9.1.({sentence})', 'F03', 'OS1.2', table='Table synthetic')
        status(f'3.1.9.1.({sentence})', 'direct')
    # Codedb attribution_status for (4) is none. The (1) pairs are not copied onto it.
    status('3.1.9.1.(4)', 'none')
    status('3.1.9.1.(5)', 'none')

    prov('B', '9.25.5.1.', 'article')
    prov('B', '9.25.5.1.(1)', 'sentence', '9.25.5.1.')
    prov('B', '9.25.5.1.(2)', 'sentence', '9.25.5.1.')
    status('9.25.5.1.(1)', 'none', '9.25.5.1.(2)', 'exception_root')
    attr('9.25.5.1.(2)', 'F51', 'OH1.1')
    status('9.25.5.1.(2)', 'direct')

    prov('B', '3.1.8.1.', 'article')
    prov('B', '3.1.8.1.(1)', 'sentence', '3.1.8.1.')
    prov('B', '3.1.8.1.(1)(a)', 'clause', '3.1.8.1.(1)')
    prov('B', '3.1.8.1.(1)(b)', 'clause', '3.1.8.1.(1)')
    status('3.1.8.1.(1)', 'clause_level')
    attr('3.1.8.1.(1)(a)', 'F03', 'OS1.2', 1)
    attr('3.1.8.1.(1)(a)', 'F03', 'OP1.2', 2)
    status('3.1.8.1.(1)(a)', 'direct')
    status('3.1.8.1.(1)(b)', 'none', how='not_determined')

    prov('B', '3.1.4.2.', 'article')
    prov('B', '3.1.4.2.(1)', 'sentence', '3.1.4.2.')
    prov('B', '3.1.4.2.(1)(a)', 'clause', '3.1.4.2.(1)')
    attr('3.1.4.2.(1)', 'F02', 'OS1.2')
    status('3.1.4.2.(1)', 'direct')
    status('3.1.4.2.(1)(a)', 'inherits', '3.1.4.2.(1)', 'parent_sentence')

    # Shaped like 9.23.17.3.(1): codedb status none / not_determined, an intent, and an
    # article row that must not be copied onto the sentence.
    prov('B', '9.23.17.3.', 'article')
    prov('B', '9.23.17.3.(1)', 'sentence', '9.23.17.3.')
    attr('9.23.17.3.', 'F99', 'OS9.9')
    status('9.23.17.3.(1)', 'none', None, 'not_determined')
    intent('9.23.17.3.(1)', 'SYNTHETIC intent for an unattributed sentence', 'match', objective=None)

    prov('B', '8.1.1.1.', 'article')
    prov('B', '8.1.1.1.(1)', 'sentence', '8.1.1.1.')
    attr('8.1.1.1.', 'F10', 'OS3.7')
    status('8.1.1.1.(1)', 'none')

    prov('C', '2.3.1.1.', 'article')
    prov('C', '2.3.1.1.(3)', 'sentence', '2.3.1.1.')
    prov('C', '2.4.1.1.', 'article')
    prov('C', '2.4.1.1.(1)', 'sentence', '2.4.1.1.')
    prov('A', '1.2.1.1.', 'article')
    prov('A', '1.2.1.1.(1)', 'sentence', '1.2.1.1.')
    for pid in ('2.3.1.1.(3)', '2.4.1.1.(1)', '1.2.1.1.(1)'):
        intent(pid, 'SYNTHETIC farm intent must not attach', 'provision_missing_in_ae')

    prov('B', '9.1.1.1.', 'article')
    prov('B', '9.1.1.1.(1)', 'sentence', '9.1.1.1.')
    prov('B', '9.1.1.1.(2)', 'sentence', '9.1.1.1.')
    intent('9.1.1.1.(1)', 'SYNTHETIC missing intent must not attach', 'provision_missing_in_ae')
    intent('9.1.1.1.(2)', 'SYNTHETIC division B intent may attach', 'match')
    con.commit()
    con.close()
