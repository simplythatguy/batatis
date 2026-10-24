"""Offline tests for the labeler arm: no network (live.openai_json is monkeypatched)."""
from __future__ import annotations

import pytest

from evals_dev.identify_bench import live, verify_arm
from evals_dev.identify_bench.cases import Case

ARTS = {
    '9.10.15.5.': {'id': '9.10.15.5.', 'part': '9', 'title': 'Construction of Exposing Building Face',
                   'section': 'Fire Protection', 'subsection': 'Spatial Separations',
                   'text': 'Except as provided in Sentences (2) to (6), each exposing building face  shall have a '
                           'fire-resistance rating.'},
    '9.8.8.1.': {'id': '9.8.8.1.', 'part': '9', 'title': 'Required Guards', 'section': 'Stairs',
                 'subsection': 'Guards', 'text': 'Every surface to which access is provided shall be protected by a guard.'},
    '3.2.4.1.': {'id': '3.2.4.1.', 'part': '3', 'title': 'Fire Alarm', 'section': 'Building Fire Safety',
                 'subsection': 'Fire Alarm', 'text': 'A fire alarm system shall be installed.'},
}
POOL = list(ARTS)


def row(a, label, quote='', reason='r', confidence=0.9):
    return {'article': a, 'label': label, 'quote': quote, 'reason': reason, 'confidence': confidence}


def fake(payload, seen=None):
    def call(name, schema, system, user, **kw):
        if seen is not None:
            seen.append({'schema': schema, 'system': system, 'user': user, **kw})
        return payload(user) if callable(payload) else payload, {'input_tokens': 10, 'output_tokens': 5,
                                                                 'usd': 0.001, 'seconds': 1.0}
    return call


def test_schema_is_strict_and_enumerates_pool(monkeypatch):
    seen = []
    monkeypatch.setattr(live, 'openai_json', fake({'labels': [row(a, 'unlikely') for a in POOL]}, seen))
    res = verify_arm.label_pool('desc', POOL, arts=ARTS, effort='medium')
    s = seen[0]['schema']
    item = s['properties']['labels']['items']
    assert s['additionalProperties'] is False and item['additionalProperties'] is False
    assert set(item['required']) == set(item['properties'])
    assert item['properties']['article']['enum'] == POOL
    assert item['properties']['label']['enum'] == ['applies', 'check', 'unlikely']
    assert seen[0]['effort'] == 'medium' and seen[0]['model'] == 'gpt-6-luna'
    assert all(f'<article id="{a}">' in seen[0]['user'] for a in POOL)
    assert res.plain() == {a: 'unlikely' for a in POOL}
    assert res.counts['missing'] == res.counts['unknown'] == res.counts['duplicate'] == 0


def test_applies_with_bad_quote_is_downgraded_and_counted(monkeypatch):
    payload = {'labels': [
        row('9.10.15.5.', 'applies', 'each exposing building face shall have a fire-resistance rating'),  # whitespace ok
        row('9.8.8.1.', 'applies', 'every guard shall be 1070 mm high'),                                   # not in text
        row('3.2.4.1.', 'applies', ''),                                                                    # empty
    ]}
    monkeypatch.setattr(live, 'openai_json', fake(payload))
    res = verify_arm.label_pool('desc', POOL, arts=ARTS)
    assert res.plain() == {'9.10.15.5.': 'applies', '9.8.8.1.': 'check', '3.2.4.1.': 'check'}
    assert res.counts['quote_downgraded'] == 2
    assert res.labels['9.8.8.1.']['flag'] == 'quote_downgraded'
    assert res.labels['9.10.15.5.']['quote_ok'] is True


def test_missing_duplicate_unknown_ids(monkeypatch):
    payload = {'labels': [row('9.10.15.5.', 'unlikely'), row('9.10.15.5.', 'applies', 'x'),
                          row('1.1.1.1.', 'applies', 'x'), row('3.2.4.1.', 'unlikely')]}
    monkeypatch.setattr(live, 'openai_json', fake(payload))
    res = verify_arm.label_pool('desc', POOL, arts=ARTS)
    assert list(res.labels) == POOL
    assert res.counts['duplicate'] == 1 and res.counts['unknown'] == 1 and res.counts['missing'] == 1
    assert res.labels['9.10.15.5.']['label'] == 'unlikely'          # first row wins
    assert res.labels['9.8.8.1.'] == {**res.labels['9.8.8.1.'], 'label': 'check', 'flag': 'missing'}


def test_malformed_payload_counts_everything_missing(monkeypatch):
    monkeypatch.setattr(live, 'openai_json', fake({'labels': 'nope'}))
    res = verify_arm.label_pool('desc', POOL, arts=ARTS)
    assert res.counts['missing'] == 3 and set(res.plain().values()) == {'check'}


def test_unknown_input_ids_are_not_sent(monkeypatch):
    seen = []
    monkeypatch.setattr(live, 'openai_json', fake({'labels': []}, seen))
    res = verify_arm.label_pool('desc', POOL + ['9.99.99.99.'], arts=ARTS)
    assert '9.99.99.99.' not in seen[0]['user'] and res.counts['unknown_input'] == 1


def test_two_pass_only_rereads_non_applies_and_only_raises(monkeypatch):
    seen = []

    def payload(user):
        if len(seen) == 1:
            return {'labels': [row('9.10.15.5.', 'applies', 'shall have a fire-resistance rating'),
                               row('9.8.8.1.', 'check'), row('3.2.4.1.', 'unlikely')]}
        return {'labels': [row('9.8.8.1.', 'unlikely'),
                           row('3.2.4.1.', 'applies', 'A fire alarm system shall be installed.')]}
    monkeypatch.setattr(live, 'openai_json', fake(payload, seen))
    res = verify_arm.label_pool('desc', POOL, arts=ARTS, two_pass=True)
    assert len(seen) == 2 and '9.10.15.5.' not in seen[1]['user'] and seen[1]['system'] == verify_arm.SECOND_PASS
    assert res.plain() == {'9.10.15.5.': 'applies', '9.8.8.1.': 'check', '3.2.4.1.': 'applies'}
    assert res.counts['raised'] == 1 and res.usage['usd'] == pytest.approx(0.002)


def test_build_pool_is_deterministic_and_keeps_gold():
    case = Case('c1', 'dev', 'd', ('9.10.15.5.',), ('9.8.8.1.',))
    ranked = ['9.10.15.5.', '1.0.0.0.', '3.2.4.1.']
    p1 = verify_arm.build_pool(case, ranked=ranked, arts=ARTS)
    p2 = verify_arm.build_pool(case, ranked=list(ranked), arts=ARTS)
    assert p1 == p2 and sorted(p1) == sorted(POOL)
    small = verify_arm.build_pool(case, ranked=ranked, arts=ARTS, size=2)
    assert sorted(small) == ['9.10.15.5.', '9.8.8.1.']
    other = verify_arm.build_pool(Case('c2', 'dev', 'd', ('9.10.15.5.',), ('9.8.8.1.',)), ranked=ranked, arts=ARTS)
    assert sorted(other) == sorted(p1)
