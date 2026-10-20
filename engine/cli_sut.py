"""Command-line system under test for the held-out judge (run_judge.py contract).

Reads applicant prose on stdin and prints one JSON object:
    {"articles": [{"provision", "division", "committed"}...],     ranked
     "section_c": [{"provision", "division", "pairs": [{"function", "objective", "condition"}]}...],
     "engineering_required": ..., "intake_action": ..., "questions": [...]}

Pipeline: engine.identify (Jev screen of every Division B article, then one-request rerank) -> optional
verifier (only when ANTHROPIC_API_KEY is set) -> commit Part 9 articles whose rerank probability is at least
COMMIT_THRESHOLD (at most MAX_COMMITS); everything else is returned uncommitted -> Section C by deterministic lookup
(engine.section_c) for committed articles only. If Jev fails, falls back to BM25 order with no commits.

The judge runs this from a temporary directory, so call it by absolute path:
    SSL_CERT_FILE=/etc/ssl/cert.pem /path/.venv/bin/python /path/engine/cli_sut.py < prose.txt
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

if __package__ in (None, ''):                      # run as a script from any directory
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from engine.codes import Codes, default_db  # noqa: E402
from engine.identify import Judge, articles, bm25_rank, identify  # noqa: E402
from engine.section_c import section_c_rows  # noqa: E402

COMMIT_THRESHOLD = 0.75    # rerank probability; placeholder until fitted on the calibration fold (plan, day 7)
MAX_COMMITS = 3            # placeholder cap: rerank probabilities run high, and each commit adds whole-article rows
COMMIT_PARTS = {9}         # Part 9 commits automatically; other Parts are quoted choices (2-week-build.md)
TOP_K = 10                 # articles returned, ranked
RERANK_N = 60              # articles re-judged together after the screen
VERIFY_N = 15              # rerank top-N the verifier reads in full
QUESTION_K = 3             # uncommitted choices turned into confirmation questions


def _verify(prose: str, db: Path, ranked: list[str], trace: dict) -> list[str] | None:
    """Verifier picks (quote-checked, in rank order), or None when it is skipped or fails."""
    if not os.environ.get('ANTHROPIC_API_KEY'):
        trace['verifier'] = 'skipped: ANTHROPIC_API_KEY not set'
        return None
    try:
        from engine.identify.verify import ClaudeVerifier
        v = ClaudeVerifier(db).verify(prose, ranked[:VERIFY_N])
    except Exception as e:                          # a verifier failure must not sink the run
        trace['verifier'] = f'failed: {type(e).__name__}'
        return None
    trace['verifier'] = {'picks': [p.article for p in v.picks], 'dropped': len(v.dropped)}
    return [p.article for p in v.picks]


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


def typesafe_ask(model: str | None = None):
    """The one Jev/TypeSafe call site outside the vendored client. Refused in live mode."""
    from engine.openai_only import refuse_non_openai
    refuse_non_openai('Jev client')
    from engine.identify.jevkit import client
    from engine.identify.screen import JEV_MODEL, JEV_PROVIDER
    pinned = model or JEV_MODEL

    def ask(state, questions, timeout):
        return client.ask(state, questions, timeout=timeout, model=pinned, provider=JEV_PROVIDER)
    return ask


def run(prose: str, db_path: Path | str | None = None, judge: Judge | None = None) -> dict:
    db = Path(db_path) if db_path else default_db()
    arts = articles(db)
    trace: dict = {}
    try:
        ident = identify(prose, db, judge, rerank_n=RERANK_N)
        ranked = [(a, p) for a, p in ident.ranked]
        trace.update(ranker=f'jev screen+rerank ({ident.model})', usage=ident.usage)
    except Exception as e:                          # Jev unreachable or key missing: BM25 baseline, commit nothing
        ranked = [(a, None) for a in bm25_rank(prose, db)[:RERANK_N]]
        trace.update(ranker='bm25 fallback', error=f'{type(e).__name__}: {e}'[:300])

    picks = _verify(prose, db, [a for a, _ in ranked], trace) if trace['ranker'] != 'bm25 fallback' else None
    if picks is not None:                           # verifier picks lead, then the rest in rerank order
        prob = dict(ranked)
        ranked = [(a, prob.get(a)) for a in picks] + [(a, p) for a, p in ranked if a not in picks]

    out_articles, n_committed = [], 0
    for a, p in ranked[:TOP_K]:
        committed = (n_committed < MAX_COMMITS and p is not None and p >= COMMIT_THRESHOLD
                     and arts[a]['part'] in COMMIT_PARTS and (picks is None or a in picks))
        n_committed += committed
        out_articles.append({'provision': a, 'division': 'B', 'committed': committed,
                             'title': arts[a]['title'], 'part': arts[a]['part'],
                             'probability': None if p is None else round(p, 4)})

    committed_ids = [x['provision'] for x in out_articles if x['committed']]
    rows = section_c(committed_ids, Codes(db)) if committed_ids else []
    questions = [f"Does your design meet, rely on, or depart from the requirement on "
                 f"\"{x['title']}\" (Division B, Article {x['provision']})?"
                 for x in out_articles if not x['committed']][:QUESTION_K]

    return {
        'articles': out_articles,
        'section_c': rows,
        # TODO: engineering_required needs the Division C professional-involvement rules; placeholder for now.
        'engineering_required': 'depends',
        # TODO: intake_action needs the missing-fact and out-of-scope checks; placeholder from commit coverage.
        'intake_action': 'proceed_conditionally' if committed_ids else 'ask',
        'questions': questions,
        'trace': {**trace, 'commit_threshold': COMMIT_THRESHOLD, 'max_commits': MAX_COMMITS,
              'commit_parts': sorted(COMMIT_PARTS)},
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
