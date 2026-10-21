"""The spend ledger: hard stop, recomputed spend, orphans, tamper evidence, and the verified price."""
import json
import threading
from decimal import Decimal

import pytest

from evals_dev.identify_bench import pricing
from evals_dev.identify_bench.ledger import (OPENAI_HARD_CAP_USD, BudgetExceeded, Ledger, LedgerCorrupt)


@pytest.fixture
def ledger(tmp_path):
    return Ledger(tmp_path / 'openai.jsonl', 'openai', '1.00')


def test_the_openai_stop_cannot_be_raised_above_ten_dollars(tmp_path):
    assert OPENAI_HARD_CAP_USD == Decimal('10.00')
    Ledger(tmp_path / 'a.jsonl', 'openai', '10.00')
    with pytest.raises(ValueError):
        Ledger(tmp_path / 'b.jsonl', 'openai', '10.01')
    with pytest.raises(ValueError):
        Ledger(tmp_path / 'c.jsonl', 'openai', None)
    Ledger(tmp_path / 'd.jsonl', 'jev', None)                      # Jev has no stop


def test_reserve_settle_recomputes_spend_from_the_file(ledger, tmp_path):
    r = ledger.reserve(model='gpt-6-luna', worst_case_usd=Decimal('0.30'))
    assert ledger.spent() == Decimal('0.30')                       # the reservation counts at its worst case
    total = ledger.settle(r, usd=Decimal('0.0123'), input_tokens=6000, output_tokens=2400, reasoning_tokens=1800)
    assert total == Decimal('0.0123') == ledger.spent() == ledger.settled()
    again = Ledger(tmp_path / 'openai.jsonl', 'openai', '1.00')     # a fresh process sees the same number
    assert again.spent() == Decimal('0.0123')
    lines = (tmp_path / 'openai.jsonl').read_text().splitlines()
    assert [json.loads(x)['op'] for x in lines] == ['reserve', 'settle']


def test_a_call_that_could_cross_the_stop_is_refused_before_it_is_made(ledger):
    a = ledger.reserve(model='gpt-6-luna', worst_case_usd=Decimal('0.60'))
    ledger.settle(a, usd=Decimal('0.55'))
    with pytest.raises(BudgetExceeded):
        ledger.reserve(model='gpt-6-luna', worst_case_usd=Decimal('0.50'))   # 0.55 + 0.50 > 1.00
    ledger.reserve(model='gpt-6-luna', worst_case_usd=Decimal('0.45'))        # 0.55 + 0.45 = 1.00 is allowed
    with pytest.raises(BudgetExceeded):
        ledger.reserve(model='gpt-6-luna', worst_case_usd=Decimal('0.01'))    # the open reservation is counted


def test_release_gives_the_reservation_back(ledger):
    r = ledger.reserve(model='gpt-6-luna', worst_case_usd=Decimal('0.90'))
    with pytest.raises(BudgetExceeded):
        ledger.reserve(model='gpt-6-luna', worst_case_usd=Decimal('0.20'))
    ledger.release(r)
    assert ledger.spent() == Decimal(0)
    ledger.reserve(model='gpt-6-luna', worst_case_usd=Decimal('0.20'))


def test_an_unknown_outcome_is_charged_at_its_worst_case(ledger):
    r = ledger.reserve(model='gpt-6-luna', worst_case_usd=Decimal('0.25'))
    assert ledger.unknown(r, 'client timeout after the request was sent') == Decimal('0.25')
    assert ledger.settled() == Decimal('0.25')


def test_orphaned_reservations_count_until_they_are_closed(ledger, tmp_path):
    ledger.reserve(model='gpt-6-luna', worst_case_usd=Decimal('0.40'))        # the process "dies" here
    restarted = Ledger(tmp_path / 'openai.jsonl', 'openai', '1.00')
    assert restarted.spent() == Decimal('0.40') and restarted.settled() == Decimal(0)
    assert restarted.close_orphans() == 1
    assert restarted.settled() == Decimal('0.40') and restarted.summary()['open_reservations'] == 0


def test_concurrent_reservations_can_never_jointly_cross_the_stop(tmp_path):
    ledger = Ledger(tmp_path / 'l.jsonl', 'openai', '1.00')
    granted, refused = [], []

    def attempt():
        try:
            granted.append(ledger.reserve(model='gpt-6-luna', worst_case_usd=Decimal('0.30')))
        except BudgetExceeded:
            refused.append(1)

    threads = [threading.Thread(target=attempt) for _ in range(16)]
    [t.start() for t in threads]
    [t.join() for t in threads]
    assert len(granted) == 3 and len(refused) == 13 and ledger.spent() == Decimal('0.90')


