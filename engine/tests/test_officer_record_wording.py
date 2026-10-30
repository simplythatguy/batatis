"""What the officer sends and keeps reads like the rest of the app (QA 2026-10-28).

The return letter named the raw form field ("field "Signature1"") and said "confirm the a named registered
professional"; "Applicant signature" stayed on the officer's list after both people signed in the app; the
close-out record showed internal ids, "1 request(s)" and the UTC date of an evening decision.
"""
from engine.codes import Codes
from engine.export.sample import sample_case
from engine.models import Case, Decision
from engine.models_review import Attribute, DocumentRow, Finding, Pointer
from engine.review import close_out
from engine.review import information_request as ir
from engine.review.package import review_case
from engine.review.sessions import CloseoutRecord
from engine.tests.test_officer_workspace import session
from engine.tests.test_workspace_export import signed
from engine.workspace import signers


def test_the_return_letter_names_no_form_widget_and_no_doubled_article():
    signature = Finding(key='signature:presence', section='A', field='signature', label='applicant signature',
                        status='not_found', problem='signature_unread', message='Check the signature boxes.',
                        routed_to='applicant', pointers=[Pointer(file='application.pdf', page=2, form_field='Signature1')])
    named = Finding(key='D12:responsible_professional', section='D', field='responsible_professional',
                    label='a named registered professional required for this work', status='missing',
                    problem='saved_constraint', message='The applicant has not named one.', routed_to='applicant')
    texts = [item.text for item in ir.build([signature, named]).items]
    # The applicant answers by section; the package file and its pages are the officer's view (audit row 5).
    assert texts[0] == 'Please confirm that the application is signed and dated (Section A).'
    assert texts[1].startswith('Please provide or confirm a named registered professional required for this work (Section D).')
    assert not any('Signature1' in text or 'the a ' in text for text in texts)


def test_the_officer_reads_signatures_made_in_the_app_as_signed():
    codes = Codes()
    case = sample_case(codes)
    for signer in signers(case):
        signed(case, signer.role)
    parts = review_case(case, codes)
    assert 'signature:presence' not in {finding.key for finding in parts.findings}
    readings = {reading.field: reading for reading in parts.fields}
    assert readings['Signature1'].status == 'present'
    assert readings['Signature1'].value == 'Signed in the application by Ada Synthetic Owner'


def test_the_close_out_record_uses_plain_words_and_the_alberta_date():
    case = Case(id='case_synthetic', facts=[], status='accepted')
    # 7:53 PM MDT on Oct 28 is 01:53 UTC on Oct 29.
    case.decision = Decision(outcome='accept', by_id='officer', by_name='Officer', message='', at='2026-10-29T01:53:12+00:00')
    review = session([], case_id=case.id, case_version=case.version, created_at='2026-10-29T01:52:51+00:00')
    review.information_request.message_id = 'message_1'
    documents = [DocumentRow(id='ev_1', title=Attribute(value='Assembly listing', known=True), file='file_86636e153554',
                             responsible=Attribute(), type=Attribute(), issuer=Attribute(), date=Attribute(),
                             evidence_rung=Attribute(), seal=Attribute(), listed_in_section_d=True)]
    record = CloseoutRecord(case.decision.at, '', '', '2026-10-28', 'Officer')
    built = close_out.build(case, [review], record, documents)
    details = {item.label: item.detail for item in built.record_package.send_to_council + built.record_package.retain_on_file}
    assert details['Copy of the variance as issued'] == 'Issued Oct 28, 2026.'
    assert details['Supporting documents'] == 'Assembly listing (attached)'
    assert details['Information requests and applicant revisions'].startswith('1 request sent;')
    assert details['Latest administrative package review'].startswith('Oct 28, 2026: No required items, ')
    text = ' '.join(details.values())
    assert 'case_' not in text and 'file_' not in text and '(s)' not in text
