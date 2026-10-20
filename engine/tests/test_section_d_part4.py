"""Part 4 design is derived from stated facts, including an explicit negative."""
from engine.professional import professional_involvement
from engine.section_d_flag_eval import evaluate, load_codes, observe


def _case(text: str) -> dict:
    return {'id': 'part4-probe', 'description': text, 'known_facts': []}


def _part4(text: str):
    facts, _signals = observe(_case(text))
    return facts.part4_design


def test_wood_frame_house_with_no_trigger_is_not_part4():
    assert _part4('two-storey house, 210 m², wood frame') is False


def test_wood_frame_house_with_a_stated_short_span_answers_no():
    codes, _codedb = load_codes()
    text = 'two-storey house, 210 m², wood frame, 6 m clear span'
    assert _part4(text) is False
    label, _question = evaluate(_case(text), codes, 'rules_plus_unknown')
    assert label == 'no'


def test_unstated_span_still_asks_after_the_negative():
    codes, _codedb = load_codes()
    text = 'two-storey house, 210 m², wood frame'
    assert _part4(text) is False
    label, _question = evaluate(_case(text), codes, 'rules_plus_unknown')
    assert label == 'unknown'


def test_positive_part4_triggers():
    assert _part4('1-in-50 hourly wind pressure of 1.2 kPa') is True
    assert _part4('Sa(0.2) of 1.9') is True
    assert _part4('Sa(0.2) of 1.3') is None
    assert _part4('lumber roof sheathing and Sa(0.2) of 1.3') is True
    assert _part4('lumber roof sheathing and Sa(0.2) of 1.2') is None
    assert _part4('5.2 m joist span') is True
    assert _part4('4.9 m joist span') is None
    assert _part4('joists spanning 5.2 m') is True
    assert _part4('specified live load of 2.5 kPa') is True
    assert _part4('specified live load of 2.4 kPa') is None
    assert _part4('reinforced concrete wall') is True
    assert _part4('loadbearing steel studs') is True
    assert _part4('non-loadbearing steel studs') is None
    assert _part4('foundations on permafrost') is True


def test_wind_below_1_2_does_not_override_the_wood_frame_negative():
    text = 'two-storey house, 210 m², wood frame, 1-in-50 hourly wind pressure of 1.1 kPa'
    assert _part4(text) is False


def test_group_a_hall_is_part4_even_inside_the_size_exception():
    """Div A 1.3.3.2.(1) sends Group A to Part 4. Div C 2.4.1.1.(1) would still except 200 m²."""
    codes, _codedb = load_codes()
    text = 'one-storey community hall, building area of 200 m2, wood frame, 6 m clear span'
    assert _part4(text) is True
    facts, _signals = observe(_case(text))
    result = professional_involvement(facts, codes)
    assert result.general_required == 'no'
    assert result.required == 'yes'
    assert any(reason.code == 'part4' and reason.required == 'yes' for reason in result.reasons)
    label, _question = evaluate(_case(text), codes, 'rules_plus_unknown')
    assert label == 'yes'


def test_size_past_part9_overrides_wood_frame():
    assert _part4('four-storey house, 210 m², wood frame') is True
    assert _part4('two-storey house, 700 m², wood frame') is True
