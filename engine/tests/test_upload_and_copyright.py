import asyncio
import hashlib
import json
import logging
import re
import sqlite3

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from codedb import store as codedb_store
from engine.api import create_app, read_capped
from engine.export import EXPORT_FAILED_DETAIL, FORM_NOT_FOUND_DETAIL
from engine.codes import Codes
from engine.copyright import NRC_PUBLICATION_URL, PII_NOTICE, attribute_code, has_consecutive_words
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
                 json.dumps([nested, nested]), json.dumps([note, note]), 1, 1))
    con.execute('INSERT INTO provisions_fts (doc, division, id, title, text) VALUES (?,?,?,?,?)',
                ('NBC-AE', 'B', '9.1.1.1.(1)', 'Synthetic sentence', text))
    con.execute('INSERT INTO docs VALUES (?,?,?,?,?,?,?)',
                ('NBC-AE', 'NBC(AE) 2023 p2', 'code', 1, 'x', 'y', 'abc'))
    con.commit()
    con.close()
    return text.split()


def test_search_rejects_more_than_20_hits(tmp_path, monkeypatch):
    monkeypatch.setenv('BATATIS_SEARCH_RATE_LIMIT', '10')
    reset_for_tests()
    path = tmp_path / 'codedb.sqlite'
    provision_words = _synthetic_db(path)
    client = TestClient(create_app(store=CaseStore(tmp_path / 'cases.sqlite'), codes=Codes(path)))
    found = client.get('/code/search', params={'q': 'w00', 'limit': 20})
    assert found.status_code == 200
    plain = ' '.join(re.findall(r'[A-Za-z0-9]+', found.text))
    assert has_consecutive_words(plain, provision_words)
    rejected = client.get('/code/search', params={'q': 'w00', 'limit': 21})
    assert rejected.status_code == 422 and rejected.json()['detail'] == 'The maximum is 20.'


def test_applicant_quotes_are_not_labelled_as_code_text():
    long = _long('u')
    applicant = attribute_code({
        'field': 'note',
        'value': long,
        'question': long,
        'source': {'type': 'user_text', 'ref': 'msg', 'quote': long},
    })
    assert applicant['value'] == long
    assert applicant['question'] == long
    assert applicant['source']['quote'] == long
    assert 'url' not in applicant and 'url' not in applicant['source']
    code = attribute_code({
        'value': long,
        'source': {'type': 'code', 'ref': '9.1.1.1.(1)', 'quote': long},
        'pdf_page': 4,
    })
    assert code['source']['quote'] == long
    assert code['value'] == long
    assert code['source']['url'] == NRC_PUBLICATION_URL
    assert code['url'] == NRC_PUBLICATION_URL


def test_code_text_stays_whole_and_keeps_its_citation_and_link():
    long = _long('p')
    body = attribute_code({
        'id': '9.1.1.1.(1)',
        'citation': 'NBC(AE) 2023 p2, Div B, Sentence 9.1.1.1.(1)',
        'division': 'B',
        'pdf_page': 12,
        'text': long,
        'notes': [long, {'text': long, 'note_id': 'A-9.1.1.1.'}],
        'clauses': [long, [long, 'a']],
        'title': 'kept whole ' + long,
    })
    assert body['text'] == long
    assert body['clauses'] == [long, [long, 'a']]
    assert body['notes'][0] == long
    assert body['notes'][1]['text'] == long
    assert body['title'] == 'kept whole ' + long
    assert body['citation'].startswith('NBC(AE) 2023 p2')
    assert body['url'] == NRC_PUBLICATION_URL
    assert body['notes'][1]['url'] == NRC_PUBLICATION_URL
    assert 'clipped' not in body


