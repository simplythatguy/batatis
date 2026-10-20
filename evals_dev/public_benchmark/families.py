"""Revision families for the public precedent benchmark, for leave-one-family-out testing.

A variance and its r1/rev versions are one family (`family_id` in research/precedents/index.json).
When testing precedent matching on a case, every precedent in the case's family must be hidden,
otherwise the matcher finds its own answer.

    .venv/bin/python evals_dev/public_benchmark/families.py   # rebuild cases.json with `family`

    from evals_dev.public_benchmark.families import excluded_precedents
    excluded_precedents(case)  # -> sorted precedent ids to hide
"""
import json
import pathlib
from functools import lru_cache

HERE = pathlib.Path(__file__).resolve().parent
REPO = HERE.parent.parent
INDEX = REPO / 'research/precedents/index.json'
SOURCE = REPO / 'docs/research/2026-10-20-vision/jev-benchmark/data/cases.json'
CASES = HERE / 'cases.json'


@lru_cache(maxsize=None)
def _index(path=INDEX):
    return {r['id']: r.get('family_id') or r['id'] for r in json.loads(pathlib.Path(path).read_text())}


def family_of(precedent_id: str, index_path=INDEX) -> str:
    """Family id for a precedent; a precedent missing from the index is its own family."""
    return _index(index_path).get(precedent_id, precedent_id)


def excluded_precedents(case, index_path=INDEX) -> list[str]:
    """Precedent ids to hide when evaluating precedent matching on `case` (its whole revision family)."""
    fam = case.get('family') or family_of(case['id'], index_path)
    members = {pid for pid, f in _index(index_path).items() if f == fam}
    return sorted(members | {case['id']})


def build(source=SOURCE, out=CASES, index_path=INDEX):
    cases = json.loads(pathlib.Path(source).read_text())
    for c in cases:
        c['family'] = family_of(c['id'], index_path)
    pathlib.Path(out).write_text(json.dumps(cases, indent=1, ensure_ascii=False) + '\n')
    return cases


if __name__ == '__main__':
    cases = build()
    fams = {c['family'] for c in cases}
    multi = sorted(f for f in fams if sum(c['family'] == f for c in cases) > 1)
    print(f'{len(cases)} cases, {len(fams)} families; families with more than one case: {multi}')
