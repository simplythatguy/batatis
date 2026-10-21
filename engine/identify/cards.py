"""Code-database fields for identify cards: sentence ids, citations, quotes, objective and function codes.

Ported from PR #12 (engine/identify/cards.py), cut to the lookups. Nothing here invents a provision
id or a quote: a sentence id is returned only when exactly one codedb sentence of the article
contains the quote, and objective and function codes come from the attribution tables.
Dev's copyright policy returns code text whole with the NRC link (engine/copyright.py, HttpGuard),
so #12's 25-word clipping is not ported.
"""
from __future__ import annotations

import re

from engine.codes import CodeDbMissing, Codes
from engine.models_identify import Term

_SENTENCE = re.compile(r'^\d+(?:\.\d+){3}\.\(\d+\)$')
_WS = re.compile(r'\s+')
_COMPLIANCE = re.compile(r'\b(?:compl(?:y|ies|ied|iant|iance)|safe(?:ly|ty)?|approv(?:e|ed|al)|acceptable)\b', re.I)
QUOTE_WORDS = 40


def flat(text: str | None) -> str:
    return _WS.sub(' ', text or '').strip()


def provision(codes: Codes | None, provision_id: str | None, division: str = 'B') -> dict | None:
    if codes is None or not provision_id:
        return None
    try:
        return codes.provision(provision_id, division)
    except (CodeDbMissing, FileNotFoundError, ValueError):
        return None


def sentence_for_quote(codes: Codes | None, article_id: str, quote: str | None) -> tuple[str | None, str | None]:
    """(sentence id, verbatim sentence text) when exactly one sentence of the article contains the quote."""
    wanted = flat(quote)
    record = provision(codes, article_id)
    if not wanted or record is None:
        return None, None
    matched = []
    for child in record.get('children') or []:
        if child.get('level') != 'sentence' or not _SENTENCE.match(child.get('id') or ''):
            continue
        full = provision(codes, child['id']) or child
        text = flat(full.get('text'))
        if text and wanted in text:
            matched.append((child['id'], text))
    return matched[0] if len(matched) == 1 else (None, None)


def first_sentence(codes: Codes | None, article_id: str) -> tuple[str | None, str | None]:
    """The article's first sentence (id, verbatim text), the deterministic quote when no verifier quote exists."""
    record = provision(codes, article_id)
    for child in (record or {}).get('children') or []:
        if child.get('level') == 'sentence' and _SENTENCE.match(child.get('id') or ''):
            full = provision(codes, child['id']) or child
            if flat(full.get('text')):
                return child['id'], flat(full.get('text'))
    return None, None


def short(text: str | None, words: int = QUOTE_WORDS) -> str | None:
    """A prefix of verbatim text at a word boundary. Still a substring of the source after flattening."""
    parts = flat(text).split(' ')
    out = ' '.join(parts[:words]).strip()
    return out or None


def citation(codes: Codes | None, provision_id: str | None) -> str | None:
    record = provision(codes, provision_id)
    return record.get('citation') if record else None


def _label(codes: Codes | None, code: str) -> str | None:
    if codes is None:
        return None
    defined = codes.definition(code)
    title = (defined or {}).get('title') if isinstance(defined, dict) else None
    return title if isinstance(title, str) and title.strip() else None


def terms(codes: Codes | None, provision_id: str | None) -> tuple[list[Term], list[Term], bool]:
    """Objective and function codes from the attribution rows of this provision (and, for an article, its
    sentences). Third value is True when the attribution tables have no row for it."""
    record = provision(codes, provision_id)
    if record is None:
        return [], [], True
    rows = list(record.get('attributions') or [])
    if not rows and record.get('level') == 'article':
        for child in record.get('children') or []:
            rows.extend((provision(codes, child.get('id')) or {}).get('attributions') or [])
    objectives: dict[str, Term] = {}
    functions: dict[str, Term] = {}
    for row in rows:
        for code in row.get('objectives') or []:
            objectives.setdefault(code, Term(id=code, label=_label(codes, code)))
        for code in row.get('fs') or []:
            functions.setdefault(code, Term(id=code, label=_label(codes, code)))
    return list(objectives.values()), list(functions.values()), not rows


def model_reason(text: str | None) -> str | None:
    """A model's one-line reason, or None when it claims compliance, safety or approval."""
    reason = flat(text)
    if not reason or _COMPLIANCE.search(reason):
        return None
    return reason[:300]
