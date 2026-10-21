"""Stage 0: the harness reproduces the recorded Jev and BM25 numbers on public53 with no API call."""
import socket

import pytest

from evals_dev.identify_bench import cases as case_select
from evals_dev.identify_bench import datasets, stage0
from evals_dev.identify_bench.rows import RESULTS, RowStore


def test_the_published_numbers_reproduce_from_recorded_judgments_without_a_network(monkeypatch):
    def no_network(*a, **k):
        raise AssertionError('Stage 0 must not open a connection')
    monkeypatch.setattr(socket.socket, 'connect', no_network)
    result = stage0.run()
    assert result['n_cases'] == 53 and result['differences'] == []
    m = result['metrics']
    assert (round(m['R0-bm25-rec']['hit@1'] * 100), round(m['R0-bm25-rec']['hit@5'] * 100)) == (32, 66)
    assert (round(m['R5-jev-screen-rerank60-rec']['hit@1'] * 100), round(m['R5-jev-screen-rerank60-rec']['hit@5'] * 100)) == (64, 81)
    assert round(m['R5-jev-screen-rerank60-rec']['mrr'], 3) == 0.723 >= 0.70       # gate G1's MRR floor
    assert round(m['R6-bm25-jev-rerank60-rec']['mrr'], 3) == 0.728
    assert round(m['R4-jev-screen-rec']['recall@50'], 2) == 0.88


def test_a_wrong_number_is_reported(monkeypatch):
    result = stage0.run()
    bad = {a: dict(m) for a, m in result['metrics'].items()}
    bad['R0-bm25-rec']['hit@1'] = 0.40
    assert any('BM25' in p and 'hit@1' in p for p in stage0.check(bad))


def test_recorded_rows_are_marked_cached_and_carry_the_top_60_probabilities():
    rows = stage0.stage0_rows()
    assert len(rows) == 4 * 53
    for r in rows:
        assert r['cached'] is True and r['source'] == 'recorded' and r['profile'] == 'recorded' and r['latency_ms'] == {}
    r5 = next(r for r in rows if r['arm'] == 'R5-jev-screen-rerank60-rec')
    assert len(r5['probabilities']) == 60 and len(r5['order']) == 2080


def test_committed_recorded_rows_are_current(tmp_path):
    committed = RowStore(RESULTS)
    fresh = RowStore(tmp_path)
    for r in stage0.stage0_rows():
        fresh.append(r)
    for arm in stage0.ARMS:
        if not (RESULTS / f'{arm}.jsonl.gz').exists():
            pytest.skip('recorded rows not written yet (python -m evals_dev.identify_bench stage0 --write)')
        assert fresh.pack(arm).read_bytes() == (RESULTS / f'{arm}.jsonl.gz').read_bytes(), arm
        assert len(committed.arm_rows(arm)) == 53


# ---- datasets ---------------------------------------------------------------------------------------------

def test_dataset_sizes_and_part_groups_match_the_plan():
    cases = datasets.load_all()
    by = {}
    for c in cases:
        by.setdefault((c.dataset, c.part_group), []).append(c)
    assert len(cases) == 139 and sum(1 for c in cases if c.gold) == 117
    assert {k: len(v) for k, v in by.items()} == {
        ('public53', 'part9'): 24, ('public53', 'other'): 20, ('public53', 'mixed'): 9,
        ('dev', 'part9'): 11, ('dev', 'other'): 27, ('dev', 'none'): 22,
        ('idr26', 'part9'): 21, ('idr26', 'other'): 5}
    assert all(c.fold for c in cases)


def test_gold_is_article_level_and_division_b():
    for c in datasets.load_all():
        for a in c.gold + c.acceptable + c.forbidden:
            assert a.count('.') == 4 and a.endswith('.') and a.replace('.', '').isdigit()
        assert not set(c.gold) & set(c.forbidden)


def test_idr26_copy_matches_the_original_when_pr_39_has_merged():
    if not datasets.IDR26_ORIGINAL.is_file():
        pytest.skip('PR #39 has not merged; idr26 is the vendored copy')
    import json
    original = {c['id']: c for c in json.loads(datasets.IDR26_ORIGINAL.read_text())['cases']}
    for c in datasets.load_idr26():
        assert c.query == original[c.id]['description']


def test_balanced_selection_is_seeded_and_spread_over_the_groups():
    a = case_select.select(balanced=30)
    b = case_select.select(balanced=30)
    assert [c.id for c in a] == [c.id for c in b] and len(a) == 30
    groups = {g: sum(1 for c in a if c.part_group == g) for g in ('part9', 'other', 'mixed')}
    assert groups == {'part9': 10, 'other': 10, 'mixed': 9} or sum(groups.values()) == 30 and min(groups.values()) >= 9
