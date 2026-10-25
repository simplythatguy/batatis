"""Numeric ranges are source values, not hyphenated words."""
import pytest
from engine.intake import review


@pytest.mark.parametrize('dash', ['-', '\u2013', '\uff0d'])
def test_line_wrapped_numeric_range_cannot_become_one_invented_number(dash):
    source = f'Wall height: 25{dash}\n30 metres.'
    payload = {'facts': [{'text': 'Wall height is 2530 metres.', 'status': 'stated',
                         'evidence': [{'file': 'f', 'page': None, 'quote': '2530 metres'}]}]}
    out = review.run('Review this record.', [('f', 'source.txt', source.encode())],
                     outbound=lambda text, _: text, transport=lambda *args: (payload, {}), status='live')
    assert out.facts == []
    assert out.dropped == 1
