import json

from evals_dev.public_benchmark import families as f


def test_every_case_has_a_family_from_the_index():
    cases = json.loads(f.CASES.read_text())
    assert len(cases) == 53
    assert all(c['family'] == f.family_of(c['id']) for c in cases)


def test_revision_pairs_share_a_family_and_are_excluded_together():
    case = {'id': 'standata-nbc2023-variance-23-bcv-010r1', 'family': 'standata-nbc2023-variance-23-bcv-010'}
    ex = f.excluded_precedents(case)
    assert 'standata-nbc2023-variance-23-bcv-010' in ex and case['id'] in ex


def test_singleton_excludes_only_itself():
    case = {'id': 'standata-nbc2023-variance-23-bcv-001'}
    assert f.excluded_precedents(case) == ['standata-nbc2023-variance-23-bcv-001']
