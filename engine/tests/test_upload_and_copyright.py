import asyncio
import json
import re
import sqlite3

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from codedb import store as codedb_store
from engine.api import create_app, read_capped
from engine.codes import Codes
from engine.copyright import clip_marker, clip_tree, has_consecutive_words, words
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


def _long(prefix):
    return ' '.join(f'{prefix}{i:02d}' for i in range(40))


def _synthetic_db(path):
    con = sqlite3.connect(path)
    con.executescript(codedb_store.SCHEMA)
    text = _long('w')
    clause = _long('c')
    note = _long('n')
    nested = _long('k')
    con.execute('''INSERT INTO provisions (doc, division, id, level, part, section, subsection, article,
                   sentence, clause, subclause, parent_id, article_title, title, text, text_raw, clauses,
                   pdf_page, pdf_page_end, volume, sort_key)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',
                ('NBC-AE', 'B', '9.1.1.1.(1)', 'sentence', 9, '9.1.', '9.1.1.', '9.1.1.1.', 1, None, None,
                 '9.1.1.1.', 'Synthetic', 'Synthetic sentence', text, text,
                 json.dumps([clause, 'a']), 1, 1, 1, '0001'))
    con.execute('INSERT INTO notes VALUES (?,?,?,?,?,?,?,?,?)',
                ('NBC-AE', 'B', 'A-9.1.1.1.', 'Note A-9.1.1.1.', note, note, 1, 1, 1))
    con.execute('INSERT INTO note_links VALUES (?,?,?,?,?)',
                ('NBC-AE', 'B', 'A-9.1.1.1.', '9.1.1.1.(1)', 'note_id'))
    con.execute('INSERT INTO intents VALUES (?,?,?,?,?,?,?,?,?,?)',
                ('NBC-2020', 'NBC-AE', '9.1.1.1.(1)', 0, 'OS1.1', '[]',
                 json.dumps([[nested, 'keep-me'], nested]), json.dumps([note]), 1, 1))
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
    rejected = client.get('/code/search', params={'q': 'w00', 'limit': 21})
    assert rejected.status_code == 422 and rejected.json()['detail'] == 'The maximum is 20.'
    for body in bodies:
        # JSON quotes stick to the first and last word; compare the word sequence, not the raw tokens.
        plain = ' '.join(re.findall(r'[A-Za-z0-9]+', body))
        assert has_consecutive_words(plain, provision_words[:25])
        assert not has_consecutive_words(plain, provision_words[:26])


def test_clip_tree_clips_notes_clauses_and_nested_lists():
    long = _long('p')
    tree = {
        'id': '9.1.1.1.(1)',
        'citation': 'NBC(AE) 2023 p2, Div B, Sentence 9.1.1.1.(1) [PDF p.1] ' + long,
        'url': 'https://example.test/' + long.replace(' ', '-'),
        'division': 'B',
        'text': long,
        'notes': [long, {'text': long, 'note_id': 'A-9.1.1.1.'}],
        'clauses': [long, [long, 'a']],
    }
    clipped = clip_tree(tree)
    plain = '… [clipped, see NBC(AE) 2023]'
    assert clipped['id'] == tree['id']
    assert clipped['citation'] == tree['citation']
    assert clipped['url'] == tree['url']
    assert clipped['division'] == 'B'
    assert plain not in clipped['id'] and plain not in clipped['citation']
    assert 'clipped_fields' not in clip_tree({'id': '9.1.1.1.(1)', 'text': 'one short sentence'})
    assert clipped['text'] == ' '.join(words(long)[:25]) + ' ' + plain
    assert clipped['notes'][0].endswith(plain)
    assert clipped['notes'][1]['text'].endswith(plain)
    assert clipped['notes'][1]['note_id'] == 'A-9.1.1.1.'
    assert 'text' in clipped['notes'][1]['clipped_fields']
    assert clipped['clauses'][0].endswith(plain)
    assert clipped['clauses'][1][0].endswith(plain)
    assert clipped['clauses'][1][1] == 'a'
    assert set(clipped['clipped_fields']) >= {'text', 'notes', 'clauses'}
    paged = clip_tree({'pdf_page': 12, 'text': long, 'title': 'kept whole ' + long})
    assert paged['text'].endswith(clip_marker(12))
    assert 'text' in paged['clipped_fields']
    assert paged['title'] == 'kept whole ' + long
    assert 'title' not in paged['clipped_fields']


def test_code_response_clips_notes_clauses_and_nested_lists(tmp_path, monkeypatch):
    monkeypatch.setenv('BATATIS_SEARCH_RATE_LIMIT', '10')
    reset_for_tests()
    path = tmp_path / 'codedb.sqlite'
    _synthetic_db(path)
    client = TestClient(create_app(store=CaseStore(tmp_path / 'cases.sqlite'), codes=Codes(path)))
    body = client.get('/code/9.1.1.1.(1)', params={'division': 'B'}).json()
    assert body['id'] == '9.1.1.1.(1)'
    assert body['citation'].startswith('NBC(AE) 2023 p2')
    assert '… [clipped' not in body['citation']
    page = '… [clipped, see NBC p.1]'
    assert body['text'].endswith(page)
    assert 'text' in body['clipped_fields']
    assert body['notes'][0]['text'].endswith(page)
    assert 'text' in body['notes'][0]['clipped_fields']
    assert body['clauses'][0].endswith(page)
    assert body['clauses'][1] == 'a'
    assert 'clauses' in body['clipped_fields']
    nested = body['intents'][0]['attribution_notes']
    assert nested[0][0].endswith(page)
    assert nested[0][1] == 'keep-me'
    assert nested[1].endswith(page)
    assert 'attribution_notes' in body['intents'][0]['clipped_fields']
    long = _long('q')
    case_id = client.post('/cases', json={'title': 'facts stay whole'}).json()['id']
    saved = client.post(f'/cases/{case_id}/facts', json={
        'field': 'occupancy', 'value': long, 'kind': 'pointed', 'status': 'unconfirmed',
        'source': {'type': 'user_text', 'ref': 'msg', 'quote': long},
    })
    assert saved.status_code == 200
    fact = saved.json()['facts'][0]
    assert fact['value'] == long and fact['source']['quote'] == long
    assert 'clipped_fields' not in saved.json() and '… [clipped' not in saved.text


def test_unreachable_database_is_503():
    import psycopg

    class Down:
        def get(self, case_id):
            raise psycopg.OperationalError('could not connect to server at secret-host.example')

    client = TestClient(create_app(store=Down(), codes=None))
    response = client.get('/cases/missing')
    assert response.status_code == 503
    assert response.json() == {'detail': 'case store unavailable'}
    assert 'secret-host' not in response.text


def test_export_without_the_scc_form_is_503(tmp_path, monkeypatch):
    monkeypatch.delenv('BATATIS_SCC_FORM', raising=False)
    monkeypatch.setattr('engine.export.scc.DEFAULT_FORM', tmp_path / 'missing-guide.pdf')
    monkeypatch.setattr('engine.export.scc.BUNDLE_FORM', tmp_path / 'missing-bundle.pdf')
    monkeypatch.setattr('engine.export.scc.blockers', lambda *args, **kwargs: [])
    monkeypatch.setattr('engine.export.scc._canonical_case', lambda case, codes: case)
    path = tmp_path / 'codedb.sqlite'
    _synthetic_db(path)
    client = TestClient(create_app(store=CaseStore(tmp_path / 'cases.sqlite'), codes=Codes(path)))
    case_id = client.post('/cases', json={'title': 'export'}).json()['id']
    response = client.post(f'/cases/{case_id}/export', json={'draft': True})
    assert response.status_code == 503
    assert response.json() == {'detail': 'PDF export is unavailable on this deployment: SCC form not configured'}


def test_search_is_rate_limited(tmp_path, monkeypatch):
    monkeypatch.setenv('BATATIS_SEARCH_RATE_LIMIT', '2')
    reset_for_tests()
    path = tmp_path / 'codedb.sqlite'
    _synthetic_db(path)
    client = TestClient(create_app(store=CaseStore(tmp_path / 'cases.sqlite'), codes=Codes(path)))
    assert client.get('/code/search', params={'q': 'w00'}).status_code == 200
    assert client.get('/code/search', params={'q': 'w00'}).status_code == 200
    limited = client.get('/code/search', params={'q': 'w00'})
    assert limited.status_code == 429
    assert limited.json()['detail'].startswith('Search limit reached; try again in ')
    assert limited.json()['detail'].endswith(' seconds')
    assert limited.headers['retry-after'].isdigit()
