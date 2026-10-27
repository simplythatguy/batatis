"""Offline R4 regressions; no corpus items or provider requests are used."""
from __future__ import annotations

import io
import json
import socket

import httpx
import pytest
from reportlab.pdfgen import canvas

from engine.intake import review, service
from engine.models import Case
from evals_dev.data_prompts import checks


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError('R4 regressions must remain offline')
    monkeypatch.setattr(socket.socket, 'connect', forbidden)
    monkeypatch.setattr(httpx.Client, 'send', forbidden)


def reviewed(payload, text='An attachment records a wall dimension.'):
    return review.run('Review the attached record.', [('file1', 'source.txt', text.encode())],
                      outbound=lambda s, _: s, transport=lambda *args: (payload, {}), status='live')


REJECT = [
    'The design requires a variance and is safe.',
    'The design requires documentation and is compliant.',
    'The design does not comply with the code and is safe.',
    'The letter states that the design is safe and the design is compliant.',
    'Confirm that the design meets the requirements and the design is adequate.',
    'No report is attached, and the design is safe.',
    'The letter states that the report is attached and the design is safe.',
    'The design is structurally safe.',
    'The design is safe, what else is needed?',
]
KEEP = [
    'The letter states that the design is safe and is compliant.',
    'Confirm that the design meets the requirements and is adequate.',
    'A report must show that the design meets the requirements and is structurally safe.',
    'The letter states that the design is safe, and is compliant.',
    'The letter states that the design is structurally and functionally safe.',
    'Does the design meet the requirements?',
    'Batatis does not say whether the design complies with the code.',
    'The design does not comply with the code.',
]


@pytest.mark.parametrize('text', REJECT)
def test_review_run_drops_ungoverned_verdict_in_missing(text):
    out = reviewed({'missing': [{'text': text, 'why': ''}]})
    assert out.status == 'live'
    assert out.missing == []
    assert out.dropped == 1


@pytest.mark.parametrize('text', KEEP)
def test_review_run_keeps_governed_shared_predicate(text):
    out = reviewed({'missing': [{'text': text, 'why': ''}]})
    assert [item.text for item in out.missing] == [text]


@pytest.mark.parametrize('text', REJECT)
def test_harness_independently_detects_ungoverned_verdict(monkeypatch, text):
    def forbidden(*args, **kwargs):
        raise AssertionError('the harness must not reuse the production verdict guard')
    monkeypatch.setattr(review, 'verdict', forbidden)
    monkeypatch.setattr(review, '_clean', forbidden)
    assert checks.claims([text]) == [text]


@pytest.mark.parametrize('text', KEEP)
def test_harness_keeps_governed_shared_predicate(text):
    assert checks.claims([text]) == []


def ref(quote):
    return {'file': 'file1', 'page': None, 'quote': quote}


@pytest.mark.parametrize('separator', ['\n', '\r\n', '\n\n', '\n  '])
def test_review_run_keeps_conflict_between_distinct_labelled_rows(separator):
    one, two = 'Wall length: 25 metres', 'Wall length: 30 metres'
    out = reviewed({'conflicts': [{'text': 'The wall lengths disagree.',
                                  'evidence': [ref(one), ref(two)]}]}, one + separator + two)
    assert len(out.conflicts) == 1
    assert [e.quote for e in out.conflicts[0].evidence] == [one, two]


@pytest.mark.parametrize('text,quotes', [
    ('Wall length: exactly 25 metres', ('Wall length', 'exactly 25 metres')),
    ('Wall length: exactly\n25 metres', ('Wall length', 'exactly 25 metres')),
    ('Wall length: exactly 25 metres and con-\nfiguration: north.',
     ('Wall length', 'configuration: north')),
    ('Wall length: 25 metres\nWall length: 30 metres',
     ('Wall length: 25 metres', 'length: 25 metres')),
    ('Wall length: 25 metres\nWall length: 25 metres',
     ('Wall length', '25 metres')),
])
def test_row_handling_does_not_turn_clips_or_wrapping_into_conflicts(text, quotes):
    out = reviewed({'conflicts': [{'text': 'The wall lengths disagree.',
                                  'evidence': [ref(q) for q in quotes]}]}, text)
    assert out.conflicts == []


def pdf(text):
    buf = io.BytesIO()
    page = canvas.Canvas(buf)
    for index, line in enumerate(text.splitlines()):
        page.drawString(72, 700 - index * 20, line)
    page.showPage()
    page.save()
    return buf.getvalue()


