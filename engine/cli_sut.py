"""Command-line system under test for the held-out judge (run_judge.py contract).

Reads applicant prose on stdin and prints one JSON object. The ranking, commit policy, benchmark,
and Section C lookup are `engine.identify.pipeline.run`, the same function the HTTP identify route uses.

    SSL_CERT_FILE=/etc/ssl/cert.pem /path/.venv/bin/python /path/engine/cli_sut.py < prose.txt
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

if __package__ in (None, ''):                      # run as a script from any directory
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from engine.identify.config import (COMMIT_PARTS, COMMIT_THRESHOLD, MAX_COMMITS, QUESTION_K,  # noqa: E402
                                    RERANK_N, TOP_K, VERIFY_N)
from engine.identify.pipeline import run, section_c_dicts  # noqa: E402

__all__ = ['COMMIT_PARTS', 'COMMIT_THRESHOLD', 'MAX_COMMITS', 'QUESTION_K', 'RERANK_N', 'TOP_K',
           'VERIFY_N', 'run', 'section_c']


def section_c(article_ids: list[str], codes) -> list[dict]:
    return section_c_dicts(article_ids, codes)


def main() -> int:
    prose = sys.stdin.read().strip()
    if not prose:
        print('cli_sut: no prose on stdin', file=sys.stderr)
        return 2
    print(json.dumps(run(prose), indent=2))
    return 0


if __name__ == '__main__':
    sys.exit(main())
