"""Counterexamples at the intake review's privacy and evidence boundaries."""
import json

import pytest

from engine.intake import review, service
from engine.redact import scrub


def evidence(quote, file='file1', page=None):
    return {'file': file, 'page': page, 'quote': quote}


def run(payload, text, *, request='Review the source.'):
    return review.run(request, [('file1', 'source.txt', text.encode())],
                      outbound=lambda s, own: scrub(s, own),
                      transport=lambda *args: (payload, {}), status='live')


def test_conflicting_personal_candidates_are_scrubbed_in_both_service_model_passes():
    from engine.tests.test_intake_pdf import pdf

    text = 'Owner: Alice Smith\nOwner: Bob Jones\nPermit number: AB-1234\nPermit number: CD-5678'
    seen = {'intake': [], 'review': []}

    def intake_model(system, user, schema):
        seen['intake'].append(user)
        return {'facts': []}, {}

    def review_model(system, user, schema, model, effort):
        seen['review'].append(user)
        return {}, {}

    data = pdf([[(72, 700 - 20 * i, line) for i, line in enumerate(text.splitlines())]])
    out = service.run(text, [('file1', 'Alice Smith AB-1234.pdf', data)],
                      transport=intake_model, status='live', review_transport=review_model,
                      review_status='live')
    assert out.review.status == 'live' and all(seen.values())
    for sent in seen.values():
        for value in ('Alice Smith', 'Bob Jones', 'AB-1234', 'CD-5678'):
            assert value not in json.dumps(sent), value
    assert 'Attachment 1' in seen['review'][0]


def test_short_names_and_permits_are_personal_but_short_legal_numbers_are_not():
    values = review.personal_values(['Owner: Al\nPermit number: X7\nLot: 2\nBlock: 3'])
    assert set(values) == {'Al', 'X7'}


def test_service_keeps_short_legal_numbers_but_scrubs_short_names_and_permits():
    seen = []

    def model(system, user, *args):
        seen.append(user)
        return {'facts': []}, {}

    service.run('Owner: Al\nPermit number: X7\nLot: 202\nThe wall length is 202 m.', [],
                transport=model, status='live', review_transport=model, review_status='live')
    assert len(seen) == 2
    for sent in seen:
        text = json.loads(sent).get('text', json.loads(sent).get('request'))
        assert 'Al' not in text and 'X7' not in text
        assert 'Lot: 202' in text and '202 m' in text


def test_a_person_identified_on_page_61_is_scrubbed_from_every_service_outbound():
    from engine.tests.test_intake_pdf import pdf

    pages = [[(72, 700, 'Alice Smith supplied the brief.')]]
    pages += [[(72, 700, 'Ordinary source text.')]] * 59
    pages += [[(72, 700, 'Owner: Alice Smith')]]
    seen = []

    def model(system, user, *args):
        seen.append(json.loads(user))
        return {'facts': []}, {}

    out = service.run("Review Alice Smith's brief.", [('file1', 'Alice Smith.pdf', pdf(pages))],
                      transport=model, status='live', review_transport=model, review_status='live')
    assert out.review.status == 'live' and len(seen) > 1
    assert all('Alice Smith' not in json.dumps(sent) for sent in seen)
    assert any(p['page'] == 61 for p in seen[-1]['files'][0]['pages'])


@pytest.mark.parametrize('agent_quote', ['Agent [personal detail]', 'Agent [PERSONAL DETAIL]'])
def test_unresolved_repeated_evidence_blocks_person_substitution(agent_quote):
    original = 'Owner Alice; Agent Bob; Agent Carol.'
    scrubbed = scrub(original, ['Alice', 'Bob', 'Carol'])
    check = review._Checker('', [review.Source('file1', 'source.txt', [(None, scrubbed)], 1)],
                            {('file1', None): original})
    refs = check.evidence([evidence('Owner [personal detail]'), evidence(agent_quote)])
    assert refs[0].quote == 'Owner Alice'
    assert refs[1].quote == agent_quote
    assert check.unscrub('Agent [personal detail]', refs) == 'Agent [personal detail]'


@pytest.mark.parametrize('text', [
    'The letter states that the design is safe and is compliant.',
    'Confirm that the design meets the requirements and is adequate.',
    'A report must show that the design meets the requirements and is structurally safe.',
    'The letter states that the design is safe, and is compliant.',
    'The letter states that the design is structurally and functionally safe.',
])
def test_shared_subject_predicates_keep_their_attribution_or_requirement(text):
    assert review._clean(text, lambda _: True) == text


@pytest.mark.parametrize('text', [
    'No report is attached, and the design is safe.',
    'No additional report is needed because the design complies with the code.',
    'The design is structurally safe.',
    'The letter states that the report is attached and the design is safe.',
    'The design is not documented and is safe.',
    'The design is structurally and functionally safe.',
    'The design is safe, what else is needed?',
])
def test_an_independent_claim_does_not_inherit_an_unrelated_hedge(text):
    assert review._clean(text, lambda _: True) == ''


@pytest.mark.parametrize('cited,source', [
    ('9.10.15.4.(1)(a)(ii)', '9.10.15.4.(1)(a)(i)'),
    ('9.10.15.4. (2)', '9.10.15.4.(1)'),
    ('Articles 9.10.15.4. and 99.9.9.9.', 'Article 9.10.15.4.'),
])
def test_every_complete_cited_identifier_must_be_in_its_evidence(cited, source):
    out = run({'provisions': [{'cited': cited, 'code': 'NBC(AE) 2023',
                               'evidence': [evidence(source)]}]}, source)
    assert out.provisions == []


