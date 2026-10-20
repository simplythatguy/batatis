"""POST /identify. The per-IP gate runs first. A full spend cap returns keyword search.

The label `keyword search, no AI` is the offline result. It is not a finding that
the design complies. The code database is read only for that keyword list.
"""
from __future__ import annotations

from pydantic import BaseModel, Field

from .codes import Codes, default_db
from .llm_gate import client_ip_from, llm_retry_after
from .spend import CAP_NOTICE, ROUTE_IDENTIFY_RERANK, keyed_openai_call

KEYWORD_LABEL = 'keyword search, no AI'
IDENTIFY_MODEL = 'gpt-4.1-mini'
IDENTIFY_MAX_INPUT = 16_000
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


def identify(request, body: IdentifyRequest, *, codes: Codes | None, client) -> IdentifyResponse | tuple[int, dict, int]:
    """Return a response, or `(429, body, retry_after)` when this IP is over the limit."""
    wait = llm_retry_after(client_ip_from(request))
    if wait is not None:
        return 429, {'detail': f'Live model limit reached; try again in {wait} seconds'}, wait
    result = keyed_openai_call(
        route=ROUTE_IDENTIFY_RERANK,
        model=IDENTIFY_MODEL,
        max_input_tokens=IDENTIFY_MAX_INPUT,
        max_output_tokens=IDENTIFY_MAX_OUTPUT,
        client=client,
    )
    if result.offline:
        notice = result.notice if result.notice == CAP_NOTICE else result.notice
        return IdentifyResponse(label=KEYWORD_LABEL, notice=notice, hits=keyword_hits(body.query, codes))
    return IdentifyResponse(label='model', notice=None, hits=[])
