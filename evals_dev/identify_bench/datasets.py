"""The code-identification datasets as one list of ``BenchCase``.

| dataset  | cases | what it is |
|----------|-------|------------|
| public53 | 53    | regulator precedents (STANDATA, Calgary SPV); query = the precedent text with article numbers replaced by ``[ref]`` |
| dev      | 60    | applicant prose written from the code database (``evals_dev/cases``); 38 with benchmark gold, 18 ``ask``, 4 ``redirect`` |
| idr26    | 26    | identify regression set (PR #39), plain-language applicants, selected after a cold-run failure |

Gold is collapsed to the Division B article (``9.25.5.2.(1)`` -> ``9.25.5.2.``). ``gold`` is the hit definition;
``acceptable`` articles are relevant but not required and are never penalised; ``forbidden`` articles are a
regression if presented. ``ask`` and ``redirect`` cases have no gold: they are scored on the action.

A case's ``part_group`` is ``part9`` (every gold article in Part 9), ``other`` (none in Part 9), ``mixed`` or ``none``.
"""
from __future__ import annotations

import json
from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path

from evals_dev.metrics.ranking import article_of

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent
PUBLIC53 = REPO / 'evals_dev' / 'public_benchmark' / 'cases.json'
DEV_CASES = REPO / 'evals_dev' / 'cases'
IDR26 = HERE / 'data' / 'idr26.json'
IDR26_ORIGINAL = REPO / 'docs' / 'research' / '2026-10-20-data-nerd' / 'identify-regression.json'
FOLDS_FILE = REPO / 'evals_dev' / 'folds' / 'folds-v1.json'

DATASETS = ('public53', 'dev', 'idr26')
SELECTION_DATASETS = ('public53', 'idr26')


@dataclass(frozen=True)
class BenchCase:
    id: str
    dataset: str
    query: str
    gold: tuple[str, ...] = ()
    acceptable: tuple[str, ...] = ()
    forbidden: tuple[str, ...] = ()
    action: str | None = None            # dev only: ask | proceed_conditionally | redirect
    kind: str = ''                       # precedent type or applicant type
    family: str = ''                     # revision family, for leave-one-family-out and clustered intervals
    fold: str | None = None              # selection | calibration | validation, from the frozen folds file
    extra: dict = field(default_factory=dict, compare=False, hash=False)

    @property
    def parts(self) -> tuple[int, ...]:
        return tuple(sorted({int(a.split('.')[0]) for a in self.gold}))

    @property
    def part_group(self) -> str:
        return part_group(self.gold)

    @property
    def stratum(self) -> str:
        """Fold stratum: the Part group for a gold-bearing case, else the intake action."""
        if self.gold:
            return self.part_group
        return self.action if self.action in ('ask', 'redirect') else 'none'


def part_group(gold: Iterable[str]) -> str:
    parts = {int(a.split('.')[0]) for a in gold}
    if not parts:
        return 'none'
    if parts == {9}:
        return 'part9'
    return 'mixed' if 9 in parts else 'other'


def _articles(entries, *, roles: set[str] | None = None, exclude_roles: set[str] | None = None) -> tuple[str, ...]:
    """Division B article ids from must_cite style entries, in order, without duplicates."""
    out: list[str] = []
    for e in entries or []:
        if isinstance(e, str):
            division, provision, role = 'B', e, None
        else:
            division, provision, role = e.get('division') or 'B', e.get('provision'), e.get('role')
        if division != 'B':
            continue
        if roles is not None and role not in roles:
            continue
        if exclude_roles is not None and role in exclude_roles:
            continue
        art = article_of(provision)
        if art and art not in out:
            out.append(art)
    return tuple(out)


def load_public53(path: Path = PUBLIC53) -> list[BenchCase]:
    cases = []
    for c in json.loads(path.read_text()):
        cases.append(BenchCase(id=c['id'], dataset='public53', query=c['query'], gold=_articles(c['gold']),
                               kind=c['type'], family=c.get('family') or c['id'],
                               extra={'edition': c.get('edition')}))
    return cases


def load_dev(directory: Path = DEV_CASES) -> list[BenchCase]:
    cases = []
    for p in sorted(directory.glob('dev-*.json')):
        c = json.loads(p.read_text())
        g = c['gold']
        gold = _articles(g.get('must_cite'), roles={'benchmark'})
        acceptable = tuple(a for a in _articles(g.get('must_cite'), exclude_roles={'benchmark'}) +
                           _articles(g.get('should_cite')) if a not in gold)
        # must_not_cite names sentences (an exception whose condition the facts rule out). At article level it can
        # collapse onto the gold article itself, so only articles disjoint from the gold remain forbidden.
        forbidden = tuple(a for a in _articles(g.get('must_not_cite')) if a not in gold)
        cases.append(BenchCase(
            id=c['id'], dataset='dev', query=c['description'], gold=gold,
            acceptable=tuple(dict.fromkeys(acceptable)), forbidden=forbidden,
            action=g.get('intake_action'), kind=c.get('applicant_type', ''), family=c['id'],
            extra={'topic': c.get('topic'), 'code_part': c.get('code_part'), 'redirect_to': g.get('redirect_to')}))
    return cases


def load_idr26(path: Path = IDR26) -> list[BenchCase]:
    data = json.loads(path.read_text())
    return [BenchCase(id=c['id'], dataset='idr26', query=c['query'], gold=tuple(c['gold']),
                      acceptable=tuple(c['acceptable']), forbidden=tuple(c['forbidden']),
                      kind=c['applicant_type'], family=c['id']) for c in data['cases']]


def load_folds(path: Path = FOLDS_FILE) -> dict[str, str]:
    """case id -> fold, from the frozen folds file. Empty when the file is absent."""
    if not path.is_file():
        return {}
    return {cid: row['fold'] for cid, row in json.loads(path.read_text())['cases'].items()}


def load_all(*, with_folds: bool = True, datasets: Iterable[str] = DATASETS) -> list[BenchCase]:
    """Every case of the chosen datasets, in a fixed order, with its fold when the folds file knows it."""
    wanted = set(datasets)
    loaders = {'public53': load_public53, 'dev': load_dev, 'idr26': load_idr26}
    folds = load_folds() if with_folds else {}
    out: list[BenchCase] = []
    for name in DATASETS:
        if name not in wanted:
            continue
        for c in loaders[name]():
            out.append(BenchCase(**{**c.__dict__, 'fold': folds.get(c.id)}) if folds else c)
    ids = [c.id for c in out]
    if len(ids) != len(set(ids)):
        raise ValueError('case ids must be unique across datasets')
    return out


def gold_bearing(cases: Iterable[BenchCase]) -> list[BenchCase]:
    return [c for c in cases if c.gold]