def as_result(extraction, request):
    case = Case()
    service.apply(case, request, extraction)
    return {'errors': [], 'case': case.model_dump(mode='json'),
            'identify_skipped': True, 'expected_stages': {'intake_model': True}}


def test_service_partial_attached_page_failure_is_operationally_incomplete():
    sent = []

    def intake_model(system, user, schema):
        text = json.loads(user)['text']
        sent.append(text)
        if 'Attached record' in text:
            raise httpx.ReadTimeout('offline attachment failure')
        return {'facts': []}, {}

    request = 'Review the submitted building proposal.'
    out = service.run(request, [('file1', 'record.pdf', pdf('Project brief: Attached record of wall dimensions.'))],
                      transport=intake_model, status='live')
    assert len(sent) == 2 and 'Attached record' not in sent[0] and 'Attached record' in sent[1]
    assert out.model.status == 'live' and out.model.reason == 'ReadTimeout'
    assert checks.completion(as_result(out, request)) == ['intake_model:partial:ReadTimeout']


def test_service_success_with_unread_attachment_is_not_an_operational_failure():
    request = 'Review the submitted building proposal.'
    out = service.run(request, [('file1', 'image.png', b'offline image bytes')],
                      transport=lambda *args: ({'facts': []}, {}), status='live',
                      review_transport=lambda *args: ({}, {}), review_status='live')
    assert out.model.status == 'live' and out.model.reason is None
    assert any(flag.kind == 'not_read' for flag in out.review.flags)
    assert checks.completion(as_result(out, request)) == []


@pytest.mark.parametrize('context', ['reference', 'unknown', 'mixed'])
def test_service_excluded_passages_remain_review_context_without_project_answers(context):
    reference = ('Owner: Reference Owner\nSite address: 10111 104 Avenue NW\n'
                 'A four-storey office building.\nArticle 9.10.11.2.(2)')
    text = {
        'reference': 'Policy: Synthetic reference guidance\n' + reference,
        'unknown': 'Unclassified record\n' + reference,
        'mixed': ('Project brief\nOur new building is a two-storey house.\n'
                  'Site address: 42 Project Street\nAppendix: reference guidance\n' + reference),
    }[context]
    intake_requests, review_requests = [], []

    def intake_model(system, user, schema):
        intake_requests.append(json.loads(user)['text'])
        return {'facts': []}, {}

    def document_review(system, user, schema, model, effort):
        review_requests.append(user)
        return {'facts': [{'text': 'A four-storey office building.', 'status': 'stated',
                           'evidence': [{'file': 'file1', 'page': 1,
                                         'quote': 'A four-storey office building.'}]}]}, {}

    request = 'Review the submitted wall proposal.'
    out = service.run(request, [('file1', 'record.pdf', pdf(text))],
                      transport=intake_model, status='live',
                      review_transport=document_review, review_status='live')
    case = Case()
    service.apply(case, request, out)
    assert len(intake_requests) == (2 if context == 'mixed' else 1)
    assert all('four-storey' not in sent for sent in intake_requests)
    assert len(review_requests) == 1 and 'four-storey' in review_requests[0]
    for sent in [*intake_requests, *review_requests]:
        assert all(value not in sent for value in ('Reference Owner', '10111 104 Avenue NW', '42 Project Street'))
    assert case.intake.conflicts == []
    assert case.intake.files[0].status == 'read'
    assert case.intake.review.status == 'live'
    assert [fact.text for fact in case.intake.review.facts] == ['A four-storey office building.']
    assert [(c.entered, c.source_ref, c.page) for c in case.intake.unresolved_citations] == [
        ('9.10.11.2.(2)', 'file1', 1)]
    file_facts = [fact for fact in case.facts if fact.source.ref == 'file1']
    if context == 'mixed':
        assert [(fact.value, fact.status) for fact in file_facts if fact.field == 'storeys'] == [(2, 'confirmed')]
        assert [fact.value for fact in file_facts if fact.field == 'municipal_address'] == ['42 Project Street']
        assert not [fact for fact in file_facts if fact.field == 'owner_name']
    elif context == 'unknown':
        # An unmarked document may only propose values; nothing it says becomes an answer by itself.
        assert all(fact.status == 'unconfirmed' for fact in file_facts)
    else:
        assert file_facts == []
        assert case.intake.files[0].reason
    assert checks.completion(as_result(out, request)) == []
