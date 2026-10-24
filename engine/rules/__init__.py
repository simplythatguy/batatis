"""Coded rules (WP-31): departure flags for the articles applicants vary most often. See `evaluator.py`."""
from .evaluator import RuleError, evaluate, evaluate_all, fmt, load_index, load_rule, load_rules

__all__ = ['RuleError', 'evaluate', 'evaluate_all', 'fmt', 'load_index', 'load_rule', 'load_rules']
