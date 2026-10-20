import asyncio
import json
import logging
import re
import sqlite3

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from codedb import store as codedb_store
from engine.api import create_app, read_capped
from engine.codes import Codes
from engine.copyright import (NRC_PUBLICATION_URL, PII_NOTICE, RESPONSE_WORD_BUDGET, SNIPPET_WORD_LIMIT,
                              clip_marker, clip_response, has_consecutive_words, is_nrc_string, words)
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
    assert rejected.status_code == 413 and rejected.json()['detail'] == PDF_TOO_LARGE_DETAIL
    assert rejected.json()['meta']['notice'] == PII_NOTICE


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


def _nrc_snippets(node, key=None, parent=None):
    if isinstance(node, dict):
        found = []
        for name, value in node.items():
            if name in ('meta', 'clipped', 'url', 'href'):
                continue
            found.extend(_nrc_snippets(value, name, node))
        return found
    if isinstance(node, list):
        found = []
        for item in node:
            found.extend(_nrc_snippets(item, key, parent))
        return found
    if is_nrc_string(key, node, parent):
        return [node.split('… [clipped', 1)[0].strip()]
    return []


def _assert_budget(payload):
    snippets = _nrc_snippets(payload)
    assert all(len(words(snippet)) <= SNIPPET_WORD_LIMIT for snippet in snippets)
    assert sum(len(words(snippet)) for snippet in snippets) <= RESPONSE_WORD_BUDGET


def test_response_budget_caps_each_snippet_and_the_total():
    long = _long('p')
    clipped = clip_response({
        'id': '9.1.1.1.(1)',
        'citation': 'NBC(AE) 2023 p2, Div B, Sentence 9.1.1.1.(1) [PDF p.1] ' + long,
        'url': 'https://example.test/' + long.replace(' ', '-'),
        'division': 'B',
        'pdf_page': 12,
        'text': long,
        'notes': [long, {'text': long, 'note_id': 'A-9.1.1.1.'}, long, long],
        'clauses': [long, [long, 'a']],
        'title': 'kept whole ' + long,
    })
    plain = clip_marker(12)
    assert clipped['id'] == '9.1.1.1.(1)'
    assert clipped['citation'].startswith('NBC(AE) 2023 p2')
    assert plain not in clipped['citation'] and plain not in clipped['url']
    assert clipped['division'] == 'B'
    assert clipped['title'] == 'kept whole ' + long
    assert clipped['text'] == ' '.join(words(long)[:25]) + ' ' + plain
    assert clipped['clipped'] is True
    assert clipped['clauses'][1][1] == 'a'
    assert clipped['notes'][1]['note_id'] == 'A-9.1.1.1.'
    _assert_budget(clipped)
    # Past 75 words the rest is the marker, the citation, and the NRC link.
    assert any(note == plain or (isinstance(note, dict) and note.get('text') == plain) for note in clipped['notes'])
    untouched = clip_response({'id': '9.1.1.1.(1)', 'text': 'one short sentence'})
    assert 'clipped' not in untouched and '…' not in untouched['text'] and 'url' not in untouched


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
    assert body['clipped'] is True
    assert body['clauses'][1] == 'a'
    assert body['url'] == NRC_PUBLICATION_URL
    _assert_budget(body)
    blocked = client.get('/code/9.1.1.1.(1)', params={'division': 'B', 'offset': 2, 'sentence': 1})
    assert blocked.status_code == 400 and blocked.json()['detail'] == 'this route accepts only division'
    long = _long('q')
    case_id = client.post('/cases', json={'title': 'quote is code text'}).json()['id']
    saved = client.post(f'/cases/{case_id}/facts', json={
        'field': 'occupancy', 'value': long, 'kind': 'pointed', 'status': 'unconfirmed',
        'source': {'type': 'code', 'ref': '9.1.1.1.(1)', 'quote': long},
    })
    assert saved.status_code == 200
    fact = saved.json()['facts'][0]
    assert fact['source']['quote'].endswith('… [clipped, see NBC(AE) 2023]')
    assert fact['source']['clipped'] is True
    assert fact['source']['url'] == NRC_PUBLICATION_URL
    assert fact['source']['ref'] == '9.1.1.1.(1)'
    _assert_budget(saved.json())


