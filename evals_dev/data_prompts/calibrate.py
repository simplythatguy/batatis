"""Sensitivity of the judge, with synthetic reports whose right answer is known.

  oracle   a report that states every reference fact and raises every review and boundary point: ~100%
  empty    a report with no content: only prohibitions pass
  swapped  another case's oracle report: low, because its facts belong to a different record
  altered  the oracle with every number changed: facts with numbers must fail

    .venv/bin/python -m evals_dev.data_prompts.calibrate --cases 20
"""
from __future__ import annotations

import argparse
import re
from collections import Counter
from concurrent.futures import ThreadPoolExecutor

from engine.codes import Codes, default_db

from . import corpus, gold, judge, ledger, sut


def oracle(items: list[gold.Item]) -> str:
    lines = ['FACTS READ'] + [f'- {i.text}' for i in items if i.kind == 'F']
    lines += ['NOTES AND QUESTIONS'] + [f'- {i.text}' for i in items if i.kind in 'RB']
    return '\n'.join(lines)


def altered(report: str) -> str:
    return re.sub(r'\d+(?:[.,]\d+)?', lambda m: str(int(float(m.group(0).replace(',', '')) * 3 + 7)), report)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--cases', type=int, default=20)
    parser.add_argument('--model', default='gpt-6.1-sol')
    parser.add_argument('--effort', default='low')
    args = parser.parse_args(argv)
    sut.load_env()
    ledger.install()
    codes = Codes(default_db())
    cases = corpus.select('dev')[:args.cases]
    golds = [gold.gold(c, codes) for c in cases]

    def grade(index: int, variant: str):
        case, g = cases[index], golds[index]
        items = list(g.items)
        report = {'oracle': oracle(items), 'empty': 'DOCUMENTS\n- (none)',
                  'swapped': oracle(list(golds[(index + len(golds) // 2) % len(golds)].items)),
                  'altered': altered(oracle(items))}[variant]
        verdicts = judge.grade(case.prompt, report, items, model=args.model, effort=args.effort)
        has_number = {i.id for i in items if re.search(r'\d', i.text)}
        return variant, verdicts, has_number

    jobs = [(i, v) for i in range(len(cases)) for v in ('oracle', 'empty', 'swapped', 'altered')]
    with ThreadPoolExecutor(8) as pool:
        results = list(pool.map(lambda job: grade(*job), jobs))
    tally: dict[str, Counter] = {}
    for variant, verdicts, has_number in results:
        t = tally.setdefault(variant, Counter())
        for v in verdicts:
            t[f'{v.kind}_n'] += 1
            t[f'{v.kind}_pass'] += v.passed
            if variant == 'altered' and v.kind == 'F' and v.id in has_number:
                t['F_numeric_n'] += 1
                t['F_numeric_pass'] += v.passed
    for variant, t in tally.items():
        parts = [f"{k}: {t[k + '_pass']}/{t[k + '_n']}" for k in ('F', 'R', 'B', 'F_numeric') if t[k + '_n']]
        print(variant.ljust(8), '  '.join(parts))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
