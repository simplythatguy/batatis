"""In-sample regressions for the shipped provision search.

Skipped with the rest of the db tests when codedb/build/codedb.sqlite is absent.
Gold here is the Case A key plus Unc's confirmation of 9.23.17.3.(1). These
checks are not the held-out split.
"""
from codedb import search
from codedb.search_rank import article_of, covers

MIRA_GOLD = ('9.27.5.1.(2)', '9.27.5.3.(3)(b)', '9.23.17.3.(1)')
MIRA_ARTICLES = ('9.27.5.1.', '9.27.5.3.', '9.23.17.3.')
LONG = (
    'We manufacture NailBase CI-50, a 50 mm rigid foam panel with a 6 mm fibre-cement facer '
    'that replaces 11 mm OSB sheathing on 2x6 walls at 400 mm o.c. Vinyl siding is nailed '
    'directly into the facer with no furring. We want approval to sell it across Alberta and '
    'to build a pilot house in Edmonton: 2-storey single-family, about 190 m2, unsprinklered, '
    'builder Birchfield Example Homes, address 0000 Example Way NW. We have our product data '
    'sheet, a US lab permeance test summary, and an unsigned draft engineer letter about nail '
    'pull-out. We have no CCMC evaluation yet, no air-leakage test, and no bracing design. '
    'Do we need an engineer to stamp anything?'
)
IDR_001 = (
    'We make a new insulated sheathing panel and want it approved in Alberta so builders can '
    'nail siding straight onto it. What do I need?'
)
IDR_002 = (
    'Our panel is selling in two other provinces *(claim not verified)*. We want **approval to '
    'sell it across Alberta** and a first **pilot house** in Edmonton this spring. Builders love '
    "it because vinyl siding nails **straight into the facer**, so there's no OSB and no strapping."
)


def _ids(terms: str) -> list[str]:
    return [row['id'] for row in search(terms, division='B', limit=8)]


def _no_interior_nail(ids: list[str]) -> None:
    assert '9.29.9.3.' not in {article_of(hit) for hit in ids[:5]}


def test_mira_short_queries_cover_case_a_and_omit_interior_nails():
    for terms in ('sheathing nail siding', 'foam insulation sheathing'):
        ids = _ids(terms)
        for gold in MIRA_GOLD:
            assert any(covers(hit, gold) for hit in ids[:5]), (terms, gold, ids[:5])
        _no_interior_nail(ids)


def test_mira_long_query_keeps_two_gold_articles():
    ids = _ids(LONG)
    found = {article_of(hit) for hit in ids[:5]} & set(MIRA_ARTICLES)
    assert len(found) >= 2, ids[:5]
    _no_interior_nail(ids)


def test_cladding_through_insulation_ranks_attachment_and_furring():
    ids = _ids('cladding fastened through exterior insulation into furring')
    for gold in ('9.27.5.1.(1)', '9.27.5.1.(2)', '9.27.5.3.'):
        assert any(covers(hit, gold) or article_of(hit) == gold for hit in ids[:5]), (gold, ids[:5])
    _no_interior_nail(ids)


def test_case_a_identify_queries_omit_interior_nail_article():
    for terms in (IDR_001, IDR_002):
        _no_interior_nail(_ids(terms))


def test_provision_id_query_returns_that_provision_first():
    from codedb.ids import canon

    for query in ('3.1.9.1', '3.1.9.1.', '3.1.9.1.(1)', '9.10.19.3'):
        rows = search(query, division='B', limit=8)
        assert rows[0]['id'] == canon(query), (query, [row['id'] for row in rows])
        assert (rows[0].get('text') or '').split()
    article = search('3.1.9.1', division='B', limit=8)
    assert [row['id'] for row in article] == [
        '3.1.9.1.',
        '3.1.9.1.(1)', '3.1.9.1.(2)', '3.1.9.1.(3)', '3.1.9.1.(4)',
        '3.1.9.1.(5)', '3.1.9.1.(6)', '3.1.9.1.(7)',
    ]
    assert all((row.get('text') or '').split() for row in article)
    other = search('3.1.9.1', division='C', limit=8)
    assert all(row['id'] != '3.1.9.1.' for row in other)
    assert '9.99.99.99.' not in _ids('9.99.99.99')


