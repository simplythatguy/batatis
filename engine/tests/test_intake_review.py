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
    out = review.run(request, [('file1', 'letter.html', page.encode())], outbound=lambda s, own: scrub(s, own),
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
        {'text': 'The letter is for [personal detail].', 'status': 'stated',
         'evidence': _evidence('Prepared for 74-[personal detail].')}]})
    sent = json.dumps(seen)
    assert '94 Newton Road' not in sent and '[personal detail]' in sent
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
    assert [(p.cited, p.resolves_to) for p in out.provisions] == [('Sentence 9.10.15.4.(1)', None)]
    assert out.missing == []


def test_no_transport_means_no_review_and_a_closed_gate_is_reported():
    assert review.run(REQUEST, [], outbound=lambda s, own: s, transport=None, status='off').status == 'off'

    def closed(*args):
        raise review.GateClosed('offline-cap')
    out = review.run(REQUEST, [('file1', 'a.html', b'<p>text</p>')], outbound=lambda s, own: s, transport=closed,
                     status='live')
    assert (out.status, out.reason) == ('gate_closed', 'offline-cap')


def test_restore_maps_an_excerpt_back_to_the_original_text():
    original = 'Contact jo@x.com or 403-555-1234 about 74-94 Newton Road.'
    text, hidden = review.restore('Contact [email] or [phone]', scrub(original), original)
    assert text == 'Contact jo@x.com or 403-555-1234'
    assert hidden == ['jo@x.com', '403-555-1234']
    assert review.restore('no placeholder here', scrub(original), original) is None
    assert isinstance(EvidenceRef(source_ref='file1', page=1, quote=text), EvidenceRef)


def test_review_settings_are_bounded():
    for model, effort, ok in (('claude-sonnet-5-5', 'low', True), ('claude-sonnet-5-5', 'max', False),
                              ('gpt-6-luna', 'medium', False)):
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



def test_a_short_invented_fragment_between_real_ones_fails_verification():
    out, _ = _run({**EMPTY, 'facts': [
        {'text': 'The travel distance is 999 m.', 'status': 'proposed',
         'evidence': _evidence('travel distance ... 999 ... point of choice')}]})
    assert out.facts == [] and out.dropped == 1


def test_a_quote_fragment_cannot_borrow_digits_from_a_different_number():
    assert not review._occurs('Travel distance ... 999 ... to a point',
                              'Travel distance is 1999 m to a point of choice.')


def test_a_cited_provision_needs_its_own_number_in_the_excerpt():
    out, _ = _run({**EMPTY, 'provisions': [
        {'cited': 'Article 9.10.15.4.', 'code': 'NBC(AE) 2019', 'evidence': _evidence('Fire engineering letter.')},
        {'cited': 'Clause D1.4', 'code': 'BCA 2013', 'evidence': _evidence('Fire engineering letter.')}]},
        codes=_codes())
    assert out.provisions == [] and out.dropped == 2


def test_a_verdict_after_an_article_number_or_after_an_unrelated_hedge_is_removed():
    out, _ = _run({**EMPTY, 'missing': [
        {'text': 'Confirm the rating under Article 9.10.15.4. The design complies with the code.', 'why': 'x'},
        {'text': 'No report is attached, and the design is safe.', 'why': 'x'},
        {'text': 'Confirm the rating. the design complies with the code.', 'why': 'x'},
        {'text': 'A report must show that the design meets the requirements.', 'why': 'x'}]}, codes=_codes())
    texts = [m.text for m in out.missing]
    assert not any('complies with the code' in t or 'design is safe' in t for t in texts)
    assert 'A report must show that the design meets the requirements.' in texts


def test_restore_is_exact_with_adjacent_and_repeated_placeholders():
    original = 'Owners Alice Smith Bob Jones; write to a@x.com and b@y.com today.'
    scrubbed = 'Owners [personal detail] [personal detail]; write to [email] and [email] today.'
    text, values = review.restore('Owners [personal detail] [personal detail]', scrubbed, original)
    assert (text, values) == ('Owners Alice Smith Bob Jones', [])
    assert review.restore('[personal detail]', scrubbed, original) is None
    text, values = review.restore('write to [email] and [email] today', scrubbed, original)
    assert (text, values) == ('write to a@x.com and b@y.com today', ['a@x.com', 'b@y.com'])


