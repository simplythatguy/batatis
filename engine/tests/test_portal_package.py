"""Portal package without a code database and without the SCC form PDF."""
import pytest

from engine.export.portal import (
    SCO_FIELDS, PortalAttachment, check_attachment, code_items_for, portal_package, suggest_filename,
)
from engine.models import Case, Fact, Jurisdiction, Source

DOC = ('The Division C Section 2.3.1 documentation for this alternative solution is included '
       'with this application.')


@pytest.fixture(autouse=True)
def unavailable_code_database(tmp_path, monkeypatch):
    """Keep this module's documented no-corpus condition on developer machines too."""
    monkeypatch.setenv('BATATIS_CODEDB', str(tmp_path / 'absent-corpus.sqlite'))


def _case(**facts):
    case = Case(title='Synthetic portal fixture',
                jurisdiction=Jurisdiction(id='edmonton', name='City of Edmonton', authority='City of Edmonton'))
    for key, value in facts.items():
        case.facts.append(Fact(field=key, value=value, kind='pointed', status='confirmed',
                               source=Source(type='user_text', ref='synthetic-portal', quote=str(value))))
    return case


def test_preflight_reuses_the_documentation_gate_and_does_not_include_the_form():
    package = portal_package(_case(civic_address='100 Example Avenue, Edmonton, Alberta'))
    assert package.form_pdf is None and package.form_included is False
    assert any('division_c_2_3_1' in reason and 'IB-2025-11-18' in reason for reason in package.preflight_reasons)
    assert package.reminder_verdict == 'reminder'
    assert 'within 10 days' in package.reminder
    assert 'copy of each variance' in package.reminder.casefold()
    assert all('within 10 days' not in reason for reason in package.preflight_reasons)
    text = package.text().casefold()
    assert 'complies' not in text
    assert 'prepared for the safety codes officer to register' in text
    assert 'not council approval' in text
    assert 'applicant registers' not in text
    assert 'applicant to register' not in text
    form = package.manifest[0]
    assert form.role == 'form' and form.needs_personal_information and not form.included


def test_redaction_flags_personal_information_only_in_supporting_attachments():
    flagged = portal_package(
        _case(**{'division_c_2_3_1': DOC, 'civic_address': '100 Example Avenue, Edmonton, Alberta'}),
        attachments=[PortalAttachment('notes.txt', 'Reach the owner at owner@example.test or 780-555-0100.')])
    kinds = sorted(flag.kind for flag in flagged.redaction_flags)
    assert kinds == ['email', 'phone']
    assert all(flag.bulletin_id == 'IB-2026-10-01' for flag in flagged.redaction_flags)
    assert all(not flag.message.casefold().startswith('safe') for flag in flagged.redaction_flags)
    assert 'does not edit the file' in flagged.redaction_flags[0].message
    supporting = next(item for item in flagged.manifest if item.role == 'supporting')
    assert supporting.needs_personal_information is False

    clean = portal_package(
        _case(**{'division_c_2_3_1': DOC, 'civic_address': '100 Example Avenue, Edmonton, Alberta'}),
        attachments=[PortalAttachment('product-sheet.txt', 'Synthetic product sheet for the soffit assembly.')])
    assert clean.redaction_flags == []
    assert clean.preflight_reasons == []
    assert clean.form_pdf is None  # no code database and no form file on this machine

    on_form = portal_package(
        _case(**{'division_c_2_3_1': DOC, 'civic_address': '100 Example Avenue, Edmonton, Alberta'}),
        attachments=[PortalAttachment('identity.txt', 'owner@example.test', needs_personal_information=True)])
    assert on_form.redaction_flags == []


def _entry(package, name):
    return next(item for item in package.manifest if item.name == name)


def test_sco_fields_are_blank_for_the_registering_officer():
    case = _case(
        civic_address='100 Example Avenue, Edmonton',
        issuing_sco='Synthetic Officer',
        designation_of_power='DOP-1',
        employer='Synthetic Employer',
        discipline='Building',
        ahj='Synthetic AHJ',
        variance_status='Issued',
        issue_date='2026-10-20',
        permit_number='BP-1',
        owner_name='Synthetic Owner',
    )
    package = portal_package(case)
    sco = [item for item in package.manifest if item.role == 'filled by the registering SCO']
    assert [item.name for item in sco] == list(SCO_FIELDS)
    assert all(item.value == '' and item.included is False for item in sco)
    assert case.jurisdiction.name not in ''.join(item.value for item in sco)
    assert 'Synthetic Officer' not in package.text()
    assert 'Synthetic AHJ' not in package.text()
    permit = _entry(package, 'Permit #')
    assert permit.role == 'optional' and permit.value == 'BP-1'
    assert _entry(portal_package(_case()), 'Permit #').value == ''
    assert package.not_ovp_fields == ('owner', 'signature', 'objectives')
    assert not any(item.name.casefold() in {'owner', 'signature', 'objectives'} for item in package.manifest)
    assert 'not OVP fields' in package.text()


