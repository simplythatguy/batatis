"""Record one offline BM25 identify run for the seeded demo cases.

The committed cache keeps a verbatim codedb snippet of at most 25 words on
each article. It does not keep an article's full text and it does not call a model.
"""
from __future__ import annotations

import copy
import json
import re
from pathlib import Path

from engine.codes import Codes, default_db
from engine.identify.demo_cache import DEMO_CASE_IDS, cache_key
from engine.identify.requirement import benchmark as requirement_benchmark

ROOT = Path(__file__).resolve().parents[2]
BRIEFS = ROOT / 'evals' / 'demo-cases'
SNIPPET_WORDS = 25
_WS = re.compile(r'\s+')
_SENTENCE = re.compile(r'^\d+(?:\.\d+){3}\.\(\d+\)$')


def _flat(text: str | None) -> str:
    return _WS.sub(' ', text or '').strip()


def _words(text: str | None, limit: int = SNIPPET_WORDS) -> str | None:
    flat = _flat(text)
    if not flat:
        return None
    return ' '.join(flat.split(' ')[:limit])


def _sentences(codes: Codes, article_id: str) -> list[tuple[str, str]]:
    record = codes.provision(article_id, 'B')
    found = []
    for child in (record or {}).get('children') or []:
        if child.get('level') != 'sentence' or not _SENTENCE.match(child.get('id') or ''):
            continue
        full = codes.provision(child['id'], 'B') or child
        text = _flat(full.get('text'))
        if text:
            found.append((child['id'], text))
    return found


def snippet_for(codes: Codes, article_id: str, quote: str | None) -> tuple[str, str | None]:
    """Verbatim prefix. A unique sentence match wins; otherwise the article's opening words."""
    record = codes.provision(article_id, 'B')
    if record is None:
        raise ValueError(f'{article_id} is not in the code database')
    probe = _flat(quote)
    matched = []
    if probe:
        for sentence_id, text in _sentences(codes, article_id):
            if probe in text or text in probe:
                matched.append((sentence_id, text))
    if len(matched) == 1:
        snippet = _words(matched[0][1])
        if snippet:
            return snippet, matched[0][0]
    snippet = _words(record.get('text'))
    if not snippet:
        raise ValueError(f'{article_id} has no codedb text to snippet')
    return snippet, None


def _contained(snippet: str | None, source: str | None) -> str | None:
    """First 25 words of `source` when `snippet` is not itself a verbatim span of that text."""
    if snippet and snippet in _flat(source):
        return snippet
    return _words(source)


def trim_payload(result: dict, codes: Codes) -> dict:
    """Drop full articles. Every stored code quote is a verbatim span of at most 25 words."""
    payload = copy.deepcopy(result)
    payload.pop('trace', None)
    payload['section_c'] = []
    articles = []
    for article in payload.get('articles') or []:
        quote = article.pop('quote', None)
        article.pop('text', None)
        article.pop('committed', None)
        article['suggested'] = False
        snippet, sentence_id = snippet_for(codes, article['provision'], quote)
        article['snippet'] = snippet
        if sentence_id:
            sentence = codes.provision(sentence_id, 'B') or {}
            article['benchmark'] = requirement_benchmark(sentence_id, sentence.get('text'), None)
        else:
            article.pop('benchmark', None)
        articles.append(article)
    payload['articles'] = articles
    benchmark = payload.get('benchmark') or {}
    if benchmark.get('provision'):
        record = codes.provision(benchmark['provision'], 'B') or {}
        benchmark['quote'] = _contained(_words(benchmark.get('quote')), record.get('text'))
    for row in benchmark.get('section_c') or []:
        record = codes.provision(row.get('provision_id') or '', 'B') or {}
        explainer = row.get('explainer') or {}
        if explainer.get('quote'):
            explainer['quote'] = _contained(_words(explainer.get('quote')), record.get('text'))
            row['explainer'] = explainer
    if benchmark:
        payload['benchmark'] = benchmark
    models = dict(payload.get('model_ids') or {})
    models['invoked'] = False
    payload['model_ids'] = models
    payload['cached'] = True
    payload['persisted'] = False
    payload['mode'] = 'cached_demo'
    payload['source'] = 'cache'
    _assert_snips(payload, codes)
    return payload


def _assert_snips(payload: dict, codes: Codes) -> None:
    blob = json.dumps(payload)
    for article in payload['articles']:
        record = codes.provision(article['provision'], 'B')
        if record is None:
            raise ValueError(article['provision'])
        full = record.get('text') or ''
        flat = _flat(full)
        snippet = article.get('snippet') or ''
        if len(snippet.split()) > SNIPPET_WORDS:
            raise ValueError(f'snippet longer than {SNIPPET_WORDS} words: {article["provision"]}')
        if len(flat.split()) > SNIPPET_WORDS and (full in blob or flat in blob):
            raise ValueError(f'whole article cached: {article["provision"]}')
        if not _is_verbatim(codes, article['provision'], snippet):
            raise ValueError(f'snippet is not codedb text: {article["provision"]}')
        quote = (payload.get('benchmark') or {}).get('quote')
        if isinstance(quote, str) and len(quote.split()) > SNIPPET_WORDS:
            raise ValueError('benchmark quote is longer than 25 words')
    for row in (payload.get('benchmark') or {}).get('section_c') or []:
        quote = (row.get('explainer') or {}).get('quote')
        if isinstance(quote, str) and len(quote.split()) > SNIPPET_WORDS:
            raise ValueError(f'explainer quote is longer than 25 words: {row.get("provision_id")}')


def _is_verbatim(codes: Codes, article_id: str, snippet: str) -> bool:
    record = codes.provision(article_id, 'B') or {}
    if snippet and _flat(record.get('text')).startswith(snippet):
        return True
    return any(text.startswith(snippet) for _, text in _sentences(codes, article_id))


def brief_for(case_id: str) -> str:
    return (BRIEFS / case_id / 'input' / 'project-brief.md').read_text()


def build_rows() -> list[dict]:
    """One BM25 run per seeded brief. Raises when the code database is missing."""
    import os

    os.environ.pop('OPENAI_API_KEY', None)
    os.environ.pop('ANTHROPIC_API_KEY', None)
    if not default_db().exists():
        raise FileNotFoundError('code database not found')
    from engine.identify.pipeline import run

    codes = Codes()
    rows = []
    for case_id in DEMO_CASE_IDS:
        prose = brief_for(case_id)
        result = run(prose, ranker='bm25')
        if result.get('mode') != 'bm25_fallback':
            raise RuntimeError(f'{case_id}: refusing to cache a model run')
        models = result.get('model_ids') or {}
        if models.get('screen') or models.get('rerank') or models.get('verifier'):
            raise RuntimeError(f'{case_id}: a model id was set on an offline run')
        if any(article.get('suggested') for article in result.get('articles') or []):
            raise RuntimeError(f'{case_id}: BM25 suggested an article')
        payload = trim_payload(result, codes)
        candidates = [{
            'provision': article['provision'],
            'title': article.get('title') or '',
            'text': article['snippet'],
            'part': article.get('part'),
        } for article in payload['articles']]
        rows.append({
            'id': case_id,
            'description': prose,
            'description_sha256': cache_key(prose),
            'candidates': candidates,
            'payload': payload,
        })
    return rows