def test_restoration_abstains_when_a_repeated_excerpt_has_different_original_values():
    original = 'Contact a@x.com; contact b@y.com.'
    assert review.restore('contact [email]', scrub(original), original) is None


def test_restoration_never_substitutes_a_personal_value_into_a_different_kind_of_placeholder():
    out, _ = _run({**EMPTY, 'facts': [
        {'text': 'Call [phone].', 'status': 'stated',
         'evidence': _evidence('Prepared for 74-[personal detail]')}]})
    assert out.facts[0].text == 'Call [phone].'


def test_a_restatement_keeps_its_placeholders_when_they_could_be_mixed_up():
    page = 'The owner is Ana Li and the reviewer is Bo Chen, per the letter to Council.'
    transport = _model({**EMPTY, 'facts': [
        {'text': 'The reviewer is [personal detail] and the owner is [personal detail].', 'status': 'stated',
         'evidence': _evidence('The owner is [personal detail] and the reviewer is [personal detail]')}]})
    out = review.run(REQUEST, [('file1', 'letter.html', page.encode())],
                     outbound=lambda s, own: scrub(s, ['Ana Li', 'Bo Chen', *own]), transport=transport,
                     status='live', codes=None)
    assert out.facts[0].evidence[0].quote == 'The owner is Ana Li and the reviewer is Bo Chen'
    assert out.facts[0].text == 'The reviewer is [personal detail] and the owner is [personal detail].'


def test_compound_dimensions_and_conflict_numbers_are_checked():
    page = 'Proposed studs are 2x6. The wall is 25 m long. The plan says 25 m.'
    transport = _model({**EMPTY,
                        'facts': [{'text': 'Proposed studs are 2x8.', 'status': 'proposed',
                                   'evidence': _evidence('Proposed studs are 2x6.')}],
                        'conflicts': [{'text': 'One page says 999 m and another 888 m.',
                                       'evidence': _evidence('The wall is 25 m long.') + _evidence('The plan says 25 m.')},
                                      {'text': 'The length is stated twice.',
                                       'evidence': _evidence('The wall is 25 m long.') + _evidence('The wall is 25 m long.')}]})
    out = review.run(REQUEST, [('file1', 'notes.html', page.encode())], outbound=lambda s, own: s,
                     transport=transport, status='live', codes=None)
    assert out.facts[0].text == 'Proposed studs are 2x6.'
    assert out.conflicts == []


def test_personal_details_anywhere_in_the_files_and_their_names_never_reach_the_model():
    html = ('<p>Fire letter.</p>' + '<p>filler text</p>' * 50 +
            '<p>Owner: Alice Smith</p><p>Permit number: AB-987654</p>').encode()
    _, seen = None, None
    transport = _model(EMPTY)
    review.run(REQUEST, [('file1', 'Alice Smith permit AB-987654.html', html)],
               outbound=lambda s, own: scrub(s, own), transport=transport, status='live', codes=None)
    sent = json.dumps(transport.seen)
    assert 'Alice Smith' not in sent and 'AB-987654' not in sent


def test_a_filename_alone_cannot_disclose_an_unlabelled_name():
    transport = _model(EMPTY)
    review.run(REQUEST, [('file1', 'Alice Smith.pdf', b'not a readable PDF')],
               outbound=lambda s, own: scrub(s, own), transport=transport, status='live')
    assert 'Alice Smith' not in json.dumps(transport.seen)
    assert transport.seen['files'][0]['name'] == 'Attachment 1'


def test_the_review_names_no_provider_or_model():
    from engine.tests.test_no_provider_names_exposed import IDENTIFY_NAMES
    out, _ = _run(EMPTY)
    assert out.model == 'review-3'
    assert not IDENTIFY_NAMES.search(out.model_dump_json())


