"""Metrics for the evaluation lane: intervals, paired tests, bootstrap and ranking metrics.

    from evals_dev.metrics import clopper_pearson_lower, sign_test, bootstrap_ci, evaluate
"""
from .bootstrap import DEFAULT_RESAMPLES, DEFAULT_SEED, bootstrap_ci, paired_bootstrap_ci
from .intervals import (binom_cdf, binom_sf, clopper_pearson_interval, clopper_pearson_lower,
                        clopper_pearson_upper, proportion, rate, wilson_interval)
from .paired import paired_counts, paired_counts_graded, sign_test, sign_test_cases
from .ranking import (DEFAULT_KS, article_of, evaluate, first_gold_rank, hit_at_k, recall_at_k,
                      reciprocal_rank)

__all__ = [
    'DEFAULT_KS', 'DEFAULT_RESAMPLES', 'DEFAULT_SEED', 'article_of', 'binom_cdf', 'binom_sf', 'bootstrap_ci',
    'clopper_pearson_interval', 'clopper_pearson_lower', 'clopper_pearson_upper', 'evaluate',
    'first_gold_rank', 'hit_at_k', 'paired_bootstrap_ci', 'paired_counts', 'paired_counts_graded', 'proportion', 'rate',
    'recall_at_k', 'reciprocal_rank', 'sign_test', 'sign_test_cases', 'wilson_interval',
]
