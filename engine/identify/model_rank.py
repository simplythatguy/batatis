"""Optional model rank over the requirement ledger.

The model reads the leading candidates and its picks move toward the front, in its order. A pick counts
only when its quote is word for word in the article (`verify.check_quotes`). On its own the rank only
reorders: the deterministic quote, sentence, citation and Section C terms of every article stay as
discovered, and nothing is added or removed. Rules the applicant decided or named stay ahead of the model's picks.
Without a key, an access code or a working call, the deterministic order stays. On 64 real Alberta
records this rank put a regulator-cited article first in 46 cases, against 26 for the deterministic
order (experiments/workflow-bakeoff-v2).

With a table-of-contents search (`model_rank_toc`), the model first reads every Division B article id with
its title and place, and names up to 12. Those that are real Division B articles lead a widened pool of 72,
and the same rank runs over it. A pick that discovery did not reach joins the ledger, built from the source
(`requirements.add_found`). In the bakeoff this put a cited article first in 54 of 64 cases.
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
# The table-of-contents search: up to 12 named articles lead, then the pool above, 72 in all.
TOC_N, TOC_POOL_N = 12, 72
CARD_CHARS = 700
REASON_CHARS = 300
OPENING_WORDS = 14             # an added article's quote, when a save has no other: its opening words

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


# The bakeoff's R0 request, word for word (experiments/workflow-bakeoff-v2/requests.py).
TOC_SYSTEM = """You are the candidate-search step of an assistant that prepares Alberta alternative-solution (variance) applications under the NBC(AE) 2023, Division B.
You get an applicant's description and the full table of contents of Division B: every article id with its title and its place in the code (Part > Section > Subsection).
Name up to 12 articles from the table of contents that the application most likely has to address: the acceptable solution the design departs from or asks about, and the articles that set its scope, limits or exceptions. Think about which Part applies (Part 9 for houses and small buildings, Part 3 for larger buildings, Parts 4 to 6 for structure, environmental separation and mechanical systems) and use the titles.
Use only ids from the table of contents, copied exactly with the trailing period. Never invent an id. Give a short reason for each.
Answer with the JSON object only."""
_TOC_ID = re.compile(r'(\d{1,2}\.\d{1,2}\.\d{1,2}\.\d{1,2})\.?(?:\(\d+\))*(?:\([a-z]\))*')


class TocCandidate(BaseModel):
    id: str
    why: str


class TocCandidates(BaseModel):
    candidates: list[TocCandidate]


def toc_text(arts: dict[str, dict]) -> str:
    """One line per Division B article, in code order: id, title and place."""
    return '\n'.join(f"{a} {art['title']} (Part {art['part']} > {art['section']} > {art['subsection']})"
                     for a, art in arts.items())


def toc_article(raw: str) -> str | None:
    """'9.10.15.5' or '9.10.15.5.(8)(a)' -> '9.10.15.5.'; anything else -> None."""
    match = _TOC_ID.fullmatch((raw or '').strip().replace(' ', ''))
    return match[1] + '.' if match else None


def toc_candidates(named: list[str], arts: dict[str, dict], n: int = TOC_N) -> tuple[list[str], int]:
    """The named ids that are Division B articles, deduplicated, first n; and how many named ids were not."""
    ids = [toc_article(raw) for raw in named]
    real = [a for a in ids if a in arts]
    return list(dict.fromkeys(real))[:n], len(ids) - len(real)


class RankPick(BaseModel):
    article: str = Field(description='Article id exactly as listed, e.g. 9.10.15.5.')
    quote: str = Field(description='Verbatim text copied from that article')
    reason: str = Field(description='One plain sentence: why the application has to address this article')
    confidence: float = Field(ge=0, le=1)


class RankPicks(BaseModel):
    picks: list[RankPick]


_BARE_ID = re.compile(r'^\s*(\d{1,2}(?:\.\d{1,2}){3})\.?\s*$')


def article_id(text: str) -> str:
    """An article id as the code writes it, with its trailing period; anything else is left as it came."""
    match = _BARE_ID.match(text or '')
    return f'{match.group(1)}.' if match else text


class RankVerifier(ClaudeVerifier):
    """The request the bakeoff measured: numbered candidates, each its title, place and first 700 characters."""

    system = RANK_SYSTEM
    output_format = RankPicks

    def picks(self, parsed) -> list:
        """The bakeoff read each id with its trailing period restored; a pick written "9.10.15.4" counts."""
        return [pick.model_copy(update={'article': article_id(pick.article)}) for pick in parsed.picks]

    def prompt(self, query: str, candidates: list[str]) -> str:
        listed = '\n'.join(f'[{n}] {a} {card(self.arts[a], CARD_CHARS)}' for n, a in enumerate(candidates, 1))
        return f'Applicant description:\n<<<\n{query}\n>>>\n\nCandidate articles ({len(candidates)}):\n{listed}'

    def toc_prompt(self, query: str) -> str:
        return (f'Applicant description:\n<<<\n{query}\n>>>\n\n'
                f'Table of contents of Division B (one article per line):\n{toc_text(self.arts)}')

    def search(self, query: str, n: int = TOC_N) -> tuple[list[str], int, dict]:
        """(Division B article ids the model named from the table of contents, ids dropped, usage)."""
        resp = self.client.messages.parse(
            model=self.model, max_tokens=self.max_tokens, system=TOC_SYSTEM,
            output_config={'effort': self.effort}, output_format=TocCandidates,
            messages=[{'role': 'user', 'content': self.toc_prompt(query)}])
        usage = {'input_tokens': resp.usage.input_tokens, 'output_tokens': resp.usage.output_tokens}
        named = [c.id for c in resp.parsed_output.candidates] if resp.parsed_output is not None else []
        ids, dropped = toc_candidates(named, self.arts, n)
        return ids, dropped, usage


def pool(result: IdentifyResult, prose: str, db: Path, lead: list[str] = ()) -> list[str]:
    """The ledger's leading articles and keyword hits; with `lead` (table-of-contents ids) first, 72 in all."""
    arts = articles(db)
    ledger = [a.provision for a in result.articles if a.provision in arts][:LEDGER_N]
    keyword = [a for a in bm25_rank(prose, db) if a in arts][:KEYWORD_N]
    base = list(dict.fromkeys(ledger + keyword))[:POOL_N]
    return list(dict.fromkeys([*lead, *base]))[:TOC_POOL_N] if lead else base


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


