"""POST /identify. The per-IP gate runs first. A full spend cap returns keyword search.

The label `keyword search, no AI` is the offline result. It is not a finding that
the design complies. The code database is read only for that keyword list.
"""
from __future__ import annotations

from pydantic import BaseModel, Field

from .codes import Codes, default_db
from .llm_gate import client_ip_from, llm_retry_after
from .spend import ROUTE_IDENTIFY_RERANK, openai_chat_json

KEYWORD_LABEL = 'keyword search, no AI'
MODEL_LABEL = 'model output, not verified'
API_FALLBACK_LABEL = 'API fallback'
IDENTIFY_MODEL = 'gpt-4.1-mini'
IDENTIFY_MAX_OUTPUT = 2_000

# Exact paths that must not return the code database file.
CODEDB_DOWNLOADS = frozenset({
    '/codedb.sqlite',
    '/codedb/build/codedb.sqlite',
    '/api/codedb.sqlite',
    '/api/codedb/build/codedb.sqlite',
})


class IdentifyRequest(BaseModel):
    query: str = Field(min_length=1, max_length=4000)


class IdentifyResponse(BaseModel):
    label: str
    notice: str | None = None
    hits: list[str]


def keyword_hits(query: str, codes: Codes | None = None) -> list[str]:
    """BM25 article ids. An unreadable code database yields an empty list, not a 500."""
    try:
        from .identify.corpus import bm25_rank
        path = codes.db_path if codes is not None else default_db()
        return bm25_rank(query, path, limit=20)[:10]
    except Exception:
        return []


def identify_messages(query: str) -> list[dict[str, str]]:
    """Messages reserved and sent for one identify call."""
    return [{'role': 'user', 'content': query}]


def identify(request, body: IdentifyRequest, *, codes: Codes | None) -> IdentifyResponse | tuple[int, dict, int]:
    """Return a response, or `(429, body, retry_after)` when this IP is over the limit.

    A provider error releases the reservation inside ``openai_chat_json`` and
    comes back here as keyword hits under the label ``API fallback``. That path
    is HTTP 200. Cap and ledger refusals keep ``keyword search, no AI``.
    """
    wait = llm_retry_after(client_ip_from(request))
    if wait is not None:
        return 429, {'detail': f'Live model limit reached; try again in {wait} seconds'}, wait
    hits = keyword_hits(body.query, codes)
    try:
        result = openai_chat_json(
            identify_messages(body.query),
            model=IDENTIFY_MODEL,
            max_completion_tokens=IDENTIFY_MAX_OUTPUT,
            route=ROUTE_IDENTIFY_RERANK,
        )
    except Exception:
        return IdentifyResponse(label=API_FALLBACK_LABEL, notice=None, hits=hits)
    if result.offline:
        # Cap and ledger refusals keep the keyword label and the notice together.
        # A missing notice is only the ordinary offline path (live mode unset).
        return IdentifyResponse(label=KEYWORD_LABEL, notice=result.notice, hits=hits)
    return IdentifyResponse(label=MODEL_LABEL, notice=None, hits=[])
