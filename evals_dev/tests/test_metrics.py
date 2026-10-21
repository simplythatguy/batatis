"""Metrics: Wilson, exact Clopper-Pearson, paired sign test, bootstrap, ranking.

The two anchor values are the ones the plan quotes for gate G4: the exact one-sided 95% lower bound is
0.9086 for 49 of 50 and 0.9106 for 32 of 32.
"""
import gzip
import json
import math
import pathlib

import pytest

from evals_dev import stats
from evals_dev.metrics import (bootstrap_ci, clopper_pearson_interval, clopper_pearson_lower,
                               clopper_pearson_upper, evaluate, first_gold_rank, hit_at_k, paired_bootstrap_ci,
                               paired_counts, paired_counts_graded, rate, recall_at_k, reciprocal_rank, sign_test, sign_test_cases,
                               wilson_interval)
from evals_dev.metrics.intervals import binom_cdf, binom_sf
from evals_dev.metrics.ranking import article_of

REPO = pathlib.Path(__file__).resolve().parents[2]
RESULTS = REPO / 'docs/research/2026-10-20-vision/jev-benchmark/results'
CASES = REPO / 'evals_dev/public_benchmark/cases.json'


# ---- exact Clopper-Pearson -------------------------------------------------------------------------------

def test_plan_anchor_49_of_50_is_0_9086():
    assert round(clopper_pearson_lower(49, 50), 4) == 0.9086


def test_plan_anchor_32_of_32_is_0_9106():
    assert round(clopper_pearson_lower(32, 32), 4) == 0.9106
    assert clopper_pearson_lower(32, 32) == pytest.approx(0.05 ** (1 / 32), abs=1e-12)


def test_one_sided_lower_is_the_p_at_which_the_tail_equals_alpha():
    x, n = 47, 53
    p = clopper_pearson_lower(x, n)
    assert binom_sf(x, n, p) == pytest.approx(0.05, abs=1e-9)
    q = clopper_pearson_upper(x, n)
    assert binom_cdf(x, n, q) == pytest.approx(0.05, abs=1e-9)


@pytest.mark.parametrize('x,n,low,high', [
    (0, 10, 0.0, 0.3085),
    (10, 10, 0.6915, 1.0),
    (5, 10, 0.1871, 0.8129),
    (1, 20, 0.0013, 0.2487),
    (50, 100, 0.3983, 0.6017),
])
def test_two_sided_matches_published_tables(x, n, low, high):
    got = clopper_pearson_interval(x, n)
    assert got[0] == pytest.approx(low, abs=6e-5)
    assert got[1] == pytest.approx(high, abs=6e-5)


def test_exact_interval_is_more_conservative_than_wilson():
    cp = clopper_pearson_interval(49, 50)
    w = wilson_interval(49, 50)
    assert cp[0] < w[0]                       # exact lower bound sits below Wilson's
    assert (cp[1] - cp[0]) > (w[1] - w[0])    # and the exact interval is wider overall
    assert clopper_pearson_interval(50, 50)[1] == 1.0


def test_edges_and_empty():
    assert clopper_pearson_lower(0, 7) == 0.0
    assert clopper_pearson_upper(7, 7) == 1.0
    assert clopper_pearson_interval(0, 0) is None
    with pytest.raises(ValueError):
        clopper_pearson_lower(8, 7)
    with pytest.raises(ValueError):
        clopper_pearson_lower(3, 7, confidence=1.0)


def test_large_n_does_not_overflow():
    low = clopper_pearson_lower(4900, 5000)
    assert 0.97 < low < 0.98


def test_rate_carries_every_interval_and_keeps_stats_proportion_unchanged():
    r = rate(49, 50)
    assert r['label'] == '49 of 50' and r['rate'] == 0.98
    assert r['wilson_95'] == stats.wilson_interval(49, 50)
    assert round(r['cp_lower_95_one_sided'], 4) == 0.9086
    assert rate(0, 0)['rate'] is None and rate(0, 0)['cp_lower_95_one_sided'] is None
    assert stats.proportion(3, 4) == {k: v for k, v in rate(3, 4).items() if k in stats.proportion(3, 4)}


# ---- paired sign test ------------------------------------------------------------------------------------

def test_sign_test_exact_values():
    assert sign_test(2, 8, 'less') == pytest.approx((1 + 10 + 45) / 1024)
    assert sign_test(2, 8, 'two-sided') == pytest.approx(2 * 56 / 1024)
    assert sign_test(0, 5, 'less') == pytest.approx(1 / 32)
    assert sign_test(5, 0, 'greater') == pytest.approx(1 / 32)
    assert sign_test(3, 3, 'two-sided') == 1.0
    assert sign_test(0, 0) == 1.0


