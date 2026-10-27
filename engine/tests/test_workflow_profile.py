"""The selected workflow keeps Luna generation, deterministic requirement discovery and Jev relevance."""
from engine import relevance
from engine.identify.config import load_config
from engine.intake import model, review


def test_selected_workflow_uses_luna_and_deterministic_discovery():
    config = load_config(env={})
    assert (model.MODEL, model.EFFORT) == ('gpt-6-luna', 'medium')
    assert (review.DEFAULT_MODEL, review.DEFAULT_EFFORT) == ('gpt-6-luna', 'medium')
    assert config.screen == 'requirements' and not config.exhaustive
    assert config.model_ids() == {'screen': None, 'rerank': None, 'verifier': None}


def test_code_library_relevance_keeps_the_historical_jev_profile(monkeypatch):
    monkeypatch.setenv('BATATIS_PROVIDER', 'fake')
    judge = relevance.live_judge()
    assert (judge.method, judge.model) == ('jev', 'jev-1.13.0')
    assert (judge.config.rerank, judge.config.rerank_model, judge.config.rerank_n) == ('jev', 'jev-1.13.0', 60)
    assert judge.config.config_hash == load_config(env={'BATATIS_IDENTIFY_SCREEN': 'jev'}).config_hash
