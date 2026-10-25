"""Bounded experimental identification, through offline transports; no database or network access."""
from dataclasses import replace
import os
from pathlib import Path

import pytest

from engine import llm_gate
from engine.identify import fakes, pipeline, shortlist
from engine.identify.commit import CommitPolicy
from engine.identify.config import ConfigError, IdentifyConfig, load_config
from engine.identify.corpus import card
from engine.identify.providers import Transports, metered_openai_json, transports
from engine.identify.screen import ELEPHANT_MODEL, GOVERN, SELF_QUESTION, Judge, noul
from engine.public_names import names_a_provider
from engine.tests._network_guard import block_network


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    for name in list(os.environ):
        if name.startswith(('BATATIS_', 'VERCEL')) or name in {
                'OPENROUTER_API_KEY', 'OPENAI_API_KEY', 'ANTHROPIC_API_KEY', 'JEV_API_KEY', 'TYPESAFE_API_KEY'}:
            monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv('BATATIS_PROVIDER', 'fake')
    block_network(monkeypatch)
    llm_gate.reset_for_tests()
    yield
    llm_gate.reset_for_tests()


def corpus(n):
    return {f'9.1.1.{i}.': dict(id=f'9.1.1.{i}.', title=f'Ventilation {i}', part=9,
                               section='General', subsection='Ventilation',
                               text=f'Ventilation requirement {i} shall be addressed. ' + 'Full body text. ' * 55
                                    + f'Unique final requirement {i}.') for i in range(1, n + 1)}


class Codes:
    """Synthetic read-only code source. Any attempt to open db_path would fail."""
    db_path = Path('/nonexistent/synthetic-code-source.sqlite')

    def __init__(self, arts):
        self.arts = arts

    def provision(self, pid, division='B'):
        article = pid.split('(')[0]
        art = self.arts.get(article)
        if not art:
            return None
        return dict(id=pid, text=art['text'] if '(' in pid else '', citation=f'Synthetic {pid}',
                    level='sentence' if '(' in pid else 'article', attributions=[],
                    children=[] if '(' in pid else [dict(id=article + '(1)', level='sentence')])

    def definition(self, _):
        return None


@pytest.fixture
def source(monkeypatch):
    arts = corpus(85)
    monkeypatch.setattr(pipeline, 'articles', lambda _: arts)
    monkeypatch.setattr(pipeline, '_lexical', lambda *_: list(arts))
    monkeypatch.setattr(pipeline, 'process_refs', lambda _: [])
    return arts, Codes(arts)


def config(**changes):
    return replace(load_config(env={'BATATIS_IDENTIFY_SCREEN': 'shortlist'}), **changes)


def fitted(cfg):
    return CommitPolicy('calibrated', 'injected fit', {9: 0.0001}, 3, cfg.config_hash)


def row(a, quote, **changes):
    return dict(article=a, label='applies', quote=quote, reason='The proposal changes this requirement.',
                confidence=0.9, **changes)


def test_historical_hashes_and_default_configuration_are_unchanged():
    assert IdentifyConfig().config_hash == '464590da27f5cbf1'
    assert load_config(env={'BATATIS_IDENTIFY_SCREEN': 'jev',
                            'BATATIS_IDENTIFY_RERANK': 'jev'}).config_hash == '5f1c92331550984a'
    assert load_config(env={'BATATIS_IDENTIFY_SCREEN': 'decisions',
                            'BATATIS_IDENTIFY_RERANK': 'decisions'}).config_hash == '43272040048a6036'
    assert replace(IdentifyConfig(), shortlist_n=99).as_dict() == IdentifyConfig().as_dict()
    assert 'question_style' not in IdentifyConfig().as_dict()
    assert IdentifyConfig().verify_n == 15 and IdentifyConfig().top_k == 10


def test_opt_in_hash_binds_question_prompt_pool_and_review_prompts(monkeypatch):
    shared = IdentifyConfig()
    assert replace(shared, question_style='self').config_hash != shared.config_hash
    cfg = config()
    for change in ({'shortlist_n': 61}, {'shortlist_toc_n': 39}, {'verifier_effort': 'high'},
                   {'question_style': 'self'}, {'rerank': 'none'}):
        assert replace(cfg, **change).config_hash != cfg.config_hash
    old = cfg.config_hash
    monkeypatch.setattr(shortlist, 'REVIEW_SYSTEM', shortlist.REVIEW_SYSTEM + ' Changed.')
    assert cfg.config_hash != old and shared.config_hash == '464590da27f5cbf1'
    old = cfg.config_hash
    monkeypatch.setattr(shortlist, 'TOC_SYSTEM', shortlist.TOC_SYSTEM + ' Changed.')
    assert cfg.config_hash != old


