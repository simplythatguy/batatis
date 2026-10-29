"""The table-of-contents search sends the measured request, widens the rank's pool with real Division B
articles only, and adds a picked article to the ledger only from CodeDB with a word-for-word quote."""
import ast
import re
from pathlib import Path

import pytest

from engine import llm_gate
from engine.codes import Codes
from engine.identify import cards, fakes
from engine.identify.compact import compact_identify
from engine.identify.config import DIVISION_B_ARTICLES, load_config
from engine.identify.corpus import articles, card
from engine.identify.model_rank import TOC_SYSTEM, RankVerifier, TocCandidates, pool
from engine.identify.pipeline import run
from engine.identify.providers import MeteredAnthropic
from engine.identify.verify import normalize
from engine.public_names import names_a_provider

from engine.tests.test_model_rank import PROSE

REQUESTS = Path(__file__).resolve().parents[2] / 'experiments' / 'workflow-bakeoff-v2' / 'requests.py'
ON, OFF = {}, {'BATATIS_IDENTIFY_MODEL_RANK_TOC': '0'}
_LISTED = re.compile(r'^\[\d+\] (\S+) ', re.M)


def measured(name: str):
    """A literal from the bakeoff's request builder, read without importing it."""
    tree = ast.parse(REQUESTS.read_text())
    return next(ast.literal_eval(node.value) for node in tree.body
                if isinstance(node, ast.Assign) and any(getattr(t, 'id', None) == name for t in node.targets))


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    llm_gate.reset_for_tests()
    for name in ('BATATIS_LIVE', 'BATATIS_PROVIDER', 'ANTHROPIC_API_KEY', 'BATATIS_IDENTIFY_CONFIG', 'VERCEL'):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv('BATATIS_PROVIDER', 'fake')     # the metered client passes the gate offline


@pytest.fixture(scope='module')
def codes():
    return Codes()


@pytest.fixture(scope='module')
def ledger(codes):
    result = run(PROSE, codes=codes, config=load_config(env={'BATATIS_IDENTIFY_MODEL_RANK': 'none'})).result
    return [r.provision_id for r in result.requirements if r.division == 'B']


@pytest.fixture(scope='module')
def outside(codes, ledger):
    """Division B articles discovery did not reach for PROSE, with Section C rows and a first sentence."""
    found = [a for a in articles(codes.db_path) if a not in set(ledger)
             and cards.terms(codes, a)[0] and cards.first_sentence(codes, a)[0]]
    assert len(found) >= 2
    return found


def quote_of(user: str, article: str) -> str:
    """The first words of an article's card as the rank request lists it."""
    line = next(line for line in user.splitlines() if line.startswith('[') and f'] {article} ' in line)
    return fakes._quote(line.split(f'] {article} ', 1)[1])


def ranked(codes, *, picker=fakes.honest_picks, searcher=fakes.toc_search, env=ON):
    fake = fakes.FakeAnthropic(picker, searcher)
    ranker = RankVerifier(codes.db_path, client=MeteredAnthropic(fake), model='claude-haiku-5-5')
    return run(PROSE, codes=codes, config=load_config(env=env), ranker=ranker).result, fake.messages.calls


def stage(result, name):
    return next((s for s in result.trace.stages if s.stage == name), None)


def test_the_search_sends_the_measured_request(codes):
    _, calls = ranked(codes)
    search = calls[0]
    assert TOC_SYSTEM == measured('R0_SYSTEM') and search['system'] == TOC_SYSTEM
    assert (search['model'], search['output_config']) == ('claude-haiku-5-5', {'effort': 'medium'})
    user = search['messages'][0]['content']
    assert user.startswith(f'Applicant description:\n<<<\n{PROSE}\n>>>\n\n')
    lines = user.split('\n>>>\n\n', 1)[1].splitlines()[1:]
    expected = [f"{a} {art['title']} (Part {art['part']} > {art['section']} > {art['subsection']})"
                for a, art in articles(codes.db_path).items()]
    assert len(expected) == DIVISION_B_ARTICLES and lines == expected
    schema = TocCandidates.model_json_schema()
    item = schema['$defs'][schema['properties']['candidates']['items']['$ref'].rsplit('/', 1)[1]]
    shape = measured('R0_SCHEMA')
    assert schema['required'] == shape['required'] and set(item['properties']) == {'id', 'why'}
    assert item['required'] == shape['properties']['candidates']['items']['required']


