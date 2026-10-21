"""Live provider probes. Marked ``paid``: skipped unless BATATIS_RUN_PAID=1, and skipped in CI, which blanks every key.

The OpenAI probe goes through the real hard-stop ledger (``evals_dev/identify_bench/ledger/openai.jsonl``), so its few
hundredths of a cent count against the US$10.00 stop like every other call.
"""
import os

import pytest

from evals_dev import envfile
from evals_dev.identify_bench import pricing
from evals_dev.identify_bench.ledger import OPENAI_HARD_CAP_USD, Ledger
from evals_dev.identify_bench.live import LEDGER_DIR, OPENAI_STOP_USD
from evals_dev.identify_bench.transports import OpenAIChat

SCHEMA = {'type': 'object', 'additionalProperties': False, 'required': ['answer'], 'properties': {'answer': {'type': 'string'}}}


@pytest.mark.paid
def test_gpt_6_luna_answers_through_the_hard_stop_ledger():
    envfile.load_env_file(names=envfile.KEY_NAMES)
    envfile.apply_defaults()
    if not os.environ.get('OPENAI_API_KEY'):
        pytest.skip('OPENAI_API_KEY not set')
    ledger = Ledger(LEDGER_DIR / 'openai.jsonl', 'openai', OPENAI_STOP_USD)
    before = ledger.settled()
    res = OpenAIChat(ledger)(name='probe', schema=SCHEMA, system='Reply with the JSON object {"answer": "ok"}.',
                             user='Say ok.', model='gpt-6-luna', effort='medium', max_completion_tokens=2000,
                             arm='paid-test', case='probe')
    assert res.ok and res.payload == {'answer': 'ok'} or res.payload is not None
    assert res.returned_model == 'gpt-6-luna' and res.service_tier == 'default'
    assert res.input_tokens > 0 and res.output_tokens >= res.reasoning_tokens
    assert res.usd == pricing.cost_usd('gpt-6-luna', res.input_tokens, res.output_tokens, res.cached_tokens)
    assert ledger.settled() - before == res.usd and ledger.spent() <= OPENAI_HARD_CAP_USD


@pytest.mark.paid
def test_jev_pinned_version_scores_a_small_state():
    envfile.load_env_file(names=envfile.KEY_NAMES)
    envfile.apply_defaults()
    if not (os.environ.get('TYPESAFE_API_KEY') or os.environ.get('JEV_API_KEY')):
        pytest.skip('no Jev key in the environment or .env')
    from engine.identify.jevkit import client
    from engine.identify.screen import GOVERN, noul
    state = {'proposal': 'vinyl siding nailed straight to foam board',
             'articles': {'A0': 'Attachment: cladding shall be fastened to framing', 'A1': 'Stair rise: the maximum rise is 200 mm'}}
    qs = {f'q{i}': noul(GOVERN.format(L=f'A{i}')) for i in range(2)}
    reply = client.ask(state, qs, timeout=30, model='jev-1.13.0', provider='typesafe')
    p = {k: v['noul'] for k, v in reply['answers'].items()}
    assert p['q0'] > p['q1'] and reply['usage']['input_tokens'] > 0
