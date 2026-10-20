"""Keep code text out of API responses. NRC text is linked, not redistributed."""
from __future__ import annotations

import re

WORD_LIMIT = 25
CODE_TEXT_KEYS = frozenset({'text', 'text_raw', 'function_text', 'objective_text', 'application_note'})
CODE_LIST_KEYS = frozenset({'intents'})
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
    """Truncate provision text fields. Other strings (facts, gap messages) stay whole."""
    if isinstance(node, str):
        if key in CODE_TEXT_KEYS:
            return snippet(node) or ''
        return node
    if isinstance(node, list):
        if key in CODE_LIST_KEYS and all(isinstance(item, str) for item in node):
            return [snippet(item) or '' for item in node]
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
