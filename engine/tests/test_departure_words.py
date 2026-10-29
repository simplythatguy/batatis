"""The departure card refuses the same words in the browser that the engine refuses with a 422."""
import re
from pathlib import Path

from engine.identify import cards


def web_pattern() -> str:
    web = (Path(__file__).resolve().parents[2] / 'web/src/calm/departure.ts').read_text()
    block = web.split('export const CLAIM_WORDS = new RegExp(', 1)[1].split('"i")', 1)[0]
    return ''.join(re.findall(r'String\.raw`([^`]*)`', block))


def test_the_departure_card_and_the_engine_refuse_the_same_words():
    assert web_pattern() == cards._COMPLIANCE.pattern
    assert cards._COMPLIANCE.flags & re.I


def test_the_shared_pattern_refuses_claims_and_keeps_the_domain_terms():
    for text in ('We want approval to sell it across Alberta.', 'The wall complies.', 'It is SAFE.', 'Fire safety is kept.'):
        assert cards.model_reason(text) is None, text
    for text in ('The design departs from the acceptable solution.', 'A thinner assembly than the table allows.', 'Safeguards stay in place.'):
        assert cards.model_reason(text) == text, text
