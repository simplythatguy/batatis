"""Offline tests for lexical candidates: reference parsing, emitted ids, expansion order."""
import pytest

from engine.identify import corpus
from engine.tests._db_skip import require_repo_db
from evals_dev.identify_bench.candidates_lexical import (DB, Graph, Ref, bm25, build_graph, expand, interleave,
                                                         parse_refs, pool, rrf, subsection_complete)


@pytest.mark.parametrize('text, refs', [
    ('See Article 9.10.9.6. for', [Ref('article', '9.10.9.6.')]),
    ('Articles 9.10.14.1. to 9.10.14.5. apply', [Ref('article', '9.10.14.1.', '9.10.14.5.')]),
    ('required by Sentence 9.10.15.4.(2)', [Ref('article', '9.10.15.4.')]),
    ('Sentences 11.2.1.2.(1) to (4), the', [Ref('article', '11.2.1.2.')]),
    ('Clause 9.10.9.6.(1)(b) or', [Ref('article', '9.10.9.6.')]),
    ('Subclause 9.10.9.6.(1)(b)(ii) and Sentence (2)', [Ref('article', '9.10.9.6.')]),
    ('Sentences 3.2.2.25.(2), 3.2.2.32.(2) and 3.2.2.85.(2) for',
     [Ref('article', '3.2.2.25.'), Ref('article', '3.2.2.32.'), Ref('article', '3.2.2.85.')]),
    ('Articles 3.1.5.2. to 3.1.5.24., 3.1.13.4. and 3.2.2.16., a building',
     [Ref('article', '3.1.5.2.', '3.1.5.24.'), Ref('article', '3.1.13.4.'), Ref('article', '3.2.2.16.')]),
    ('Subsection 9.10.8. and Section 9.20.', [Ref('subsection', '9.10.8.'), Ref('section', '9.20.')]),
    ('Subsections 9.29.4. to 9.29.9., b)', [Ref('subsection', '9.29.4.', '9.29.9.')]),
    ('given in Table 9.10.14.4.-A for', [Ref('table', '9.10.14.4.')]),
    ('Clause 1.2.1.1.(1)(b) of Division A, the', []),
    ('in Article 1.4.1.2. of Division A and Article 1.3.2.1.', [Ref('article', '1.3.2.1.')]),
    ('the requirements of Sentence (1) apply', []),
    ('(See Note A-9.10.9.6.(1).)', []),
])
def test_parse_refs(text, refs):
    assert parse_refs(text) == refs


def _toy() -> Graph:
    order = ['1.1.1.1.', '1.1.1.2.', '1.1.1.3.', '1.1.2.1.', '2.1.1.1.', '2.1.1.2.']
    g = Graph(order=order, pos={a: i for i, a in enumerate(order)},
              subsection_members={'1.1.1.': order[:3], '1.1.2.': order[3:4], '2.1.1.': order[4:]})
    g.refs_out = {'1.1.1.1.': {'2.1.1.2.': 'note', '1.1.2.1.': 'article'}, '2.1.1.1.': {'1.1.1.3.': 'article'}}
    g.refs_in = {'2.1.1.2.': {'1.1.1.1.': 'note'}, '1.1.2.1.': {'1.1.1.1.': 'article'},
                 '1.1.1.3.': {'2.1.1.1.': 'article'}}
    g.container_out = {'2.1.1.2.': {'1.1.1.': 'subsection'}}
    for members in g.subsection_members.values():
        for a in members:
            g.same_subsection[a] = [b for b in members if b != a]
    return g


def test_expand_keeps_seed_order_and_ranks_neighbours():
    g = _toy()
    # seed 0's neighbours first, an article edge before a note edge, then seed 1's neighbours.
    assert expand(['1.1.1.1.', '2.1.1.1.'], g=g) == ['1.1.1.1.', '2.1.1.1.', '1.1.2.1.', '2.1.1.2.', '1.1.1.3.']
    assert expand(['1.1.1.1.', '2.1.1.1.'], max_new=1, g=g) == ['1.1.1.1.', '2.1.1.1.', '1.1.2.1.']
    assert expand(['1.1.2.1.'], mode='in', g=g) == ['1.1.2.1.', '1.1.1.1.']
    assert expand(['1.1.2.1.'], hops=2, mode='both', g=g) == ['1.1.2.1.', '1.1.1.1.', '2.1.1.2.']
    assert expand(['2.1.1.2.'], types=('subsection',), g=g) == ['2.1.1.2.', '1.1.1.1.', '1.1.1.2.', '1.1.1.3.']
    assert expand(['9.9.9.9.', '1.1.1.2.'], g=g) == ['1.1.1.2.']      # unknown ids never emitted


def test_subsection_complete_and_pool():
    g = _toy()
    assert subsection_complete(['1.1.1.2.', '2.1.1.1.'], top=1, g=g) == ['1.1.1.2.', '2.1.1.1.', '1.1.1.1.', '1.1.1.3.']
    assert pool(['1.1.1.1.', '2.1.1.1.', '1.1.1.2.'], 4, seeds=1, g=g) == ['1.1.1.1.', '1.1.2.1.', '2.1.1.2.', '2.1.1.1.']


def test_fusion():
    assert rrf(['a', 'b', 'c'], ['b', 'c', 'd'])[:2] == ['b', 'c']
    assert interleave(['a', 'b'], ['c', 'a', 'd']) == ['a', 'c', 'b', 'd']


def test_graph_and_arms_emit_only_codedb_articles():
    require_repo_db()
    arts = corpus.articles(DB)
    g = build_graph(DB)
    assert len(g.order) == len(arts)
    for src, dsts in g.refs_out.items():
        assert src in arts and all(d in arts and d != src for d in dsts)
    for members in list(g.subsection_members.values()):
        assert all(a in arts for a in members)
    # Known edges: Article 9.10.9.6. cites 9.10.9.7. to 9.10.9.9.; its note cites 3.1.9.1.
    assert {'9.10.9.7.', '9.10.9.8.', '9.10.9.9.'} <= set(g.refs_out['9.10.9.6.'])
    assert g.refs_out['9.10.9.6.'].get('3.1.9.1.') == 'note'
    ranked = bm25('fire separation penetration by plumbing pipe in a house', 50)
    assert ranked and all(a in arts for a in ranked)
    grown = expand(ranked[:10], hops=2, mode='both', g=g)
    assert grown[:10] == ranked[:10] and len(set(grown)) == len(grown) and all(a in arts for a in grown)
