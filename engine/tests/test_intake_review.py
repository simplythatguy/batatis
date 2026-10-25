"""Document review: nothing the model writes reaches the case unless it checks out against the text."""
from __future__ import annotations

import json

import pytest

from engine.codes import CodeDbMissing, Codes
from engine.intake import review
from engine.models_intake import EvidenceRef
from engine.redact import scrub

PAGE = ('Fire engineering letter. Table 2: travel distance to a point of choice 25 m (DtS limit 20 m). '
        'The proposed fire control centre is not at the front entrance. Prepared for 74-94 Newton Road, '
        'Wetherill Park. Sentence 9.10.15.4.(1) of NBC(AE) 2019 was considered.')
REQUEST = 'Review the attached letter and list what it leaves to a later stage.'


def _codes():
    try:
        return Codes()
    except CodeDbMissing:
        return None


def _model(payload: dict):
    def transport(system, user, schema, model, effort):
        seen = json.loads(user)
        transport.seen = seen
        return payload, {'input_tokens': 10, 'output_tokens': 10}
    return transport


def _run(payload: dict, codes=None, request=REQUEST, page=PAGE):
    transport = _model(payload)
    out = review.run(request, [('file1', 'letter.html', page.encode())], outbound=lambda s: scrub(s),
                     transport=transport, status='live', codes=codes)
    return out, transport.seen


def _evidence(quote, page=None, file='file1'):
    return [{'file': file, 'page': page, 'quote': quote}]


EMPTY = {'documents': [], 'flags': [], 'facts': [], 'conflicts': [], 'provisions': [], 'missing': [], 'questions': []}


def test_a_fact_needs_an_excerpt_that_is_in_the_page():
    out, _ = _run({**EMPTY, 'facts': [
        {'text': 'The travel distance to a point of choice is 25 m against a 20 m limit.', 'status': 'proposed',
         'evidence': _evidence('travel distance to a point of choice 25 m (DtS limit 20 m)')},
        {'text': 'The building has a sprinkler system.', 'status': 'existing',
         'evidence': _evidence('the building is fully sprinklered')}]})
    assert [f.text for f in out.facts] == ['The travel distance to a point of choice is 25 m against a 20 m limit.']
    assert out.dropped == 1


def test_a_restatement_with_a_number_the_excerpt_lacks_shows_the_excerpt_instead():
    out, _ = _run({**EMPTY, 'facts': [
        {'text': 'The travel distance to a point of choice is 35 m.', 'status': 'proposed',
         'evidence': _evidence('travel distance to a point of choice 25 m')}]})
    assert out.facts[0].text == 'travel distance to a point of choice 25 m'


def test_batatis_never_says_a_design_complies_in_its_own_words():
    out, _ = _run({**EMPTY,
                   'missing': [{'text': 'The design complies with the code. A fire engineering report is needed.',
                                'why': 'The letter is preliminary.'}],
                   'questions': [{'text': 'The proposal is safe.', 'why': 'x'},
                                 {'text': 'Does the travel distance meet the code?', 'why': 'It exceeds the DtS limit.'}],
                   'flags': [{'kind': 'record_status', 'text': 'The letter states the solution complies with BCA 2013.',
                              'evidence': []}]})
    assert [m.text for m in out.missing] == ['A fire engineering report is needed.']
    assert [q.text for q in out.questions] == ['Does the travel distance meet the code?']
    assert out.flags[0].text.startswith('The letter states')


def test_the_model_only_sees_the_scrubbed_text_and_the_user_sees_the_original():
    out, seen = _run({**EMPTY, 'facts': [
        {'text': 'The letter is for [address], Wetherill Park.', 'status': 'stated',
         'evidence': _evidence('Prepared for 74-[address], Wetherill Park.')}]})
    sent = json.dumps(seen)
    assert '94 Newton Road' not in sent and '[address]' in sent
    assert out.facts[0].evidence[0].quote == 'Prepared for 74-94 Newton Road, Wetherill Park.'
    assert out.facts[0].text == 'The letter is for 94 Newton Road, Wetherill Park.'


def test_cited_provisions_resolve_only_through_the_code_database():
    codes = _codes()
    if codes is None:
        pytest.skip('code database not built')
    out, _ = _run({**EMPTY, 'provisions': [
        {'cited': 'Sentence 9.10.15.4.(1)', 'code': 'NBC(AE) 2019', 'evidence': _evidence('Sentence 9.10.15.4.(1)')},
        {'cited': '99.1.1.1', 'code': None, 'evidence': _evidence('Sentence 9.10.15.4.(1)')},
        {'cited': 'D1.4', 'code': 'BCA 2013', 'evidence': _evidence('not in the page at all')}],
        'missing': [{'text': 'Show how Article 99.9.9.9. is met.', 'why': 'x'}]}, codes=codes)
    assert [(p.cited, p.resolves_to) for p in out.provisions] == [('Sentence 9.10.15.4.(1)', '9.10.15.4.'),
                                                                 ('99.1.1.1', None)]
    assert out.missing == []


def test_no_transport_means_no_review_and_a_closed_gate_is_reported():
    assert review.run(REQUEST, [], outbound=str, transport=None, status='off').status == 'off'

    def closed(*args):
        raise review.GateClosed('offline-cap')
    out = review.run(REQUEST, [('file1', 'a.html', b'<p>text</p>')], outbound=str, transport=closed, status='live')
    assert (out.status, out.reason) == ('gate_closed', 'offline-cap')


def test_restore_maps_an_excerpt_back_to_the_original_text():
    original = 'Contact jo@x.com or 403-555-1234 about 74-94 Newton Road.'
    text, hidden = review.restore('Contact [email] or [phone]', scrub(original), original)
    assert text == 'Contact jo@x.com or 403-555-1234'
    assert hidden == ['jo@x.com', '403-555-1234']
    assert review.restore('no placeholder here', scrub(original), original) is None
    assert isinstance(EvidenceRef(source_ref='file1', page=1, quote=text), EvidenceRef)


def test_luna_and_sol_settings_are_bounded():
    for model, effort, ok in (('gpt-6-luna', 'xhigh', True), ('gpt-6-luna', 'max', False),
                              ('gpt-6.1-sol', 'low', True), ('gpt-6.1-sol', 'high', False)):
        env = {'BATATIS_REVIEW_MODEL': model, 'BATATIS_REVIEW_EFFORT': effort}
        with pytest.MonkeyPatch.context() as mp:
            for k, v in env.items():
                mp.setenv(k, v)
            if ok:
                assert review.configured() == (model, effort)
            else:
                with pytest.raises(ValueError):
                    review.configured()


def test_a_long_file_keeps_the_pages_the_request_names_and_each_files_first_pages():
    pages = [(n, f'page {n} ' + ('filler words ' * 40)) for n in range(1, 41)]
    pages[29] = (30, 'page 30 travel distance schedule ' + 'filler words ' * 40)
    long = review.Source('file1', 'long.pdf', pages, 40)
    short = review.Source('file2', 'short.pdf', [(1, 'one page')], 1)
    assert review._select('anything', [long, short], 10**6) == [long, short]
    kept = review._select('Read the travel distance schedule on p. 18.', [long, short], 2600)
    numbers = [n for n, _ in kept[0].pages]
    assert {1, 2, 18} <= set(numbers) and numbers == sorted(numbers)
    assert 30 in numbers and kept[1].pages == short.pages
