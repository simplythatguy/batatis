"""The neutral words a client may read about how Batatis works (engine/public_names.py)."""
from __future__ import annotations

import json

import pytest

from engine.identify.config import ANTHROPIC_VERIFIER, OPENAI_RERANK, OPENAI_VERIFIER, IdentifyConfig
from engine.identify.screen import ELEPHANT_MODEL, JEV_MODEL
from engine.models_identify import BenchmarkRecord, IdentifyResult, IdentifyTrace, StageRecord
from engine.public_names import (CUSTOM, GENERIC_LABEL, MODEL_VERSIONS, UNAVAILABLE, VERIFIER_UNAVAILABLE,
                                 names_a_provider, public_config, public_event, public_label, public_method,
                                 public_model_id, public_ranker, public_spend, public_text)
from engine.relevance_models import PUBLIC_MODEL

RAW_CONFIG = IdentifyConfig().as_dict()
RAW_SPEND = {'jev': {'requests': 21, 'input_tokens': 900, 'output_tokens': 40, 'usd': 0.000123},
             'openai': {'requests': 1, 'input_tokens': 300, 'output_tokens': 50, 'usd': 0.00021}}


def test_every_model_the_pipeline_can_pin_has_an_opaque_version():
    for pin in (ELEPHANT_MODEL, JEV_MODEL, OPENAI_VERIFIER, OPENAI_RERANK, ANTHROPIC_VERIFIER):
        assert pin in MODEL_VERSIONS and not names_a_provider(public_model_id(pin)), pin
    assert public_model_id(JEV_MODEL) == PUBLIC_MODEL
    assert {public_model_id(OPENAI_VERIFIER), public_model_id(ANTHROPIC_VERIFIER)} == {'verifier-1', 'verifier-2'}


def test_a_pin_that_is_not_listed_reads_as_custom_and_a_neutral_id_is_kept():
    assert public_model_id(None) is None
    assert public_model_id('some-new-model-9') == CUSTOM
    for neutral in (PUBLIC_MODEL, 'verifier-1', CUSTOM):
        assert public_model_id(neutral) == neutral


@pytest.mark.parametrize('text', [
    'BATATIS_LIVE is off or the TypeSafe credential is absent', 'jev gate: offline-cap', 'Jev unavailable',
    'OpenAI unavailable', 'failed: openai gate: offline-cap', 'gpt-6-luna read the top 15 in full',
    'claude-sonnet-5-5', 'Anthropic is not a configured identify provider', 'ANTHROPIC_API_KEY is absent',
    'JEV_API_KEY', 'Elephant', 'OpenRouter', 'baseten/elephant-1:free', 'OPENROUTER_API_KEY'])
def test_text_that_names_a_provider_a_model_or_a_credential_is_caught(text):
    assert names_a_provider(text) and public_text(text, UNAVAILABLE) == UNAVAILABLE


@pytest.mark.parametrize('text', [None, '', 'scoring unavailable', 'RuntimeError/TimeoutError',
                                  'screen scored 2079 of 2080 Division B articles', 'keyword screen found no article',
                                  '3 picked, 1 dropped', 'not run: keyword fallback'])
def test_neutral_text_is_kept(text):
    assert not names_a_provider(text) and public_text(text, UNAVAILABLE) == text


def test_methods_read_as_model_and_the_keyword_methods_are_kept():
    assert {public_method(m) for m in ('elephant', 'jev', 'openai', 'anthropic', 'model')} == {'model'}
    assert [public_method(m) for m in ('bm25', 'bm25_v3', 'none')] == ['bm25', 'bm25_v3', 'none']
    assert public_ranker('jev screen + jev rerank') == public_ranker('jev screen + openai rerank') == 'model screen + model rerank'
    assert public_ranker('bm25 fallback') == 'bm25 fallback' and public_ranker('bm25 screen + none rerank') == 'bm25 screen + none rerank'


def test_the_config_names_no_service_and_unused_stages_hold_none():
    public = public_config(RAW_CONFIG)
    assert not names_a_provider(' '.join(str(v) for v in public.values()))
    assert (public['screen'], public['rerank'], public['verifier']) == ('model', 'model', 'model')
    assert (public['screen_model'], public['rerank_model'], public['verifier_model']) == ('relevance-3', 'relevance-3', 'verifier-1')
    assert public['card_chars'] == RAW_CONFIG['card_chars'] and set(public) == set(RAW_CONFIG)
    lexical = public_config({**RAW_CONFIG, 'screen': 'bm25', 'rerank': 'none', 'verifier': 'none'})
    assert (lexical['screen'], lexical['rerank'], lexical['verifier']) == ('bm25', 'none', 'none')
    assert (lexical['screen_model'], lexical['rerank_model'], lexical['verifier_model']) == (None, None, None)
    assert public_config(public) == public


