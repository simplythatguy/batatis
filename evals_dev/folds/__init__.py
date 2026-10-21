"""Frozen, seeded, stratified folds for the evaluation lane (seed 20261021).

    python -m evals_dev.folds show      # counts per fold, dataset and stratum
    python -m evals_dev.folds verify    # hash, coverage and seeded rule; non-zero exit on any problem
    python -m evals_dev.folds extend    # assign cases added since the freeze; never moves an existing case
    python -m evals_dev.folds build     # first freeze only; refuses to overwrite an existing file
"""
from .core import (CALIBRATION_SHARE, FOLDS, SEED, SELECTION_DATASETS, Item, build, digest, extend,
                   target_calibration, verify)

__all__ = ['CALIBRATION_SHARE', 'FOLDS', 'SEED', 'SELECTION_DATASETS', 'Item', 'build', 'digest', 'extend',
           'target_calibration', 'verify']
