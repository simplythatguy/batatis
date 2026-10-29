"""Run every arm for every case and simulated applicant; write per-run rows and the summary tables."""
from __future__ import annotations

import csv
import json
import statistics
import sys
from collections import defaultdict

from common import RUNS, load_cases, read_json, section_c_summary, write_json
from arms import ARMS, friction, quality

from engine.intake import service
from engine.models import Case


def response(stage: str, case_id: str):
    path = RUNS / 'responses' / stage / f'{case_id}.json'
    return read_json(path) if path.exists() else None


def with_code_book(sheet: dict | None, case: dict) -> dict | None:
    """The expert who opens the code book: identification and attributions are right; essays stay theirs."""
    if sheet is None:
        return None
    sc = section_c_summary(case['gold'][0]) or {}
    return {**sheet, 'benchmark_article': case['gold'][0], 'division_b_provisions': list(case['gold']),
            'objectives': sc.get('objectives', []), 'functional_statements': sc.get('functions', [])}


def shell_case(description: str) -> Case:
    from common import codes
    shell = Case()
    service.apply(shell, description, service.run(description, [], codes=codes()))
    return shell


def main(only_complete: bool = True) -> None:
    rows, skipped = [], []
    for case in load_cases():
        s0 = read_json(RUNS / 'stage0' / f"{case['id']}.json")
        r1, r2 = response('r1', case['id']), response('r2', case['id'])
        expert = response('persona_expert', case['id'])
        personas = {'novice': response('persona_novice', case['id']), 'expert': with_code_book(expert, case),
                    'expert_memory': expert}
        if only_complete and (r1 is None or r2 is None or None in personas.values()):
            skipped.append(case['id'])
            continue
        shell = shell_case(case['description'])
        for kind, persona in personas.items():
            for name, arm in ARMS.items():
                run = arm(case, s0, r1, r2, persona or {}, kind, shell)
                rows.append({'case': case['id'], 'type': case['type'], 'arm': name, 'persona': kind,
                             'friction': friction(run), 'quality': quality(run, case), 'package': run.package,
                             'inputs': run.inputs})
    write_json(RUNS / 'results' / 'runs.json', rows)
    summarize(rows)
    if skipped:
        print('skipped (missing responses):', len(skipped))


def mean(values):
    values = [v for v in values if v is not None]
    return round(statistics.mean(values), 3) if values else None


def summarize(rows: list[dict]) -> None:
    groups = defaultdict(list)
    for row in rows:
        groups[(row['arm'], row['persona'])].append(row)
    table = []
    for (arm, persona), items in sorted(groups.items(), key=lambda kv: (kv[0][1], list(ARMS).index(kv[0][0]))):
        f = [r['friction'] for r in items]
        q = [r['quality'] for r in items]
        alt = [r for r in items if r['quality']['path_correct'] is not None]
        table.append({
            'persona': persona, 'arm': arm, 'n': len(items),
            'inputs': mean(x['inputs'] for x in f), 'expert_inputs': mean(x['expert'] for x in f),
            'essays': mean(x['essay'] for x in f), 'unknowns': mean(x['unknown'] for x in f),
            'words_typed': mean(x['words'] for x in f), 'minutes_est': mean(x['minutes'] for x in f),
            'dead_ends': sum(x['dead_end'] for x in f),
            'forced_guesses': sum(x['diamond_guessed'] for x in f),
            'path_correct_on_variances': f"{sum(r['quality']['path_correct'] for r in alt)}/{len(alt)}",
            'benchmark_hit': sum(x['benchmark_hit'] for x in q),
            'article_recall': mean(x['article_recall'] for x in q),
            'invalid_citations': sum(x['invalid_citations'] for x in q),
            'section_c_exact': sum(1 for x in q if x['section_c_exact']),
            'section_c_invented_codes': sum(x['section_c_invented_codes'] for x in q),
            'coverage_of_10': mean(x['coverage_score'] for x in q),
            'app_claims': sum(x['app_claims'] for x in q),
            'app_claims_regex': sum(x['app_claims_regex'] for x in q),
        })
    write_json(RUNS / 'results' / 'summary.json', table)
    with open(RUNS / 'results' / 'summary.csv', 'w', newline='') as fh:
        writer = csv.DictWriter(fh, fieldnames=list(table[0]))
        writer.writeheader()
        writer.writerows(table)
    cols = list(table[0])
    print('\t'.join(cols))
    for row in table:
        print('\t'.join(str(row[c]) for c in cols))


if __name__ == '__main__':
    main(only_complete='--partial' not in sys.argv)
