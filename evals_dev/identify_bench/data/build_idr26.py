"""Normalise the identify regression set (PR #39, "idr26") into data/idr26.json.

PR #39 (`research/data-nerd-2026-10-20-clean`) is not merged yet, so the benchmark carries a trimmed copy:
id, applicant type, the applicant's own words, gold article ids by role, and the articles that must not be
returned. No code text, quotes or titles are copied. When #39 merges, the original lives at
``docs/research/2026-10-20-data-nerd/identify-regression.json`` and ``datasets.py`` cross-checks it.

    git show origin/research/data-nerd-2026-10-20-clean:docs/research/2026-10-20-data-nerd/identify-regression.json \
        > /tmp/identify-regression.json
    python evals_dev/identify_bench/data/build_idr26.py /tmp/identify-regression.json \
        --commit 9e8ff5311692aa6fa8e3ce4acdb9d4f1dbda0614

Roles: ``benchmark*`` and ``gold*`` are the retrieval target (the hit definition); ``related*`` and ``scope``
are relevant but not required and are never penalised.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = HERE / 'idr26.json'
SOURCE_PATH = 'docs/research/2026-10-20-data-nerd/identify-regression.json'


def normalise(raw: bytes, commit: str | None) -> dict:
    data = json.loads(raw)
    cases = []
    for c in data['cases']:
        gold, acceptable = [], []
        for g in c['gold_articles']:
            if g['division'] != 'B':
                raise ValueError(f"{c['id']}: only Division B gold is expected, got {g['division']}")
            role = (g.get('role') or '').lower()
            target = gold if role.startswith(('benchmark', 'gold')) else acceptable
            if g['article'] not in target:
                target.append(g['article'])
        cases.append({
            'id': c['id'],
            'applicant_type': c['applicant_type'],
            'query': c['description'],
            'gold': gold,
            'acceptable': acceptable,
            'forbidden': sorted({m['article'] for m in c.get('must_not_return', []) if m['division'] == 'B'}),
        })
    return {
        'name': 'idr26',
        'label': 'model-checked, not human-verified',
        'provenance': {
            'pull_request': 39,
            'branch': 'research/data-nerd-2026-10-20-clean',
            'commit': commit,
            'source_path': SOURCE_PATH,
            'source_sha256': hashlib.sha256(raw).hexdigest(),
            'note': 'Trimmed copy: ids, applicant words, article ids by role. Selected after a cold-run failure, '
                    'so it is biased towards hard cases. Scored at article level.',
        },
        'cases': cases,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('source', type=Path)
    ap.add_argument('--commit')
    args = ap.parse_args()
    OUT.write_text(json.dumps(normalise(args.source.read_bytes(), args.commit), indent=1, ensure_ascii=False) + '\n')
    print(f'wrote {OUT}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