@pytest.mark.parametrize('values', [{'shortlist_n': 121}, {'shortlist_toc_n': 61},
                                 {'shortlist_n': 0}, {'shortlist_n': True}, {'shortlist_toc_n': 1.5},
                                 {'verifier': 'anthropic'}, {'rerank': 'jev'}])
def test_shortlist_configuration_is_bounded(values):
    with pytest.raises(ConfigError):
        config(**values)


@pytest.mark.parametrize('style', ['shared', 'self'])
def test_question_payload_shapes_and_real_offline_wire(style):
    arts = corpus(2)
    judge = Judge(lambda *_: None, method='elephant', model=ELEPHANT_MODEL, question_style=style)
    batch = [(a, card(art, 700)) for a, art in arts.items()]
    state, questions = judge._payload('Ventilation', batch)
    if style == 'shared':
        assert state == {'proposal': 'Ventilation', 'articles': {'A0': batch[0][1], 'A1': batch[1][1]}}
        assert questions == {f'q{i}': noul(GOVERN.format(L=f'A{i}')) for i in range(2)}
    else:
        assert state == {'proposal': 'Ventilation'}
        assert questions == {f'q{i}': noul(SELF_QUESTION.format(card=text)) for i, (_, text) in enumerate(batch)}
    tp = transports(scoring={'elephant'})
    scores = Judge(tp.elephant, question_style=style).judge('Ventilation', arts, list(arts))
    assert set(scores) == set(arts) and len(tp.log.calls) == 1
    assert tp.log.calls[0]['accounting'] == 'settled'
    assert set(fakes.fake_jev_ask()(state, questions, 5)['answers']) == set(questions)


def test_self_shape_keeps_byte_admission_and_aborts_without_retry():
    from engine.identify.elephant_runtime import ElephantError
    arts = corpus(60)
    calls = []
    def broken(*_):
        calls.append(1)
        raise ElephantError('rate_limited')
    judge = Judge(broken, method='elephant', model=ELEPHANT_MODEL, question_style='self', attempts=4)
    with pytest.raises(ElephantError, match='rate_limited'):
        judge.judge('Ventilation', arts, list(arts))
    assert len(calls) == 1
    calls.clear()
    arts[list(arts)[-1]]['text'] = '☃' * 20000
    judge.chars = 50000
    with pytest.raises(ElephantError, match='request_too_large'):
        judge.judge('Ventilation', arts, list(arts))
    assert not calls


def test_whole_toc_validated_union_and_cap(source):
    arts, _ = source
    ids = list(arts)
    captured = []
    def select(name, schema, system, user, **kw):
        captured.append((name, system))
        return {'articles': [ids[-1], ids[-1], '9.1.1.1', '99.99.99.99.', None, {}, ids[-2]]}, {}
    pool = shortlist.candidate_pool(select, 'Ventilation', arts, ids, model='gpt-6-luna', effort='medium',
                                    toc_n=2, pool_n=5)
    assert pool == [ids[-1], ids[0], ids[-2], ids[1], ids[2]]
    assert all(f'{a} {arts[a]["title"]}' in captured[0][1] for a in ids)
    assert captured[0][0] == 'toc_candidates'


@pytest.mark.parametrize('payload', [None, [], {}, {'articles': {}}, {'articles': []},
                                     {'articles': ['99.99.99.99.', '9.1.1.1', None]}])
def test_unusable_toc_is_rejected(source, payload):
    arts, _ = source
    with pytest.raises(shortlist.ShortlistUnavailable):
        shortlist.candidate_pool(lambda *a, **kw: (payload, {}), 'Ventilation', arts, list(arts),
                                 model='gpt-6-luna', effort='medium', toc_n=40, pool_n=60)


def test_strict_labels_quotes_duplicates_and_unknowns_default_to_check(source):
    arts, _ = source
    ids = list(arts)[:7]
    good = row(ids[0], 'Ventilation requirement 1 shall be addressed.')
    duplicate = row(ids[1], 'Ventilation requirement 2 shall be addressed.')
    payload = {'labels': [good, duplicate, duplicate, row(ids[2], 'Invented quotation.'),
                          row(ids[3], arts[ids[3]]['title']),
                          {**row(ids[4], 'Ventilation'), 'confidence': float('nan')},
                          {**row(ids[5], 'Ventilation'), 'label': 'certain'},
                          row('99.99.99.99.', 'Ventilation'), {'article': []}, None]}
    review = shortlist.parse_review(payload, ids, arts)
    assert [p.article for p in review.picks] == [ids[0]]
    assert all(review.labels[a].label == 'check' for a in ids[1:])
    assert review.labels[ids[-1]].flag == 'missing'
    assert review.counts == dict(malformed=3, unknown=2, duplicate=1, missing=1, quote_downgraded=2)
    assert set(review.labels) == set(ids)


