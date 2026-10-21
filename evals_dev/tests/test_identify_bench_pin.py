"""The pin file is what the identify service reads: fields, hash and rejection of what the schema cannot express."""
import json

import pytest

from evals_dev.identify_bench import pin
from evals_dev.identify_bench.arms import standard_arms


def test_the_default_winner_chain_maps_onto_every_config_field():
    fields = pin.pin_for(standard_arms(), 'V15f-R5')
    assert set(fields) == set(pin.FIELDS)
    assert fields == {'screen': 'jev', 'screen_model': 'jev-1.13.0', 'card_chars': 700, 'rerank': 'jev', 'rerank_model': 'jev-1.13.0',
                      'rerank_n': 60, 'verifier': 'openai', 'verifier_model': 'gpt-6-luna', 'verifier_effort': 'medium', 'verify_n': 15,
                      'fallback': 'bm25', 'top_k': 10, 'choices_k': 3}


def test_a_lexical_chain_has_no_model_stages():
    fields = pin.pin_for(standard_arms(), 'R1-searchrank-v3', fallback='bm25_v3')
    assert (fields['screen'], fields['rerank'], fields['verifier'], fields['fallback']) == ('bm25_v3', 'none', 'none', 'bm25_v3')
    assert pin.pin_for(standard_arms(), 'R6-bm25-jev-rerank60')['rerank'] == 'jev'


def test_what_the_schema_cannot_express_is_refused_not_approximated():
    with pytest.raises(pin.NotRepresentable):
        pin.pin_for(standard_arms(), 'F1-rrf-R5-R1-R2')
    with pytest.raises(pin.NotRepresentable):
        pin.pin_for(standard_arms(), 'V15c-R5')                          # card-length verifier text: the config reads full text
    with pytest.raises(pin.NotRepresentable):
        pin.pin_for(standard_arms(), 'R2-precedent-lofo')


def test_the_pin_file_carries_only_keys_the_loader_accepts():
    fields = pin.pin_for(standard_arms(), 'V15f-R5')
    data = json.loads(pin.pipeline_json(fields, chosen_at='2026-10-21', memo_sha='ab' * 32))
    assert set(data) == set(pin.FIELDS) | {'chosen_by', 'chosen_at', 'comment'}
    assert pin.config_hash(fields) in data['comment'] and 'calibration.json' in data['comment']


def test_the_hash_and_fields_agree_with_the_engines_identify_config_when_it_is_importable():
    try:
        from engine.identify.config import IdentifyConfig, load_config
    except ImportError:
        pytest.skip('engine.identify.config arrives with PR #52')
    fields = pin.pin_for(standard_arms(), 'V15f-R5')
    config = IdentifyConfig(**fields)                                       # validates every field and the Jev pin
    assert config.config_hash == pin.config_hash(fields)
    import tempfile
    from pathlib import Path
    with tempfile.TemporaryDirectory() as d:
        path = Path(d) / 'pipeline.json'
        path.write_text(pin.pipeline_json(fields, chosen_at='2026-10-21', memo_sha='cd' * 32))
        assert load_config(path, env={}).config_hash == config.config_hash        # the loader accepts the file as written
