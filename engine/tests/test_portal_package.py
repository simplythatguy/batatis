"""Portal package without a code database and without the SCC form PDF."""
from engine.export.portal import PortalAttachment, portal_package
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