def test_invented_out_of_division_and_duplicate_ids_never_reach_the_pool_or_the_applicant(codes, outside):
    named = ['99.1.1.1.', '9.99.99.9.', '2.3.1.1.', '1.4.1.2.', 'Article 9.9.10.1.', outside[0],
             outside[0].rstrip('.'), outside[0] + '(1)', outside[1]]
    seen = {}

    def picker(user):
        seen['pool'] = _LISTED.findall(user)
        lies = fakes.lying_picks(3)(user)
        return lies + [{'article': a, 'quote': 'shall be provided', 'reason': 'r', 'confidence': 0.9}
                       for a in ('99.1.1.1.', '2.3.1.1.', '1.4.1.2.')]

    result, _ = ranked(codes, picker=picker, searcher=lambda user: [{'id': n, 'why': 'w'} for n in named])
    assert seen['pool'][:2] == [outside[0], outside[1]]
    assert len(seen['pool']) == len(set(seen['pool'])) <= 72
    assert not {'99.1.1.1.', '9.99.99.9.', '2.3.1.1.', '1.4.1.2.'} & set(seen['pool'])
    assert stage(result, 'model_search').detail == '2 candidates; 5 named ids are not Division B articles'
    arts = articles(codes.db_path)
    assert all(a.provision in arts for a in result.articles)
    assert all(r.provision_id in arts for r in result.requirements if r.division == 'B')
    assert set(result.trace.added) <= {outside[0], outside[1]}


def test_an_article_only_the_search_found_joins_with_codedb_section_c_and_its_verbatim_quote(codes, outside):
    found, unverifiable = outside[0], outside[1]

    def picker(user):
        return [{'article': found, 'quote': quote_of(user, found), 'reason': 'The window must open.', 'confidence': 0.9},
                {'article': unverifiable, 'quote': 'ZZZ ' + quote_of(user, unverifiable), 'reason': 'r',
                 'confidence': 0.8}]

    searcher = lambda user: [{'id': found, 'why': 'w'}, {'id': unverifiable, 'why': 'w'}]
    result, _ = ranked(codes, picker=picker, searcher=searcher)
    assert result.trace.added == [found]
    assert unverifiable not in {a.provision for a in result.articles} | {r.provision_id for r in result.requirements}
    article = next(a for a in result.articles if a.provision == found)
    record = next(r for r in result.requirements if r.provision_id == found)
    assert result.articles[0] is article and article.verifier == 'picked' and article.quote_source == 'verifier'
    assert article.quote == record.quote and normalize(article.quote) in normalize(card(articles(codes.db_path)[found], None))
    assert [d.kind for d in record.discoveries] == ['model_search'] and record.applicability == 'unknown'
    objectives, functions, _ = cards.terms(codes, article.provision_id or found)
    assert objectives and [t.id for t in article.objectives] == [t.id for t in objectives]
    assert [t.id for t in article.functions] == [t.id for t in functions]
    assert article.citation == cards.citation(codes, article.provision_id or found)
    assert record.citation.startswith('NBC(AE) 2023 p2, Div B, Article ' + found)
    if article.provision_id:
        assert normalize(article.quote) in normalize(codes.provision(article.provision_id, 'B')['text'])
        assert record.evidence_ids
    assert not names_a_provider(compact_identify(result).model_dump_json())


