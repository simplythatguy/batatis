"""Measure real engine HTTP saves on disposable data; no listener or provider calls.

Run with an engine-ready Python: scripts/measure_durable_saves.py --mode before|after.
The same ten changed answers and 100 existing facts are used on each side.
"""
from __future__ import annotations

import argparse
import json
import statistics
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi.testclient import TestClient

from engine.api import create_app
from engine.models import Case, Fact, Source
from engine.store import CaseStore


class MeasuredStore(CaseStore):
    statements: list[str]

    def _connect(self):
        con = super()._connect()
        con.set_trace_callback(lambda sql: self.statements.append(sql))
        return con

    def __init__(self, path):
        self.statements = []
        super().__init__(path)


def fact(index: int, changed: bool = False) -> Fact:
    text = ("Applicant revised answer " if changed else "Existing applicant answer ") + str(index)
    return Fact(id=f'answer-{index}', field=f'benchmark.answer_{index}', value=text,
                kind='pointed', status='confirmed',
                source=Source(type='user_text', ref='Applicant', quote=text))


def measure(mode: str, rounds: int):
    results = []
    with tempfile.TemporaryDirectory(prefix='batatis-save-measure-') as tmp:
        store = MeasuredStore(Path(tmp) / 'cases.sqlite')
        client = TestClient(create_app(store=store))
        for iteration in range(rounds):
            saved = store.put(Case(facts=[fact(i) for i in range(100)]))
            changes = [fact(i, changed=True).model_dump(mode='json') for i in range(10)]
            assert client.get(f'/cases/{saved.id}').status_code == 200  # same warm HTTP stack on both sides
            store.statements.clear()
            start = time.perf_counter()
            requests = 0
            responses = []
            if mode == 'before':
                for change in changes:
                    responses.append(client.post(f'/cases/{saved.id}/facts', json=change))
                    requests += 1
            else:
                responses.append(client.patch(f'/cases/{saved.id}/draft', json={
                    'expected_version': saved.version, 'facts': changes,
                }))
                requests += 1
            elapsed = (time.perf_counter() - start) * 1000
            writes = [sql for sql in store.statements if sql.lstrip().upper().startswith('UPDATE CASES')]
            errors = [response.status_code for response in responses if not 200 <= response.status_code < 300]
            actual = store.get(saved.id)
            correct = all(next(f for f in reversed(actual.facts) if f.field == change['field']).value == change['value']
                          for change in changes)
            result = {'run': iteration + 1, 'milliseconds': round(elapsed, 3), 'requests': requests,
                      'case_updates': len(writes), 'sql_update_bytes': sum(len(sql.encode()) for sql in writes),
                      'errors': errors, 'answers_verified': 10 if correct else 0}
            results.append(result)
            if errors or not correct:
                raise RuntimeError(json.dumps(result))
    times = [r['milliseconds'] for r in results]
    return {'mode': mode, 'storage': 'SQLite', 'transport': 'real FastAPI TestClient HTTP; in process',
            'provider': 'none', 'runs': results, 'median_ms': statistics.median(times),
            'range_ms': [min(times), max(times)]}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--mode', choices=['before', 'after', 'compare'], required=True)
    parser.add_argument('--rounds', type=int, default=5)
    args = parser.parse_args()
    if args.mode == 'compare':
        paired = []
        for _ in range(args.rounds):
            paired.extend(measure(mode, 1) for mode in ('before', 'after'))
        print(json.dumps({'alternating_runs': paired}, indent=2))
    else:
        print(json.dumps(measure(args.mode, args.rounds), indent=2))
