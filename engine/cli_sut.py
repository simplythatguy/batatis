"""Command-line system under test for the held-out judge (run_judge.py contract).

Reads applicant prose on stdin and prints one JSON object:
    {"articles": [{"provision", "division", "committed"}...],     ranked
     "section_c": [{"provision", "division", "pairs": [{"function", "objective", "condition"}]}...],
     "engineering_required": ..., "intake_action": ..., "questions": [...]}

Pipeline: the same configured exhaustive screen, rerank, full-text quote verifier, and exact-config
calibration gate as the identify API. The default uses Elephant. Uncalibrated or failed
runs never commit; Section C remains deterministic lookup for calibrated commits only.

The judge runs this from a temporary directory, so call it by absolute path:
    SSL_CERT_FILE=/etc/ssl/cert.pem /path/.venv/bin/python /path/engine/cli_sut.py < prose.txt
"""
from __future__ import annotations

import json
import sys
from dataclasses import replace
from pathlib import Path

if __package__ in (None, ''):                      # run as a script from any directory
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from engine.codes import Codes, default_db  # noqa: E402
from engine.identify import Judge  # noqa: E402
from engine.identify.config import load_config  # noqa: E402
from engine.identify.pipeline import run as identify_run  # noqa: E402
from engine.identify.providers import transports  # noqa: E402
from engine.section_c import section_c_rows  # noqa: E402

TOP_K = 10


def section_c(article_ids: list[str], codes: Codes) -> list[dict]:
    rows = []
    for row in section_c_rows(article_ids, codes):
        pairs, seen = [], set()
        for p in row.pairs:
            key = (p.function, p.objective, p.application_note)
            if key not in seen:
                seen.add(key)
                pairs.append({'function': p.function, 'objective': p.objective, 'condition': p.application_note})
        rows.append({'provision': row.provision_id, 'division': 'B', 'citation': row.citation,
                     'attribution_status': row.attribution_status, 'pairs': pairs})
    return rows


def run(prose: str, db_path: Path | str | None = None, judge: Judge | None = None) -> dict:
    db = Path(db_path) if db_path else default_db()
    config = load_config()
    tp = None
    if judge is not None:
        config = replace(config, screen=judge.method, screen_model=judge.model,
                         rerank=judge.method, rerank_model=judge.model, card_chars=judge.chars)
        tp = transports(scoring={config.screen, config.rerank}, anthropic=config.verifier == 'anthropic')
        if judge.method == 'elephant':
            tp.elephant = judge.ask
        elif judge.method == 'decisions':
            tp.decisions = judge.ask
        else:
            tp.jev = judge.ask
    codes = Codes(db)
    result = identify_run(prose, codes=codes, config=config, transports=tp).result
    out_articles = [{'provision': a.provision, 'division': 'B', 'committed': a.provision in result.committed,
                     'title': a.title, 'part': a.part, 'probability': a.probability} for a in result.articles]
    return {
        'articles': out_articles,
        'section_c': section_c(result.committed, codes) if result.committed else [],
        'engineering_required': result.engineering_required,
        'intake_action': 'proceed_conditionally' if result.committed else 'ask',
        'questions': result.questions,
        'trace': {**result.trace.model_dump(), 'commit_policy': result.commit_policy},
    }


def main() -> int:
    prose = sys.stdin.read().strip()
    if not prose:
        print('cli_sut: no prose on stdin', file=sys.stderr)
        return 2
    print(json.dumps(run(prose), indent=2))
    return 0


if __name__ == '__main__':
    sys.exit(main())
