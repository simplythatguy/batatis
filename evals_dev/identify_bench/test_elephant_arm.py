"""Offline tests for the Elephant pool-scoring arm. No network: the fake transport answers every request."""
from __future__ import annotations

import pytest

from engine.identify.corpus import articles, bm25_rank
from engine.identify.elephant_runtime import CONTEXT_TOKENS, FRAMING_TOKENS, raw_ask, request_bytes
from engine.identify.fakes import fake_elephant_post
from engine.identify.screen import ELEPHANT_MODEL, Judge

from evals_dev.identify_bench import elephant_arm as arm

DESCRIPTION = ('Basement secondary suite in a house: the stair guard is 900 mm high instead of the required height, '
               'and the bedroom window opening is smaller than the egress window requirement.')


def fake_ask():
    return raw_ask(post=fake_elephant_post, credential=lambda: 'offline-fake')


def recorder(inner):
    sent = []

    def ask(state, questions, timeout):
        sent.append(request_bytes(state, questions, ELEPHANT_MODEL))
        return inner(state, questions, timeout)
    return ask, sent


@pytest.fixture(scope='module')
def pool():
    return bm25_rank(DESCRIPTION, arm.DB)[:60]


def test_production_is_byte_identical_to_engine_judge(pool):
    engine_ask, engine_sent = recorder(fake_ask())
    judge = Judge(engine_ask, chars=700, model=ELEPHANT_MODEL, method='elephant')
    expected = judge.judge(DESCRIPTION, articles(arm.DB), pool)
    arm_ask, arm_sent = recorder(fake_ask())
    scores, info = arm.score_pool(DESCRIPTION, pool, variant='production', ask=arm_ask)
    assert len(engine_sent) > 1                       # the pool spans several requests
    assert arm_sent == engine_sent
    assert scores == expected
    assert info['requests'] == len(engine_sent) and info['bytes'] == [len(b) for b in engine_sent]


@pytest.mark.parametrize('name', sorted(arm.VARIANTS))
def test_every_variant_scores_every_pool_article_within_bound(pool, name):
    ask, sent = recorder(fake_ask())
    scores, info = arm.score_pool(DESCRIPTION, pool, variant=name, ask=ask)
    assert list(scores) == pool and all(0 <= p <= 1 for p in scores.values())
    assert info['requests'] == len(sent) and info['questions'] == len(pool)
    v = arm.get_variant(name)
    for batch in arm.pack(DESCRIPTION, pool, v):
        state, questions = v.payload(DESCRIPTION, batch)
        body = request_bytes(state, questions, ELEPHANT_MODEL)       # raises when over the bound
        budget = sum(128 + 64 * len(q.get('criteria') or ()) for q in questions.values())
        assert len(body) + FRAMING_TOKENS + budget <= CONTEXT_TOKENS


@pytest.mark.parametrize('name', sorted(arm.VARIANTS))
def test_packing_is_greedy(pool, name):
    v = arm.get_variant(name)
    batches = arm.pack(DESCRIPTION, pool, v)
    assert [a for b in batches for a, _ in b] == pool
    for batch, nxt in zip(batches, batches[1:]):
        with pytest.raises(Exception):                 # the next card would not have fitted
            request_bytes(*v.payload(DESCRIPTION, [*batch, nxt[0]]), ELEPHANT_MODEL)


def test_oversized_single_card_is_an_error(pool, monkeypatch):
    monkeypatch.setattr(arm, 'card', lambda a, n: 'x' * 15_000)     # never truncated to fit
    with pytest.raises(Exception, match='request_too_large'):
        arm.pack(DESCRIPTION, pool[:2], arm.get_variant('production'))


def test_focused_cards_are_deterministic_and_bounded(pool):
    v = arm.get_variant('focused-350')
    arts = articles(arm.DB)
    for a in pool[:20]:
        first, second = v.card(a, DESCRIPTION), v.card(a, DESCRIPTION)
        assert first == second
        head = f"{arts[a]['title']} (Part {arts[a]['part']} > {arts[a]['section']} > {arts[a]['subsection']}): "
        assert first.startswith(head)
        assert len(first) - len(head) <= 350 + len(' ...')
    # most-overlapping sentence comes first; scope sentences stay first
    sents = arm.sentences('9.8.8.3.')
    best = max(sents, key=lambda s: len(arm.words(DESCRIPTION) & arm.words(s)))
    assert arm.focused_card(arts['9.8.8.3.'], sents, DESCRIPTION, 2000).split(': ', 1)[1].startswith(best)
    scope = ('1) This Article applies to guards.', '2) Guards shall be 900 mm high in a secondary suite.')
    body = arm.focused_card(arts['9.8.8.3.'], scope, DESCRIPTION, 2000).split(': ', 1)[1]
    assert body.startswith(scope[0])


