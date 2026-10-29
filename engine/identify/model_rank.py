"""Optional model rank over the requirement ledger.

The configured verifier reads the leading candidates in full and its quote-checked picks move to the
front, in its order. Nothing is removed, and a pick whose quote is not in the article text is dropped by
`verify.check_quotes`. Without the verifier (no key, no access code, an error) the deterministic order
stays. On 64 real Alberta records this rank put a regulator-cited article first in 46 cases, against 26
for the deterministic order (experiments/workflow-bakeoff-v2).
"""
from __future__ import annotations

import logging
import time
from pathlib import Path

from engine.models_identify import IdentifyResult, StageRecord

from .corpus import articles, bm25_rank, card
from .verify import ClaudeVerifier, Verifier

logger = logging.getLogger(__name__)

# The pool measured in the bakeoff: the ledger's first 45 articles, then 20 keyword hits, at most 60.
LEDGER_N, KEYWORD_N, POOL_N = 45, 20, 60


CARD_CHARS = 700


class RankVerifier(ClaudeVerifier):
    """The request the bakeoff measured: numbered candidates, each its title, place and first 700 characters."""

    def prompt(self, query: str, candidates: list[str]) -> str:
        listed = '\n'.join(f'[{n}] {a} {card(self.arts[a], CARD_CHARS)}' for n, a in enumerate(candidates, 1))
        return f'Applicant description:\n<<<\n{query}\n>>>\n\nCandidate articles ({len(candidates)}):\n{listed}'


def pool(result: IdentifyResult, prose: str, db: Path) -> list[str]:
    arts = articles(db)
    ledger = [a.provision for a in result.articles if a.provision in arts][:LEDGER_N]
    keyword = [a for a in bm25_rank(prose, db) if a in arts][:KEYWORD_N]
    return list(dict.fromkeys(ledger + keyword))[:POOL_N]


def model_rank(result: IdentifyResult, prose: str, db: Path, verifier: Verifier, model: str | None) -> None:
    from engine.intake.review import sentences, verdict
    candidates = pool(result, prose, Path(db))
    started = time.monotonic()
    record = StageRecord(stage='model_rank', method='anthropic', model=model, requests=1)
    try:
        checked = verifier.verify(prose, candidates)
    except Exception as exc:                      # the deterministic order is the fallback, never an error
        logger.warning('model rank skipped: %s', type(exc).__name__)
        record.errors, record.detail = 1, 'skipped: the deterministic order stands'
        result.trace.stages.append(record)
        return
    record.seconds = round(time.monotonic() - started, 3)
    record.input_tokens = checked.usage.get('input_tokens')
    record.output_tokens = checked.usage.get('output_tokens')
    result.trace.stages.append(record)
    order = {pick.article: (n, pick) for n, pick in enumerate(checked.picks)}
    if not order:
        return
    last = len(order)
    result.requirements.sort(key=lambda r: order[r.provision_id][0] if r.division == 'B' and r.provision_id in order else last)
    result.articles.sort(key=lambda a: order[a.provision][0] if a.provision in order else last)
    for rank, article in enumerate(result.articles, 1):
        article.rank = rank
        if article.provision in order:
            pick = order[article.provision][1]
            article.verifier, article.quote, article.quote_source = 'picked', pick.quote, 'verifier'
            reason = ' '.join(s for s in sentences(pick.reason) if not verdict(s)).strip()
            article.reason = reason or None
    result.trace.picks = [pick.article for pick in checked.picks]
    from engine.public_names import public_stage_model
    result.model_ids = {**result.model_ids, 'verifier': public_stage_model('anthropic', model)}
