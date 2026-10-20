"""Verifier: a frontier model reads the full text of shortlisted articles and picks the governing ones.

Every pick must carry a word-for-word quote. Quotes are checked against the database text of the picked
article after whitespace normalization; a pick whose quote does not match is dropped, never repaired.
The verifier ranks; it never decides compliance.
"""
from __future__ import annotations

import os
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol

from pydantic import BaseModel, Field

from .corpus import articles, card

VERIFIER_MODEL = 'claude-sonnet-5-5'

SYSTEM = """You help prepare Alberta alternative-solution (variance) applications under the National Building \
Code - 2023 Alberta Edition. Given a proposal and candidate Division B articles, pick the articles whose \
acceptable-solution requirement the proposal must meet, relies on, or departs from. Rank the most directly \
governing article first. For each pick, copy one sentence or phrase word for word from that article's text \
as the quote that shows the requirement; do not paraphrase, abbreviate or join separate passages. Pick only \
articles from the list. If none govern, return no picks. Do not judge whether the design complies."""


class Pick(BaseModel):
    article: str = Field(description='Article id exactly as listed, e.g. 9.10.15.5.')
    quote: str = Field(description='Verbatim text copied from that article')
    reason: str = Field(description='One sentence: how the proposal meets, relies on, or departs from it')
    confidence: float = Field(ge=0, le=1)


class Picks(BaseModel):
    picks: list[Pick]


@dataclass
class Verification:
    picks: list[Pick]                       # quote-checked, in the model's rank order
    dropped: list[tuple[Pick, str]]         # (pick, why) for picks removed by the quote check
    stop_reason: str | None = None
    usage: dict = field(default_factory=dict)
    seconds: float = 0.0


class Verifier(Protocol):
    def verify(self, query: str, candidates: list[str]) -> Verification: ...


def normalize(text: str) -> str:
    return re.sub(r'\s+', ' ', text).strip()


def check_quotes(picks: list[Pick], candidates: list[str], arts: dict[str, dict]) -> tuple[list[Pick], list]:
    """Keep picks whose article is a candidate and whose quote occurs verbatim (modulo whitespace) in its text."""
    keep, dropped, seen = [], [], set()
    allowed = set(candidates)
    for p in picks:
        if p.article not in allowed or p.article not in arts:
            dropped.append((p, 'article not in candidate list'))
        elif p.article in seen:
            dropped.append((p, 'duplicate article'))
        elif not normalize(p.quote) or normalize(p.quote) not in normalize(card(arts[p.article], None)):
            dropped.append((p, 'quote not found in article text'))
        else:
            keep.append(p)
            seen.add(p.article)
    return keep, dropped


def anthropic_verifier_allowed() -> bool:
    """Live mode and the hosted engine are OpenAI only."""
    from ..openai_only import non_openai_allowed
    return non_openai_allowed()


def _refuse_anthropic() -> None:
    from ..openai_only import refuse_non_openai
    refuse_non_openai('Anthropic verifier')


class ClaudeVerifier:
    """Adapter over the Anthropic Messages API (structured output). `client` is injectable for tests."""

    def __init__(self, db_path: Path | str, *, client=None, model: str = VERIFIER_MODEL, effort: str = 'medium',
                 max_tokens: int = 16000):
        _refuse_anthropic()
        self.arts = articles(Path(db_path))
        self.model, self.effort, self.max_tokens = model, effort, max_tokens
        if client is None:
            import anthropic
            if not os.environ.get('ANTHROPIC_API_KEY'):
                raise RuntimeError('ANTHROPIC_API_KEY is not set')
            client = anthropic.Anthropic()
        self.client = client

    def prompt(self, query: str, candidates: list[str]) -> str:
        listed = '\n\n'.join(f'<article id="{a}">\n{card(self.arts[a], None)}\n</article>' for a in candidates)
        return f'<proposal>\n{query}\n</proposal>\n\n<candidates>\n{listed}\n</candidates>'

    def verify(self, query: str, candidates: list[str]) -> Verification:
        _refuse_anthropic()
        candidates = [a for a in candidates if a in self.arts]
        t0 = time.monotonic()
        resp = self.client.messages.parse(
            model=self.model, max_tokens=self.max_tokens, system=SYSTEM,
            output_config={'effort': self.effort}, output_format=Picks,
            messages=[{'role': 'user', 'content': self.prompt(query, candidates)}])
        seconds = time.monotonic() - t0
        usage = {'input_tokens': resp.usage.input_tokens, 'output_tokens': resp.usage.output_tokens}
        if resp.stop_reason == 'refusal' or resp.parsed_output is None:
            return Verification([], [], resp.stop_reason, usage, seconds)
        keep, dropped = check_quotes(resp.parsed_output.picks, candidates, self.arts)
        return Verification(keep, dropped, resp.stop_reason, usage, seconds)