def test_criteria_and_compact_requests_shape(pool):
    batch = [(a, arm.get_variant('production').card(a, DESCRIPTION)) for a in pool[:3]]
    state, questions = arm.get_variant('criteria').payload(DESCRIPTION, batch)
    assert all(set(q['criteria']) == {'true', 'false'} for q in questions.values())
    request_bytes(state, questions, ELEPHANT_MODEL)
    state, questions = arm.get_variant('compact').payload(DESCRIPTION, batch)
    assert state['rule'] == arm.RULE and list(state) == ['proposal', 'rule', 'articles']
    assert questions['q2']['instructions'] == 'Apply `rule` to article A2.'
    request_bytes(state, questions, ELEPHANT_MODEL)


def test_compact_packs_at_least_as_many_as_production(pool):
    assert len(arm.pack(DESCRIPTION, pool, arm.get_variant('compact'))) <= \
        len(arm.pack(DESCRIPTION, pool, arm.get_variant('production')))


def test_variant_names():
    assert arm.get_variant('focused-500+compact') == arm.Variant('focused-500+compact', 500, False, True)
    for bad in ('focused', 'focused-0', 'compact+compact', 'production+compact', 'nope'):
        with pytest.raises(ValueError):
            arm.get_variant(bad)


def test_plan_requests_dry_run(pool):
    plan = arm.plan_requests([('c1', DESCRIPTION, pool[:20]), ('c2', DESCRIPTION, pool)], 'production')
    assert plan['per_case']['c1'] >= 1 and plan['total'] == sum(plan['per_case'].values())


def test_cache_only_live_ask_never_dispatches(pool, monkeypatch):
    from evals_dev.identify_bench import live
    monkeypatch.setattr(live, '_stores', lambda: (type('S', (), {'get': lambda self, k: None})(), None, None))
    with pytest.raises(live.BudgetExhausted):
        arm.score_pool(DESCRIPTION, pool[:5], variant='production', budget=None)


# --- calibrated bound -------------------------------------------------------------------------------

def unbounded_fake_ask(state, questions, timeout):
    """The fake wire response, validated by the engine, without the engine's byte bound (as the probe does)."""
    import json
    from engine.identify import elephant_runtime as er
    body = json.dumps({'model': ELEPHANT_MODEL, 'state': state, 'questions': questions, 'provider': er.ROUTING},
                      ensure_ascii=False, separators=(',', ':')).encode('utf-8')
    status, raw = fake_elephant_post(body, {}, timeout)
    assert status == 200
    return er._validate(json.loads(raw), questions)


@pytest.mark.parametrize('name', sorted(arm.VARIANTS))
def test_calibrated_bound_scores_every_article_and_packs_tighter(pool, name):
    v = arm.get_variant(name)
    batches = arm.pack(DESCRIPTION, pool, v, bound='calibrated')
    assert [a for b in batches for a, _ in b] == pool
    for batch in batches:
        assert arm.calibrated_tokens(*v.payload(DESCRIPTION, batch)) <= arm.CAL_LIMIT
    for batch, nxt in zip(batches, batches[1:]):
        assert arm.calibrated_tokens(*v.payload(DESCRIPTION, [*batch, nxt[0]])) > arm.CAL_LIMIT
    assert len(batches) <= len(arm.pack(DESCRIPTION, pool, v))
    scores, info = arm.score_pool(DESCRIPTION, pool, variant=v, ask=unbounded_fake_ask, bound='calibrated')
    assert list(scores) == pool and info['requests'] == len(batches) and info['bound'] == 'calibrated'


def test_calibrated_bound_admits_the_measured_40_article_request(pool):
    # live: 40 production cards succeeded at 10,512 input tokens; the estimate must admit such a request
    v = arm.get_variant('production')
    batch = [(a, v.card(a, DESCRIPTION)) for a in pool[:40]]
    est = arm.calibrated_tokens(*v.payload(DESCRIPTION, batch))
    assert est <= arm.CAL_LIMIT
    assert len(arm.pack(DESCRIPTION, pool[:40], v, bound='calibrated')) == 1
    assert len(arm.pack(DESCRIPTION, pool[:40], v)) > 1          # the engine bound needs several


def test_calibrated_cache_only_never_dispatches(pool, monkeypatch):
    from evals_dev.identify_bench import live
    monkeypatch.setattr(live, '_stores', lambda: (type('S', (), {'get': lambda self, k: None})(), None, None))
    monkeypatch.setattr(live, 'load_keys', lambda *a: pytest.fail('credentials must not be loaded'))
    with pytest.raises(live.BudgetExhausted):
        arm.score_pool(DESCRIPTION, pool[:5], variant='production', budget=None, bound='calibrated')


def test_unknown_bound_is_an_error(pool):
    with pytest.raises(ValueError):
        arm.pack(DESCRIPTION, pool[:2], arm.get_variant('production'), bound='loose')
