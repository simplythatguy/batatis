"""Attach NRC attribution to code text. The text is returned whole."""
from __future__ import annotations

import re

from .privacy import PII_NOTICE

NRC_PUBLICATION_URL = (
    'https://nrc-publications.canada.ca/eng/view/ft/?id=0316d953-0d55-4311-af69-cad55efec499'
)
# Prose copied from the code. Identifiers, citations, and URLs are not in this set.
# `quote` is not in this set: it counts only when its source type is `code`.
PROSE_KEYS = frozenset({
    'text', 'text_raw', 'objective_text', 'function_text', 'application_note',
})
# List items under these keys are prose when they are sentences, not clause letters.
LIST_PROSE_KEYS = frozenset({
    'clauses', 'notes', 'attribution_notes', 'intents',
})
_WORD = re.compile(r'\S+')


def words(text: str) -> list[str]:
    return _WORD.findall(text)


def _source_type(parent) -> str | None:
    """`code`, `user_text`, and the other fact source types, from this object or its `source`."""
    if not isinstance(parent, dict):
        return None
    source = parent.get('source')
    if isinstance(source, dict) and isinstance(source.get('type'), str):
        return source['type']
    kind = parent.get('type')
    if kind in ('code', 'file', 'user_text', 'drawing', 'user_click'):
        return kind
    return None


def is_nrc_string(key, text, parent=None) -> bool:
    """True when this string is NRC code text that keeps its citation and the publication link.

    A `quote` or a fact `value` counts only when `source.type` is `code`.
    Applicant `user_text` and engine question strings are not code text.
    Provision fields (`text`, intent notes, and the rest of PROSE_KEYS) count
    when the object is not itself an applicant source.
    """
    if not isinstance(text, str) or not key:
        return False
    if key in ('question', 'questions', 'prompt', 'message', 'fix_hint', 'label'):
        return False
    kind = _source_type(parent)
    if key in ('quote', 'value'):
        return kind == 'code'
    if kind not in (None, 'code'):
        return False
    if key in PROSE_KEYS:
        return True
    if key in LIST_PROSE_KEYS and len(words(text)) >= 2:
        return True
    return False


def _holds_code(node, key=None, parent=None) -> bool:
    if isinstance(node, dict):
        return any(_holds_code(value, name, node) for name, value in node.items())
    if isinstance(node, list):
        return any(_holds_code(item, key, parent) for item in node)
    return isinstance(node, str) and is_nrc_string(key, node, parent)


def attribute_code(node, key=None, parent=None):
    """Return code text unchanged and put the NRC publication link on each object that carries it.

    A citation already on the object stays. Applicant text is left alone and gets no link.
    """
    if isinstance(node, dict):
        out = {}
        for name, value in node.items():
            if name in ('clipped', 'clipped_fields'):
                continue
            out[name] = attribute_code(value, name, node)
        if _holds_code(node) and 'url' not in out and 'href' not in out:
            out['url'] = NRC_PUBLICATION_URL
        return out
    if isinstance(node, list):
        return [attribute_code(item, key, parent) for item in node]
    return node


def attach_meta(payload):
    """Put the privacy notice on every JSON body. Arrays stay addressable under `items`."""
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
