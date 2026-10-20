"""Keep code text out of API responses. NRC text is linked, not redistributed."""
from __future__ import annotations

import re

WORD_LIMIT = 25
# Identifiers, citations, enums, and URLs stay whole. Every other string is clipped.
SAFE_KEYS = frozenset({
    'id', 'provision_id', 'parent_id', 'case_id', 'doc', 'note_id', 'article_id',
    'table_id', 'root_provision', 'related_root', 'sort_key', 'code',
    'citation',
    'division', 'level', 'kind', 'status', 'type', 'source',
    'attribution_status', 'intent_comparison', 'related_root_method', 'root_method',
    'url', 'href',
    'title', 'article_title', 'objective', 'function', 'bracket', 'label',
    'clause', 'subclause',
})
_WORD = re.compile(r'\S+')


def words(text: str) -> list[str]:
    return _WORD.findall(text)


def snippet(text: str | None, limit: int = WORD_LIMIT) -> str | None:
    """At most `limit` words. Short strings are returned unchanged."""
    if text is None:
        return None
    found = words(text)
    if len(found) <= limit:
        return text
    return ' '.join(found[:limit])


def clip_tree(node, key: str | None = None):
    """Clip every string to 25 words. Allowlisted keys (ids, cites, enums, urls) stay whole."""
    if isinstance(node, str):
        if key in SAFE_KEYS:
            return node
        return snippet(node) or ''
    if isinstance(node, list):
        return [clip_tree(item, key) for item in node]
    if isinstance(node, dict):
        return {name: clip_tree(value, name) for name, value in node.items()}
    return node


def has_consecutive_words(haystack: str, needle: list[str]) -> bool:
    if not needle:
        return False
    found = words(haystack)
    width = len(needle)
    return any(found[index:index + width] == needle for index in range(len(found) - width + 1))
