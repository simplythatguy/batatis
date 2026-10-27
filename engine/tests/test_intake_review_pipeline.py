"""Narrative review cannot replace facts the applicant can confirm in the ledger."""
import json
import io

import pytest
from reportlab.pdfgen import canvas

from engine.intake import service


REQUEST = 'Review the attached proposal and identify missing administrative evidence.'
PAGE = 'The building has 2 storeys. The proposed roof soffit projection is 0.3 m.'


def execute(*, failed=False, partial=False):
    calls = []

    def intake(system, user, schema):
        text = json.loads(user)['text']
        calls.append(text)
        quote = 'The proposed roof soffit projection is 0.3 m.'
        facts = [{'field': 'statement', 'value': quote, 'quote': quote}] if quote in text else []
        return {'facts': facts}, {}

    def review(system, user, schema, model, effort):
        if failed:
            raise TimeoutError('provider unavailable')
        body = json.loads(user)
        page = body['files'][0]['pages'][0]
        return {'documents': [{'file': 'file1', 'kind': 'proposal'}],
                'facts': [{'text': 'The proposed roof soffit projection is 0.3 m.', 'status': 'proposed',
                           'evidence': [{'file': 'file1', 'page': page['page'],
                                         'quote': 'The proposed roof soffit projection is 0.3 m.'}]}],
                'flags': ([{'kind': 'not_read', 'text': 'A referenced drawing is missing.', 'evidence': []}]
                          if partial else [])}, {}

    data = io.BytesIO()
    document = canvas.Canvas(data)
    document.drawString(30, 775, 'Project brief')
    document.drawString(30, 750, PAGE)
    document.save()
    result = service.run(REQUEST, [('file1', 'proposal.pdf', data.getvalue())],
                         outbound=lambda text, personal: text, transport=intake, status='live',
                         review_transport=review, review_status='live')
    return result, calls


def test_review_does_not_remove_file_facts_from_the_confirmation_flow():
    result, calls = execute()
    assert result.review.status == 'live'
    assert result.review.facts[0].evidence[0].quote == 'The proposed roof soffit projection is 0.3 m.'
    assert any(f.field == 'storeys' and f.value == 2 for f in result.facts)
    semantic = next(f for f in result.facts if f.field.startswith('statement.'))
    assert semantic.value == semantic.source.quote == 'The proposed roof soffit projection is 0.3 m.'
    assert semantic.source.ref == 'file1' and semantic.source.page == 1
    assert semantic.status == 'unconfirmed'
    assert any(p.fact_id == semantic.id for p in result.pointers)
    assert len(calls) == 2 and calls[0] == REQUEST


@pytest.mark.parametrize('options,status', [({'failed': True}, 'failed'), ({'partial': True}, 'live')])
def test_unavailable_or_incomplete_review_keeps_the_file_model_fallback(options, status):
    result, calls = execute(**options)
    assert result.review.status == status
    assert len(calls) == 2
    assert calls[0] == REQUEST
    assert PAGE in calls[1]
