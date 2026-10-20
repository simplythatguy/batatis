"""Serve NRC quotes through the copyright clipper.

Applicant `user_text`, files, drawings, and clicks stay as written. A snippet
over 25 words keeps the clipper's marker. Short text is unchanged.
"""
from __future__ import annotations

from .copyright import SNIPPET_MAX_WORDS, clip_marker, clip_response, snippet, words

_APPLICANT = frozenset({'user_text', 'file', 'drawing', 'user_click'})
# `snippet` is not an NRC key in the clipper. Cards still serve it as provision text.
_QUOTE_KEYS = frozenset({'snippet', 'requirement_snippet', 'quote'})


def _page(node: dict, inherited):
    for key in ('pdf_page', 'page'):
        own = node.get(key)
        if isinstance(own, bool):
            continue
        if isinstance(own, int) and own > 0:
            return own
        if isinstance(own, str) and own.isdigit() and int(own) > 0:
            return int(own)
    return inherited


def _kind(node: dict) -> str | None:
    source = node.get('source')
    if isinstance(source, dict) and isinstance(source.get('type'), str):
        return source['type']
    kind = node.get('type')
    return kind if isinstance(kind, str) else None


def _clip_string(text: str, page, owner: dict) -> str:
    flat = ' '.join(text.split())
    if len(words(flat)) <= SNIPPET_MAX_WORDS:
        return flat
    owner['clipped'] = True
    return snippet(flat) + ' ' + clip_marker(page)


def _walk(node, page=None) -> None:
    if isinstance(node, dict):
        page = _page(node, page)
        kind = _kind(node)
        applicant = kind in _APPLICANT
        for key, value in list(node.items()):
            if isinstance(value, str) and key in _QUOTE_KEYS and not applicant:
                # A code quote was already clipped, with its marker, by clip_response.
                if key == 'quote' and kind == 'code':
                    continue
                node[key] = _clip_string(value, page, node)
            else:
                _walk(value, page)
    elif isinstance(node, list):
        for item in node:
            _walk(item, page)


def clip_body(node):
    """Apply the copyright budget, then snippet fields that budget does not name."""
    if not isinstance(node, (dict, list)):
        return node
    clipped = clip_response(node)
    _walk(clipped)
    return clipped
