"""The selected workflow keeps Luna generation, deterministic requirement discovery and Jev relevance."""
import pytest

from engine import relevance
from engine.identify.config import ConfigError, load_config
from engine.intake import model, review


def test_selected_workflow_uses_luna_and_deterministic_discovery_with_a_model_rank():
    config = load_config(env={})
    assert (model.MODEL, model.EFFORT) == ('claude-sonnet-5-5', 'low')
    assert (review.DEFAULT_MODEL, review.DEFAULT_EFFORT) == ('claude-sonnet-5-5', 'low')
    assert config.screen == 'requirements' and not config.exhaustive
    # Measured in experiments/workflow-bakeoff-v2: Haiku 5.5 at medium effort reorders the leading candidates.
    assert (config.model_rank, config.model_rank_model, config.model_rank_effort) == ('anthropic', 'claude-haiku-5-5', 'medium')
    assert config.model_ids() == {'screen': None, 'rerank': None, 'verifier': 'claude-haiku-5-5'}


def test_the_shipped_rank_searches_the_table_of_contents_and_turning_it_off_keeps_the_rank_profile():
    # Measured in experiments/workflow-bakeoff-v2: 12 table-of-contents candidates lead a pool of 72.
    shipped, off = load_config(env={}), load_config(env={'BATATIS_IDENTIFY_MODEL_RANK_TOC': '0'})
    assert shipped.model_rank_toc == 12 and shipped.as_dict()['model_rank_toc_pool'] == 72
    assert off.config_hash == '5b5eb07257b3d1de' != shipped.config_hash   # the rank's hash before the search
    assert 'model_rank_toc' not in off.as_dict()
    with pytest.raises(ConfigError):
        load_config(env={'BATATIS_IDENTIFY_MODEL_RANK_TOC': '13'})


def test_turning_the_model_rank_off_restores_the_deterministic_profile():
    config = load_config(env={'BATATIS_IDENTIFY_MODEL_RANK': 'none'})
    assert config.model_ids() == {'screen': None, 'rerank': None, 'verifier': None}
    assert config.config_hash != load_config(env={}).config_hash


def test_code_library_relevance_keeps_the_historical_jev_profile(monkeypatch):
    monkeypatch.setenv('BATATIS_PROVIDER', 'fake')
    judge = relevance.live_judge()
    assert (judge.method, judge.model) == ('jev', 'jev-1.13.0')
    assert (judge.config.rerank, judge.config.rerank_model, judge.config.rerank_n) == ('jev', 'jev-1.13.0', 60)
    assert judge.config.config_hash == load_config(env={'BATATIS_IDENTIFY_SCREEN': 'jev'}).config_hash
