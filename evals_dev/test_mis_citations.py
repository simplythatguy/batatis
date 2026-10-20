"""Mis-citation traps. The database assertions skip when codedb is not built."""
import re

import pytest

from evals_dev.traps.check import citations_in, cites, load_traps, violations

ARTICLE = re.compile(r'\b\d{1,2}\.\d{1,2}\.\d{1,2}\.\d{1,2}\.?')


def by_id(cid):
    return next(trap for trap in load_traps() if trap['id'] == cid)


def test_catalog_covers_the_named_traps():
    traps = {trap['id']: trap for trap in load_traps()}
    assert set(traps) == {
        'part9-travel-distance', 'sprinkler-requirement', 'not-an-exit', 'egress-dwelling-only',
        'group-c-sprinklered', 'spatial-separation-by-building-type', 'between-dwelling-units',
        'part9-floor-rating', 'stair-rise-run',
    }
    travel = traps['part9-travel-distance']
    assert [item['provision'] for item in travel['must_cite']] == ['9.9.8.2.(1)']
    assert {item['provision'] for item in travel['must_not_cite']} == {'3.4.2.4.', '9.9.8.1.'}
    sprinkler = traps['sprinkler-requirement']
    assert [item['provision'] for item in sprinkler['must_cite']] == ['3.2.2.18.(1)']
    assert {item['provision'] for item in sprinkler['must_not_cite']} == {'3.2.5.12.', '9.10.1.3.(8)'}
    exits = traps['not-an-exit']
    assert {item['provision'] for item in exits['must_not_cite']} == {'9.9.4.4.', '3.3.1.5.', '9.9.7.4.'}
    assert {item['provision'] for item in traps['egress-dwelling-only']['must_not_cite']} == {'9.9.9.1.'}
    group_c = traps['group-c-sprinklered']
    assert [item['provision'] for item in group_c['must_cite']] == ['3.2.2.51.']
    assert [item['provision'] for item in group_c['must_not_cite']] == ['3.2.2.50.']
    space = traps['spatial-separation-by-building-type']
    assert [item['provision'] for item in space['must_cite']] == ['9.10.15.1.(1)']
    assert [item['provision'] for item in space['must_not_cite']] == ['9.10.14.']
    units = traps['between-dwelling-units']
    assert [item['provision'] for item in units['must_cite']] == ['9.10.9.16.']
    assert [item['provision'] for item in units['must_not_cite']] == ['9.10.9.15.']
    assert [item['provision'] for item in traps['part9-floor-rating']['must_cite']] == ['9.10.8.1.']
    assert [item['provision'] for item in traps['stair-rise-run']['must_cite']] == ['Table 9.8.4.1.', 'Table 9.8.4.2.']
    for trap in traps.values():
        assert not ARTICLE.search(trap['description'])
        cited = {item['provision'] for item in trap['must_cite']}
        banned = {item['provision'] for item in trap['must_not_cite']}
        assert cited.isdisjoint(banned)


def test_identify_ranking_and_citation_text_use_the_same_match():
    travel = by_id('part9-travel-distance')
    assert violations(travel, ['9.9.8.2.(1)']) == []
    assert violations(travel, ['9.9.8.2']) == []
    assert [item['provision'] for item in violations(travel, ['3.4.2.4', '9.9.8.2.(1)'])] == ['3.4.2.4.']
    assert [item['provision'] for item in violations(travel, ['9.9.8.1.(2)'])] == ['9.9.8.1.']
    assert violations(travel, ['9.9.8.10.(1)']) == []
    space = by_id('spatial-separation-by-building-type')
    assert [item['provision'] for item in violations(space, ['9.10.14.2.(2)'])] == ['9.10.14.']
    assert violations(space, ['9.10.15.4.(1)']) == []
    sprinkler = by_id('sprinkler-requirement')
    assert violations(sprinkler, ['3.2.2.18.(1)']) == []
    assert violations(sprinkler, ['9.10.1.3.(1)']) == []
    assert [item['provision'] for item in violations(sprinkler, ['9.10.1.3.(8)'])] == ['9.10.1.3.(8)']
    text = 'Part 9 travel distance is Sentence 3.4.2.4.(1), not the house sentence.'
    assert [item['provision'] for item in violations(travel, citations_in(text))] == ['3.4.2.4.']
    assert cites('Table 9.8.4.1.', 'Table 9.8.4.1')
    assert not cites('Table 9.8.4.1.', 'Table 9.8.4.2.')


def test_trap_ids_resolve_when_codedb_is_present():
    from codedb import store
    try:
        con = store.connect()
    except FileNotFoundError:
        pytest.skip('no codedb')
    missing = []
    with con:
        for trap in load_traps():
            for ref in trap['must_cite'] + trap['must_not_cite']:
                provision = ref['provision']
                if provision.lower().startswith('table'):
                    table_id = provision if provision.startswith('Table') else 'Table ' + provision
                    row = con.execute(
                        "SELECT 1 FROM code_tables WHERE doc='NBC-AE' AND table_id=?",
                        (table_id,)).fetchone()
                else:
                    row = con.execute(
                        "SELECT title FROM provisions WHERE doc='NBC-AE' AND division='B' AND id=?",
                        (provision,)).fetchone()
                if row is None:
                    missing.append(provision)
        reserved = con.execute(
            "SELECT title FROM provisions WHERE doc='NBC-AE' AND division='B' AND id='3.2.2.50.'"
        ).fetchone()
    assert missing == []
    assert reserved is not None and 'reserved' in reserved['title'].casefold()
