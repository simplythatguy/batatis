"""Keep NRC code text inside one response budget. The code is linked, not redistributed."""
from __future__ import annotations

import re

SNIPPET_WORD_LIMIT = 25
RESPONSE_WORD_BUDGET = 75
WORD_LIMIT = SNIPPET_WORD_LIMIT
NRC_PUBLICATION_URL = (
    'https://nrc-publications.canada.ca/eng/view/ft/?id=0316d953-0d55-4311-af69-cad55efec499'
)
PII_NOTICE = 'Do not upload personal information. Demo data may be deleted.'
# Prose copied from the code. Identifiers, citations, and URLs are not in this set.
PROSE_KEYS = frozenset({
    'text', 'text_raw', 'objective_text', 'function_text', 'application_note', 'quote',
})
# List items under these keys are prose when they are sentences, not clause letters.
LIST_PROSE_KEYS = frozenset({
    'clauses', 'notes', 'attribution_notes', 'intents',
})
_WORD = re.compile(r'\S+')


def words(text: str) -> list[str]:
    return _WORD.findall(text)


def snippet(text: str | None, limit: int = SNIPPET_WORD_LIMIT) -> str | None:
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


def is_nrc_string(key, text, parent=None) -> bool:
    """True when this string is NRC code text the response budget has to count."""
    if not isinstance(text, str) or not key:
        return False
    if key in PROSE_KEYS:
        return True
    if key in LIST_PROSE_KEYS and len(words(text)) >= 2:
        return True
    if key == 'value' and isinstance(parent, dict):
        source = parent.get('source')
        if isinstance(source, dict) and source.get('type') == 'code':
            return True
    return False


def _page(node: dict, inherited):
    own = node.get('pdf_page')
    if isinstance(own, int) and not isinstance(own, bool) and own > 0:
        return own
    if isinstance(own, str) and own.isdigit() and int(own) > 0:
        return int(own)
    return inherited


class _Budget:
    def __init__(self) -> None:
        self.left = RESPONSE_WORD_BUDGET


def _mark(owners: list[dict]) -> None:
    """Flag every ancestor. The object that holds the string gains the NRC link."""
    for owner in owners:
        owner['clipped'] = True
    if owners and 'url' not in owners[0] and 'href' not in owners[0]:
        owners[0]['url'] = NRC_PUBLICATION_URL


def _clip_string(text: str, page, budget: _Budget, owners: list[dict]) -> str:
    found = words(text)
    if not found:
        return text
    room = min(SNIPPET_WORD_LIMIT, budget.left)
    if len(found) <= room:
        budget.left -= len(found)
        return text
    _mark(owners)
    if room <= 0:
        return clip_marker(page)
    budget.left -= room
    return ' '.join(found[:room]) + ' ' + clip_marker(page)


def _walk(node, key, page, budget: _Budget, owners: list[dict], parent):
    if isinstance(node, dict):
        page = _page(node, page)
        out: dict = {}
        child_owners = [out, *owners]
        for name, value in node.items():
            if name in ('clipped', 'clipped_fields'):
                continue
            out[name] = _walk(value, name, page, budget, child_owners, node)
        return out
    if isinstance(node, list):
        return [_walk(item, key, page, budget, owners, parent) for item in node]
    if isinstance(node, str) and is_nrc_string(key, node, parent):
        return _clip_string(node, page, budget, owners)
    return node


def clip_response(node):
    """Apply the response budget to one JSON body.

    Each NRC snippet is at most 25 words. The body keeps at most 75 words of NRC text.
    Past that, the string is the page marker only, and the object keeps its citation,
    gains the NRC link, and sets clipped to true.
    """
    return _walk(node, None, None, _Budget(), [], None)


def clip_tree(node, key: str | None = None):
    """Same guard as clip_response. `key` applies when `node` itself is an NRC string."""
    if isinstance(node, str):
        return _walk(node, key, None, _Budget(), [], None)
    return clip_response(node)


def attach_meta(payload):
    """Put the demo notice on every JSON body. Arrays stay addressable under `items`."""
    notice = {'notice': PII_NOTICE}
    if isinstance(payload, dict):
        out = dict(payload)
        out['meta'] = notice
        return out
    if isinstance(payload, list):
        return {'items': payload, 'meta': notice}
    return payload


def has_consecutive_words(haystack: str, needle: list[str]) -> bool:
    if not needle:
        return False
    found = words(haystack)
    width = len(needle)
    return any(found[index:index + width] == needle for index in range(len(found) - width + 1))
