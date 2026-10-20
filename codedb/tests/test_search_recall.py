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
