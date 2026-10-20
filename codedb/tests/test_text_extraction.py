"""Source-backed regressions; copyrighted source data stays in ignored build/."""
import json

from codedb import store


def provision(pid):
    con = store.connect()
    try:
        return con.execute("SELECT text FROM provisions WHERE division='B' AND id=?", (pid,)).fetchone()[0]
    finally:
        con.close()


def test_justification_and_raised_units_in_9_25_5_1():
    text = provision('9.25.5.1.(1)')
    assert 'characteristic less than 0.1 L/(s×m²) at 75 Pa' in text
    assert '60 ng/(Pa×s×m²)' in text


def test_italic_boundaries_in_9_10_14_2():
    assert 'fire compartments by fire separations' in provision('9.10.14.2.(1)')
    assert 'exposing building face shall' in provision('9.10.14.2.(2)')


def test_liquid_water_hyphenation_in_intent():
    con = store.connect()
    try:
        row = con.execute("SELECT intents FROM intents WHERE provision_id='9.27.3.2.(1)' AND block_seq=0").fetchone()
        assert 'resistance to liquid-water transfer' in json.loads(row[0])[0]
    finally:
        con.close()