def test_a_pick_never_moves_ahead_of_a_rule_the_applicant_named(codes):
    prose = PROSE + ' The bedroom window also follows Article 9.9.10.1.'
    off = run(prose, codes=codes, config=load_config(env={'BATATIS_IDENTIFY_MODEL_RANK': 'none'})).result
    found = next(a for a in articles(codes.db_path) if a not in {r.provision_id for r in off.requirements}
                 and cards.first_sentence(codes, a)[0])
    fake = fakes.FakeAnthropic(lambda user: [{'article': found, 'quote': quote_of(user, found), 'reason': 'r',
                                              'confidence': 0.9}], lambda user: [{'id': found, 'why': 'w'}])
    ranker = RankVerifier(codes.db_path, client=MeteredAnthropic(fake), model='claude-haiku-5-5')
    result = run(prose, codes=codes, config=load_config(env=ON), ranker=ranker).result
    assert result.trace.added == [found]
    position = [r.provision_id for r in result.requirements]
    named = [r.provision_id for r in result.requirements if any(d.kind == 'explicit' for d in r.discoveries)]
    assert '9.9.10.1.' in named and all(position.index(n) < position.index(found) for n in named)


def test_a_failed_search_still_ranks_the_normal_pool(codes):
    def broken(user):
        raise TimeoutError('provider timed out')

    seen = {}

    def picker(user):
        seen['pool'] = _LISTED.findall(user)
        return fakes.honest_picks(user)

    result, calls = ranked(codes, picker=picker, searcher=broken)
    assert stage(result, 'model_search').errors == 1 and stage(result, 'model_rank').errors == 0
    deterministic = run(PROSE, codes=codes, config=load_config(env={'BATATIS_IDENTIFY_MODEL_RANK': 'none'})).result
    assert len(calls) == 2 and seen['pool'] == pool(deterministic, PROSE, Path(codes.db_path))
    picked = [a for a in result.articles if a.verifier == 'picked']
    assert picked and result.articles[:len(picked)] == picked and result.trace.added == []


def test_a_failed_rank_after_a_search_keeps_the_deterministic_order(codes, ledger, outside):
    def broken(user):
        raise TimeoutError('provider timed out')

    result, _ = ranked(codes, picker=broken, searcher=lambda user: [{'id': outside[0], 'why': 'w'}])
    assert stage(result, 'model_search').errors == 0 and stage(result, 'model_rank').errors == 1
    assert [r.provision_id for r in result.requirements if r.division == 'B'] == ledger
    assert result.trace.added == [] and not any(a.verifier == 'picked' for a in result.articles)


def test_a_save_keeps_the_added_articles_and_calls_no_model(codes, outside):
    found = outside[0]
    picker = lambda user: [{'article': found, 'quote': quote_of(user, found), 'reason': 'r', 'confidence': 0.9},
                           *fakes.honest_picks(user)]
    first, calls = ranked(codes, picker=picker, searcher=lambda user: [{'id': found, 'why': 'w'}])
    assert found in first.trace.added
    stored = compact_identify(first)                  # what a case keeps between requests

    class Refuse:
        def verify(self, query, candidates):
            pytest.fail('a save called the model')

        search = verify

    again = run(PROSE, codes=codes, config=load_config(env=ON), previous=stored, ranker=Refuse(), rank=False).result
    assert len(calls) == 2
    assert not {'model_search', 'model_rank'} & {s.stage for s in again.trace.stages}
    assert again.trace.added == first.trace.added
    order = [r.provision_id for r in again.requirements]
    assert order[:len(first.trace.picks)] == [r.provision_id for r in first.requirements][:len(first.trace.picks)]
    record = next(r for r in again.requirements if r.provision_id == found)
    assert record.quote == next(r for r in first.requirements if r.provision_id == found).quote
    assert [d.kind for d in record.discoveries] == ['model_search']


def test_with_the_search_off_the_rank_is_todays(codes):
    seen = {}

    def picker(user):
        seen['pool'] = _LISTED.findall(user)
        return fakes.honest_picks(user)

    result, calls = ranked(codes, picker=picker, env=OFF)
    deterministic = run(PROSE, codes=codes, config=load_config(env={'BATATIS_IDENTIFY_MODEL_RANK': 'none'})).result
    assert len(calls) == 1 and stage(result, 'model_search') is None
    assert seen['pool'] == pool(deterministic, PROSE, Path(codes.db_path))
    assert result.trace.added == [] and 'model_rank_toc' not in result.trace.config
