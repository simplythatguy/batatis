"""A document's words are not necessarily answers about the applicant's project."""
from engine.intake import service
from engine.models import Case
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
