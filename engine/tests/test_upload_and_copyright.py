import asyncio
import re
import sqlite3

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from codedb import store as codedb_store
from engine.api import create_app, read_capped
from engine.codes import Codes
from engine.copyright import has_consecutive_words
from engine.llm_gate import reset_for_tests
from engine.store import CaseStore
from engine.uploads import PDF_MAX_BYTES, PDF_TOO_LARGE_DETAIL


def test_content_length_and_stream_stop_at_4mb():
    class Request:
        def __init__(self, headers, chunks):
            self.headers = headers
            self._chunks = chunks

        async def stream(self):
            for chunk in self._chunks:
                yield chunk

    over = Request({'content-length': str(PDF_MAX_BYTES + 1)}, [b'%PDF'])
    with pytest.raises(HTTPException) as raised:
        asyncio.run(read_capped(over))
    assert raised.value.status_code == 413 and raised.value.detail == PDF_TOO_LARGE_DETAIL

    streamed = Request({}, [b'a' * PDF_MAX_BYTES, b'b'])
    with pytest.raises(HTTPException) as raised:
        asyncio.run(read_capped(streamed))
    assert raised.value.status_code == 413


def test_upload_accepts_small_pdf_and_rejects_oversize(tmp_path):
    store = CaseStore(tmp_path / 'cases.sqlite')
    client = TestClient(create_app(store=store, codes=None))
    case_id = client.post('/cases', json={'title': 'upload'}).json()['id']
    pdf = b'%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF'
    saved = client.post(f'/cases/{case_id}/files', content=pdf, headers={'content-type': 'application/pdf',
                                                                         'x-filename': 'plan.pdf'})
    assert saved.status_code == 201 and saved.json()['name'] == 'plan.pdf'
    assert store.get_file(case_id, saved.json()['id'])['data'] == pdf
    assert client.get(f'/cases/{case_id}').headers['x-robots-tag'] == 'noindex, nofollow'
    assert client.get('/api/cases/missing').status_code == 404

    too_big = b'%PDF-' + b'0' * PDF_MAX_BYTES
    rejected = client.post(f'/cases/{case_id}/files', content=too_big, headers={'content-type': 'application/pdf'})
    assert rejected.status_code == 413 and rejected.json() == {'detail': PDF_TOO_LARGE_DETAIL}


def _synthetic_db(path):
    con = sqlite3.connect(path)
    con.executescript(codedb_store.SCHEMA)
    text = ' '.join(f'w{i:02d}' for i in range(40))
    con.execute('''INSERT INTO provisions (doc, division, id, level, part, section, subsection, article,
                   sentence, clause, subclause, parent_id, article_title, title, text, text_raw, clauses,
                   pdf_page, pdf_page_end, volume, sort_key)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',
                ('NBC-AE', 'B', '9.1.1.1.(1)', 'sentence', 9, '9.1.', '9.1.1.', '9.1.1.1.', 1, None, None,
                 '9.1.1.1.', 'Synthetic', 'Synthetic sentence', text, text, '[]', 1, 1, 1, '0001'))
    con.execute('INSERT INTO provisions_fts (doc, division, id, title, text) VALUES (?,?,?,?,?)',
                ('NBC-AE', 'B', '9.1.1.1.(1)', 'Synthetic sentence', text))
    con.execute('INSERT INTO docs VALUES (?,?,?,?,?,?,?)',
                ('NBC-AE', 'NBC(AE) 2023 p2', 'code', 1, 'x', 'y', 'abc'))
    con.commit()
    con.close()
    return text.split()


def test_responses_keep_at_most_25_provision_words(tmp_path, monkeypatch):
    monkeypatch.setenv('BATATIS_SEARCH_RATE_LIMIT', '10')
    reset_for_tests()
    path = tmp_path / 'codedb.sqlite'
    provision_words = _synthetic_db(path)
    client = TestClient(create_app(store=CaseStore(tmp_path / 'cases.sqlite'), codes=Codes(path)))
    bodies = [
        client.get('/code/9.1.1.1.(1)', params={'division': 'B'}).text,
        client.get('/code/search', params={'q': 'w00', 'limit': 20}).text,
    ]
    assert client.get('/code/search', params={'q': 'w00', 'limit': 21}).status_code == 422
    for body in bodies:
        # JSON quotes stick to the first and last word; compare the word sequence, not the raw tokens.
        plain = ' '.join(re.findall(r'[A-Za-z0-9]+', body))
        assert has_consecutive_words(plain, provision_words[:25])
        assert not has_consecutive_words(plain, provision_words[:26])


def test_search_is_rate_limited(tmp_path, monkeypatch):
    monkeypatch.setenv('BATATIS_SEARCH_RATE_LIMIT', '2')
    reset_for_tests()
    path = tmp_path / 'codedb.sqlite'
    _synthetic_db(path)
    client = TestClient(create_app(store=CaseStore(tmp_path / 'cases.sqlite'), codes=Codes(path)))
    assert client.get('/code/search', params={'q': 'w00'}).status_code == 200
    assert client.get('/code/search', params={'q': 'w00'}).status_code == 200
    assert client.get('/code/search', params={'q': 'w00'}).status_code == 429
