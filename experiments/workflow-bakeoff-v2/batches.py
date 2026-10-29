"""Pending request files for a stage, split into batches for T3 tasks. Prints each batch's lines."""
from __future__ import annotations

import json
import sys

from common import RUNS


def pending(stage: str) -> list[tuple[str, str]]:
    out = []
    for req in sorted((RUNS / 'requests' / stage).glob('*.json')):
        resp = RUNS / 'responses' / stage / req.name
        ok = False
        if resp.exists():
            try:
                json.loads(resp.read_text())
                ok = True
            except ValueError:
                ok = False
        if not ok:
            out.append((str(req), str(resp)))
    return out


if __name__ == '__main__':
    stage, size = sys.argv[1], int(sys.argv[2])
    todo = pending(stage)
    print(f'# {stage}: {len(todo)} pending')
    for n in range(0, len(todo), size):
        print(f'## batch {n // size + 1}')
        for req, resp in todo[n:n + size]:
            print(f'{req} -> {resp}')