def test_unreachable_database_is_503():
    import psycopg

    class Down:
        def get(self, case_id):
            raise psycopg.OperationalError('could not connect to server at secret-host.example')

    client = TestClient(create_app(store=Down(), codes=None))
    response = client.get('/cases/missing')
    assert response.status_code == 503
    assert response.json()['detail'] == 'case store unavailable'
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
    assert response.json()['detail'] == 'PDF export is unavailable on this deployment: SCC form not configured'


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


def _insert_provision(con, division, pid, text, page):
    con.execute('''INSERT INTO provisions (doc, division, id, level, part, section, subsection, article,
                   sentence, clause, subclause, parent_id, article_title, title, text, text_raw, clauses,
                   pdf_page, pdf_page_end, volume, sort_key)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',
                ('NBC-AE', division, pid, 'sentence', 2, '2.3.', '2.3.1.', '2.3.1.1.', 1, None, None,
                 None, 'Synthetic', pid, text, text, json.dumps(['a']), page, page, 1, pid))
    con.execute('INSERT INTO provisions_fts (doc, division, id, title, text) VALUES (?,?,?,?,?)',
                ('NBC-AE', division, pid, pid, text))


def test_every_registered_route_stays_inside_the_nrc_budget(tmp_path, monkeypatch):
    from fastapi.routing import APIRoute

    monkeypatch.setenv('BATATIS_SEARCH_RATE_LIMIT', '100')
    reset_for_tests()
    path = tmp_path / 'codedb.sqlite'
    seeded = _synthetic_db(path)
    con = sqlite3.connect(path)
    for index, pid in enumerate(('9.1.1.2.(1)', '9.1.1.3.(1)', '9.1.1.4.(1)')):
        _insert_provision(con, 'B', pid, _long('w'), index + 2)
    for pid in ('2.3.1.1.(2)(a)', '2.3.1.1.(3)', '2.3.1.1.(2)(b)', '2.3.1.1.(4)',
                '2.4.1.1.(1)', '2.4.1.1.(2)', '2.4.1.1.(3)', '2.4.1.1.(4)', '2.4.1.1.(5)',
                '2.4.1.2.(1)', '2.4.1.2.(2)', '2.4.1.3.(1)', '2.4.1.4.(1)', '9.23.14.11.(2)'):
        division = 'B' if pid.startswith('9.') else 'C'
        _insert_provision(con, division, pid, _long('w'), 9)
    con.commit()
    con.close()
    app = create_app(store=CaseStore(tmp_path / 'cases.sqlite'), codes=Codes(path))
    client = TestClient(app, raise_server_exceptions=False)
    case_id = client.post('/cases', json={'title': 'route walk'}).json()['id']
    long = _long('q')
    calls = []
    delete = []
    for route in app.routes:
        if not isinstance(route, APIRoute):
            continue
        for method in sorted(route.methods - {'HEAD', 'OPTIONS'}):
            (delete if method == 'DELETE' else calls).append((method, route.path))
    assert calls
    lookup = next(route for route in app.routes if getattr(route, 'path', None) == '/code/{provision_id}')
    names = {getattr(param, 'alias', None) or param.name for param in lookup.dependant.query_params}
    assert names <= {'division'}
    for method, route_path in calls + delete:
        url = (route_path.replace('{case_id}', case_id)
               .replace('{provision_id}', '9.1.1.1.(1)'))
        kwargs = {}
        if route_path == '/code/search':
            kwargs['params'] = {'q': 'w00', 'division': 'B', 'limit': 20}
        elif route_path == '/code/{provision_id}':
            kwargs['params'] = {'division': 'B'}
        elif route_path == '/ccmc/search':
            kwargs['params'] = {'q': 'board'}
        elif route_path == '/section-c':
            kwargs['json'] = {'provisions': ['9.1.1.1.(1)']}
        elif route_path.endswith('/section-d') and method == 'POST':
            kwargs['json'] = {'provisions': ['9.1.1.1.(1)']}
        elif route_path.endswith('/facts'):
            kwargs['json'] = {
                'field': 'again', 'value': long, 'kind': 'pointed', 'status': 'unconfirmed',
                'source': {'type': 'code', 'ref': '9.1.1.1.(1)', 'quote': long},
            }
        elif route_path.endswith('/files'):
            kwargs['content'] = b'%PDF-1.4 route-walk'
            kwargs['headers'] = {'content-type': 'application/pdf'}
        elif route_path.endswith('/export'):
            kwargs['json'] = {'draft': True}
        elif route_path == '/cases' and method == 'POST':
            kwargs['json'] = {'title': 'another'}
        response = client.request(method, url, **kwargs)
        plain = ' '.join(re.findall(r'[A-Za-z0-9]+', response.text))
        assert not has_consecutive_words(plain, seeded[:26]), (method, route_path, response.status_code)
        assert response.headers.get('x-batatis-notice') == PII_NOTICE
        if 'application/json' in response.headers.get('content-type', '') and response.content:
            payload = response.json()
            assert isinstance(payload, dict) and payload['meta']['notice'] == PII_NOTICE
            _assert_budget(payload)
    assert client.get(f'/cases/{case_id}').status_code == 404


def test_access_log_has_ids_route_and_status_only(tmp_path, caplog):
    store = CaseStore(tmp_path / 'cases.sqlite')
    client = TestClient(create_app(store=store, codes=None))
    quote = 'applicant quote must stay out of the log'
    upload = b'%PDF-applicant-upload-must-stay-out-of-the-log'
    with caplog.at_level(logging.INFO, logger='engine.access'):
        created = client.post('/cases', json={'title': quote})
        case_id = created.json()['id']
        client.post(f'/cases/{case_id}/facts', json={
            'field': 'note', 'value': quote, 'kind': 'pointed', 'status': 'unconfirmed',
            'source': {'type': 'user_text', 'ref': 'msg', 'quote': quote},
        })
        uploaded = client.post(f'/cases/{case_id}/files', content=upload,
                               headers={'content-type': 'application/pdf', 'x-filename': 'plan.pdf'})
        assert uploaded.status_code == 201
        fetched = client.get(f'/cases/{case_id}')
    assert fetched.status_code == 200
    assert quote not in caplog.text
    assert b'applicant-upload-must-stay-out-of-the-log' not in caplog.text.encode()
    messages = [record.message for record in caplog.records if record.name == 'engine.access']
    assert f'POST /cases/{case_id}/facts 200' in messages
    assert f'GET /cases/{case_id} 200' in messages
    assert all(message.count(' ') == 2 for message in messages)


def test_delete_removes_the_case_and_its_file(tmp_path):
    store = CaseStore(tmp_path / 'cases.sqlite')
    client = TestClient(create_app(store=store, codes=None))
    case_id = client.post('/cases', json={'title': 'delete me'}).json()['id']
    saved = client.post(f'/cases/{case_id}/files', content=b'%PDF-1.4 keep',
                        headers={'content-type': 'application/pdf'})
    file_id = saved.json()['id']
    assert store.get_file(case_id, file_id)['data'].startswith(b'%PDF')
    removed = client.delete(f'/cases/{case_id}')
    assert removed.status_code == 204
    assert client.get(f'/cases/{case_id}').status_code == 404
    assert store.get_file(case_id, file_id) is None
    assert client.delete(f'/cases/{case_id}').status_code == 404
