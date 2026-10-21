"""The identify pipeline (WP-20, PR #52) as a judge SUT: prose on stdin, one JSON object on stdout.

This is the arm to register for the held-out run once PR #52 has merged: it runs ``engine.identify.pipeline.run`` with the pinned
``engine/identify/pipeline.json`` (or ``BATATIS_IDENTIFY_CONFIG``) and the calibration file the engine reads, and maps the
``IdentifyResult`` onto the ``engine/cli_sut.py`` contract the judge scores:

    articles           the shown articles in rank order, ``committed`` true only for status ``committed``
    intake_action      ``proceed_conditionally`` when something was committed, else ``ask`` (the identify route does not decide
                       redirects; the judge scores this field as the placeholder it is)
    engineering_required  ``depends`` (identification does not decide professional involvement)

Live runs need ``BATATIS_LIVE=1``, the provider keys and a daily spend cap high enough for the run, for example::

    BATATIS_LIVE=1 BATATIS_DAILY_SPEND_CAP_USD=5 python -m evals_dev.judge run --split dev --sut identify

``to_contract`` is a pure function over the documented result shape so it is tested without the engine.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

TOP_K = 10


def to_contract(result: dict) -> dict:
    """Map an ``IdentifyResult`` (as a dict) onto the judge's SUT contract."""
    shown = []
    for a in result.get('articles') or []:
        provision = a.get('provision')
        if not provision:
            continue
        shown.append({'provision': provision, 'division': 'B', 'committed': a.get('status') == 'committed',
                      'title': a.get('title'), 'part': a.get('part'), 'probability': a.get('probability')})
    committed = [a for a in shown if a['committed']]
    trace = result.get('trace') or {}
    return {
        'articles': shown[:TOP_K],
        'section_c': [],
        'engineering_required': 'depends',
        'intake_action': 'proceed_conditionally' if committed else 'ask',
        'questions': [q.get('question') if isinstance(q, dict) else str(q) for q in (result.get('choices') or [])][:3],
        'trace': {'mode': result.get('mode'), 'config_hash': trace.get('config_hash'), 'ranker': trace.get('ranker'),
                  'fallback_reason': trace.get('fallback_reason'), 'usd': trace.get('usd')},
    }


def main() -> int:
    prose = sys.stdin.read().strip()
    if not prose:
        print('identify_pipeline: no prose on stdin', file=sys.stderr)
        return 2
    try:
        from engine.codes import Codes, default_db
        from engine.identify.pipeline import run
    except ImportError:
        print('identify_pipeline: engine.identify.pipeline is not on this branch (needs PR #52)', file=sys.stderr)
        return 2
    output = run(prose, codes=Codes(default_db()))
    result = output.result
    data = result.model_dump() if hasattr(result, 'model_dump') else dict(result)
    print(json.dumps(to_contract(data)))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