def _search(result: IdentifyResult, prose: str, verifier, model: str | None, n: int) -> list[str] | None:
    """The table-of-contents ids, or None when the call failed (the normal pool is ranked)."""
    started = time.monotonic()
    record = StageRecord(stage='model_search', method='anthropic', model=model, requests=1)
    result.trace.stages.append(record)
    try:
        ids, dropped, usage = verifier.search(prose, n)
    except Exception as exc:                      # the normal pool is the fallback, never an error
        logger.warning('table-of-contents search skipped: %s', type(exc).__name__)
        record.errors, record.detail = 1, 'skipped: the normal pool is ranked'
        return None
    record.seconds = round(time.monotonic() - started, 3)
    record.input_tokens, record.output_tokens = usage.get('input_tokens'), usage.get('output_tokens')
    record.detail = f'{len(ids)} candidates; {dropped} named ids are not Division B articles'
    return ids


def model_rank(result: IdentifyResult, prose: str, db: Path, verifier: Verifier, model: str | None, *,
               toc: int = 0, facts=()) -> None:
    lead = _search(result, prose, verifier, model, toc) if toc else None
    started = time.monotonic()
    record = StageRecord(stage='model_rank', method='anthropic', model=model, requests=1)
    try:
        checked = verifier.verify(prose, pool(result, prose, Path(db), lead or ()))
    except Exception as exc:                      # the deterministic order is the fallback, never an error
        logger.warning('model rank skipped: %s', type(exc).__name__)
        record.errors, record.detail = 1, 'skipped: the deterministic order stands'
        result.trace.stages.append(record)
        return
    record.seconds = round(time.monotonic() - started, 3)
    record.input_tokens = checked.usage.get('input_tokens')
    record.output_tokens = checked.usage.get('output_tokens')
    record.detail = rank_detail(checked)
    result.trace.stages.append(record)
    if lead is not None:
        _add(result, db, facts, [(pick.article, pick.quote) for pick in checked.picks])
    apply(result, [(pick.article, pick.reason) for pick in checked.picks])
    if checked.picks:
        from engine.public_names import public_stage_model
        result.model_ids = {**result.model_ids, 'verifier': public_stage_model('anthropic', model)}


def rank_detail(checked) -> str:
    """How many picks the quote check kept and dropped, and why, so an empty rank is never silent."""
    reasons: dict[str, int] = {}
    for _, why in checked.dropped:
        reasons[why] = reasons.get(why, 0) + 1
    detail = f'{len(checked.picks)} kept, {len(checked.dropped)} dropped'
    if reasons:
        detail += ' (' + ', '.join(f'{n} {why}' for why, n in reasons.items()) + ')'
    if not checked.picks and not checked.dropped:
        detail += '; no picks returned'
    if checked.stop_reason not in (None, 'end_turn'):
        detail += f'; stopped: {checked.stop_reason}'
    return detail


def _add(result: IdentifyResult, db: Path, facts, found: list[tuple[str, str]]) -> None:
    from .requirements import add_found
    try:
        added = add_found(result, Path(db), facts, found)
    except Exception as exc:                      # an unreadable source adds nothing, never an error
        logger.warning('model-found articles not added: %s', type(exc).__name__)
        return
    result.trace.added = [*result.trace.added, *added]


def carry(result: IdentifyResult, previous: IdentifyResult, db: Path, facts=()) -> None:
    """A save re-runs the deterministic search; the last model order, and the articles the model rank added,
    carry over without a new call. A stored result keeps its picks and ledger, not its article cards."""
    quotes = {r.provision_id: r.quote for r in previous.requirements if r.division == 'B'}
    if any(not quotes.get(a) for a in previous.trace.added):
        texts = articles(Path(db))          # discovery reached it last time, by reference, with no quote
        quotes.update({a: ' '.join(texts[a]['text'].split()[:OPENING_WORDS]) for a in previous.trace.added
                       if not quotes.get(a) and a in texts})
    _add(result, db, facts, [(a, quotes[a]) for a in previous.trace.added if quotes.get(a)])
    ledger = {r.provision_id for r in result.requirements if r.division == 'B'}
    result.trace.added = [a for a in previous.trace.added if a in ledger]
    reasons = {a.provision: a.reason for a in previous.articles if a.verifier == 'picked'}
    apply(result, [(a, reasons.get(a)) for a in previous.trace.picks])
