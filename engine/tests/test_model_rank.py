"""The model rank reorders the requirement ledger with quote-checked picks and never adds, removes or rewrites a rule."""
import re
from pathlib import Path
from types import SimpleNamespace

import pytest

from engine import llm_gate
from engine.codes import Codes
from engine.identify import fakes, verify
from engine.identify.config import load_config
from engine.identify.model_rank import RANK_SYSTEM, RankVerifier, apply, safe_reason
from engine.identify.pipeline import run
from engine.identify.providers import MeteredAnthropic
from engine.models import Case, Fact, Source

PROSE = ('We build houses. One bedroom window sits low with a long drop outside, and we want a window opening '
         'control device that limits the opening to about 100 mm while the window still works as an emergency '
         'escape that opens from the inside without keys or tools.')


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    llm_gate.reset_for_tests()
    for name in ('BATATIS_LIVE', 'BATATIS_PROVIDER', 'ANTHROPIC_API_KEY', 'BATATIS_IDENTIFY_CONFIG', 'VERCEL'):
        monkeypatch.delenv(name, raising=False)


@pytest.fixture
def fake_gate(monkeypatch):
    monkeypatch.setenv('BATATIS_PROVIDER', 'fake')     # the metered client passes the gate offline


@pytest.fixture(scope='module')
def codes():
    return Codes()


def verifier(codes, picker):
    return RankVerifier(codes.db_path, client=MeteredAnthropic(fakes.FakeAnthropic(picker)), model='claude-haiku-5-5')


def deterministic(codes):
    return run(PROSE, codes=codes, config=load_config(env={'BATATIS_IDENTIFY_MODEL_RANK': 'none'})).result


def ranked(codes, picker):
    return run(PROSE, codes=codes, config=load_config(env={}), ranker=verifier(codes, picker)).result


def ran(result):
    return any(stage.stage == 'model_rank' and not stage.errors for stage in result.trace.stages)


def test_picks_move_to_the_front_and_every_article_keeps_its_own_sentence_and_section_c(codes, fake_gate):
    before = {a.provision: a for a in deterministic(codes).articles}
    after = ranked(codes, fakes.honest_picks)
    picked = [a for a in after.articles if a.verifier == 'picked']
    assert ran(after) and picked and after.articles[:len(picked)] == picked
    assert {a.provision for a in after.articles} == set(before)
    assert [a.rank for a in after.articles] == list(range(1, len(after.articles) + 1))
    for article in after.articles:
        old = before[article.provision]
        assert (article.quote, article.provision_id, article.citation, article.objectives, article.functions) == \
               (old.quote, old.provision_id, old.citation, old.objectives, old.functions)
    first = [r.provision_id for r in after.requirements if r.division == 'B'][:len(picked)]
    assert first == [a.provision for a in picked]


@pytest.mark.parametrize('seed', range(5))
def test_invented_or_paraphrased_picks_never_reach_the_applicant(codes, seed, fake_gate):
    after = ranked(codes, fakes.lying_picks(seed))
    assert ran(after)
    assert {a.provision for a in after.articles} == {a.provision for a in deterministic(codes).articles}
    for article in after.articles:
        if article.verifier == 'picked':
            assert codes.provision(article.provision, 'B') is not None


def test_a_failed_call_or_pool_keeps_the_deterministic_order(codes, fake_gate, monkeypatch):
    class Broken:
        def verify(self, query, candidates):
            raise TimeoutError('provider timed out')

    order = [a.provision for a in deterministic(codes).articles]
    result = run(PROSE, codes=codes, config=load_config(env={}), ranker=Broken()).result
    assert [a.provision for a in result.articles] == order
    assert any(stage.stage == 'model_rank' and stage.errors == 1 for stage in result.trace.stages)
    monkeypatch.setattr('engine.identify.model_rank.bm25_rank', lambda *a, **k: (_ for _ in ()).throw(OSError('fts')))
    result = ranked(codes, fakes.honest_picks)
    assert [a.provision for a in result.articles] == order


@pytest.mark.parametrize('reason', [
    'The proposed device complies with the code and is safe.',
    'The design meets this requirement.',
    'The wall satisfies the fire rating.',
    'Applies together with 9.10.14.4. for the wall.',
    'Claude thinks this article governs the window.',
])
def test_a_reason_that_judges_the_design_names_a_provider_or_cites_a_number_is_not_shown(reason):
    assert safe_reason(reason) is None


def test_a_plain_reason_is_kept_and_capped():
    assert safe_reason('The window must still open fully for emergency escape.') == \
        'The window must still open fully for emergency escape.'
    assert len(safe_reason('The window must open. ' * 40)) <= 300


def test_rules_the_applicant_decided_stay_ahead_of_the_model_picks(codes):
    result = deterministic(codes)
    decided = result.requirements[-1]
    decided.discoveries[0].kind = 'human'
    picks = [(r.provision_id, 'The window must still open.') for r in result.requirements[:3] if r.division == 'B']
    apply(result, picks)
    assert result.requirements[0].id == decided.id
    assert [r.provision_id for r in result.requirements[1:1 + len(picks)]] == [p for p, _ in picks]


