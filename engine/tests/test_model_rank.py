"""The model rank reorders the requirement ledger with quote-checked picks and never adds or removes a rule."""
import pytest

from engine import llm_gate
from engine.codes import Codes
from engine.identify import fakes
from engine.identify.config import load_config
from engine.identify.pipeline import run
from engine.identify.providers import MeteredAnthropic
from engine.identify.model_rank import RankVerifier

PROSE = ('We build houses. One bedroom window sits low with a long drop outside, and we want a window opening '
         'control device that limits the opening to about 100 mm while the window still works as an emergency '
         'escape that opens from the inside without keys or tools.')


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    llm_gate.reset_for_tests()
    for name in ('BATATIS_LIVE', 'BATATIS_PROVIDER', 'ANTHROPIC_API_KEY', 'BATATIS_IDENTIFY_CONFIG', 'VERCEL'):
        monkeypatch.delenv(name, raising=False)


@pytest.fixture(scope='module')
def codes():
    return Codes()


@pytest.fixture
def fake_gate(monkeypatch):
    monkeypatch.setenv('BATATIS_PROVIDER', 'fake')     # the metered client passes the gate offline


def verifier(codes, picker):
    return RankVerifier(codes.db_path, client=MeteredAnthropic(fakes.FakeAnthropic(picker)), model='claude-haiku-5-5')


def ran(result):
    return any(stage.stage == 'model_rank' and not stage.errors for stage in result.trace.stages)


def deterministic(codes):
    return run(PROSE, codes=codes, config=load_config(env={'BATATIS_IDENTIFY_MODEL_RANK': 'none'})).result


def test_quote_checked_picks_move_to_the_front_and_nothing_is_removed(codes, fake_gate):
    before = deterministic(codes)
    ranked = run(PROSE, codes=codes, config=load_config(env={}), ranker=verifier(codes, fakes.honest_picks)).result
    picked = [a for a in ranked.articles if a.verifier == 'picked']
    assert picked and ranked.articles[:len(picked)] == picked
    assert {a.provision for a in ranked.articles} == {a.provision for a in before.articles}
    assert [a.rank for a in ranked.articles] == list(range(1, len(ranked.articles) + 1))
    assert all(a.quote_source == 'verifier' and a.quote for a in picked)
    first = [r.provision_id for r in ranked.requirements if r.division == 'B'][:len(picked)]
    assert first == [a.provision for a in picked]
    assert ran(ranked)


@pytest.mark.parametrize('seed', range(5))
def test_invented_or_paraphrased_picks_never_reach_the_applicant(codes, seed, fake_gate):
    ranked = run(PROSE, codes=codes, config=load_config(env={}), ranker=verifier(codes, fakes.lying_picks(seed))).result
    real = {a.provision for a in deterministic(codes).articles}
    assert ran(ranked)
    assert {a.provision for a in ranked.articles} == real
    for article in ranked.articles:
        if article.verifier == 'picked':
            assert codes.provision(article.provision, 'B') is not None


def test_a_failed_call_keeps_the_deterministic_order(codes, fake_gate):
    class Broken:
        def verify(self, query, candidates):
            raise TimeoutError('provider timed out')

    ranked = run(PROSE, codes=codes, config=load_config(env={}), ranker=Broken()).result
    assert [a.provision for a in ranked.articles] == [a.provision for a in deterministic(codes).articles]
    assert any(stage.stage == 'model_rank' and stage.errors == 1 for stage in ranked.trace.stages)


def test_a_reason_that_states_compliance_is_not_shown(codes, fake_gate):
    def boastful(user):
        picks = fakes.honest_picks(user, n=1)
        for pick in picks:
            pick['reason'] = 'The proposed device complies with the code and is safe.'
        return picks

    ranked = run(PROSE, codes=codes, config=load_config(env={}), ranker=verifier(codes, boastful)).result
    picked = [a for a in ranked.articles if a.verifier == 'picked']
    assert picked and all(a.reason is None for a in picked)


def test_without_a_key_the_shipped_profile_stays_deterministic(codes, monkeypatch):
    monkeypatch.setenv('BATATIS_LIVE', '1')
    import anthropic
    monkeypatch.setattr(anthropic, 'Anthropic', lambda *a, **k: pytest.fail('Anthropic client built'))
    ranked = run(PROSE, codes=codes, config=load_config(env={})).result
    assert not any(stage.stage == 'model_rank' for stage in ranked.trace.stages)
    assert [a.provision for a in ranked.articles] == [a.provision for a in deterministic(codes).articles]


def test_the_result_names_the_rank_model_only_when_it_ran(codes, fake_gate):
    ranked = run(PROSE, codes=codes, config=load_config(env={}), ranker=verifier(codes, fakes.honest_picks)).result
    assert ranked.model_ids['verifier'] == 'verifier-3'
    assert deterministic(codes).model_ids == {'screen': None, 'rerank': None, 'verifier': None}


def test_the_request_is_the_one_the_bakeoff_measured(codes):
    v = RankVerifier(codes.db_path, client=object(), model='claude-haiku-5-5')
    text = v.prompt(PROSE, ['9.9.10.1.', '9.8.8.1.'])
    assert text.startswith('Applicant description:\n<<<\n' + PROSE)
    assert '\n[1] 9.9.10.1. Egress Windows or Doors for Bedrooms' in text and '\n[2] 9.8.8.1. Required Guards' in text
    assert all(len(line) < 900 for line in text.splitlines() if line.startswith('['))