@pytest.mark.parametrize('payload', [None, [], {'labels': None}, {'labels': 'invalid'}, {'labels': [], 'extra': 1}])
def test_malformed_review_keeps_every_article_as_check(source, payload):
    arts, _ = source
    ids = list(arts)
    review = shortlist.parse_review(payload, ids, arts)
    assert not review.picks and list(review.labels) == ids
    assert all(v.label == 'check' for v in review.labels.values())


def test_review_reasons_are_neutral_and_unknown_rows_are_never_exposed(source):
    arts, _ = source
    a = next(iter(arts))
    review = shortlist.parse_review({'labels': [dict(article=a, label='applies',
        quote='Ventilation requirement 1 shall be addressed.', reason='OpenAI says this applies.', confidence=0.9),
        row('99.99.99.99.', 'Private invented quotation')]}, [a], arts)
    assert review.picks[0].reason == ''
    assert not review.dropped and review.counts['unknown'] == 1


def test_shortlist_pipeline_keeps_all_60_reviews_full_text_and_never_commits(source):
    arts, codes = source
    cfg = config(question_style='self', verify_n=1, top_k=1)
    tp, requests = transports(scoring={'elephant'}), []
    original = tp.openai
    def capture(name, schema, system, user, **kw):
        requests.append((name, user))
        return original(name, schema, system, user, **kw)
    tp.openai = capture
    out = pipeline.run('Ventilation', codes=codes, config=cfg, transports=tp, policy=fitted(cfg))
    result = out.result
    assert len(result.articles) == 60 and len(result.choices) == 3
    assert result.committed == [] and result.commit_policy['max_commits'] == 0
    assert result.commit_policy['thresholds'] == {} and result.commit_policy['status'] == 'uncalibrated'
    assert out.screen is None and len(out.rerank) == 60 and not result.trace.exhaustive
    assert [name for name, _ in requests] == ['toc_candidates', 'pool_review']
    _, supplied = fakes.parse_request(requests[-1][1])
    assert len(supplied) == 60
    assert all(f'Unique final requirement {a.split(".")[3]}.' in text for a, text in supplied)
    assert {a for a, _ in supplied} == {a.provision for a in result.articles}
    assert all(a.quote_source == 'verifier' and a.status in ('choice', 'candidate') for a in result.articles)
    assert 'Non-exhaustive' in result.label and 'required articles may be missing' in result.label
    assert 'Offline fake providers' in result.label and not names_a_provider(result.model_dump_json())
    assert {c['provider'] for c in tp.log.calls} == {'openai', 'elephant'}
    assert sum(c['output_tokens'] for c in tp.log.calls) > 0


@pytest.mark.parametrize('failure', ['rerank', 'malformed_rerank', 'review', 'malformed_review', 'missing_rows'])
def test_partial_failure_keeps_the_entire_tentative_pool(source, failure):
    arts, codes = source
    cfg = config()
    tp = transports(scoring={'elephant'})
    original = tp.openai
    def broken(*_, **__):
        raise RuntimeError('OpenRouter secret body must never reach the response')
    if failure == 'rerank':
        tp.elephant = broken
    elif failure == 'malformed_rerank':
        tp.elephant = lambda state, questions, timeout: {'answers': {q: {'noul': 'invalid'} for q in questions}}
    else:
        def review(name, *args, **kw):
            if name != 'pool_review':
                return original(name, *args, **kw)
            if failure == 'review':
                return broken()
            return ({'labels': []} if failure == 'missing_rows' else {'labels': 'bad'}), {}
        tp.openai = review
    out = pipeline.run('Ventilation', codes=codes, config=cfg, transports=tp, policy=fitted(cfg))
    result = out.result
    assert len(result.articles) == 60 and not result.committed and not result.trace.exhaustive
    assert out.screen is None and not names_a_provider(result.model_dump_json())
    assert 'secret body' not in result.model_dump_json()
    if failure in ('rerank', 'malformed_rerank'):
        assert out.rerank is None and result.narrowed and 'Rerank unavailable' in result.label
    else:
        assert not result.trace.picks and not result.narrowed
        assert all(a.verifier != 'picked' for a in result.articles)


