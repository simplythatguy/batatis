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


def clip_marker(page) -> str:
    """Page from the enclosing attribution, or the edition when the page is unknown."""
    if isinstance(page, bool):
        page = None
    if isinstance(page, int) and page > 0:
        return f'… [clipped, see NBC p.{page}]'
    if isinstance(page, str) and page.isdigit() and int(page) > 0:
        return f'… [clipped, see NBC p.{int(page)}]'
    return '… [clipped, see NBC(AE) 2023]'


def _page(node: dict, inherited):
    own = node.get('pdf_page')
    if isinstance(own, int) and not isinstance(own, bool) and own > 0:
        return own
    if isinstance(own, str) and own.isdigit() and int(own) > 0:
        return int(own)
    return inherited


def _clip_node(node, key: str | None, page):
    """Return (value, whether any string in this node was clipped)."""
    if isinstance(node, str):
        if key in SAFE_KEYS:
            return node, False
        found = words(node)
        if len(found) <= WORD_LIMIT:
            return node, False
        return ' '.join(found[:WORD_LIMIT]) + ' ' + clip_marker(page), True
    if isinstance(node, list):
        changed = False
        out = []
        for item in node:
            value, did = _clip_node(item, key, page)
            out.append(value)
            changed = changed or did
        return out, changed
    if isinstance(node, dict):
        page = _page(node, page)
        out = {}
        fields = []
        for name, value in node.items():
            if name == 'clipped_fields':
                continue
            new, did = _clip_node(value, name, page)
            out[name] = new
            if did:
                fields.append(name)
        if fields:
            out['clipped_fields'] = fields
            return out, True
        return out, False
    return node, False


def clip_tree(node, key: str | None = None):
    """Clip every string to 25 words. Allowlisted keys (ids, cites, enums, urls) stay whole.

    A clipped string ends with the page marker. Its object gains `clipped_fields`.
    Unclipped strings and objects gain neither.
    """
    value, _did = _clip_node(node, key, None)
    return value


def has_consecutive_words(haystack: str, needle: list[str]) -> bool:
    if not needle:
        return False
    found = words(haystack)
    width = len(needle)
    return any(found[index:index + width] == needle for index in range(len(found) - width + 1))
