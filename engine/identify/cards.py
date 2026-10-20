"""Shape an identify payload into the article cards the applicant UI renders.

Sentence ids, snippets, and citations come from codedb or from rows already stored
on the payload. A missing sentence stays null. Nothing in this module invents a
provision id or a quote.
"""
from __future__ import annotations

import re

from engine.codes import CodeDbMissing, Codes
from engine.identify.publication import publication
from engine.identify.requirement import benchmark as requirement_benchmark

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


def present(result: dict, codes: Codes | None, mode: str, facts=None) -> dict:
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
            article['suggested'] = False
            article.pop('committed', None)
        result['section_c'] = []
    elif mode == 'live':
        result['source'] = 'live'
        result['cached'] = False
    result['persisted'] = False
    source = publication()
    shaped = []
    for index, article in enumerate(result.get('articles') or [], start=1):
        shaped.append(_card(article, index, stored, codes, result, mode, facts, source))
    result['articles'] = shaped
    _guard_quotes(result)
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


def _page(record: dict | None) -> int | None:
    if not record:
        return None
    page = record.get('pdf_page')
    return page if isinstance(page, int) else None


def _terms(record: dict | None, codes: Codes | None) -> tuple[list[dict], list[dict], bool]:
    """Objective and function ids from attribution rows. Labels are definition titles."""
    rows = (record or {}).get('attributions') or []
    if not rows:
        return [], [], True
    objectives: list[dict] = []
    functions: list[dict] = []
    seen_objectives: list[str] = []
    seen_functions: list[str] = []
    for row in rows:
        for objective in row.get('objectives') or []:
            if objective in seen_objectives:
                continue
            seen_objectives.append(objective)
            objectives.append({'id': objective, 'label': _label(codes, objective)})
        for function in row.get('fs') or []:
            if function in seen_functions:
                continue
            seen_functions.append(function)
            functions.append({'id': function, 'label': _label(codes, function)})
    return objectives, functions, False


def _label(codes: Codes | None, code: str) -> str | None:
    if codes is None or not hasattr(codes, 'definition'):
        return None
    defined = codes.definition(code)
    title = (defined or {}).get('title') if isinstance(defined, dict) else None
    return title if isinstance(title, str) and title.strip() else None


def _guard_quotes(node) -> None:
    """No served quote is longer than 25 words. Article cards drop `quote` before this runs."""
    if isinstance(node, dict):
        if isinstance(node.get('quote'), str):
            node['quote'] = _words(node['quote'])
        for value in node.values():
            _guard_quotes(value)
    elif isinstance(node, list):
        for item in node:
            _guard_quotes(item)


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


def _status(article: dict, result: dict, mode: str) -> str:
    """Ranking hint. `suggested` is not an acceptance of the article for the case."""
    if mode == 'bm25_fallback':
        return 'unknown'
    if article.get('suggested') or article.get('committed'):
        return 'suggested'
    verifier = (result.get('trace') or {}).get('verifier')
    if isinstance(verifier, dict) or article.get('stage') == 'verify':
        return 'candidate'
    current = article.get('status') or article.get('verifier_status')
    if current in {'suggested', 'candidate', 'unknown'}:
        return current
    return 'unknown'


def _finish(article: dict, result: dict, mode: str) -> dict:
    legacy = bool(article.pop('committed', False))
    if mode == 'bm25_fallback':
        article['suggested'] = False
    elif legacy and 'suggested' not in article:
        article['suggested'] = True
    status = _status(article, result, mode)
    article['status'] = status
    article['verifier_status'] = status
    if article.get('decision') not in {'yes', 'no', 'not_sure'}:
        article['decision'] = None
    if article.get('decision') != 'not_sure':
        article['open_question_id'] = None
    article['excluded'] = article.get('decision') == 'no'
    return article


def _explainer(article: dict, sentence_id: str | None, snippet: str | None, stored: list[dict]) -> dict | None:
    if not snippet:
        return None
    if article.get('explainer') and article['explainer'].get('label') == 'explanation':
        kept = dict(article['explainer'])
        kept['quote'] = snippet
        if _COMPLIANCE.search(kept.get('text') or ''):
            kept['text'] = EXPLANATION_NOTE
            kept['source'] = 'deterministic'
        return kept
    row = next((item for item in stored if sentence_id and item.get('provision_id') == sentence_id), None)
    existing = (row or {}).get('explainer') or {}
    source = existing.get('source') if existing.get('source') in {'deterministic', 'ai_written'} else 'deterministic'
    text = (existing.get('text') or '').strip()
    if _COMPLIANCE.search(text):
        source = 'deterministic'
        text = ''
    if not text:
        named = sentence_id or article.get('provision') or 'the quoted provision'
        text = f'Division B {named} is quoted from the code database.'
    if EXPLANATION_NOTE not in text:
        text = f'{text} {EXPLANATION_NOTE}'
    if _COMPLIANCE.search(text):
        text = EXPLANATION_NOTE
        source = 'deterministic'
    return {'text': text, 'quote': snippet, 'source': source, 'label': 'explanation'}


def _annotate(card: dict, sentence_id: str | None, codes: Codes | None, facts, source: dict,
              stored: list[dict]) -> dict:
    """Codedb fields. Snippet and the requirement are read from the sentence, never from a model quote."""
    card.pop('quote', None)
    card.pop('text', None)
    record = _provision(codes, sentence_id) if sentence_id else None
    sentence = record.get('text') if record and record.get('id') == sentence_id else None
    snippet = _words(sentence) if sentence else None
    card['snippet'] = snippet
    card['url'] = source.get('url')
    card['printing'] = source.get('printing')
    card['page'] = _page(record)
    objectives, functions, missing = _terms(record, codes)
    card['objectives'] = objectives
    card['functions'] = functions
    card['attribution_missing'] = missing
    card['benchmark'] = requirement_benchmark(sentence_id, sentence, facts)
    card['explainer'] = _explainer(card, sentence_id, snippet, stored)
    return card


def _card(article: dict, rank: int, stored: list[dict], codes: Codes | None, result: dict, mode: str,
          facts, source: dict) -> dict:
    shaped = bool(article.get('verifier_status') and (article.get('explainer') or {}).get('label') == 'explanation')
    if shaped:
        card = article
        card['rank'] = rank
        sentence_id = card.get('provision_id')
    else:
        article_id = article.get('provision') or ''
        sentence_id = _sentence_id(article_id, article.get('quote'), stored, codes)
        card = dict(article)
        card.update({
            'rank': rank,
            'provision_id': sentence_id,
            'link': f'/code/{article_id}?division=B' if article_id else None,
            'citation': _citation(sentence_id, article_id, stored, codes),
            'title': article.get('title'),
            'why': article.get('reason'),
            'benchmark_acceptable_solution': sentence_id,
        })
    _annotate(card, sentence_id, codes, facts, source, stored)
    return _finish(card, result, mode)