def test_nested_citations_accept_permissible_whitespace():
    source = 'Sentences 9.10.15.4. (1) (a) (ii) and 9.10.15.5.(2) are cited.'
    cited = '9.10.15.4.(1)(a)(ii) and 9.10.15.5. (2)'
    out = run({'provisions': [{'cited': cited, 'evidence': [evidence(source)]}]}, source)
    assert out.provisions[0].cited == cited


@pytest.mark.parametrize('source,fragment', [('19.9', '9'), ('1,999', '999'), ('999.1', '999')])
def test_excerpt_fragments_cannot_borrow_part_of_a_numeric_token(source, fragment):
    assert not review._occurs(f'The length ... {fragment} ... was recorded',
                              f'The length {source} m was recorded.')
    assert review._occurs(f'The length ... {source} ... was recorded',
                          f'The length {source} m was recorded.')


def test_overlapping_or_clipped_excerpts_cannot_manufacture_a_conflict():
    source = 'The wall length is 25 m.'
    out = run({'conflicts': [{'text': 'The wall lengths disagree.', 'evidence': [
        evidence(source), evidence('wall length is 25 m')]}]}, source)
    assert out.conflicts == []


def test_a_clipped_copy_of_the_same_assertion_in_another_file_cannot_manufacture_a_conflict():
    source = 'The wall length is 25 m.'
    out = review.run('', [('file1', 'one.txt', source.encode()), ('file2', 'two.txt', source.encode())],
                     outbound=lambda s, own: s, transport=lambda *args: ({'conflicts': [{
                         'text': 'The wall lengths disagree.', 'evidence': [
                             evidence(source), evidence('wall length is 25 m', file='file2')]}]}, {}), status='live')
    assert out.conflicts == []


@pytest.mark.parametrize('separate_files', [False, True])
def test_two_disjoint_clips_of_one_assertion_cannot_establish_a_conflict(separate_files):
    source = 'The wall length is exactly 25 metres.'
    files = [('file1', 'one.txt', source.encode())]
    if separate_files:
        files.append(('file2', 'two.txt', source.encode()))
    out = review.run('', files, outbound=lambda s, own: s, transport=lambda *args: ({'conflicts': [{
        'text': 'The wall lengths disagree.', 'evidence': [evidence('The wall length'),
            evidence('exactly 25 metres', file='file2' if separate_files else 'file1')]}]}, {}), status='live')
    assert out.conflicts == []


def test_independent_conflicting_assertions_in_different_files_are_kept():
    one, two = 'The wall length is 25 m.', 'The wall length is 30 m.'
    out = review.run('', [('file1', 'one.txt', one.encode()), ('file2', 'two.txt', two.encode())],
                     outbound=lambda s, own: s, transport=lambda *args: ({'conflicts': [{
                         'text': 'The wall lengths disagree.', 'evidence': [
                             evidence(one), evidence(two, file='file2')]}]}, {}), status='live')
    assert len(out.conflicts) == 1


@pytest.mark.parametrize('pages', [
    [(1, 'The wall length is 25 m. The wall length is 30 m.')],
    [(1, 'The wall length is 25 m; the wall length is 30 m.')],
    [(1, 'The wall length is 25 m.'), (2, 'The wall length is 30 m.')],
])
def test_independent_source_statements_can_support_a_conflict(monkeypatch, pages):
    monkeypatch.setattr(review, 'read_source', lambda *args: review.Source('file1', 'source.pdf', pages, len(pages)))
    out = run({'conflicts': [{'text': 'The wall lengths disagree.', 'evidence': [
        evidence('The wall length is 25 m.', page=1),
        evidence('The wall length is 30 m.', page=pages[-1][0])]}]}, '')
    assert len(out.conflicts) == 1


@pytest.mark.parametrize('payload', [[], {'facts': [None]}, {'facts': [{'text': 'A statement.', 'status': 'stated',
    'evidence': [evidence('A source statement.', page='one')]}]}, {'facts': 'wrong'},
    {'facts': [{'text': 7, 'status': 'stated', 'evidence': []}]}])
def test_malformed_external_payload_is_a_controlled_failed_review(payload):
    out = service.run('Review the source.', [], review_transport=lambda *args: (payload, {}),
                      review_status='live')
    assert out.review.status == 'failed'
    assert out.review.reason in ('ValidationError', 'ValueError')


@pytest.mark.parametrize('source,restatement', [
    ('The design complies with the code.', 'The design complies with the code.'),
    ('Article 99.9.9.9. of BCA 2013 is cited.', 'Article 99.9.9.9. of BCA 2013 is cited.'),
    ('Council decided that the design is adequate.', 'The design is adequate.'),
])
def test_rejected_restatement_keeps_verified_source_evidence_without_a_verdict(source, restatement):
    out = run({'facts': [{'text': restatement, 'status': 'stated', 'evidence': [evidence(source)]}]}, source)
    assert len(out.facts) == 1
    assert out.facts[0].text == 'The source contains the quoted statement.'
    assert out.facts[0].evidence[0].quote == source


def test_historical_opinions_keep_their_attribution():
    source = 'Council decided that the design is adequate.'
    out = run({'facts': [{'text': source, 'status': 'decided', 'evidence': [evidence(source)]}]}, source)
    assert out.facts[0].text == source


@pytest.mark.parametrize('value', ['The design is structurally safe', 'Article 99.9.9.9'])
def test_restoring_a_private_span_cannot_bypass_the_own_voice_filter(value):
    source = 'Owner: ' + value
    out = run({'facts': [{'text': 'The owner is [personal detail].', 'status': 'stated',
                          'evidence': [evidence('Owner: [personal detail]')]}]}, source)
    assert out.facts[0].text == 'The source contains the quoted statement.'
    assert out.facts[0].evidence[0].quote == source
