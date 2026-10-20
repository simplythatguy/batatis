"""Portal package without a code database and without the SCC form PDF."""
import json

from engine.export.portal import (
    PortalAttachment, check_attachment, code_items_for, derive_ahj, portal_package, suggest_filename,
    write_portal_package,
)
from engine.models import Case, Fact, Jurisdiction, Source

DOC = ('The Division C Section 2.3.1 documentation for this alternative solution is included '
       'with this application.')


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


def test_sco_fields_stay_blank_and_permit_is_optional():
    case = _case(
        civic_address='100 Example Avenue, Edmonton T5J 0N3',
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
    blank_sco = [item for item in package.manifest if item.role == 'filled by the registering SCO']
    assert [item.name for item in blank_sco] == [
        'Issuing SCO', 'Designation of Power', 'Employer', 'Discipline', 'Variance status', 'Issue Date']
    assert all(item.value == '' and item.included is False for item in blank_sco)
    assert 'Synthetic Officer' not in package.text()
    assert 'Synthetic AHJ' not in package.text()
    assert 'Synthetic Employer' not in package.text()
    assert _entry(package, 'AHJ').value == 'City of Edmonton'
    assert _entry(package, 'AHJ').role == 'derived, free text'
    permit = _entry(package, 'Permit #')
    assert permit.role == 'optional' and permit.value == 'BP-1'
    blank = portal_package(_case(civic_address='100 Example Avenue, Edmonton T5J 0N3'))
    assert _entry(blank, 'Permit #').value == ''
    assert blank.not_ovp_fields == ('owner', 'signature', 'objectives')
    assert not any(item.name.casefold() in {'owner', 'signature', 'objectives'} for item in package.manifest)
    assert 'not OVP fields' in package.text()
    assert 'unofficial' in package.text().casefold()
    assert 'may change' in package.text().casefold()


def test_location_accepts_civic_or_legal_or_ats_without_municipal_address():
    civic = portal_package(_case(municipal_address='Suite 4, 100 Example Avenue, Edmonton, Alberta T5J 0N3'))
    assert civic.location.label == 'Civic Address' and civic.location.parsed is True
    assert civic.location.suite == '4' and civic.location.house == '100'
    assert civic.location.civic_street == 'Example Avenue'
    assert civic.location.municipality == 'Edmonton' and civic.location.postal_code == 'T5J 0N3'
    alias = portal_package(_case(civic_address='100 Example Avenue, Edmonton T5J0N3'))
    assert alias.location.ready is True and alias.location.postal_code == 'T5J 0N3'
    kept = portal_package(_case(municipal_address='somewhere near the river'))
    assert kept.location.parsed is False and kept.location.ready is False
    assert kept.location.unparsed == 'somewhere near the river'
    assert kept.location.flag == 'civic address could not be parsed'
    legal = portal_package(_case(lot='14', block='7', plan='2610001'))
    assert legal.location.ready is True
    assert legal.location.civic_street == '' and legal.location.postal_code == ''
    assert (legal.location.lot, legal.location.block, legal.location.plan) == ('14', '7', '2610001')
    ats = portal_package(_case(ats_qtr='NW', ats_sec='12', ats_twp='52', ats_rge='25', ats_mer='W4'))
    assert ats.location.ready is True and ats.location.label == 'Civic Address'
    out_of_range = portal_package(_case(ats_qtr='NW', ats_sec='40', ats_twp='52', ats_rge='25', ats_mer='W4'))
    assert out_of_range.location.ready is False
    missing = portal_package(_case(civic_address='100 Example Avenue, Edmonton'))
    assert missing.location.ready is False
    assert missing.location.unparsed == '100 Example Avenue, Edmonton'


def test_code_items_flag_article_only_ids_and_do_not_invent_a_sentence():
    case = _case(code_or_standard='NBC(AE) 2023')
    case.provisions = ['3.5.2.1.(2)', '3.5.2.1.']
    package = portal_package(case, sentence_lookup=lambda _article: None)
    by_ref = {item.reference: item for item in package.code_items}
    assert by_ref['3.5.2.1.(2)'].sentence_level is True
    assert by_ref['3.5.2.1.(2)'].flag is None
    assert by_ref['3.5.2.1.(2)'].code_set == 'NBC(AE) 2023'
    assert by_ref['3.5.2.1.'].flag == 'needs sentence-level reference'
    assert by_ref['3.5.2.1.'].reference == '3.5.2.1.'
    assert all(item.reference != '3.5.2.1.(1)' for item in code_items_for(case, sentence_lookup=lambda _article: None))


def _sentence(case, quote):
    case.facts.append(Fact(field='applicant_note', value=quote, kind='pointed', status='confirmed',
                           source=Source(type='user_text', ref='quote', quote=quote)))


def test_sentence_mapping_uses_codedb_only_when_the_case_identifies_one():
    children = ['3.5.2.1.(1)', '3.5.2.1.(2)', '3.5.2.1.(3)']

    one = _case()
    one.provisions = ['3.5.2.1.']
    _sentence(one, 'The alternative addresses sentence 3.5.2.1.(2).')
    mapped = code_items_for(one, sentence_lookup=lambda _article: children)[0]
    assert mapped.reference == '3.5.2.1.(2)' and mapped.flag is None and mapped.candidates == []

    several = _case()
    several.provisions = ['3.5.2.1.']
    _sentence(several, 'Sentences 3.5.2.1.(1) and 3.5.2.1.(3) were discussed.')
    pending = code_items_for(several, sentence_lookup=lambda _article: children)[0]
    assert pending.reference == '3.5.2.1.'
    assert pending.flag == 'needs sentence-level reference'
    assert pending.candidates == ['3.5.2.1.(1)', '3.5.2.1.(3)']

    unnamed = _case()
    unnamed.provisions = ['3.5.2.1.']
    listed = code_items_for(unnamed, sentence_lookup=lambda _article: ['3.5.2.1.(1)'])[0]
    assert listed.reference == '3.5.2.1.'
    assert listed.flag == 'needs sentence-level reference'
    assert listed.candidates == ['3.5.2.1.(1)']


def test_attachments_require_both_types_and_check_format_size_and_name():
    good = check_attachment('notes.pdf', 'Supporting Document', 25 * 1024 * 1024)
    assert good.format_ok and good.size_ok and good.name_ok and good.suggested_name == 'notes.pdf'
    assert check_attachment('photo.jpg', 'Supporting Document', 10).format_ok
    assert check_attachment('sheet.csv', 'Variance Form', 10).format_ok
    assert check_attachment('scan.tif', 'Supporting Document', 10).format_ok
    rejected = check_attachment('notes.docx', 'Supporting Document', 10)
    assert rejected.format_ok is False
    assert check_attachment('big.pdf', 'Supporting Document', 25 * 1024 * 1024 + 1).size_ok is False
    messy = check_attachment('report:final?.pdf', 'Supporting Document', 10)
    assert messy.name_ok is False
    assert messy.suggested_name == 'report-final.pdf'
    assert ':' not in messy.suggested_name and '?' not in messy.suggested_name
    long_name = 'a' * 97 + '.pdf'
    assert len(long_name) == 101
    assert suggest_filename(long_name) == 'a' * 96 + '.pdf'
    assert len(suggest_filename(long_name)) == 100

    both = portal_package(
        _case(**{'division_c_2_3_1': DOC, 'civic_address': '100 Example Avenue, Edmonton T5J 0N3'}),
        attachments=[
            PortalAttachment('Variance-form.pdf', 'form', size_bytes=100, document_type='Variance Form'),
            PortalAttachment('product-sheet.pdf', 'sheet', size_bytes=100, document_type='Supporting Document'),
        ])
    assert {item.document_type for item in both.attachment_checks if item.present} == {
        'Variance Form', 'Supporting Document'}
    assert both.documents_ready is True
    support_only = portal_package(
        _case(civic_address='100 Example Avenue, Edmonton T5J 0N3'),
        attachments=[PortalAttachment('product-sheet.pdf', 'sheet', size_bytes=100)])
    assert support_only.documents_ready is False
    assert any('Variance Form' in problem for item in support_only.attachment_checks for problem in item.problems)


def test_discipline_and_ahj_are_derived_only_when_unambiguous():
    building = portal_package(_case(code_or_standard='National Building Code - 2023 Alberta Edition (2nd printing)'))
    assert _entry(building, 'Discipline').value == 'Building'
    assert _entry(building, 'AHJ').value == 'City of Edmonton'
    assert 'TODO' in building.sidecar['discipline']['todo']
    assert building.sidecar['discipline']['free_text'] is True
    assert building.sidecar['employer']['value'] is None
    assert building.sidecar['variance_status']['value'] is None
    assert building.sidecar['issuing_sco'] is None
    assert building.sidecar['issue_date'] is None

    fire = portal_package(_case(code_or_standard='National Fire Code - 2023 Alberta Edition'))
    assert _entry(fire, 'Discipline').value == ''
    assert _entry(portal_package(_case()), 'Discipline').value == ''

    ambiguous = _case(code_or_standard='National Building Code - 2023 Alberta Edition')
    ambiguous.jurisdiction = Jurisdiction(id='edmonton', name='Edmonton', authority='City of Edmonton')
    assert derive_ahj(ambiguous) == ''
    assert _entry(portal_package(ambiguous), 'AHJ').value == ''
    assert _entry(portal_package(ambiguous), 'Discipline').value == 'Building'


def test_sidecar_names_attachments_and_flags_a_name_only_supporting_file(tmp_path):
    case = _case(permit_number='BP-1', municipal_address='100 Example Avenue, Edmonton T5J 0N3',
                 owner_name='Synthetic Owner')
    case.facts.append(Fact(field='file.file_abc.name', value='report.pdf', kind='exact', status='confirmed',
                           source=Source(type='file', ref='file_abc', quote='report.pdf')))
    package = portal_package(case)
    assert package.portal_gaps == ['supporting document file missing']
    assert any('supporting document file missing' in reason for reason in package.preflight_reasons)
    assert package.sidecar['permit_number'] == 'BP-1'
    assert package.sidecar['not_ovp_fields'] == ['owner', 'signature', 'objectives']
    assert 'owner' not in package.sidecar
    assert package.sidecar['unofficial'] is True and package.sidecar['retrieved'] == '2026-10-20'
    assert 'TODO' in package.sidecar['ahj']['todo']
    assert package.sidecar['code_items'] == []
    missing = next(item for item in package.named_attachments if item.filename == 'report.pdf')
    assert missing.present is False and missing.data is None

    covered = portal_package(case, attachments=[
        PortalAttachment('report.pdf', 'sheet', size_bytes=5, data=b'sheet', document_type='Supporting Document')])
    assert covered.portal_gaps == []
    path = write_portal_package(covered, tmp_path)
    assert json.loads(path.read_text())['permit_number'] == 'BP-1'
    assert (tmp_path / 'report.pdf').read_bytes() == b'sheet'