def test_code_lookup_returns_the_full_clause(tmp_path, monkeypatch):
    monkeypatch.setenv('BATATIS_SEARCH_RATE_LIMIT', '10')
    reset_for_tests()
    path = tmp_path / 'codedb.sqlite'
    _synthetic_db(path)
    client = TestClient(create_app(store=CaseStore(tmp_path / 'cases.sqlite'), codes=Codes(path)))
    body = client.get('/code/9.1.1.1.(1)', params={'division': 'B'}).json()
    assert body['id'] == '9.1.1.1.(1)'
    assert body['text'] == _long('w')
    assert body['clauses'][0] == _long('c')
    assert body['clauses'][1] == 'a'
    assert body['citation'].startswith('NBC(AE) 2023 p2')
    assert body['url'] == NRC_PUBLICATION_URL
    assert 'clipped' not in body
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
    assert fact['source']['quote'] == long
    assert fact['source']['url'] == NRC_PUBLICATION_URL
    assert fact['source']['ref'] == '9.1.1.1.(1)'
    assert 'clipped' not in fact['source']


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


def _export_client(tmp_path, monkeypatch):
    monkeypatch.delenv('BATATIS_SCC_FORM', raising=False)
    monkeypatch.setattr('engine.export.scc.blockers', lambda *args, **kwargs: [])
    monkeypatch.setattr('engine.export.scc._canonical_case', lambda case, codes: case)
    path = tmp_path / 'codedb.sqlite'
    _synthetic_db(path)
    client = TestClient(create_app(store=CaseStore(tmp_path / 'cases.sqlite'), codes=Codes(path)))
    case_id = client.post('/cases', json={'title': 'export'}).json()['id']
    return client, case_id


def test_export_without_the_scc_form_is_503(tmp_path, monkeypatch, caplog):
    monkeypatch.setattr('engine.export.scc.DEFAULT_FORM', tmp_path / 'missing-guide.pdf')
    monkeypatch.setattr('engine.export.scc.BUNDLE_FORM', tmp_path / 'missing-bundle.pdf')
    client, case_id = _export_client(tmp_path, monkeypatch)
    with caplog.at_level(logging.ERROR, logger='engine.api'):
        response = client.post(f'/cases/{case_id}/export', json={'draft': True})
    assert response.status_code == 503
    assert response.json()['detail'] == FORM_NOT_FOUND_DETAIL
    assert 'unavailable on this deployment' in caplog.text
    assert str(tmp_path) not in response.text


def test_mismatched_form_is_500_without_a_path(tmp_path, monkeypatch, caplog):
    bad = tmp_path / 'wrong-form.pdf'
    bad.write_bytes(b'%PDF-1.4 not the council form')
    monkeypatch.setattr('engine.export.scc.DEFAULT_FORM', bad)
    monkeypatch.setattr('engine.export.scc.BUNDLE_FORM', tmp_path / 'missing-bundle.pdf')
    client, case_id = _export_client(tmp_path, monkeypatch)
    with caplog.at_level(logging.ERROR, logger='engine.api'):
        response = client.post(f'/cases/{case_id}/export', json={'draft': True})
    assert response.status_code == 500
    assert response.json()['detail'] == EXPORT_FAILED_DETAIL
    assert str(bad) not in response.text
    assert hashlib.sha256(bad.read_bytes()).hexdigest() not in response.text
    assert str(bad) in caplog.text


def _assert_search_limited(response):
    assert response.status_code == 429
    assert response.json()['detail'].startswith('Search limit reached; try again in ')
    assert response.json()['detail'].endswith(' seconds')
    assert response.headers['retry-after'].isdigit()


def test_search_is_rate_limited(tmp_path, monkeypatch):
    monkeypatch.setenv('BATATIS_SEARCH_RATE_LIMIT', '2')
    reset_for_tests()
    path = tmp_path / 'codedb.sqlite'
    _synthetic_db(path)
    client = TestClient(create_app(store=CaseStore(tmp_path / 'cases.sqlite'), codes=Codes(path)))
    assert client.get('/code/search', params={'q': 'w00'}).status_code == 200
    assert client.get('/code/search', params={'q': 'w00'}).status_code == 200
    _assert_search_limited(client.get('/code/search', params={'q': 'w00'}))


