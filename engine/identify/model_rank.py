"""Optional model rank over the requirement ledger.

The model reads the leading candidates and its picks move toward the front, in its order. A pick counts
only when its quote is word for word in the article (`verify.check_quotes`). The rank only reorders:
the deterministic quote, sentence, citation and Section C terms of every article stay as discovered, and
nothing is added or removed. Rules the applicant decided or named stay ahead of the model's picks.
Without a key, an access code or a working call, the deterministic order stays. On 64 real Alberta
records this rank put a regulator-cited article first in 46 cases, against 26 for the deterministic
order (experiments/workflow-bakeoff-v2).
"""
from __future__ import annotations

import logging
import re
import time
from pathlib import Path

from pydantic import BaseModel, Field

from engine.models_identify import IdentifyResult, StageRecord

from .corpus import articles, bm25_rank, card
from .verify import ClaudeVerifier, Verifier

logger = logging.getLogger(__name__)

# The pool and card length measured in the bakeoff: the ledger's first 45 articles, then 20 keyword hits.
LEDGER_N, KEYWORD_N, POOL_N = 45, 20, 60
CARD_CHARS = 700
REASON_CHARS = 300

RANK_SYSTEM = """You are the code-identification step of an assistant that prepares Alberta alternative-solution \
(variance) applications under the National Building Code - 2023 Alberta Edition, 2nd printing (NBC(AE) 2023), \
Division B. You get an applicant's proposal and a numbered list of candidate Division B articles (id, title, place \
in the code, opening text). Choose the articles that the described design departs from, or that the application \
must address, ranked most important first, at most 8. The first pick is the benchmark: the acceptable solution the \
design most directly departs from or asks about.
Rules:
- Use only article ids from the list, copied exactly. Never recall or invent an article number.
- For every pick, copy a verbatim quote of 6 to 40 words from that article's text that shows why it applies, and give \
a one-line reason in plain language.
- If no candidate fits, return no picks.
- Never say the design complies, is safe, is acceptable or is approved."""


class RankPick(BaseModel):
    article: str = Field(description='Article id exactly as listed, e.g. 9.10.15.5.')
    quote: str = Field(description='Verbatim text copied from that article')
    reason: str = Field(description='One plain sentence: why the application has to address this article')
    confidence: float = Field(ge=0, le=1)


class RankPicks(BaseModel):
    picks: list[RankPick]


class RankVerifier(ClaudeVerifier):
    """The request the bakeoff measured: numbered candidates, each its title, place and first 700 characters."""

    system = RANK_SYSTEM
    output_format = RankPicks

    def prompt(self, query: str, candidates: list[str]) -> str:
        listed = '\n'.join(f'[{n}] {a} {card(self.arts[a], CARD_CHARS)}' for n, a in enumerate(candidates, 1))
        return f'Applicant description:\n<<<\n{query}\n>>>\n\nCandidate articles ({len(candidates)}):\n{listed}'


def pool(result: IdentifyResult, prose: str, db: Path) -> list[str]:
    arts = articles(db)
    ledger = [a.provision for a in result.articles if a.provision in arts][:LEDGER_N]
    keyword = [a for a in bm25_rank(prose, db) if a in arts][:KEYWORD_N]
    return list(dict.fromkeys(ledger + keyword))[:POOL_N]


_ARTICLE_ID = re.compile(r'\b\d{1,2}\.\d{1,2}\.\d{1,2}(?:\.\d{1,2})?\b')
_MEETS = re.compile(r'\b(?:meets?|meeting|satisf(?:y|ies|ied)|conforms?|acceptable)\b', re.I)


def safe_reason(text: str | None) -> str | None:
    """The model's one line, or None when it judges the design, names a provider or cites a number."""
    from engine.intake.review import sentences, verdict
    from engine.public_names import names_a_provider
    from .cards import model_reason
    reason = model_reason(text)
    if reason is None or names_a_provider(reason) or _ARTICLE_ID.search(reason) or _MEETS.search(reason):
        return None
    if any(verdict(sentence) for sentence in sentences(reason)):
        return None
    return reason[:REASON_CHARS]


def _tier(record) -> int:
    kinds = {d.kind for d in record.discoveries}
    return 0 if kinds & {'human', 'previous'} else 1 if 'explicit' in kinds else 2


def apply(result: IdentifyResult, picks: list[tuple[str, str | None]]) -> None:
    """Move picked articles forward, after the rules the applicant decided or named. Only the order changes."""
    position = {article: n for n, (article, _) in enumerate(picks)}
    if not position:
        return
    last = len(position)
    result.requirements.sort(key=lambda r: (_tier(r), position.get(r.provision_id, last) if r.division == 'B' else last))
    ledger = {r.provision_id: n for n, r in enumerate(result.requirements) if r.division == 'B'}
    result.articles.sort(key=lambda a: ledger.get(a.provision, len(ledger)))
    reasons = dict(picks)
    for rank, article in enumerate(result.articles, 1):
        article.rank = rank
        if article.provision in position:
            article.verifier = 'picked'
            article.reason = safe_reason(reasons[article.provision]) or article.reason
    result.trace.picks = [article for article, _ in picks]


def model_rank(result: IdentifyResult, prose: str, db: Path, verifier: Verifier, model: str | None) -> None:
    started = time.monotonic()
    record = StageRecord(stage='model_rank', method='anthropic', model=model, requests=1)
    try:
        checked = verifier.verify(prose, pool(result, prose, Path(db)))
    except Exception as exc:                      # the deterministic order is the fallback, never an error
        logger.warning('model rank skipped: %s', type(exc).__name__)
        record.errors, record.detail = 1, 'skipped: the deterministic order stands'
        result.trace.stages.append(record)
        return
    record.seconds = round(time.monotonic() - started, 3)
    record.input_tokens = checked.usage.get('input_tokens')
    record.output_tokens = checked.usage.get('output_tokens')
    result.trace.stages.append(record)
    apply(result, [(pick.article, pick.reason) for pick in checked.picks])
    if checked.picks:
        from engine.public_names import public_stage_model
        result.model_ids = {**result.model_ids, 'verifier': public_stage_model('anthropic', model)}


def carry(result: IdentifyResult, previous: IdentifyResult) -> None:
    """A save re-runs the deterministic search; the last model order carries over without a new call.
    A stored result keeps its picks in the trace, not its article cards (`compact.compact_identify`)."""
    reasons = {a.provision: a.reason for a in previous.articles if a.verifier == 'picked'}
    apply(result, [(article, reasons.get(article)) for article in previous.trace.picks])
