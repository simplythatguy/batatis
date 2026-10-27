"""A document's words are not necessarily answers about the applicant's project."""
import pytest

from engine.intake import service
from engine.intake import model as model_pass
from engine.models import Case, Fact, Source
from engine.models_intake import FactPointer, IntakeRecord
from engine.tests.test_intake_pdf import pdf


def test_reference_policy_does_not_supply_project_answers_or_conflicts():
    data = pdf([[(72, 740, 'Policy B23-01: Alternative Solution Submission Guide'),
                 (72, 720, '10111 104 Avenue NW'),
                 (72, 700, 'I am the owner.'),
                 (72, 680, 'Examples include a two-storey house and a three-storey office.')]])
    text = 'We are proposing a garden suite.'
    case = Case()
    out = service.run(text, [('guide', 'policy.pdf', data)])
    service.apply(case, text, out)
    assert not [f for f in case.facts if f.source.ref == 'guide'
                and not f.field.startswith(('statement.', 'claimed_provision'))]
    assert not case.intake.conflicts
    assert case.intake.files[0].status == 'read'


@pytest.mark.parametrize('heading', ['Request for Specific Variance', 'Archived guidance', 'Sample application'])
def test_templates_and_historical_records_cannot_answer_project_fields(heading):
    data = pdf([[(72, 740, heading), (72, 720, 'Permit number: Date'),
                 (72, 700, 'I am the owner.'), (72, 680, 'Where no other on-site parking is provided, a')]],
               fields=[] if heading == 'Request for Specific Variance' else
               [('Owner Name', 'Example Owner', (100, 600, 300, 20))])
    case = Case()
    service.apply(case, None, service.run(None, [('ref', 'record.pdf', data)],
                                        transport=model_pass.fake_transport, status='fake'))
    assert case.facts == []
    assert not case.intake.conflicts


def test_completed_request_form_keeps_actual_values_but_not_printed_declarations():
    data = pdf([[(72, 740, 'Request for Specific Variance'), (72, 720, 'I am the owner.'),
                 (72, 700, 'Permit number: Date')]],
               fields=[('Owner Name', 'Actual Owner', (100, 600, 300, 20))])
    case = Case()
    service.apply(case, None, service.run(None, [('form', 'form.pdf', data)]))
    assert [(f.field, f.value, f.status) for f in case.facts] == [('owner_name', 'Actual Owner', 'confirmed')]


@pytest.mark.parametrize('reference', [
    ['According to the guide:', 'A four-storey office building requires sprinklers.'],
    ['Example application', 'Project brief', 'A four-storey office building.'],
    ['Consultant office: 10111 104 Avenue NW'],
])
def test_reference_continuations_and_issuer_words_do_not_override_current_project(reference):
    lines = ['Project brief', 'Our new building is a two-storey house.', *reference]
    data = pdf([[(72, 760 - i * 20, line) for i, line in enumerate(lines)]])
    case = Case()
    service.apply(case, None, service.run(None, [('brief', 'brief.pdf', data)]))
    assert [(f.field, f.value) for f in case.facts if f.field in {'occupancy', 'storeys'}] == [
        ('storeys', 2), ('occupancy', 'single_family')]
    assert not case.intake.conflicts


@pytest.mark.parametrize('same_page', [True, False])
def test_populated_example_widgets_are_excluded_after_project_passages(same_page):
    import io
    from reportlab.pdfgen import canvas
    buf = io.BytesIO()
    c = canvas.Canvas(buf)
    c.drawString(72, 760, 'Project brief')
    c.drawString(72, 740, 'Our new building is a two-storey house.')
    if not same_page:
        c.showPage()
    c.drawString(72, 700, 'Sample application (for reference only)')
    c.acroForm.textfield(name='Owner Name', value='Historic Example Owner', x=100, y=600, width=300, height=20)
    c.showPage()
    c.save()
    case = Case()
    service.apply(case, None, service.run(None, [('mixed', 'mixed.pdf', buf.getvalue())]))
    assert not [f for f in case.facts if f.field == 'owner_name']
    assert next(f for f in case.facts if f.field == 'storeys').value == 2