def test_spend_is_keyed_by_role_and_figures_for_one_role_are_added():
    spend = public_spend(RAW_SPEND)
    assert spend == {'scoring': RAW_SPEND['jev'], 'verification': RAW_SPEND['openai']}
    both = public_spend({'openai': RAW_SPEND['openai'], 'anthropic': RAW_SPEND['openai']})
    assert both == {'verification': {'requests': 2, 'input_tokens': 600, 'output_tokens': 100, 'usd': 0.00042}}
    assert public_spend(spend) == spend and public_spend({}) == {}


def test_the_label_is_replaced_only_when_it_names_a_provider():
    raw = 'Jev (jev-1.13.0) judged all 2080 Division B articles; gpt-6-luna read the top 15 in full.'
    for mode in ('live', 'fake', 'bm25_fallback'):
        assert public_label(raw, mode) == GENERIC_LABEL[mode] and not names_a_provider(GENERIC_LABEL[mode])
    fine = 'All 2080 Division B articles were scored; the top 60 were re-checked in one request.'
    assert public_label(fine, 'live') == fine
    assert 'Nothing is committed' in GENERIC_LABEL['bm25_fallback'] and 'Offline fake providers' in GENERIC_LABEL['fake']


def test_a_stage_event_reads_neutral():
    assert public_event({'stage': 'screen', 'status': 'done', 'method': 'jev', 'articles': 2080}) == {
        'stage': 'screen', 'status': 'done', 'method': 'model', 'articles': 2080}
    assert public_event({'stage': 'questions', 'status': 'done', 'choices': 3}) == {
        'stage': 'questions', 'status': 'done', 'choices': 3}


def raw_trace(**changes):
    fields = dict(
        config=RAW_CONFIG, config_hash='abc', exhaustive=True, articles_expected=2080, articles_scored=2080,
        ranker='jev screen + jev rerank', fallback_reason='BATATIS_LIVE is off or the TypeSafe credential is absent',
        verifier='failed: openai gate: offline-cap',
        stages=[StageRecord(stage='screen', method='jev', model=JEV_MODEL),
                StageRecord(stage='verify', method='openai', model=OPENAI_VERIFIER)],
        spend=RAW_SPEND)
    return IdentifyTrace(**{**fields, **changes})


def test_the_trace_cleans_raw_values_when_it_is_built_and_again_when_it_is_read_back():
    trace = raw_trace()
    assert trace.ranker == 'model screen + model rerank'
    assert (trace.fallback_reason, trace.verifier) == (UNAVAILABLE, VERIFIER_UNAVAILABLE)
    assert [(s.method, s.model) for s in trace.stages] == [('model', PUBLIC_MODEL), ('model', 'verifier-1')]
    assert set(trace.spend) == {'scoring', 'verification'} and trace.config_hash == 'abc'
    assert not names_a_provider(trace.model_dump_json())
    assert IdentifyTrace.model_validate_json(trace.model_dump_json()) == trace


def test_a_result_stored_with_raw_values_loads_neutral():
    stored = {
        'mode': 'live', 'source': 'live', 'narrowed': False, 'scored_at': '2026-10-21T00:00:00+00:00',
        'label': 'Jev (jev-1.13.0) judged all 2080 Division B articles; gpt-6-luna read the top 15 in full.',
        'model_ids': {'screen': JEV_MODEL, 'rerank': JEV_MODEL, 'verifier': OPENAI_VERIFIER},
        'benchmark': BenchmarkRecord(identified=False).model_dump(), 'description_sha256': '0' * 64,
        'trace': {**raw_trace().model_dump(), 'config': RAW_CONFIG, 'ranker': 'jev screen + jev rerank',
                  'fallback_reason': 'Jev unavailable', 'verifier': 'failed: openai gate: offline-cap',
                  'stages': [{'stage': 'screen', 'method': 'jev', 'model': JEV_MODEL}], 'spend': RAW_SPEND}}
    assert names_a_provider(json.dumps(stored, default=str)), 'the stored row really does name providers'
    result = IdentifyResult.model_validate(stored)
    assert result.label == GENERIC_LABEL['live']
    assert result.model_ids == {'screen': PUBLIC_MODEL, 'rerank': PUBLIC_MODEL, 'verifier': 'verifier-1'}
    assert not names_a_provider(result.model_dump_json())
    assert IdentifyResult.model_validate_json(result.model_dump_json()) == result
