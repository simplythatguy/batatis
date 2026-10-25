"""The selected workflow must keep Luna generation and Jev relevance scoring."""
from engine.identify.config import load_config
from engine.intake import model, review


def test_selected_workflow_uses_luna_and_jev():
    config = load_config(env={})
    assert (model.MODEL, model.EFFORT) == ('gpt-6-luna', 'medium')
    assert (review.DEFAULT_MODEL, review.DEFAULT_EFFORT) == ('gpt-6-luna', 'medium')
    assert (config.screen, config.screen_model) == ('jev', 'jev-1.13.0')
    assert (config.rerank, config.rerank_model, config.rerank_n) == ('jev', 'jev-1.13.0', 60)
    assert (config.verifier, config.verifier_model, config.verifier_effort, config.verify_n) == (
        'openai', 'gpt-6-luna', 'medium', 15)
    assert (config.top_k, config.choices_k, config.fallback) == (10, 3, 'bm25')
