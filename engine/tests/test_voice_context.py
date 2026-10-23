"""Synthetic source/auth contracts, using only newly created temporary databases/PDFs."""
import io
import json
import sqlite3

import pytest
from fastapi import HTTPException
from reportlab.pdfgen import canvas

from codedb import store as codedb_store
from engine.account_models import User
from engine.codes import Codes
from engine.models import Case
from engine.store import CaseStore
from engine.voice_context import VoiceScope, prepare_context


def synthetic_codes(path):
    """These labels/text are test data, never an official code corpus."""
    with sqlite3.connect(path) as con:
        con.executescript(codedb_store.SCHEMA)
        con.execute('INSERT INTO docs VALUES (?,?,?,?,?,?,?)',
                    ('NBC-AE', 'SYNTHETIC voice tests only', 'code', 1, 'unused', 'unused', 'synthetic'))
        rows = [('B', '9.10.9.16.(1)', 9, '9.10.', '9.10.9.', '9.10.9.16.', 1, None)]
        rows += [('C', f'2.3.1.1.({sentence}){clause}', 2, '2.3.', '2.3.1.', '2.3.1.1.', sentence,
                  clause[1:-1] if clause else None)
                 for sentence, clause in [(2, '(a)'), (2, '(b)'), (3, ''), (4, '')]]
        for division, provision, part, section, subsection, article, sentence, clause in rows:
            text = 'SYNTHETIC source text for the voice contract; not a code interpretation.'
            con.execute('''INSERT INTO provisions
                (doc,division,id,level,part,section,subsection,article,sentence,clause,subclause,
                 parent_id,article_title,title,text,text_raw,clauses,pdf_page,pdf_page_end,volume,sort_key)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',
                ('NBC-AE', division, provision, 'clause' if clause else 'sentence', part, section, subsection,
                 article, sentence, clause, None, article, 'Synthetic', 'Synthetic', text, text, '[]', 1, 1, 1, provision))
    return Codes(path)


def pdf_bytes(text):
    output = io.BytesIO()
    pdf = canvas.Canvas(output)
    pdf.drawString(50, 750, text)
    pdf.showPage()
    pdf.save()
    return output.getvalue()


@pytest.fixture
def context_env(tmp_path):
    store = CaseStore(tmp_path / 'voice-context.sqlite')
    codes = synthetic_codes(tmp_path / 'voice-codes.sqlite')
    owner = User(email='voice-owner@example.test', name='Specific Owner', role='applicant')
    case = store.put(Case(owner_id=owner.id, authority='edmonton', title='Specific Owner project',
                          provisions=['9.10.9.16.(1)']))
    return store, codes, owner, case


def case_scope(case, **changes):
    return VoiceScope(context_id='synthetic-case-context', screen='questions',
                      case_id=case.id, case_version=case.version, **changes)


def test_authorized_case_projection_uses_exact_source_lookup_and_real_pdf_text(context_env):
    store, codes, owner, case = context_env
    saved = store.put_file(case.id, 'real-upload.pdf', pdf_bytes('Synthetic report: wall sample A. Specific Owner'))
    before = store.get(case.id).model_dump()
    prepared = prepare_context(case_scope(case, attachment_ids=[saved['id']],
        destinations=['settings', 'question-risk', 'review-decide']), store=store, code=lambda: codes, user=owner)
    data = prepared.data
    assert data['selected_code'][0]['text'].startswith('SYNTHETIC source text')
    assert data['selected_section_c'][0]['provision_id'] == '9.10.9.16.(1)'
    assert prepared.citation_ids == frozenset({'9.10.9.16.(1)', '2.3.1.1.(2)(a)',
                                            '2.3.1.1.(2)(b)', '2.3.1.1.(3)', '2.3.1.1.(4)'})
    assert {item['id'] for item in data['application']['process_fields']} >= {
        'risk_assessment', 'mitigating_measures', 'assumptions_and_limits'}
    assert not any(item['name'] == 'Decide' for item in data['navigation'])
    document = data['attachments'][0]
    assert document['content_state'] == 'text_excerpt' and document['file_id'] == saved['id']
    assert document['case_id'] == case.id
    assert document['content'][0]['source'] == {'type': 'file', 'ref': saved['id'], 'page': 1}
    assert 'Synthetic report: wall sample A.' in document['content'][0]['text']
    assert 'Specific Owner' not in json.dumps(data)
    assert store.get(case.id).model_dump() == before  # no proposed/confirmed facts or evidence edits


def test_context_authorizes_metadata_before_any_content_file_or_code_read(context_env, monkeypatch):
    store, codes, owner, case = context_env
    outsider = User(email='outsider@example.test', name='Outsider', role='applicant')
    def forbidden(*args, **kwargs):
        pytest.fail('Private content was read before authorization')
    monkeypatch.setattr(store, 'get', forbidden)
    monkeypatch.setattr(store, 'get_file', forbidden)
    with pytest.raises(HTTPException) as error:
        prepare_context(case_scope(case, attachment_ids=['not-owned']), store=store, code=forbidden, user=outsider)
    assert error.value.status_code == 404


@pytest.mark.parametrize('authority,status,expected', [
    ('edmonton', 'draft', 404), ('calgary', 'submitted', 404), ('edmonton', 'submitted', 200),
])
def test_reviewer_authority_and_submission_rules_are_shared(context_env, authority, status, expected):
    store, codes, owner, case = context_env
    case = store.put(case.model_copy(update={'status': status}))
    reviewer = User(email='officer@example.test', name='Officer', role='reviewer', authority=authority)
    if expected == 404:
        with pytest.raises(HTTPException) as error:
            prepare_context(case_scope(case), store=store, code=lambda: codes, user=reviewer)
        assert error.value.status_code == 404
    else:
        prepared = prepare_context(case_scope(case, destinations=['review-decide']),
                                   store=store, code=lambda: codes, user=reviewer)
        assert prepared.navigation('Open Decide', reviewer).destination == 'review-decide'


def test_reviewer_cannot_get_review_destinations_for_own_application(context_env):
    store, codes, owner, case = context_env
    self_reviewer = owner.model_copy(update={'role': 'reviewer', 'authority': 'edmonton'})
    case = store.put(case.model_copy(update={'status': 'submitted'}))
    prepared = prepare_context(case_scope(case, destinations=['review-decide']),
                               store=store, code=lambda: codes, user=self_reviewer)
    assert prepared.navigation('Open Decide', self_reviewer) is None


def test_cross_case_attachment_id_is_never_a_document(context_env):
    store, codes, owner, case = context_env
    other = store.put(Case(owner_id=owner.id))
    saved = store.put_file(other.id, 'elsewhere.pdf', pdf_bytes('Other application text'))
    with pytest.raises(HTTPException) as error:
        prepare_context(case_scope(case, attachment_ids=[saved['id']]), store=store, code=lambda: codes, user=owner)
    assert error.value.status_code == 404


def test_a_filename_or_unreadable_pdf_does_not_imply_document_understanding(context_env):
    store, codes, owner, case = context_env
    saved = store.put_file(case.id, 'approved-engineering-report.pdf', b'%PDF-1.4\nunreadable')
    prepared = prepare_context(case_scope(case, attachment_ids=[saved['id']]),
                               store=store, code=lambda: codes, user=owner)
    assert prepared.data['attachments'][0]['content_state'] == 'not_read'
    assert not prepared.data['attachments'][0]['content']


def test_stale_case_version_fails_before_provider_context_is_prepared(context_env):
    store, codes, owner, case = context_env
    store.rename_title(case.id, 'Changed')
    with pytest.raises(HTTPException) as error:
        prepare_context(case_scope(case), store=store, code=lambda: codes, user=owner)
    assert error.value.status_code == 409
