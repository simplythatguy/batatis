"""Identify config, the commit policy table, and the spend gate per provider. No code database needed."""
import json
from decimal import Decimal

import pytest

from engine import llm_gate
from engine.identify.commit import COMMIT_PARTS, CommitPolicy, decide, load_policy
from engine.identify.config import ConfigError, IdentifyConfig, load_config
from engine.identify.providers import (GateClosed, MeteredAnthropic, SpendLog, metered, metered_ask,
                                       metered_openai_json, transports)
from engine.identify import fakes


@pytest.fixture(autouse=True)
def clean_gate(monkeypatch):
    llm_gate.reset_for_tests()
    for name in ('BATATIS_LIVE', 'BATATIS_LIVE_ELEPHANT', 'OPENROUTER_API_KEY', 'BATATIS_PROVIDER',
                 'VERCEL', 'BATATIS_STORE', 'OPENAI_API_KEY', 'ANTHROPIC_API_KEY'):
        monkeypatch.delenv(name, raising=False)
    yield
    llm_gate.reset_for_tests()


# --- config ---------------------------------------------------------------------------------------

def test_selected_config_is_local_requirements_with_a_model_rank_and_legacy_models_inactive():
    config = load_config(env={})
    assert config.screen == 'requirements' and not config.exhaustive
    assert config.as_dict()['rerank'] == config.as_dict()['verifier'] == 'none'
    assert config.as_dict()['model_rank_model'] == 'claude-haiku-5-5'
    assert config.model_ids() == {'screen': None, 'rerank': None, 'verifier': 'claude-haiku-5-5'}


def test_the_model_rank_never_moves_a_historical_configuration_hash():
    jev = load_config(env={'BATATIS_IDENTIFY_SCREEN': 'jev'})
    assert jev.config_hash == load_config(env={'BATATIS_IDENTIFY_SCREEN': 'jev', 'BATATIS_IDENTIFY_MODEL_RANK': 'none'}).config_hash
    with pytest.raises(ConfigError):
        IdentifyConfig(model_rank='openai')


def test_anthropic_verifier_is_opt_in_and_models_are_pinned():
    assert load_config(env={'BATATIS_IDENTIFY_VERIFIER': 'anthropic'}).verifier_model == 'claude-sonnet-5-5'
    with pytest.raises(ConfigError):
        IdentifyConfig(screen_model='jev-latest')                  # Jev is pinned
    with pytest.raises(ConfigError):
        IdentifyConfig(verify_n=61)


def test_config_file_then_env_and_hash_tracks_every_choice(tmp_path):
    path = tmp_path / 'pipeline.json'
    path.write_text(json.dumps({'rerank': 'none', 'verify_n': 10, 'chosen_by': 'WP-12'}))
    config = load_config(env={'BATATIS_IDENTIFY_CONFIG': str(path), 'BATATIS_IDENTIFY_TOP_K': '8'})
    assert (config.rerank, config.verify_n, config.top_k) == ('none', 10, 8)
    assert config.config_hash != IdentifyConfig().config_hash
    assert IdentifyConfig().config_hash == IdentifyConfig().config_hash
    path.write_text(json.dumps({'nonsense': 1}))
    with pytest.raises(ConfigError):
        load_config(path)


# --- commit policy --------------------------------------------------------------------------------

CAL = CommitPolicy('calibrated', 'fitted', {9: 0.8}, 3, 'h')
UNCAL = CommitPolicy('uncalibrated', 'calibration.json is absent; automatic commits are off')
BASE = dict(part=9, probability=0.9, fallback=False, verifier_ran=True, verifier_picked=True, committed_so_far=0)

TABLE = [
    ('commits: Part 9, picked, above threshold', {}, CAL, True, 'committed'),
    ('fallback commits nothing', {'fallback': True}, CAL, False, 'keyword fallback'),
    ('Part 3 is a quoted choice', {'part': 3}, CAL, False, 'outside Part 9'),
    ('Part 4 is a quoted choice', {'part': 4}, CAL, False, 'outside Part 9'),
    ('uncalibrated commits nothing', {}, UNCAL, False, 'calibration.json is absent'),
    ('verifier must run', {'verifier_ran': False, 'verifier_picked': False}, CAL, False, 'did not run'),
    ('verifier must pick', {'verifier_picked': False}, CAL, False, 'did not pick'),
    ('below threshold', {'probability': 0.79}, CAL, False, 'below the fitted threshold'),
    ('at threshold commits', {'probability': 0.8}, CAL, True, 'committed'),
    ('no probability', {'probability': None}, CAL, False, 'below the fitted threshold'),
    ('cap of three', {'committed_so_far': 3}, CAL, False, 'at most 3'),
    ('third still commits', {'committed_so_far': 2}, CAL, True, 'committed'),
]