def test_project_brief_keeps_project_answers_and_excludes_same_page_reference_sections():
    data = pdf([[(72, 760, 'Consultant office: 10111 104 Avenue NW'),
                 (72, 740, 'Date: 2024-01-01'), (72, 720, 'Project brief'),
                 (72, 700, 'Site address: 42 Example Street'),
                 (72, 680, 'Our new building is a two-storey house.'),
                 (72, 660, 'Appendix: reference guidance'),
                 (72, 640, 'Owner: Other Owner'),
                 (72, 620, 'A three-storey office building. I am the owner.')]])
    case = Case()
    service.apply(case, None, service.run(None, [('brief', 'brief.pdf', data)]))
    values = {f.field: f.value for f in case.facts}
    assert values['municipal_address'] == '42 Example Street'
    assert values['storeys'] == 2
    assert values['occupancy'] == 'single_family'
    assert not {'owner_name', 'applicant_role', 'request_date'} & values.keys()
    assert not case.intake.conflicts
    assert all(f.status == 'confirmed' for f in case.facts)
    address = next(f for f in case.facts if f.field == 'municipal_address')
    assert address.source.page == 1 and address.source.bbox
    assert address.source.quote == '42 Example Street'


def test_unclassified_file_does_not_silently_answer_missing_project_questions():
    data = pdf([[(72, 740, 'A four-storey office building at 10111 104 Avenue NW.')]])
    case = Case()
    service.apply(case, None, service.run(None, [('unknown', 'project.pdf', data)]))
    # The filename is not evidence of project ownership: an unmarked file may only propose values,
    # which the applicant confirms on "Here's what I understood"; nothing it says is an answer yet.
    assert case.facts and all(f.status == 'unconfirmed' for f in case.facts)
    assert case.intake.files[0].status == 'read'


def test_unlabelled_conflicting_addresses_are_not_project_conflicts():
    data = pdf([[(72, 740, 'Project brief'),
                 (72, 720, '10111 104 Avenue NW; 42 Example Street')]])
    case = Case()
    service.apply(case, None, service.run(None, [('brief', 'brief.pdf', data)]))
    assert not [f for f in case.facts if f.field == 'municipal_address']
    assert not case.intake.conflicts


@pytest.mark.parametrize('line,field,value', [
    ('Street address: 42 Example Street', 'municipal_address', '42 Example Street'),
    ('Registered owner: Actual Owner', 'owner_name', 'Actual Owner'),
    ('- Site address: 42 Example Street', 'municipal_address', '42 Example Street'),
    ('| Site address | 42 Example Street |', 'municipal_address', '42 Example Street'),
])
def test_supported_project_labels_survive_context_selection(line, field, value):
    data = pdf([[(72, 740, 'Project brief'), (72, 720, line)]])
    case = Case()
    service.apply(case, None, service.run(None, [('brief', 'brief.pdf', data)]))
    assert [(f.value, f.status) for f in case.facts if f.field == field] == [(value, 'confirmed')]


def test_reference_material_does_not_hide_applicant_answers_or_leak_to_model():
    seen = []
    def transport(system, user, schema):
        seen.append(user)
        return {'facts': []}, {}
    data = pdf([[(72, 740, 'Sample application'), (72, 720, 'Owner: Jane Reference'),
                 (72, 700, 'Municipal address: 10111 104 Avenue NW')]])
    text = 'Jane Reference wants to build a two-storey house.'
    case = Case()
    service.apply(case, text, service.run(text, [('ref', 'sample.pdf', data)],
                                         transport=transport, status='fake'))
    assert seen and all('Jane Reference' not in s and '10111 104 Avenue' not in s for s in seen)
    assert next(f for f in case.facts if f.field == 'storeys').value == 2
    assert not [f for f in case.facts if f.source.type == 'file']


def test_excluded_widget_values_are_still_scrubbed_from_other_sources():
    seen = []
    def transport(system, user, schema):
        seen.append(user)
        return {'facts': []}, {}
    data = pdf([[(72, 740, 'Sample application')]],
               fields=[('Owner Name', 'Jane Reference', (100, 600, 300, 20))])
    service.run('Jane Reference wants a new office.', [('ref', 'sample.pdf', data)],
                transport=transport, status='fake')
    assert seen and all('Jane Reference' not in s for s in seen)


def test_rerun_replaces_prior_machine_readings_but_preserves_explicit_answers():
    old = Fact(field='municipal_address', value='10111 104 Avenue NW', kind='pointed', status='confirmed',
               source=Source(type='file', ref='ref', quote='10111 104 Avenue NW'))
    own = Fact(field='owner_name', value='Actual Owner', kind='pointed', status='confirmed',
               source=Source(type='user_click', ref='Confirmed by applicant', quote='Actual Owner'))
    case = Case(facts=[old, own], intake=IntakeRecord(pointers=[
        FactPointer(fact_id=old.id, field=old.field, method='rules', source_ref='ref')]))
    data = pdf([[(72, 740, 'Policy B23-01'), (72, 720, '10111 104 Avenue NW')]])
    service.apply(case, 'We are proposing a house.', service.run('We are proposing a house.', []))
    service.apply(case, None, service.run(None, [('ref', 'policy.pdf', data)]))
    assert own in case.facts
    assert not [f for f in case.facts if f.field == 'municipal_address']