def test_a_save_carries_the_last_model_order_without_calling_the_model(codes, fake_gate):
    first = ranked(codes, fakes.honest_picks)
    picked = [a.provision for a in first.articles if a.verifier == 'picked']

    class Refuse:
        def verify(self, query, candidates):
            pytest.fail('a save called the model')

    again = run(PROSE, codes=codes, config=load_config(env={}), previous=first, ranker=Refuse(), rank=False).result
    assert [a.provision for a in again.articles][:len(picked)] == picked
    assert not any(stage.stage == 'model_rank' for stage in again.trace.stages)


def test_a_save_keeps_the_model_order_after_the_case_is_stored(codes, fake_gate):
    """A stored result is compacted: its article cards are gone, its trace keeps the picks."""
    from engine.identify.compact import compact_identify
    first = ranked(codes, fakes.honest_picks)
    stored = compact_identify(first)
    assert stored.articles == [] and stored.trace.picks

    class Refuse:
        def verify(self, query, candidates):
            pytest.fail('a save called the model')

    again = run(PROSE, codes=codes, config=load_config(env={}), previous=stored, ranker=Refuse(), rank=False).result
    picks = list(first.trace.picks)
    assert [r.provision_id for r in again.requirements if r.division == 'B'][:len(picks)] == picks
    assert [a.provision for a in again.articles][:len(picks)] == picks


def test_refresh_after_a_save_never_asks_for_a_model_rank(monkeypatch):
    from engine.identify import case_input
    seen = {}

    def fake_run(*_args, **kwargs):
        seen.update(kwargs)
        return SimpleNamespace(result=SimpleNamespace(trace=SimpleNamespace(seconds=0), decisions={}))

    monkeypatch.setattr('engine.identify.pipeline.run', fake_run)
    monkeypatch.setattr('engine.identify.config.load_config', lambda: SimpleNamespace(screen='requirements'))
    monkeypatch.setattr(case_input, 'compact_identify', lambda result: result, raising=False)
    monkeypatch.setattr('engine.identify.compact.compact_identify', lambda result: result)
    case = Case(facts=[Fact(field='project.description', value='A house', kind='pointed', status='confirmed',
                            source=Source(type='user_text', ref='Your description', quote='A house'))])
    case_input.refresh(case, None, object())
    assert seen.get('rank') is False


def test_the_result_names_the_rank_model_only_when_it_ran(codes, fake_gate):
    assert ranked(codes, fakes.honest_picks).model_ids['verifier'] == 'verifier-3'
    assert deterministic(codes).model_ids == {'screen': None, 'rerank': None, 'verifier': None}


def test_without_a_key_the_shipped_profile_stays_deterministic(codes, monkeypatch):
    monkeypatch.setenv('BATATIS_LIVE', '1')
    import anthropic
    monkeypatch.setattr(anthropic, 'Anthropic', lambda *a, **k: pytest.fail('Anthropic client built'))
    result = run(PROSE, codes=codes, config=load_config(env={})).result
    assert not any(stage.stage == 'model_rank' for stage in result.trace.stages)
    assert [a.provision for a in result.articles] == [a.provision for a in deterministic(codes).articles]


def test_the_rank_sends_the_measured_request_and_leaves_the_historical_verifier_alone(codes):
    v = RankVerifier(codes.db_path, client=object(), model='claude-haiku-5-5')
    text = v.prompt(PROSE, ['9.9.10.1.', '9.8.8.1.'])
    assert text.startswith('Applicant description:\n<<<\n' + PROSE)
    assert '\n[1] 9.9.10.1. Egress Windows or Doors for Bedrooms' in text and '\n[2] 9.8.8.1. Required Guards' in text
    assert all(len(line) < 900 for line in text.splitlines() if line.startswith('['))
    assert v.system == RANK_SYSTEM and verify.ClaudeVerifier.system == verify.SYSTEM != RANK_SYSTEM
    assert 'meets' not in RankVerifier.output_format.model_json_schema()['$defs']['RankPick']['properties']['reason']['description']


@pytest.mark.parametrize('seed', range(2))
def test_the_trace_says_how_many_picks_were_kept_and_why_others_were_dropped(codes, seed, fake_gate):
    stage = next(s for s in ranked(codes, fakes.lying_picks(seed)).trace.stages if s.stage == 'model_rank')
    kept, dropped = (int(n) for n in re.match(r'(\d+) kept, (\d+) dropped', stage.detail).groups())
    assert dropped > 0 and ('quote not found' in stage.detail or 'not in candidate list' in stage.detail)


def test_a_pick_written_without_the_trailing_period_still_counts(codes, fake_gate):
    """The bakeoff harness restored the period before checking ids; the engine reads them the same way."""
    def picker(user):
        return [{**pick, 'article': pick['article'].rstrip('.')} for pick in fakes.honest_picks(user)]

    with_period = [a.provision for a in ranked(codes, fakes.honest_picks).articles if a.verifier == 'picked']
    without = ranked(codes, picker)
    assert with_period and [a.provision for a in without.articles if a.verifier == 'picked'] == with_period
