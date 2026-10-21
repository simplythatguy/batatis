"""Library navigation is source-backed; context agrees with the Section C wire rows."""
import json
import sqlite3
from contextlib import closing

import pytest
from fastapi.testclient import TestClient

from codedb import store
from engine.api import create_app
from engine.code_library import _references, table_of_contents
from engine.codes import Codes
from engine.store import CaseStore


@pytest.fixture(scope='module')
def codes():
    return Codes()


@pytest.fixture(scope='module')
def client(codes, tmp_path_factory):
    return TestClient(create_app(store=CaseStore(tmp_path_factory.mktemp('library') / 'cases.sqlite'), codes=codes))


def test_toc_contains_every_article_in_code_order_and_no_invented_part_titles(client, codes):
    response = client.get('/code/toc?division=B')
    assert response.status_code == 200
    toc = response.json()
    assert toc['division'] == 'B' and toc['edition'] == 'NBC(AE) 2023, 2nd printing'
    assert all(part['title'] is None for part in toc['parts'])
    articles = []
    sections = []
    for part in toc['parts']:
        assert isinstance(part['part'], int)
        for section in part['sections']:
            sections.append(section['id'])
            assert isinstance(section['title'], str) and isinstance(section['articles'], list)
            articles.extend(article['id'] for article in section['articles'])
            for subsection in section['subsections']:
                assert isinstance(subsection['title'], str)
                articles.extend(article['id'] for article in subsection['articles'])
    with closing(store.connect(codes.db_path)) as con:
        expected = [row['id'] for row in con.execute("SELECT id FROM provisions WHERE doc='NBC-AE' "
                    "AND division='B' AND level='article' ORDER BY sort_key")]
        expected_sections = [row['id'] for row in con.execute("SELECT id FROM provisions WHERE doc='NBC-AE' "
                             "AND division='B' AND level='section' ORDER BY sort_key")]
    assert articles == expected
    assert sections == expected_sections
    assert '9.27.3.2.' in articles
    assert table_of_contents(codes.db_path) is table_of_contents(codes.db_path)


def test_toc_uses_sort_key_and_keeps_direct_articles_and_stored_part_headings(tmp_path):
    db = tmp_path / 'toc.sqlite'
    with sqlite3.connect(db) as con:
        con.execute('CREATE TABLE provisions (doc, division, id, level, part, section, subsection, title, sort_key)')
        # Deliberately insert out of order. Headings come only from these stored rows.
        con.executemany('INSERT INTO provisions VALUES (?,?,?,?,?,?,?,?,?)', [
            ('NBC-AE', 'B', '9.2.1.2.', 'article', 9, '9.2.', '9.2.1.', 'Second article', '9-2-1-2'),
            ('NBC-AE', 'B', '9.2.', 'section', 9, '9.2.', None, 'Section', '9-2'),
            ('NBC-AE', 'B', '9.2.1.', 'subsection', 9, '9.2.', '9.2.1.', 'Subsection', '9-2-1'),
            ('NBC-AE', 'B', '9.2.1.1.', 'article', 9, '9.2.', '9.2.1.', 'First article', '9-2-1-1'),
            ('NBC-AE', 'B', '9.2.0.1.', 'article', 9, '9.2.', None, 'Direct article', '9-2-0-1'),
            ('NBC-AE', 'B', '9.', 'part', 9, None, None, 'Stored part heading', '9'),
        ])
    [part] = table_of_contents(db).parts
    assert part.title == 'Stored part heading'
    [section] = part.sections
    assert [article.id for article in section.articles] == ['9.2.0.1.']
    assert [article.id for article in section.subsections[0].articles] == ['9.2.1.1.', '9.2.1.2.']


@pytest.mark.parametrize('division', ['A', 'C'])
def test_other_divisions_have_the_same_toc_shape(client, division):
    response = client.get('/code/toc', params={'division': division})
    assert response.status_code == 200
    assert response.json()['division'] == division and response.json()['parts']


def test_invalid_toc_division(client):
    assert client.get('/code/toc?division=wrong').status_code == 400


@pytest.mark.parametrize('pid', ['9.27.3.2.(1)', '9.25.5.2.(1)(b)', '9.23.17.3.(1)', '9.32.1.3.(2)'])
def test_context_matches_section_c_exactly(client, codes, pid):
    response = client.get(f'/code/{pid}/context')
    assert response.status_code == 200
    context = response.json()
    [row] = client.post('/section-c', json={'provisions': [pid]}).json()['items']
    status = {'direct': 'direct', 'inherited from parent': 'inherited', 'no row in the attribution table': 'no-row'}
    assert context['attribution_status'] == status[row['attribution_status']]
    assert context['inherited_from'] == row['attributed_via']
    assert context['citation'] == row['citation'] == codes.provision(pid)['citation']
    assert {item['code']: item['title'] for item in context['objectives']} == {
        pair['objective']: pair['objective_text'] for pair in row['pairs']}
    assert {item['code']: item['title'] for item in context['functions']} == {
        pair['function']: pair['function_text'] for pair in row['pairs']}
    assert {(item['objective'], item['text']) for item in context['intent']} == {
        (block['objective'], text) for block in row['intents'] for text in block['intents']}
    assert context['intent_differs'] == row['differs']
    if row['differs']:
        [detail] = json.loads(context['intent_differs_detail'])
        assert detail == {'id': pid, 'only_in_intent': row['only_in_intent'], 'only_in_ae': row['only_in_ae']}
    else:
        assert context['intent_differs_detail'] is None
    assert context['path'][-1]['id'] == pid
    for node in context['path']:
        source = codes.provision(node['id'])
        assert (node['level'], node['title']) == (source['level'], source['title'])


def test_article_context_aggregates_rows_and_keeps_real_path_notes_and_references(client, codes):
    context = client.get('/code/9.27.3.2./context').json()
    rows = client.post('/section-c', json={'provisions': ['9.27.3.2.']}).json()['items']
    assert {item['code'] for item in context['objectives']} == {
        pair['objective'] for row in rows for pair in row['pairs']}
    assert [node['id'] for node in context['path']] == ['9.27.', '9.27.3.', '9.27.3.2.']
    assert len(context['referenced_by']) <= 20
    assert context['references'] or context['referenced_by']
    assert all(codes.provision(pid) is not None for pid in context['references'] + context['referenced_by'])
    rec = codes.provision('9.27.3.2.')
    assert [note['id'] for note in context['notes']] == [note['note_id'] for note in rec['notes']]
    assert all(len(note['excerpt']) <= 320 for note in context['notes'])


def test_reference_parser_keeps_only_complete_existing_targets():
    existing = frozenset({'9.27.3.2.', '9.27.3.2.(1)', '9.25.5.2.(1)(b)', '9.27.'})
    assert _references('See Article 9.27.3.2., Sentence 9.27.3.2.(1) and Clause 9.25.5.2.(1)(b). '
                       'Ignore 9.27.3.2.(99), Note A-9.27.3.2. and 9.99.99.99.', existing) == [
                           '9.27.3.2.', '9.27.3.2.(1)', '9.25.5.2.(1)(b)']


@pytest.mark.parametrize('pid,status', [('not-an-id', 400), ('9.99.99.99.', 404)])
def test_context_preserves_lookup_errors(client, pid, status):
    plain = client.get(f'/code/{pid}?division=B')
    context = client.get(f'/code/{pid}/context')
    assert context.status_code == plain.status_code == status
    assert context.json()['detail'] == plain.json()['detail']


def test_context_preserves_extra_parameter_error(client):
    assert client.get('/code/9.27.3.2./context?extra=x').status_code == 400
