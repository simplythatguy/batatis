"""Deploy guards: the code database is not a download, NRC text stays inside the word budget, and the privacy notice matches the web app."""
import json
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from engine.api import create_app
from engine.copyright import (
    NRC_PUBLICATION_URL,
    PII_NOTICE,
    RESPONSE_NRC_MAX_WORDS,
    SNIPPET_MAX_WORDS,
    clip_response,
    words,
)
from engine.models import Case
from engine.store import CaseStore

SQLITE_MAGIC = b'SQLite format 3'
MARKER = re.compile(r'… \[clipped, see NBC(?: p\.\d+|\(AE\) 2023)\]')
ROOT = Path(__file__).resolve().parents[2]


def snippet_words(text: str) -> int:
    return len(words(MARKER.sub('', text)))


@pytest.fixture
def client(tmp_path):
    return TestClient(create_app(CaseStore(tmp_path / 'cases.sqlite')))


@pytest.mark.parametrize('path', [
    '/codedb/build/codedb.sqlite',
    '/codedb.sqlite',
    '/api/codedb/build/codedb.sqlite',
    '/api/codedb.sqlite',
])
def test_codedb_file_is_not_downloadable(client, path):
    response = client.get(path)
    assert response.status_code == 404
    assert not response.content.startswith(SQLITE_MAGIC)
    assert b'CREATE TABLE' not in response.content
    assert SQLITE_MAGIC not in response.content
    head = client.head(path)
    assert head.status_code == 404
    assert not head.content.startswith(SQLITE_MAGIC)


def test_response_keeps_25_words_per_snippet_and_75_overall():
    sentence = ' '.join(f'word{i}' for i in range(40))
    out = clip_response({
        'pdf_page': 12,
        'text': sentence,
        'notes': [sentence, sentence, sentence],
        'question': sentence,
    })
    snippets = [out['text'], *out['notes']]
    assert all(snippet_words(item) <= SNIPPET_MAX_WORDS for item in snippets)
    assert sum(snippet_words(item) for item in snippets) == RESPONSE_NRC_MAX_WORDS
    assert snippet_words(out['notes'][-1]) == 0
    assert out['url'] == NRC_PUBLICATION_URL
    assert out['clipped'] is True
    assert out['question'] == sentence
    assert 'word25' not in out['text']


def test_short_prose_is_linked_and_not_marked_clipped():
    out = clip_response({'text': 'fire separation', 'pdf_page': 3})
    assert out['text'] == 'fire separation'
    assert out['url'] == NRC_PUBLICATION_URL
    assert 'clipped' not in out


def test_applicant_text_is_not_treated_as_code():
    value = ' '.join(f'name{i}' for i in range(40))
    out = clip_response({'value': value, 'source': {'type': 'user_text', 'ref': 'm'}})
    assert out['value'] == value
    assert 'url' not in out
    assert 'clipped' not in out


def test_http_response_clips_code_quotes_to_the_word_budget(client):
    quote = ' '.join(f'word{i}' for i in range(40))
    created = client.post('/cases', json={'title': 'Clip'})
    case_id = created.json()['id']
    fact = {
        'field': 'excerpt',
        'value': 'kept',
        'kind': 'exact',
        'source': {'type': 'code', 'ref': '9.10.15.5.', 'page': 12, 'quote': quote},
    }
    response = client.post(f'/cases/{case_id}/facts', json=fact)
    assert response.status_code == 200
    stored = response.json()['facts'][0]
    snippets = [stored['source']['quote']]
    assert all(snippet_words(item) <= SNIPPET_MAX_WORDS for item in snippets)
    assert sum(snippet_words(item) for item in snippets) <= RESPONSE_NRC_MAX_WORDS
    assert stored['source']['url'] == NRC_PUBLICATION_URL or stored.get('url') == NRC_PUBLICATION_URL
    assert 'word25' not in stored['source']['quote']


def test_responses_carry_noindex_and_the_privacy_notice(client):
    response = client.post('/cases', json={'title': 'Garage'})
    assert response.status_code == 201
    assert response.headers['x-robots-tag'] == 'noindex, nofollow'
    assert response.headers['x-batatis-notice'] == PII_NOTICE
    assert response.json()['meta']['notice'] == PII_NOTICE


def test_privacy_notice_matches_the_web_app():
    web = (ROOT / 'web/src/components.tsx').read_text()
    assert PII_NOTICE in web
    robots = (ROOT / 'web/public/robots.txt').read_text()
    assert 'User-agent: *' in robots and 'Disallow: /' in robots
    vercel = json.loads((ROOT / 'vercel.json').read_text())
    header = vercel['headers'][0]['headers'][0]
    assert header == {'key': 'X-Robots-Tag', 'value': 'noindex, nofollow'}
    sources = [item['source'] for item in vercel['rewrites']]
    assert sources.index('/codedb/(.*)') < sources.index('/(.*)')
    assert any(source.endswith('sqlite)') for source in sources)


def test_cases_older_than_seven_days_are_deleted(tmp_path):
    store = CaseStore(tmp_path / 'cases.sqlite')
    old = store.put(Case())
    old.created_at = (datetime.now(timezone.utc) - timedelta(days=7, seconds=1)).isoformat(timespec='seconds')
    store.put(old)
    fresh = store.put(Case())
    assert store.purge_expired() == 1
    assert store.get(old.id) is None
    assert store.get(fresh.id) is not None
    assert store.purge_expired() == 0


def test_delete_removes_a_case_on_request(client):
    created = client.post('/cases', json={'title': 'Temporary'})
    case_id = created.json()['id']
    assert client.delete(f'/cases/{case_id}').status_code == 204
    assert client.get(f'/cases/{case_id}').status_code == 404
    assert client.delete(f'/cases/{case_id}').status_code == 404
