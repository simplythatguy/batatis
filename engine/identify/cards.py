"""Shape an identify payload into the article cards the applicant UI renders.

Sentence ids, snippets, and citations come from codedb or from rows already stored
on the payload. A missing sentence stays null. Nothing in this module invents a
provision id or a quote.
"""
from __future__ import annotations

import re

from engine.codes import CodeDbMissing, Codes

_ARTICLE = re.compile(r'^(\d+(?:\.\d+){3}\.)')
_SENTENCE = re.compile(r'^\d+(?:\.\d+){3}\.\(\d+\)$')
_COMPLIANCE = re.compile(r'\b(?:complies|compliant|compliance|safe)\b', re.I)
_WS = re.compile(r'\s+')
SNIPPET_WORDS = 25
EXPLANATION_NOTE = 'This is an explanation of the quoted text.'


def empty_bm25() -> dict:
    """No ranked articles and no citation. Used when BM25 cannot read the code database."""
    return {
        'source': 'bm25',
        'message': None,
        'articles': [],
        'section_c': [],
        'benchmark': {
            'identified': False,
            'role': 'benchmark_acceptable_solution',
            'explanation': None,
            'quote': None,
            'citation': None,
            'section_c': [],
        },
        'questions': [],
        'open_questions': [],
        'mode': 'bm25_fallback',
        'persisted': False,
        'cached': False,
        'model_ids': {'screen': None, 'rerank': None, 'verifier': None, 'invoked': False},
    }


def present(result: dict, codes: Codes | None, mode: str) -> dict:
    """Attach card fields and set the HTTP mode. Idempotent for an already shaped payload."""
    result['mode'] = mode
    stored = _stored_rows(result)
    if mode == 'cached_demo':
        result['source'] = 'cache'
        result['cached'] = True
    elif mode == 'bm25_fallback':
        result['source'] = 'bm25'
        result['cached'] = False
        for article in result.get('articles') or []:
            article['committed'] = False
        result['section_c'] = []
    elif mode == 'live':
        result['source'] = 'live'
        result['cached'] = False
    result['persisted'] = False
    shaped = []
    for index, article in enumerate(result.get('articles') or [], start=1):
        shaped.append(_card(article, index, stored, codes, result, mode))
    result['articles'] = shaped
    return result


def _stored_rows(result: dict) -> list[dict]:
    rows = list(result.get('section_c') or [])
    benchmark = result.get('benchmark') or {}
    rows.extend(benchmark.get('section_c') or [])
    return [row for row in rows if isinstance(row, dict)]


def _flat(text: str | None) -> str:
    return _WS.sub(' ', text or '').strip()


def _words(text: str | None, limit: int = SNIPPET_WORDS) -> str | None:
    flat = _flat(text)
    if not flat:
        return None
    return ' '.join(flat.split(' ')[:limit])


def _article_of(provision: str | None) -> str | None:
    match = _ARTICLE.match(provision or '')
    return match.group(1) if match else None


def _provision(codes: Codes | None, provision_id: str) -> dict | None:
    if codes is None:
        return None
    try:
        return codes.provision(provision_id, 'B')
    except (CodeDbMissing, FileNotFoundError, ValueError):
        return None


def _sentence_id(article_id: str, quote: str | None, stored: list[dict], codes: Codes | None) -> str | None:
    """A sentence id only when one stored row or one codedb sentence contains the quote."""
    rows = [row for row in stored
            if _SENTENCE.match(row.get('provision_id') or '') and _article_of(row.get('provision_id')) == article_id]
    flat_quote = _flat(quote)
    matched: list[str] = []
    if flat_quote:
        for row in rows:
            row_quote = _flat((row.get('explainer') or {}).get('quote') or '')
            if row_quote and (flat_quote in row_quote or row_quote in flat_quote):
                matched.append(row['provision_id'])
        record = _provision(codes, article_id)
        for child in (record or {}).get('children') or []:
            if child.get('level') != 'sentence' or not _SENTENCE.match(child.get('id') or ''):
                continue
            text = _flat(child.get('text') or '')
            if text and (flat_quote in text or text in flat_quote):
                matched.append(child['id'])
        matched = list(dict.fromkeys(matched))
        if len(matched) == 1:
            return matched[0]
        if len(matched) > 1:
            return None
    if len(rows) == 1:
        return rows[0]['provision_id']
    return None


