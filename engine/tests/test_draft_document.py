"""A draft PDF is the application document: what the applicant confirmed, never Batatis's own to-do list.

Regression for the user's report of generated text on appended pages. Open items, their fix hints and
placeholders for unanswered passages belong to the questions and Review: the result keeps the open items,
the official export stays blocked, and confirmed answers still reach the PDF and read back.
"""
import pytest
from pypdf import PdfReader
import io

from engine.codes import Codes
from engine.export import ExportBlocked, export_case, form_path
from engine.export.g3 import appendix_text, norm, page_texts
from engine.models import Case, Fact, Source
from engine.review.package import review_uploads
from engine.review.pdf_reader import read_pdf
from engine.section_c import section_c_rows

pytestmark = pytest.mark.skipif(not form_path().exists(), reason='SCC form not present (git-excluded)')

OWNER, ADDRESS = 'SYNTHETIC Owner Name', '000 Example Meadows Boulevard SE (EXAMPLE DATA)'
DESCRIPTION = 'SYNTHETIC: replace the bedroom egress window with a smaller casement. EXAMPLE DATA only.'
RATIONALE = 'SYNTHETIC applicant rationale for the smaller window. EXAMPLE DATA only.'
GENERATED = ('Open items', 'Fix:', 'Not provided or not confirmed', 'No answer has been supplied',
             'No provisions identified', 'No supporting documents listed', 'not provided or not confirmed')


@pytest.fixture(scope='module')
def codes():
    return Codes()


def fact(field, value, status='confirmed'):
    return Fact(field=field, value=value, kind='pointed', status=status,
                source=Source(type='user_text', ref='synthetic-sparse-draft', quote=str(value)))


def sparse(codes, provisions=(), **answers):
    facts = [fact('owner_name', OWNER), fact('municipal_address', ADDRESS),
             fact('mailing_address', 'SYNTHETIC unconfirmed mailing address', 'unconfirmed')]
    facts += [fact(key, value) for key, value in answers.items()]
    return Case(title='SYNTHETIC sparse draft', facts=facts, provisions=list(provisions),
                section_c=section_c_rows(list(provisions), codes))


def blocked_reasons(case, codes) -> str:
    with pytest.raises(ExportBlocked) as blocked:
        export_case(case, codes=codes)
    return ' '.join(blocked.value.reasons)


def test_a_draft_with_only_form_answers_adds_no_pages_yet_stays_blocked_and_reads_back(codes):
    case = sparse(codes)
    reasons = blocked_reasons(case, codes)
    for required in ('risk_assessment', 'mitigating_measures', 'assumptions'):     # alternative-path process items
        assert required in reasons
    result = export_case(case, codes=codes, draft=True)
    assert result.form_pages == 7 and result.appendix_pages == 0 and result.appendix_text == []
    assert len(PdfReader(io.BytesIO(result.pdf)).pages) == 7
    assert result.open_items and any('risk_assessment' in item for item in result.open_items)
    read = read_pdf(result.pdf, 'draft.pdf')
    assert (read.fields['Owner'].status, read.fields['Owner'].value) == ('present', OWNER)
    assert (read.fields['Municipal Address'].status, read.fields['Municipal Address'].value) == ('present', ADDRESS)
    assert read.fields['Mailing Address'].status == 'blank'            # an unconfirmed value is never printed


def test_a_sparse_draft_appendix_carries_only_what_was_confirmed(codes):
    case = sparse(codes, ['9.9.10.1.(1)'], alternative_description=DESCRIPTION, rationale=RATIONALE)
    case.facts.append(fact('risk_assessment', 'SYNTHETIC UNCONFIRMED RISK', 'unconfirmed'))
    assert 'risk_assessment' in blocked_reasons(case, codes)
    result = export_case(case, codes=codes, draft=True)
    text = appendix_text(result)
    assert result.appendix_pages >= 1
    for generated in GENERATED:
        assert generated not in text, generated
    assert 'SYNTHETIC UNCONFIRMED RISK' not in norm(' '.join(page_texts(result.pdf)))
    # The confirmed description, the one answered passage with its provenance, and Section C.
    assert f'Proposed alternative: {DESCRIPTION}' in text
    assert f'P-1 Rationale {RATIONALE} Applicant source: synthetic-sparse-draft' in text and 'Provenance:' in text
    assert 'P-2' not in text and 'D. Supporting documentation' not in text
    assert 'C-1 9.9.10.1.(1)' in text
    reading = next(f for f in review_uploads([('draft.pdf', result.pdf)], codes).fields if f.field == 'rationale')
    assert (reading.status, reading.value) == ('present', RATIONALE)