@pytest.mark.parametrize('name,change,policy,expected,reason', TABLE, ids=[row[0] for row in TABLE])
def test_commit_policy_table(name, change, policy, expected, reason):
    commit, why = decide(**{**BASE, **change}, policy=policy)
    assert commit is expected and reason in why


def _write(tmp_path, **data):
    path = tmp_path / 'calibration.json'
    path.write_text(json.dumps(data))
    return path


GOOD = dict(status='calibrated', validated_on='validation', config_hash='abc', max_commits=3,
            parts={'9': {'status': 'calibrated', 'threshold': 0.82}})


@pytest.mark.parametrize('change,status,reason', [
    (None, 'uncalibrated', 'absent'),
    ({'status': 'placeholder_uncalibrated'}, 'uncalibrated', 'does not say status: calibrated'),
    ({'validated_on': 'calibration'}, 'uncalibrated', 'validation fold'),
    ({'config_hash': 'other'}, 'uncalibrated', 'different pipeline config'),
    ({'parts': {'3': {'status': 'calibrated', 'threshold': 0.5}}}, 'uncalibrated', 'no Part 9'),
    ({'parts': {'9': {'status': 'calibrated', 'threshold': 1.5}}}, 'uncalibrated', 'no Part 9'),
    ({'max_commits': 9}, 'calibrated', 'validated'),
    ({}, 'calibrated', 'validated'),
])
def test_calibration_file_gates_commits(tmp_path, change, status, reason):
    path = tmp_path / 'missing.json' if change is None else _write(tmp_path, **{**GOOD, **change})
    policy = load_policy('abc', path)
    assert policy.status == status and reason in policy.reason
    if status == 'calibrated':
        assert policy.thresholds == {9: 0.82} and policy.max_commits == 3     # cap never widened
    assert COMMIT_PARTS == {9}


def test_unreadable_calibration_commits_nothing(tmp_path):
    path = tmp_path / 'calibration.json'
    path.write_text('{not json')
    assert load_policy('abc', path).status == 'uncalibrated'


# --- spend gate per provider ----------------------------------------------------------------------

PROVIDERS = [('openai', 'gpt-4.1-2025-04-14'), ('anthropic', 'claude-sonnet-5-5'), ('jev', 'jev-1.13.0')]


@pytest.mark.parametrize('provider,model', PROVIDERS)
def test_gate_reserves_then_settles_to_reported_tokens(monkeypatch, provider, model):
    monkeypatch.setenv('BATATIS_PROVIDER', 'fake')
    log = SpendLog()
    with metered(provider, model, 100_000, 2_000, log=log) as settle:
        assert llm_gate._memory.today() == llm_gate.estimate_usd(model, 100_000, 2_000)    # reserved worst case
        settle(1_000, 50)
    assert llm_gate._memory.today() == llm_gate.estimate_usd(model, 1_000, 50) > 0          # settled actual
    assert log.calls[0]['provider'] == provider and log.usd() == float(llm_gate.estimate_usd(model, 1_000, 50))


@pytest.mark.parametrize('provider,model', PROVIDERS)
def test_gate_releases_the_reservation_when_the_call_fails(monkeypatch, provider, model):
    monkeypatch.setenv('BATATIS_PROVIDER', 'fake')
    with pytest.raises(TimeoutError):
        with metered(provider, model, 100_000, 2_000):
            raise TimeoutError('provider down')
    assert llm_gate._memory.today() == Decimal('0')


