"""Seeded, stratified, frozen folds.

Selection datasets (public53, idr26) are one fold, ``selection``: they choose the pipeline. Development cases
(``evals_dev/cases``) split into ``calibration`` (fit the commit threshold per Part) and ``validation`` (gate G4
and every reported number; nothing is fitted on it).

Stratified by Part group (``part9``, ``other``, ``mixed``) for cases with gold articles, and by intake action
(``ask``, ``redirect``) for cases without. Inside a stratum, cases are ordered by ``sha256(seed:id)`` and the
first ``round(share * n)`` go to calibration, so an assignment depends only on the seed and the stratum, never
on the order cases arrive in.

Frozen means two things. The file carries a hash over its content, and a case, once assigned, never moves:
``extend`` assigns only the cases the file has not seen, keeping each stratum at exactly ``round(share * n)``
calibration cases. ``verify`` re-derives every generation from the seed, so a hand edit fails even if someone
recomputes the hash.
"""
from __future__ import annotations

import hashlib
import json
import math
from collections import Counter, defaultdict
from collections.abc import Iterable
from dataclasses import dataclass

SCHEMA = 'batatis-folds/1'
SEED = 20261021
CALIBRATION_SHARE = 0.3
SELECTION_DATASETS = ('idr26', 'public53')
FOLDS = ('calibration', 'selection', 'validation')
STRATIFIED_BY = ('part group of the gold articles (part9, other, mixed); intake action (ask, redirect) for cases '
                 'without gold articles')


@dataclass(frozen=True)
class Item:
    id: str
    dataset: str
    stratum: str


def order_key(case_id: str, seed: int = SEED) -> str:
    return hashlib.sha256(f'{seed}:{case_id}'.encode()).hexdigest()


def target_calibration(n: int, share: float = CALIBRATION_SHARE) -> int:
    """Calibration cases wanted in a stratum of n: round half up."""
    return math.floor(share * n + 0.5)


def canonical(doc: dict) -> str:
    return json.dumps({k: v for k, v in doc.items() if k != 'sha256'}, sort_keys=True, separators=(',', ':'),
                      ensure_ascii=True)


def digest(doc: dict) -> str:
    return hashlib.sha256(canonical(doc).encode()).hexdigest()


def _assign_development(items: list[Item], previous: dict[str, str], seed: int, share: float) -> dict[str, str]:
    """Fold for every development item. Items in ``previous`` keep their fold."""
    by_stratum: dict[str, list[Item]] = defaultdict(list)
    for it in items:
        by_stratum[it.stratum].append(it)
    out: dict[str, str] = {}
    for stratum, members in by_stratum.items():
        fixed = [m for m in members if m.id in previous]
        new = sorted((m for m in members if m.id not in previous), key=lambda m: order_key(m.id, seed))
        have = sum(1 for m in fixed if previous[m.id] == 'calibration')
        need = max(0, min(len(new), target_calibration(len(members), share) - have))
        for m in fixed:
            out[m.id] = previous[m.id]
        for i, m in enumerate(new):
            out[m.id] = 'calibration' if i < need else 'validation'
    return out


def _fold_of(item: Item, dev: dict[str, str]) -> str:
    return 'selection' if item.dataset in SELECTION_DATASETS else dev[item.id]


def _counts(cases: dict[str, dict]) -> dict:
    tally: dict = defaultdict(Counter)
    for row in cases.values():
        tally[row['fold']][f"{row['dataset']}/{row['stratum']}"] += 1
    return {fold: dict(sorted(c.items())) for fold, c in sorted(tally.items())}


def _finalize(doc: dict) -> dict:
    doc['counts'] = _counts(doc['cases'])
    doc['sha256'] = digest(doc)
    return doc


def build(items: Iterable[Item], *, seed: int = SEED, share: float = CALIBRATION_SHARE) -> dict:
    """The first generation of a folds file for these items."""
    items = sorted(items, key=lambda i: i.id)
    _unique(items)
    dev_items = [i for i in items if i.dataset not in SELECTION_DATASETS]
    dev = _assign_development(dev_items, {}, seed, share)
    cases = {i.id: {'dataset': i.dataset, 'stratum': i.stratum, 'fold': _fold_of(i, dev), 'generation': 0}
             for i in items}
    doc = {'schema': SCHEMA, 'seed': seed, 'calibration_share': share, 'stratified_by': STRATIFIED_BY,
           'selection_datasets': list(SELECTION_DATASETS), 'folds': list(FOLDS),
           'generations': [{'generation': 0, 'added': len(items)}], 'cases': cases}
    return _finalize(doc)