def test_editing_or_truncating_the_ledger_is_detected(ledger, tmp_path):
    for usd in ('0.01', '0.02', '0.03'):
        ledger.settle(ledger.reserve(model='gpt-6-luna', worst_case_usd=Decimal('0.10')), usd=Decimal(usd))
    path = tmp_path / 'openai.jsonl'
    lines = path.read_text().splitlines()
    forged = [json.loads(x) for x in lines]
    forged[1]['usd'] = '0.00'                                            # hide a settlement
    path.write_text('\n'.join(json.dumps(x, sort_keys=True) for x in forged) + '\n')
    with pytest.raises(LedgerCorrupt):
        Ledger(path, 'openai', '1.00').spent()
    path.write_text('\n'.join(lines[:1] + lines[2:]) + '\n')              # delete a line
    with pytest.raises(LedgerCorrupt):
        Ledger(path, 'openai', '1.00').reserve(model='gpt-6-luna', worst_case_usd=Decimal('0.01'))


def test_summary_totals_by_model(ledger):
    for _ in range(2):
        r = ledger.reserve(model='gpt-6-luna', worst_case_usd=Decimal('0.1'))
        ledger.settle(r, usd=Decimal('0.004'), input_tokens=1000, output_tokens=500, reasoning_tokens=300,
                      cached_tokens=100)
    s = ledger.summary()
    m = s['by_model']['gpt-6-luna']
    assert (s['requests'], m['requests'], m['input_tokens'], m['output_tokens']) == (2, 2, 2000, 1000)
    assert Decimal(s['spent_usd']) == Decimal('0.008') and Decimal(s['remaining_usd']) == Decimal('0.992')


# ---- prices -----------------------------------------------------------------------------------------------

def test_gpt_6_luna_uses_the_verified_standard_tier_price():
    p = pricing.price_for('gpt-6-luna')
    assert (p.input, p.output, p.cached_input) == (Decimal('0.10'), Decimal('0.50'), Decimal('0.01'))
    # 6,000 prompt tokens and 2,600 completion tokens (reasoning included) cost $0.0019 at $0.10 / $0.50 per million
    assert pricing.cost_usd('gpt-6-luna', 6000, 2600) == Decimal('0.0019')


def test_cached_tokens_are_billed_in_full_unless_the_discount_is_asked_for():
    assert pricing.cost_usd('gpt-6-luna', 10_000, 0, cached_tokens=8_000) == Decimal('0.0010')
    assert pricing.cost_usd('gpt-6-luna', 10_000, 0, cached_tokens=8_000, cached_discount=True) == Decimal('0.000280')


def test_the_reservation_uses_the_long_context_pair_and_a_generous_token_bound():
    worst = pricing.worst_case_usd('gpt-6-luna', 24_000, 12_000)
    assert worst == Decimal('0.0138')                                    # (24000 * 0.20 + 12000 * 0.75) / 1e6
    assert worst > pricing.cost_usd('gpt-6-luna', 24_000, 12_000)
    text = 'x' * 1000
    assert pricing.input_token_upper_bound(text) >= pricing.input_token_estimate(text) * 2


def test_an_unpriced_model_is_refused_not_guessed():
    with pytest.raises(KeyError):
        pricing.price_for('gpt-9-unknown')


def test_a_ledger_without_a_stop_records_one_line_per_stage(tmp_path):
    jev = Ledger(tmp_path / 'jev.jsonl', 'jev', None)
    jev.record(model='jev-1.13.0', usd=Decimal('0.0176'), requests=21, input_tokens=394_000, output_tokens=2_100, arm='R4', case='c1')
    s = jev.summary()
    assert s['requests'] == 21 and Decimal(s['settled_usd']) == Decimal('0.0176') and s['remaining_usd'] is None
    assert len((tmp_path / 'jev.jsonl').read_text().splitlines()) == 1
    with pytest.raises(ValueError):
        Ledger(tmp_path / 'o.jsonl', 'openai', '1.00').record(model='gpt-6-luna', usd=Decimal('0.1'))   # must reserve first


def test_the_committed_openai_ledger_verifies_and_is_under_the_stop():
    from evals_dev.identify_bench.live import LEDGER_DIR, OPENAI_STOP_USD
    path = LEDGER_DIR / 'openai.jsonl'
    if not path.exists():
        pytest.skip('no OpenAI calls recorded yet')
    ledger = Ledger(path, 'openai', OPENAI_STOP_USD)            # opening it verifies the hash chain
    assert ledger.spent() <= OPENAI_HARD_CAP_USD
    assert ledger.summary()['open_reservations'] == 0