def test_location_accepts_civic_or_legal_or_ats_without_municipal_address():
    civic = portal_package(_case(civic_address='100 Example Avenue, Edmonton'))
    assert civic.location.ready is True
    assert civic.location.civic_address == '100 Example Avenue, Edmonton'
    legal = portal_package(_case(lot='14', block='7', plan='2610001'))
    assert legal.location.ready is True
    assert legal.location.civic_address == ''
    assert (legal.location.lot, legal.location.block, legal.location.plan) == ('14', '7', '2610001')
    assert 'not required' in legal.location.note
    ats = portal_package(_case(ats_qtr='NW', ats_sec='12', ats_twp='52', ats_rge='25', ats_mer='W4'))
    assert ats.location.ready is True and ats.location.civic_address == ''
    missing = portal_package(_case())
    assert missing.location.ready is False


def test_code_items_flag_article_only_ids_and_do_not_pick_a_sentence():
    case = _case(code_or_standard='NBC(AE) 2023')
    case.provisions = ['3.5.2.1.(2)', '3.5.2.1.']
    case.facts.append(Fact(
        field='applicant_note', value='Sentence 3.5.2.1.(1) was discussed.', kind='pointed', status='confirmed',
        source=Source(type='user_text', ref='quote', quote='Sentence 3.5.2.1.(1) was discussed.')))
    by_ref = {item.reference: item for item in code_items_for(case)}
    assert by_ref['3.5.2.1.(2)'].sentence_level is True and by_ref['3.5.2.1.(2)'].flag is None
    assert by_ref['3.5.2.1.(2)'].code_set == 'NBC(AE) 2023'
    assert by_ref['3.5.2.1.'].flag == 'needs sentence-level reference'
    assert by_ref['3.5.2.1.'].reference == '3.5.2.1.'
    assert '3.5.2.1.(1)' not in by_ref


def test_attachments_require_both_types_and_check_format_size_and_name():
    good = check_attachment('notes.pdf', 'Supporting Document', 25 * 1024 * 1024)
    assert good.format_ok and good.size_ok and good.name_ok and good.suggested_name == 'notes.pdf'
    assert check_attachment('photo.jpg', 'Supporting Document', 10).format_ok
    assert check_attachment('sheet.csv', 'Variance Form', 10).format_ok
    assert check_attachment('scan.tif', 'Supporting Document', 10).format_ok
    assert check_attachment('notes.txt', 'Supporting Document', 10).format_ok
    assert check_attachment('scan.png', 'Supporting Document', 10).format_ok
    assert check_attachment('notes.docx', 'Supporting Document', 10).format_ok is False
    assert check_attachment('big.pdf', 'Supporting Document', 25 * 1024 * 1024 + 1).size_ok is False
    messy = check_attachment('report:final?.pdf', 'Supporting Document', 10)
    assert messy.name_ok is False and messy.suggested_name == 'report-final.pdf'
    long_name = 'a' * 97 + '.pdf'
    assert len(suggest_filename(long_name)) == 100

    both = portal_package(
        _case(**{'division_c_2_3_1': DOC, 'lot': '1', 'block': '2', 'plan': '3'}),
        attachments=[
            PortalAttachment('Variance-form.pdf', 'form', size_bytes=100, document_type='Variance Form'),
            PortalAttachment('product-sheet.pdf', 'sheet', size_bytes=100, document_type='Supporting Document'),
        ])
    assert {item.document_type for item in both.attachment_checks if item.present} == {
        'Variance Form', 'Supporting Document'}
    assert both.documents_ready is True
    support_only = portal_package(
        _case(lot='1', block='2', plan='3'),
        attachments=[PortalAttachment('product-sheet.pdf', 'sheet', size_bytes=100)])
    assert support_only.documents_ready is False
    assert any('Variance Form' in problem for item in support_only.attachment_checks for problem in item.problems)