def extend(doc: dict, items: Iterable[Item]) -> dict:
    """Assign the items the file has not seen. Existing assignments never change."""
    items = sorted(items, key=lambda i: i.id)
    _unique(items)
    problems = verify(doc, [i for i in items if i.id in doc['cases']], partial=True)
    if problems:
        raise ValueError('refusing to extend a folds file that does not verify: ' + '; '.join(problems[:3]))
    seen = doc['cases']
    new = [i for i in items if i.id not in seen]
    if not new:
        return doc
    generation = max(g['generation'] for g in doc['generations']) + 1
    dev_items = [i for i in items if i.dataset not in SELECTION_DATASETS]
    previous = {cid: row['fold'] for cid, row in seen.items() if row['dataset'] not in SELECTION_DATASETS}
    dev = _assign_development(dev_items, previous, doc['seed'], doc['calibration_share'])
    cases = dict(seen)
    for i in new:
        cases[i.id] = {'dataset': i.dataset, 'stratum': i.stratum, 'fold': _fold_of(i, dev), 'generation': generation}
    out = {**doc, 'cases': dict(sorted(cases.items())),
           'generations': doc['generations'] + [{'generation': generation, 'added': len(new)}]}
    return _finalize(out)


def _unique(items: list[Item]) -> None:
    ids = [i.id for i in items]
    if len(ids) != len(set(ids)):
        dup = sorted(i for i, n in Counter(ids).items() if n > 1)
        raise ValueError(f'case ids must be unique across datasets: {dup[:5]}')


def verify(doc: dict, items: Iterable[Item], *, partial: bool = False) -> list[str]:
    """Problems with a folds file against the cases that exist now. Empty means it verifies.

    ``partial`` skips the "every case is assigned" check (used by ``extend`` on the cases it already knows).
    """
    problems: list[str] = []
    items = list(items)
    if doc.get('schema') != SCHEMA:
        return [f"schema is {doc.get('schema')!r}, expected {SCHEMA!r}"]
    if doc.get('sha256') != digest(doc):
        problems.append('sha256 does not match the content (the file was edited; re-freeze with a new version)')
    cases = doc.get('cases', {})
    by_id = {i.id: i for i in items}
    for cid, row in cases.items():
        if row['fold'] not in FOLDS:
            problems.append(f'{cid}: unknown fold {row["fold"]!r}')
        item = by_id.get(cid)
        if item is None:
            if not partial:
                problems.append(f'{cid}: assigned but no longer exists (add folds-v2 instead of editing v1)')
            continue
        if row['dataset'] != item.dataset or row['stratum'] != item.stratum:
            problems.append(f'{cid}: dataset or stratum changed since the freeze '
                            f'({row["dataset"]}/{row["stratum"]} -> {item.dataset}/{item.stratum})')
        if item.dataset in SELECTION_DATASETS and row['fold'] != 'selection':
            problems.append(f'{cid}: selection datasets are all in the selection fold')
        if item.dataset not in SELECTION_DATASETS and row['fold'] == 'selection':
            problems.append(f'{cid}: development cases are calibration or validation')
    if not partial:
        for cid in sorted(set(by_id) - set(cases)):
            problems.append(f'{cid}: has no fold; run `python -m evals_dev.folds extend` and commit the new file')
    problems.extend(_rederive(doc, by_id))
    return problems


def _rederive(doc: dict, by_id: dict[str, Item]) -> list[str]:
    """Re-run the assignment rule generation by generation and compare."""
    cases = doc.get('cases', {})
    seed, share = doc['seed'], doc['calibration_share']
    expected: dict[str, str] = {}
    problems: list[str] = []
    for gen in sorted({row['generation'] for row in cases.values()}):
        members = [Item(cid, row['dataset'], row['stratum']) for cid, row in cases.items()
                   if row['generation'] <= gen and row['dataset'] not in SELECTION_DATASETS]
        expected = _assign_development(members, expected, seed, share)
    for cid, fold in expected.items():
        if cases[cid]['fold'] != fold:
            problems.append(f'{cid}: fold {cases[cid]["fold"]} does not follow the seeded rule (expected {fold})')
    return problems