def test_sign_test_one_sided_alpha_0_10_rule():
    # the decision rule: "not significantly negative" means p(less) >= 0.10
    assert sign_test(3, 9, 'less') < 0.10        # 3 vs 9 discordant: significantly worse
    assert sign_test(4, 8, 'less') >= 0.10       # 4 vs 8: not significant


def test_paired_counts_only_use_shared_cases():
    a = {'c1': True, 'c2': True, 'c3': False, 'c4': False, 'c5': True}
    b = {'c1': True, 'c2': False, 'c3': True, 'c4': False}
    counts = paired_counts(a, b)
    assert counts == {'n': 4, 'both': 1, 'only_a': 1, 'only_b': 1, 'neither': 1}
    assert sign_test_cases(a, b)['p_value'] == 1.0


# ---- bootstrap -------------------------------------------------------------------------------------------

def test_bootstrap_is_seeded_and_reproducible():
    values = [1.0, 0.0, 1.0, 1.0, 0.0, 1.0, 1.0, 0.5]
    a = bootstrap_ci(values, resamples=500, seed=7)
    b = bootstrap_ci(values, resamples=500, seed=7)
    c = bootstrap_ci(values, resamples=500, seed=8)
    assert a == b and a != c
    assert a['low'] <= a['estimate'] <= a['high']


def test_bootstrap_constant_values_have_zero_width():
    out = bootstrap_ci([0.5] * 12, resamples=200)
    assert out['low'] == out['high'] == 0.5


def test_cluster_bootstrap_is_wider_when_cases_in_a_cluster_move_together():
    values = [1.0, 1.0, 0.0, 0.0, 1.0, 1.0, 0.0, 0.0]
    clusters = ['a', 'a', 'b', 'b', 'c', 'c', 'd', 'd']
    plain = bootstrap_ci(values, resamples=2000)
    clustered = bootstrap_ci(values, resamples=2000, clusters=clusters)
    assert clustered['units'] == 4 and plain['units'] == 8
    assert (clustered['high'] - clustered['low']) > (plain['high'] - plain['low'])


def test_paired_bootstrap_difference_interval_covers_the_difference():
    a = [1.0, 1.0, 1.0, 0.0, 1.0, 1.0]
    b = [1.0, 0.0, 1.0, 0.0, 0.0, 1.0]
    out = paired_bootstrap_ci(a, b, resamples=1000)
    assert out['estimate'] == pytest.approx(2 / 6)
    assert out['low'] <= out['estimate'] <= out['high']
    with pytest.raises(ValueError):
        paired_bootstrap_ci([1.0], [1.0, 2.0])


def test_bootstrap_of_nothing_is_none():
    assert bootstrap_ci([])['estimate'] is None


# ---- ranking ---------------------------------------------------------------------------------------------

def test_ranking_metrics_by_hand():
    order = ['a', 'b', 'c', 'd', 'e']
    gold = ['c', 'z']
    assert first_gold_rank(order, gold) == 3
    assert reciprocal_rank(order, gold) == pytest.approx(1 / 3)
    assert hit_at_k(order, gold, 2) is False and hit_at_k(order, gold, 3) is True
    assert recall_at_k(order, gold, 5) == 0.5
    assert first_gold_rank(order, ['q']) is None and reciprocal_rank(order, ['q']) == 0.0


def test_evaluate_counts_a_missing_ranking_as_a_miss():
    gold = {'c1': ['a'], 'c2': ['b'], 'c3': []}
    got = evaluate({'c1': ['a', 'x']}, gold, ks=(1, 5))
    assert got['n'] == 2 and got['hit@1'] == 0.5 and got['mrr'] == 0.5


def test_article_of_collapses_sentences():
    assert article_of('9.25.5.2.(1)') == '9.25.5.2.' == article_of('9.25.5.2.')
    assert article_of('A-1.1') is None and article_of(None) is None


def test_recorded_bm25_ranking_reproduces_the_research_numbers():
    cases = json.loads(CASES.read_text())
    gold = {c['id']: c['gold'] for c in cases}
    ranked = json.load(gzip.open(RESULTS / 'bm25_ranked.json.gz'))
    got = evaluate(ranked, gold)
    assert got['n'] == 53
    assert round(got['mrr'], 3) == 0.485
    assert round(got['hit@1'], 2) == 0.32 and round(got['hit@5'], 2) == 0.66
    assert math.isclose(got['hit@1'], 17 / 53)


def test_graded_pairing_counts_only_cases_whose_success_shares_differ():
    a = {'c1': 1.0, 'c2': 0.5, 'c3': 0.0, 'c4': 0.4, 'c5': 1.0}
    b = {'c1': 1.0, 'c2': 1.0, 'c3': 0.0, 'c4': 0.2, 'c5': 0.0}
    assert paired_counts_graded(a, b) == {'n': 5, 'only_a': 2, 'only_b': 1, 'same': 2}
    assert sign_test(2, 1, 'less') == pytest.approx(7 / 8)
