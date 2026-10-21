"""Frozen folds: seeded, stratified, hash-checked, no case in two folds, growth never moves a case."""
import copy
import json
from collections import Counter

import pytest

from evals_dev.folds import SEED, Item, build, digest, extend, target_calibration, verify
from evals_dev.folds import core
from evals_dev.identify_bench import datasets

FOLDS = json.loads(datasets.FOLDS_FILE.read_text())


def repo_items():
    return [Item(c.id, c.dataset, c.stratum) for c in datasets.load_all(with_folds=False)]


def synthetic(n_part9=10, n_other=10, n_ask=4, prefix='syn'):
    items = []
    for kind, n in (('part9', n_part9), ('other', n_other), ('ask', n_ask)):
        items += [Item(f'{prefix}-{kind}-{i:03}', 'dev', kind) for i in range(n)]
    return items


# ---- the committed file ----------------------------------------------------------------------------------

def test_committed_folds_file_verifies_against_the_repo_cases():
    assert verify(FOLDS, repo_items()) == [], 'run `python -m evals_dev.folds extend` after adding cases'


def test_seed_and_share_are_the_disclosed_ones():
    assert FOLDS['seed'] == SEED == 20261021
    assert FOLDS['calibration_share'] == 0.3
    assert FOLDS['sha256'] == digest(FOLDS)


def test_every_case_is_in_exactly_one_fold():
    items = repo_items()
    sets = {f: {cid for cid, row in FOLDS['cases'].items() if row['fold'] == f} for f in core.FOLDS}
    names = list(sets)
    for i, a in enumerate(names):
        for b in names[i + 1:]:
            assert not (sets[a] & sets[b]), f'{a} and {b} overlap'
    assert set().union(*sets.values()) == {i.id for i in items}
    assert sum(len(s) for s in sets.values()) == len(items)


def test_selection_datasets_are_selection_and_development_is_split():
    for cid, row in FOLDS['cases'].items():
        if row['dataset'] in ('public53', 'idr26'):
            assert row['fold'] == 'selection', cid
        else:
            assert row['fold'] in ('calibration', 'validation'), cid


def test_each_development_stratum_holds_the_calibration_share():
    strata = Counter(row['stratum'] for row in FOLDS['cases'].values() if row['dataset'] == 'dev')
    for stratum, n in strata.items():
        got = sum(1 for row in FOLDS['cases'].values()
                  if row['dataset'] == 'dev' and row['stratum'] == stratum and row['fold'] == 'calibration')
        assert got == target_calibration(n), stratum
    assert {'part9', 'other', 'ask', 'redirect'} <= set(strata)


def test_part_groups_are_the_documented_ones():
    groups = {(r['dataset'], r['stratum']) for r in FOLDS['cases'].values()}
    assert ('public53', 'mixed') in groups and ('public53', 'part9') in groups
    assert not any(g[0] != 'dev' and g[1] in ('ask', 'redirect') for g in groups)


# ---- the rule ---------------------------------------------------------------------------------------------

def test_build_is_deterministic_and_seeded():
    items = synthetic()
    assert build(items) == build(list(reversed(items)))
    assert build(items)['cases'] != build(items, seed=1)['cases']


def test_assignment_does_not_depend_on_the_other_strata():
    a = build(synthetic(n_other=10))
    b = build(synthetic(n_other=14))
    part9 = lambda doc: {k: v['fold'] for k, v in doc['cases'].items() if v['stratum'] == 'part9'}
    assert part9(a) == part9(b)


def test_extend_never_moves_an_existing_case_and_keeps_the_share_exact():
    doc = build(synthetic(8, 8, 3))
    before = {cid: row['fold'] for cid, row in doc['cases'].items()}
    items = synthetic(8, 8, 3) + synthetic(13, 0, 0, prefix='new') + [Item('new-extra-1', 'dev', 'other')]
    out = extend(doc, items)
    assert out is not doc
    for cid, fold in before.items():
        assert out['cases'][cid]['fold'] == fold and out['cases'][cid]['generation'] == 0
    assert all(out['cases'][c]['generation'] == 1 for c in out['cases'] if c.startswith('new'))
    assert verify(out, items) == []
    part9 = [r for r in out['cases'].values() if r['stratum'] == 'part9']
    assert sum(r['fold'] == 'calibration' for r in part9) == target_calibration(len(part9)) == 6
    assert extend(out, items) is out                         # nothing new: unchanged


def test_extend_in_small_steps_equals_the_share_every_time():
    doc = build(synthetic(5, 0, 0))
    items = synthetic(5, 0, 0)
    for step in range(1, 12):
        items = items + [Item(f'grow-{step:02}', 'dev', 'part9')]
        doc = extend(doc, items)
        n = sum(1 for r in doc['cases'].values() if r['stratum'] == 'part9')
        cal = sum(1 for r in doc['cases'].values() if r['stratum'] == 'part9' and r['fold'] == 'calibration')
        assert cal == target_calibration(n)
    assert verify(doc, items) == []


# ---- tamper evidence --------------------------------------------------------------------------------------

def test_editing_a_fold_breaks_the_hash():
    items = synthetic()
    doc = build(items)
    bad = copy.deepcopy(doc)
    cid = next(c for c, r in bad['cases'].items() if r['fold'] == 'validation')
    bad['cases'][cid]['fold'] = 'calibration'
    assert any('sha256' in p for p in verify(bad, items))


def test_editing_a_fold_and_rehashing_still_fails_the_seeded_rule():
    items = synthetic()
    bad = copy.deepcopy(build(items))
    cid = next(c for c, r in bad['cases'].items() if r['fold'] == 'validation' and r['stratum'] == 'part9')
    bad['cases'][cid]['fold'] = 'calibration'
    bad['sha256'] = digest(bad)
    assert any('seeded rule' in p for p in verify(bad, items))


def test_a_new_case_without_a_fold_is_reported():
    doc = build(synthetic())
    problems = verify(doc, synthetic() + [Item('late-001', 'dev', 'part9')])
    assert any('late-001' in p and 'no fold' in p for p in problems)


def test_a_changed_stratum_or_removed_case_is_reported():
    items = synthetic()
    doc = build(items)
    moved = [Item(i.id, i.dataset, 'other' if i.id == items[0].id else i.stratum) for i in items]
    assert any('stratum changed' in p for p in verify(doc, moved))
    assert any('no longer exists' in p for p in verify(doc, items[1:]))


def test_duplicate_ids_are_refused():
    with pytest.raises(ValueError):
        build([Item('a', 'dev', 'part9'), Item('a', 'idr26', 'part9')])