@pytest.mark.parametrize('failure', ['unavailable', 'malformed', 'empty'])
def test_keyword_fallback_is_labelled_and_bounded(source, failure):
    _, codes = source
    cfg = config(shortlist_n=45)
    tp = Transports(kind='live')
    if failure != 'unavailable':
        tp.openai = metered_openai_json(lambda *a, **kw: ({'articles': []} if failure == 'empty' else {}, {}))
    out = pipeline.run('Ventilation', codes=codes, config=cfg, transports=tp, policy=fitted(cfg))
    result = out.result
    assert result.mode == 'bm25_fallback' and len(result.articles) == 45
    assert 'keyword search' in result.label and 'Nothing is committed' in result.label
    assert not result.committed and out.screen is out.rerank is None
    assert all(a.verifier == 'not_run' and a.status == 'fallback' for a in result.articles)


def test_empty_corpus_never_dispatches_a_provider(source, monkeypatch):
    arts, codes = source
    arts.clear()
    tp = Transports(kind='live', openai=lambda *a, **kw: pytest.fail('empty corpus dispatched'))
    result = pipeline.run('Ventilation', codes=codes, config=config(), transports=tp).result
    assert result.mode == 'bm25_fallback' and result.articles == [] and not result.narrowed


def test_optional_rerank_and_review_can_be_disabled_without_losing_candidates(source):
    _, codes = source
    cfg = config(rerank='none', verifier='none', top_k=1)
    tp = transports(scoring=set())
    out = pipeline.run('Ventilation', codes=codes, config=cfg, transports=tp, policy=fitted(cfg))
    assert len(out.result.articles) == 60 and not out.result.trace.picks
    assert len(tp.log.calls) == 1 and tp.log.calls[0]['provider'] == 'openai'
    assert all(a.verifier == 'not_run' for a in out.result.articles)
    assert not out.result.committed and out.screen is out.rerank is None
    assert 'review was off or unavailable' in out.result.label


def test_shortlist_cannot_run_as_exhaustive_relevance_and_question_style_is_bound(monkeypatch):
    from engine import relevance
    monkeypatch.setenv('BATATIS_IDENTIFY_SCREEN', 'shortlist')
    with pytest.raises(relevance.RelevanceUnavailable, match='requires exhaustive scoring'):
        relevance.live_judge()
    monkeypatch.setenv('BATATIS_IDENTIFY_SCREEN', 'elephant')
    monkeypatch.setenv('BATATIS_IDENTIFY_QUESTION_STYLE', 'self')
    judge = relevance.live_judge()
    assert judge.question_style == judge.config.question_style == 'self'
    assert judge.config.config_hash != '464590da27f5cbf1'


def test_injected_self_judge_keeps_its_actual_shape_in_the_configuration_hash(source, monkeypatch):
    from importlib import import_module
    identify_module = import_module('engine.identify')
    arts, codes = source
    monkeypatch.setattr(identify_module, 'articles', lambda _: arts)
    tp = transports(scoring={'elephant'})
    judge = Judge(tp.elephant, question_style='self')
    result = identify_module.identify('Ventilation', codes.db_path, judge=judge, parts={9})
    assert result.config_hash == replace(IdentifyConfig(), question_style='self').config_hash
    assert set(result.screen) == set(arts)


def test_default_fake_pipeline_uses_historical_shapes_and_limits(source, monkeypatch):
    arts, codes = source
    arts.update(corpus(2080))
    monkeypatch.setattr(pipeline, '_rank_shortlist', lambda *a: pytest.fail('default entered experiment'))
    tp, calls = transports(scoring={'elephant'}), []
    original = tp.openai
    def capture(name, schema, system, user, **kw):
        calls.append((name, len(fakes.parse_request(user)[1])))
        return original(name, schema, system, user, **kw)
    tp.openai = capture
    out = pipeline.run('Ventilation', codes=codes, config=IdentifyConfig(), transports=tp)
    assert calls == [('picks', 15)]
    assert len(out.screen) == 2080 and len(out.rerank) == 60
    assert len(out.result.articles) == 10 and out.result.trace.exhaustive
    assert out.result.trace.config_hash == '464590da27f5cbf1'


def test_self_question_experiment_ignores_injected_calibration(source):
    arts, codes = source
    arts.update(corpus(2080))
    cfg = replace(IdentifyConfig(), question_style='self')
    result = pipeline.run('Ventilation', codes=codes, config=cfg, policy=fitted(cfg)).result
    assert result.trace.picks and not result.committed
    assert result.commit_policy['thresholds'] == {} and 'Tentative suggestions' in result.label