@pytest.mark.parametrize('code,expected', [
    ('NBC(AE) 2023', '9.10.15.4.'),
    ('National Building Code - 2023 Alberta Edition, 2nd printing', '9.10.15.4.'),
    ('NBC(AE) 2019', None), ('New Brunswick Building Code 2015', None),
    ('BCBC 2024', None), ('NBC 2020', None), (None, None),
])
def test_only_a_positively_named_current_alberta_code_is_matched(code, expected):
    codes = _codes()
    if codes is None:
        pytest.skip('code database not built')
    page = f'Article 9.10.15.4. of {code or "an unstated code"} was considered.'
    out, _ = _run({**EMPTY, 'provisions': [
        {'cited': 'Article 9.10.15.4.', 'code': code, 'evidence': _evidence(page)}]},
        codes=codes, page=page)
    assert out.provisions[0].resolves_to == expected


def test_a_cited_sentence_cannot_borrow_another_sentences_evidence():
    out, _ = _run({**EMPTY, 'provisions': [
        {'cited': 'Sentence 9.10.15.4.(2)', 'code': 'NBC(AE) 2023',
         'evidence': _evidence('Sentence 9.10.15.4.(1)')}]}, codes=_codes())
    assert out.provisions == []


def test_a_model_cannot_relabel_a_historical_or_unstated_source_as_current_alberta():
    out, _ = _run({**EMPTY, 'provisions': [
        {'cited': 'Sentence 9.10.15.4.(1)', 'code': 'NBC(AE) 2023',
         'evidence': _evidence('Sentence 9.10.15.4.(1) of NBC(AE) 2019 was considered.')}]}, codes=_codes())
    assert out.provisions[0].resolves_to is None


def test_personal_values_beyond_the_first_sixty_pdf_pages_are_scrubbed():
    from engine.tests.test_intake_pdf import pdf
    pages = [[(72, 700, 'Synthetic document text.')] for _ in range(60)]
    pages.append([(72, 700, 'Owner: Alice Smith'), (72, 680, 'Permit number: AB-987654')])
    transport = _model(EMPTY)
    review.run(REQUEST, [('file1', 'Alice Smith permit AB-987654.pdf', pdf(pages))],
               outbound=lambda s, own: scrub(s, own), transport=transport, status='live')
    sent = json.dumps(transport.seen)
    assert 'Alice Smith' not in sent and 'AB-987654' not in sent
    assert any(p['page'] == 61 for p in transport.seen['files'][0]['pages'])


def test_unread_scan_and_budget_omissions_are_reported_even_when_the_model_says_nothing(monkeypatch):
    from engine.tests.test_intake_pdf import pdf
    data = pdf([[(72, 700, 'First page text.')], [], [(72, 700, 'Third page text.')]], shapes_only={1})
    monkeypatch.setattr(review, 'BUDGET_CHARS', 20)
    out = review.run(REQUEST, [('file1', 'mixed.pdf', data)], outbound=lambda s, own: s,
                     transport=_model(EMPTY), status='live')
    assert out.pages_sent == 1
    assert any(f.kind == 'not_read' and '2 of 3 pages' in f.text for f in out.flags)


def test_a_rejected_verdict_is_not_reintroduced_from_its_quote_or_a_document_title():
    page = 'The design complies with the code. The travel distance is 25 m.'
    out, _ = _run({**EMPTY,
        'documents': [{'file': 'file1', 'kind': 'letter', 'title': 'The design is safe.',
                       'author': None, 'date': None, 'status': None}],
        'facts': [{'text': 'The design complies with the code.', 'status': 'stated',
                   'evidence': _evidence('The design complies with the code.')} ]}, page=page)
    assert out.facts[0].text == 'The source contains the quoted statement.'
    assert out.facts[0].evidence[0].quote == 'The design complies with the code.'
    assert out.documents[0].title is None


def test_files_that_could_not_be_read_are_flagged_by_batatis_itself():
    transport = _model(EMPTY)
    out = review.run(REQUEST, [('file1', 'drawing.jpg', b'\xff\xd8not text')], outbound=lambda s, own: s,
                     transport=transport, status='live', codes=None)
    assert [f.kind for f in out.flags] == ['not_read'] and 'drawing.jpg' in out.flags[0].text