def _snippet(sentence_id: str | None, quote: str | None, stored: list[dict], codes: Codes | None) -> str | None:
    text = None
    if sentence_id:
        record = _provision(codes, sentence_id)
        if record and record.get('text'):
            text = record['text']
        if text is None:
            for row in stored:
                if row.get('provision_id') == sentence_id:
                    text = (row.get('explainer') or {}).get('quote')
                    break
    if text is None:
        text = quote
    return _words(text)


def _citation(sentence_id: str | None, article_id: str, stored: list[dict], codes: Codes | None) -> str | None:
    if sentence_id and codes is not None:
        record = _provision(codes, sentence_id)
        if record and record.get('citation'):
            return record['citation']
    for row in stored:
        if sentence_id and row.get('provision_id') == sentence_id and row.get('citation'):
            return row['citation']
    if codes is not None:
        record = _provision(codes, article_id)
        if record and record.get('citation'):
            return record['citation']
    return None


def _verifier_status(article: dict, result: dict, mode: str) -> str:
    if mode == 'bm25_fallback':
        return 'unknown'
    if article.get('committed'):
        return 'committed'
    verifier = (result.get('trace') or {}).get('verifier')
    if isinstance(verifier, dict) or article.get('stage') == 'verify':
        return 'candidate'
    return 'unknown'


def _explainer(article: dict, sentence_id: str | None, quote: str | None, snippet: str | None,
               stored: list[dict]) -> dict | None:
    if article.get('explainer') and article['explainer'].get('label') == 'explanation':
        return article['explainer']
    row = next((item for item in stored if sentence_id and item.get('provision_id') == sentence_id), None)
    existing = (row or {}).get('explainer') or {}
    source = existing.get('source') if existing.get('source') in {'deterministic', 'ai_written'} else 'deterministic'
    text = (existing.get('text') or '').strip()
    if _COMPLIANCE.search(text):
        source = 'deterministic'
        text = ''
    grounded = snippet or _words(existing.get('quote') or quote)
    if not grounded:
        return None
    if not text:
        named = sentence_id or article.get('provision') or 'the quoted provision'
        text = f'Division B {named} is quoted from the code database.'
    if EXPLANATION_NOTE not in text:
        text = f'{text} {EXPLANATION_NOTE}'
    if _COMPLIANCE.search(text):
        text = EXPLANATION_NOTE
        source = 'deterministic'
    return {'text': text, 'quote': grounded, 'source': source, 'label': 'explanation'}


def _card(article: dict, rank: int, stored: list[dict], codes: Codes | None, result: dict, mode: str) -> dict:
    if article.get('verifier_status') and article.get('explainer', {}).get('label') == 'explanation':
        article['rank'] = rank
        if mode == 'bm25_fallback':
            article['committed'] = False
            article['verifier_status'] = 'unknown'
        return article
    article_id = article.get('provision') or ''
    quote = article.get('quote')
    sentence_id = _sentence_id(article_id, quote, stored, codes)
    snippet = _snippet(sentence_id, quote, stored, codes)
    card = dict(article)
    card.update({
        'rank': rank,
        'provision_id': sentence_id,
        'link': f'/code/{article_id}?division=B' if article_id else None,
        'citation': _citation(sentence_id, article_id, stored, codes),
        'title': article.get('title'),
        'snippet': snippet,
        'verifier_status': _verifier_status(article, result, mode),
        'why': article.get('reason'),
        'benchmark_acceptable_solution': sentence_id,
        'explainer': _explainer(article, sentence_id, quote, snippet, stored),
    })
    return card