@pytest.mark.parametrize('provider,model', PROVIDERS)
def test_gate_shut_without_live_switch_and_over_the_cap(monkeypatch, provider, model):
    with pytest.raises(GateClosed) as shut:
        with metered(provider, model, 10, 10):
            pass
    assert shut.value.source == 'offline'
    monkeypatch.setenv('BATATIS_PROVIDER', 'fake')
    monkeypatch.setenv('BATATIS_DAILY_SPEND_CAP_USD', '0.000001')
    with pytest.raises(GateClosed) as capped:
        with metered(provider, model, 1_000_000, 1_000_000):
            pass
    assert capped.value.source == 'offline-cap'


def test_fake_providers_never_pass_on_vercel_and_jev_needs_the_live_switch(monkeypatch):
    from engine.identify.jevkit import keystore
    monkeypatch.setattr(keystore, 'resolve', lambda *a, **k: pytest.fail('keychain read without BATATIS_LIVE'))
    assert not llm_gate.provider_enabled('jev')
    monkeypatch.setenv('BATATIS_PROVIDER', 'fake')
    monkeypatch.setenv('VERCEL', '1')
    assert not llm_gate.fake_providers() and not llm_gate.provider_enabled('openai')


def test_fake_provider_does_not_open_the_assistant_gate(monkeypatch):
    monkeypatch.setenv('BATATIS_PROVIDER', 'fake')
    assert llm_gate.authorize(max_input_tokens=1, max_output_tokens=1).source == 'offline'


def test_each_transport_meters_its_calls(monkeypatch):
    monkeypatch.setenv('BATATIS_PROVIDER', 'fake')
    tp = transports('203.0.113.9', scoring={'jev', 'decisions'})
    assert tp.kind == 'fake' and tp.jev and tp.anthropic and tp.openai
    tp.jev({'proposal': 'soffit', 'articles': {'A0': 'Soffit (Part 9 > a > b): soffit text'}}, {'q0': {}}, 5)
    tp.openai('scores', {}, 's', '<proposal>\nsoffit\n</proposal>', model='gpt-6-luna')
    from engine.identify.verify import Picks
    tp.anthropic.messages.parse(model='claude-sonnet-5-5', max_tokens=100, system='s', output_format=Picks,
                                messages=[{'role': 'user', 'content': '<proposal>\nx\n</proposal>'}])
    assert [c['provider'] for c in tp.log.calls] == ['jev', 'openai', 'anthropic']
    assert llm_gate._memory.today() == sum(Decimal(str(c['usd'])) for c in tp.log.calls)


def test_live_transports_are_absent_without_the_switch():
    tp = transports()
    assert tp.kind == 'live' and tp.jev is None and tp.openai is None and tp.anthropic is None
    assert tp.decisions is None
    assert tp.elephant is None
    assert set(tp.unavailable) == {'jev', 'openai', 'anthropic', 'decisions', 'elephant'}


def test_metered_wrappers_settle_from_provider_usage(monkeypatch):
    monkeypatch.setenv('BATATIS_PROVIDER', 'fake')
    log = SpendLog()
    ask = metered_ask(lambda s, q, t: {'answers': {}, 'usage': {'input_tokens': 7, 'output_tokens': 3}}, log=log)
    ask({'proposal': 'p', 'articles': {}}, {}, 1)
    call = metered_openai_json(lambda *a, **k: ({}, {'input_tokens': 11, 'output_tokens': 2}), log=log)
    call('n', {}, 's', 'u', model='gpt-4.1-2025-04-14')
    client = MeteredAnthropic(fakes.FakeAnthropic(), log=log)
    from engine.identify.verify import Picks
    client.messages.parse(model='claude-sonnet-5-5', max_tokens=10, system='', output_format=Picks,
                          messages=[{'role': 'user', 'content': 'u'}])
    assert [(c['input_tokens'], c['output_tokens']) for c in log.calls][:2] == [(7, 3), (11, 2)]


def test_jev_api_key_is_read_as_the_typesafe_credential(monkeypatch):
    from engine.identify.jevkit import keystore
    monkeypatch.delenv('TYPESAFE_API_KEY', raising=False)
    monkeypatch.setattr(keystore, '_from_keychain', lambda *a: None)
    monkeypatch.setattr(keystore, '_from_file', lambda *a: None)
    monkeypatch.setenv('JEV_API_KEY', 'x' * 32)
    assert keystore.resolve('typesafe') == 'x' * 32 and keystore.source('typesafe') == 'environment'
    monkeypatch.setenv('BATATIS_LIVE', '1')
    assert llm_gate.provider_enabled('jev')