def test_ccmc_search_shares_the_search_limit(tmp_path, monkeypatch):
    monkeypatch.setenv('BATATIS_SEARCH_RATE_LIMIT', '2')
    reset_for_tests()
    path = tmp_path / 'codedb.sqlite'
    _synthetic_db(path)
    client = TestClient(create_app(store=CaseStore(tmp_path / 'cases.sqlite'), codes=Codes(path)))
    assert client.get('/code/search', params={'q': 'w00'}).status_code == 200
    assert client.get('/ccmc/search', params={'q': 'board'}).status_code in (200, 503)
    _assert_search_limited(client.get('/ccmc/search', params={'q': 'board'}))


def _insert_provision(con, division, pid, text, page):
    con.execute('''INSERT INTO provisions (doc, division, id, level, part, section, subsection, article,
                   sentence, clause, subclause, parent_id, article_title, title, text, text_raw, clauses,
                   pdf_page, pdf_page_end, volume, sort_key)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',
                ('NBC-AE', division, pid, 'sentence', 2, '2.3.', '2.3.1.', '2.3.1.1.', 1, None, None,
                 None, 'Synthetic', pid, text, text, json.dumps(['a']), page, page, 1, pid))
    con.execute('INSERT INTO provisions_fts (doc, division, id, title, text) VALUES (?,?,?,?,?)',
                ('NBC-AE', division, pid, pid, text))


# Engine routes the Vite client calls (web/src/api/client.ts).
WEB_BUNDLE_ROUTES = {
    ('POST', '/cases'),
    ('GET', '/cases/{case_id}'),
    ('POST', '/cases/{case_id}/facts'),
    ('GET', '/code/search'),
    ('GET', '/code/{provision_id}'),
    ('POST', '/section-c'),
}
CASE_BUILDER_ROUTES = {
    ('POST', '/cases/{case_id}/section-d'),
    ('GET', '/cases/{case_id}/section-d/issues'),
    ('GET', '/cases/{case_id}/professional'),
    ('GET', '/cases/{case_id}/process-fields'),
    ('GET', '/cases/{case_id}/gaps'),
}


def test_every_registered_route_returns_code_text_and_not_the_sqlite(tmp_path, monkeypatch):
    from fastapi.routing import APIRoute

    monkeypatch.setenv('BATATIS_SEARCH_RATE_LIMIT', '100')
    reset_for_tests()
    path = tmp_path / 'codedb.sqlite'
    _synthetic_db(path)
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
    api_routes = [route for route in app.routes if isinstance(route, APIRoute)]
    for route in app.routes:
        original = getattr(route, 'original_router', None)
        if original is not None:
            api_routes.extend(child for child in original.routes if isinstance(child, APIRoute))
    for route in api_routes:
        for method in sorted(route.methods - {'HEAD', 'OPTIONS'}):
            (delete if method == 'DELETE' else calls).append((method, route.path))
    assert calls
    required = WEB_BUNDLE_ROUTES | CASE_BUILDER_ROUTES
    missing = required - set(calls)
    assert not missing, missing
    lookup = next(route for route in app.routes if getattr(route, 'path', None) == '/code/{provision_id}')
    names = {getattr(param, 'alias', None) or param.name for param in lookup.dependant.query_params}
    assert names <= {'division'}
    # Section D writes Section C. Gaps then validates citations against the source text,
    # which this synthetic database does not include. Read the gaps route first.
    def _before_section_d(item):
        method, path = item
        return 1 if method == 'POST' and path.endswith('/section-d') else 0

    for method, route_path in sorted(calls, key=_before_section_d) + delete:
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
        assert not response.content.startswith(b'SQLite format 3'), (method, route_path)
        assert b'codedb.sqlite' not in response.headers.get('content-disposition', '').encode()
        assert response.headers.get('x-batatis-notice') == PII_NOTICE, (
            method, route_path, response.status_code, response.text[:500])
        if (method, route_path) in required:
            assert response.status_code < 500, (method, route_path, response.status_code, response.text)
        if 'application/json' in response.headers.get('content-type', '') and response.content:
            payload = response.json()
            assert isinstance(payload, dict) and payload['meta']['notice'] == PII_NOTICE
    for sqlite_path in ('/codedb/build/codedb.sqlite', '/codedb.sqlite', '/api/codedb/build/codedb.sqlite'):
        missed = client.get(sqlite_path)
        assert missed.status_code == 404
        assert not missed.content.startswith(b'SQLite format 3')
    assert client.get(f'/cases/{case_id}').status_code == 404


def test_search_returns_full_hits_up_to_the_limit(tmp_path, monkeypatch):
    monkeypatch.setenv('BATATIS_SEARCH_RATE_LIMIT', '10')
    reset_for_tests()
    path = tmp_path / 'codedb.sqlite'
    _synthetic_db(path)
    con = sqlite3.connect(path)
    passages = []
    for index in range(4):
        passage = 'qxshared ' + _long(f'h{index}')
        passages.append(passage)
        _insert_provision(con, 'B', f'9.8.1.{index + 1}.(1)', passage, 30 + index)
    con.commit()
    con.close()
    client = TestClient(create_app(store=CaseStore(tmp_path / 'cases.sqlite'), codes=Codes(path)))
    response = client.get('/code/search', params={'q': 'qxshared', 'limit': 20})
    assert response.status_code == 200
    hits = response.json()['items']
    assert 1 <= len(hits) <= 20
    assert len(hits) >= 4
    by_text = {hit['text'] for hit in hits}
    assert set(passages) <= by_text
    assert all(hit['citation'] for hit in hits)
    assert all(hit['url'] == NRC_PUBLICATION_URL for hit in hits)


def test_exported_pdf_keeps_the_full_provision_and_the_nrc_link(tmp_path):
    import io
    from types import SimpleNamespace

    from pypdf import PdfReader

    from engine.export.appendix import build_appendix
    from engine.models import Case
    from engine.section_c import section_c_rows

    path = tmp_path / 'codedb.sqlite'
    seeded = _synthetic_db(path)
    con = sqlite3.connect(path)
    extras = []
    ids = ['9.1.1.1.(1)']
    for index in range(3):
        pid = f'9.8.2.{index + 1}.(1)'
        ids.append(pid)
        text = _long(f'p{index}')
        extras.append(text.split())
        _insert_provision(con, 'B', pid, text, 40 + index)
        con.execute('INSERT INTO intents VALUES (?,?,?,?,?,?,?,?,?,?)',
                    ('NBC-2020', 'NBC-AE', pid, 0, 'OS1.1', '[]',
                     json.dumps([text]), json.dumps([text]), 40 + index, 40 + index))
    for pid in ('2.3.1.1.(2)(a)', '2.3.1.1.(3)', '2.3.1.1.(2)(b)', '2.3.1.1.(4)'):
        _insert_provision(con, 'C', pid, _long('w'), 9)
    con.commit()
    con.close()
    codes = Codes(path)
    case = Case(title='pdf budget', provisions=ids, section_c=section_c_rows(ids, codes))
    plan = SimpleNamespace(overflow=[], rows_in_form=1, docs_in_form=0)
    pdf = build_appendix(case, plan, {}, {'version': 'test'}, codes=codes, open_items=[])
    text = '\n'.join(page.extract_text() or '' for page in PdfReader(io.BytesIO(pdf)).pages)
    for needle in [seeded, *extras]:
        assert has_consecutive_words(text, needle)
    assert case.section_c[0].citation in text
    assert '0316d953-0d55-4311-af69-cad55efec499' in text


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