def test_firestop_spellings_reach_the_firestops_article():
    for query in (
        'fire stopping', 'fire-stopping', 'firestopping',
        'fire stop', 'fire-stop', 'fire stops', 'firestop',
    ):
        assert '3.1.9.1.' in _ids(query), query
    split = search('firestop', division='B', limit=40)
    assert any(row['id'].startswith('9.10.13.14') for row in split)


def test_empty_article_hit_carries_its_sentences():
    rows = search('firestop', division='B', limit=8)
    article = next(row for row in rows if row['id'] == '3.1.9.1.')
    words = (article.get('text') or '').split()
    assert words and len(words) <= 25
    children = article.get('children') or []
    assert [child['id'] for child in children] == [
        '3.1.9.1.(1)', '3.1.9.1.(2)', '3.1.9.1.(3)', '3.1.9.1.(4)',
        '3.1.9.1.(5)', '3.1.9.1.(6)', '3.1.9.1.(7)',
    ]
    assert all((child.get('text') or '').split() and len(child['text'].split()) <= 25 for child in children)


def test_firestop_plastic_pipe_returns_general_rule_and_dwv_clause():
    ids = _ids('firestop plastic pipe penetration')
    assert '3.1.9.1.(1)' in ids
    assert '3.1.9.4.(4)(b)' in ids


def test_sprinkler_pipe_penetration_returns_the_three_sentences():
    ids = _ids('sprinkler pipe penetration fire separation')
    for gold in ('3.1.9.1.(4)', '3.1.9.2.(1)', '3.1.9.4.(1)'):
        assert gold in ids, (gold, ids)


def test_missing_objective_function_is_named_in_search_results():
    sprinkler = search('sprinkler pipe penetration fire separation', division='B', limit=8)
    by_id = {row['id']: row for row in sprinkler}
    assert by_id['3.1.9.1.(4)']['attribution'] == 'lookup not available'
    pipe = search('firestop plastic pipe penetration', division='B', limit=8)
    pipe_ids = {row['id']: row for row in pipe}
    assert pipe_ids['3.1.9.4.(4)']['attribution'] == 'lookup not available'
    assert pipe_ids['3.1.9.1.(1)']['attribution'] != 'lookup not available'
    assert pipe_ids['3.1.9.1.(1)']['attribution']
    for row in sprinkler + pipe:
        assert row.get('attribution')


def test_article_hit_uses_one_child_window_and_the_response_stays_short():
    from codedb import children
    from codedb.search_rank import RESPONSE_WORDS, SNIPPET_WORDS, present_article_hit

    rows = search('egress bedrooms', division='B', limit=8)
    quoted = [len((row.get('text') or '').split()) for row in rows]
    assert sum(quoted) <= RESPONSE_WORDS
    assert all(count <= SNIPPET_WORDS for count in quoted)
    article = next(row for row in rows if row['id'] == '9.9.10.1.')
    words = article['text'].split()
    assert words and len(words) <= SNIPPET_WORDS
    assert not article['text'].startswith('(See Note')

    def window_of(article: str) -> str:
        sentences = [child for child in children(article, division='B') if child['level'] == 'sentence']
        shown = present_article_hit(
            {'id': article, 'level': 'article', 'text': ''},
            sentences,
            [],
            terms=['firestop', 'plastic', 'pipe', 'penetration'],
        )
        return shown[0]['text']

    for article in ('3.1.9.1.', '3.1.9.4.'):
        text = window_of(article)
        words = text.split()
        assert words and len(words) <= SNIPPET_WORDS
        assert not text.startswith('(See Note')
        collapsed = [' '.join(child['text'].split()) for child in children(article, division='B') if child.get('text')]
        assert sum(text in body for body in collapsed) == 1

    replaced = present_article_hit(
        {'id': '9.1.1.1.', 'level': 'article', 'text': '(See Note A-9.1.1.1.)'},
        None,
        [
            {'id': '9.1.1.1.(1)(a)', 'level': 'clause', 'text': 'alpha beta gamma'},
            {'id': '9.1.1.1.(1)(b)', 'level': 'clause', 'text': ''},
        ],
    )
    assert [row['id'] for row in replaced] == ['9.1.1.1.(1)(a)']
    kept = present_article_hit(
        {'id': '9.1.1.1.', 'level': 'article', 'text': ''},
        {'id': '9.1.1.1.(1)', 'text': 'one two three four'},
        [],
    )
    assert kept[0]['text'] == 'one two three four'
    assert kept[0]['id'] == '9.1.1.1.'