def test_openai_request_pins_luna_medium_effort_and_standard_tier(monkeypatch):
    import httpx
    from engine.identify.providers import raw_openai_json
    sent = {}

    class Reply:
        def raise_for_status(self):
            pass

        def json(self):
            return {'model': 'gpt-6-luna', 'choices': [{'message': {'content': '{"picks": []}'}}],
                    'usage': {'prompt_tokens': 5, 'completion_tokens': 2}}

    class Client:
        def __init__(self, **kw):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def post(self, url, headers, json):
            sent.update(json)
            return Reply()

    monkeypatch.setattr(httpx, 'Client', Client)
    monkeypatch.setenv('OPENAI_API_KEY', 'sk-test-not-real')
    config = load_config(env={})
    payload, usage = raw_openai_json('picks', {}, 's', 'u', model=config.verifier_model, effort=config.verifier_effort)
    assert sent['model'] == 'gpt-6-luna' and sent['reasoning_effort'] == 'medium'
    assert 'service_tier' not in sent and 'max_completion_tokens' in sent and 'max_tokens' not in sent
    assert usage['input_tokens'] == 5 and payload == {'picks': []}
    assert llm_gate.PRICES['gpt-6-luna'] == (Decimal('0.20'), Decimal('0.75'))


# --- review fixes: compliance wording, numeric requirement units ----------------------------------

@pytest.mark.parametrize('text,kept', [
    ('Departs from the acceptable solution by projecting 450 mm over the face.', True),
    ('The soffit complies with the code.', False),
    ('This is safe because the wall is rated.', False),
    ('The officer approved this before.', False),
    ('Meets the compliance path.', False),
])
def test_model_reason_keeps_acceptable_solution_language(text, kept):
    from engine.identify.cards import model_reason
    assert (model_reason(text) is not None) is kept


@pytest.mark.parametrize('sentence,expected', [
    ('shall have a fire-resistance rating not less than 45 min', []),
    ('shall be not less than 1 h', []),
    ('shall resist a moment not less than 2 kNm', []),
    ('shall project not more than 450 mm beyond the face', [(450, 'mm')]),
    ('a limiting distance not less than 1.2 m.', [(1.2, 'm')]),
    ('not less than 2 kN at the top', [(2, 'kN')]),
    ('an area not less than 0.35 m² with no dimension', [(0.35, 'm²')]),
])
def test_requirement_units_end_at_a_word_boundary(sentence, expected):
    from engine.identify.requirement import parse_requirements
    assert [(r['value'], r['unit']) for r in parse_requirements(sentence)] == expected


def test_a_billed_but_unusable_answer_is_still_settled(monkeypatch):
    """A refusal (null content) or a truncated answer is billed: the ledger records the real usage, not $0."""
    import httpx
    from engine.identify.providers import UnreadableResponse, raw_openai_json
    for content in (None, '{"picks": [', ''):
        class Reply:
            def raise_for_status(self):
                pass

            def json(self, content=content):
                return {'model': 'gpt-6-luna', 'choices': [{'message': {'content': content}}],
                        'usage': {'prompt_tokens': 900, 'completion_tokens': 300}}

        class Client:
            def __init__(self, **kw):
                pass

            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

            def post(self, url, headers, json):
                return Reply()

        monkeypatch.setattr(httpx, 'Client', Client)
        monkeypatch.setenv('OPENAI_API_KEY', 'sk-test-not-real')
        with pytest.raises(UnreadableResponse) as caught:
            raw_openai_json('picks', {}, 's', 'u', model='gpt-6-luna')
        assert caught.value.usage['input_tokens'] == 900 and caught.value.usage['output_tokens'] == 300
    monkeypatch.setenv('BATATIS_PROVIDER', 'fake')
    log = SpendLog()

    def refused(*a, **k):
        raise UnreadableResponse('refusal', {'input_tokens': 900, 'output_tokens': 300})

    with pytest.raises(UnreadableResponse):
        metered_openai_json(refused, log=log)('n', {}, 's', 'u', model='gpt-6-luna')
    assert [(c['input_tokens'], c['output_tokens']) for c in log.calls] == [(900, 300)]
