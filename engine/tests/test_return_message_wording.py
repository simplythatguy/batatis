"""The officer's return message asks the applicant plainly (app audit 2026-10-29, row 5).

Every drafted open question read "Please provide or confirm the Open question from the drafted wording
(page 13 of application.pdf). Why does …?": an internal label, and a page of a package file the
applicant never saw. The lapsed-maintenance topic was asked twice, once as the drafted question and
once as the "demonstrate" prompt.
"""
from engine.models_review import Finding, Pointer
from engine.review import information_request as ir
from engine.review import workspace
from engine.tests.test_officer_workspace import session

PACKAGE = Pointer(file='application.pdf', page=17)


def drafted(index, question, section='D'):
    return Finding(key=f'draft-question:draft_1:{index}', section=section, field=f'drafting.questions.draft_1.{index}',
                   label='Open question from the drafted wording', status='missing', problem='policy_gap',
                   message=question, pointers=[PACKAGE])


LAPSES = Finding(key='demonstrate.lapsed_maintenance:not_mentioned', section='process',
                 field='demonstrate.lapsed_maintenance', label='what happens if maintenance lapses', status='unclear',
                 problem='not_mentioned', severity='warning', pointers=[PACKAGE],
                 message='The documentation does not mention what is assumed if maintenance or inspection lapses. '
                         'Ask the applicant to state it; the review does not judge adequacy.')
INSPECTION = 'Who will inspect and test door closers and smoke alarms, and how often? What happens if maintenance lapses?'


def test_a_drafted_open_question_is_sent_as_the_question_with_its_section():
    request = ir.build([drafted(0, 'Why does this project need the departure from firewalls?', 'B'),
                        drafted(1, INSPECTION, 'process')])
    assert [item.text for item in request.items] == [
        'Why does this project need the departure from firewalls? (Section B)', f'{INSPECTION} (Section D)']
    assert 'drafted wording' not in request.text and 'Please provide or confirm' not in request.text


def test_the_message_names_no_package_file_or_page():
    signature = Finding(key='signature:presence', section='A', field='signature', label='applicant signature',
                        status='missing', problem='signature_unread', message='Check the signature boxes.',
                        pointers=[Pointer(file='application.pdf', page=2, form_field='Signature1')])
    request = ir.build([signature, drafted(0, INSPECTION), LAPSES])
    assert request.items[0].text == 'Please confirm that the application is signed and dated (Section A).'
    assert 'application.pdf' not in request.text and 'page ' not in request.text


def test_a_topic_the_drafted_question_already_asks_is_sent_once():
    findings = [drafted(0, INSPECTION), LAPSES, drafted(1, INSPECTION.upper())]
    request = ir.build(findings)
    assert ir.covered(findings) == {LAPSES.key, 'draft-question:draft_1:1'}
    assert ir.render(request).count('maintenance lapses') == 1
    # The officer still sees the repeat to check, and can ask it on purpose.
    states = {s.key: s.state for s in workspace.build(session(findings)).states}
    assert states == {'draft-question:draft_1:0': 'ask', LAPSES.key: 'verify', 'draft-question:draft_1:1': 'verify'}
    synced = workspace.sync_request(session(findings))
    assert [item.finding_key for item in synced.information_request.items if item.included] == ['draft-question:draft_1:0']


def test_a_required_finding_is_never_folded_into_a_question():
    required = LAPSES.model_copy(update={'severity': 'blocking'})
    assert ir.covered([drafted(0, INSPECTION), required]) == set()
    # Without a drafted question asking it, the topic prompt is sent as before.
    assert ir.covered([LAPSES]) == set()
    assert ir.build([LAPSES]).items[0].text.startswith(
        'Please state in the documentation what happens if maintenance lapses (Section D), or say')


def test_a_drafted_question_with_verdict_words_falls_back_to_its_section_not_a_claim():
    item = ir.build([drafted(0, 'Which approved assembly is used?')]).items[0]
    assert item.text == 'Please provide or confirm the open question from the drafted wording (Section D).'
