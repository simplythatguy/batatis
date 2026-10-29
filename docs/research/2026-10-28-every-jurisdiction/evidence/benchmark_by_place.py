"""Split the saved Data Prompts baseline run (653 real cases) by the place each case comes from.

The run is historical: engine commit 8dbf2760 on 2026-10-25, Sol judge at low effort, before the
integrity repairs. It is the only full run on disk. It shows how results varied by place at that time;
it does not measure today's engine.

Run from the repository root:
  python3 docs/research/2026-10-28-every-jurisdiction/evidence/benchmark_by_place.py \
      /path/to/.dpe-cache/runs/baseline
"""
from __future__ import annotations

import csv
import hashlib
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
INDEXES = [ROOT / 'Data Prompts' / 'index.csv']   # all 653 cases with country, province and city
GUARDRAILS = ('no_claims', 'citations_resolve', 'no_alberta_commit_outside_alberta', 'ran')
KINDS = ('A', 'F', 'R', 'B')


def place_group(row: dict) -> str:
    country, prov, city = row['country'], row['province_or_state'], row['city_or_town']
    if country == 'Canada' and prov == 'Alberta':
        if city == 'Calgary':
            return 'Calgary'
        if city == 'Edmonton':
            return 'Edmonton'
        if city == 'Province-wide':
            return 'Alberta, province-wide'
        if city == 'Unspecified locality':
            return 'Alberta, place not stated'
        return 'Alberta, other named place'
    if country == 'Canada' and prov in ('British Columbia', 'Ontario', 'Saskatchewan', 'Manitoba', 'Quebec'):
        return prov
    if country == 'Canada':
        return 'Canada, other or national'
    return 'Outside Canada'


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main(run_dir: Path) -> None:
    where, cities = {}, defaultdict(Counter)
    for index in INDEXES:
        for row in csv.DictReader(index.open(encoding='utf-8')):
            where[row['case_id']] = place_group(row)
            cities[where[row['case_id']]][row['city_or_town']] += 1
    files = sorted(run_dir.glob('score-*-gpt-6.1-sol-low.jsonl'))
    cases = [json.loads(line) for f in files for line in f.open(encoding='utf-8')]
    groups = defaultdict(lambda: {'cases': 0, 'checks': Counter(), 'passed': Counter(), 'guardrails': Counter(),
                                  'all_guardrails': 0, 'case_types': Counter(), 'tiers': Counter(),
                                  'type_checks': Counter(), 'type_passed': Counter(), 'type_a': Counter(), 'type_a_passed': Counter()})
    missing = []
    for case in cases:
        group = where.get(case['case_id'])
        if group is None:
            missing.append(case['case_id'])
            continue
        g = groups[group]
        g['cases'] += 1
        g['case_types'][case['case_type']] += 1
        g['tiers'][case['tier']] += 1
        for check in case['checks']:
            g['checks'][check['kind']] += 1
            g['passed'][check['kind']] += bool(check['passed'])
            g['type_checks'][case['case_type']] += 1
            g['type_passed'][case['case_type']] += bool(check['passed'])
            if check['kind'] == 'A':
                g['type_a'][case['case_type']] += 1
                g['type_a_passed'][case['case_type']] += bool(check['passed'])
        ok = [bool(case['guardrails'][name][0]) for name in GUARDRAILS]
        for name, flag in zip(GUARDRAILS, ok):
            g['guardrails'][name] += flag
        g['all_guardrails'] += all(ok)
    order = ['Calgary', 'Edmonton', 'Alberta, other named place', 'Alberta, province-wide', 'Alberta, place not stated',
             'British Columbia', 'Ontario', 'Saskatchewan', 'Manitoba', 'Quebec', 'Canada, other or national',
             'Outside Canada']
    table = []
    for name in order:
        g = groups.get(name)
        if not g:
            continue
        n, p = sum(g['checks'].values()), sum(g['passed'].values())
        table.append({
            'place': name, 'cases': g['cases'], 'checks': n, 'passed': p, 'rate': round(p / n, 4) if n else None,
            'by_kind': {k: {'n': g['checks'][k], 'rate': round(g['passed'][k] / g['checks'][k], 4) if g['checks'][k] else None}
                        for k in KINDS},
            'guardrails_all_pass': round(g['all_guardrails'] / g['cases'], 4),
            'guardrails': {k: round(v / g['cases'], 4) for k, v in g['guardrails'].items()},
            'places_in_group': dict(cities[name].most_common()),
            'case_types': dict(g['case_types'].most_common()),
            'by_case_type': {t: {'cases': g['case_types'][t], 'checks': g['type_checks'][t],
                                 'rate': round(g['type_passed'][t] / g['type_checks'][t], 4) if g['type_checks'][t] else None,
                                 'article_checks': g['type_a'][t],
                                 'article_rate': round(g['type_a_passed'][t] / g['type_a'][t], 4) if g['type_a'][t] else None}
                             for t in g['case_types']},
        })
    out = {'run': json.loads((run_dir / 'meta.json').read_text()),
           'inputs': {f.name: sha256(f) for f in files} | {i.name: sha256(i) for i in INDEXES},
           'cases_scored': len(cases), 'cases_without_location': missing, 'table': table}
    (HERE / 'benchmark_by_place.json').write_text(json.dumps(out, indent=1, ensure_ascii=False) + '\n', encoding='utf-8')
    for row in table:
        k = row['by_kind']
        print(f"{row['place']:40} cases {row['cases']:4} checks {row['checks']:5} rate {row['rate']:.3f} "
              f"A {k['A']['rate']} (n={k['A']['n']}) F {k['F']['rate']} R {k['R']['rate']} B {k['B']['rate']} (n={k['B']['n']}) "
              f"guardrails {row['guardrails_all_pass']:.3f}")


if __name__ == '__main__':
    main(Path(sys.argv[1]))
