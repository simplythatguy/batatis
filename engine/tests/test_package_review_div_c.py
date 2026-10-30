"""Organizer additions: Div C 2.3.1.1 file items, "demonstrate, don't assert" prompts, peer-review signal."""
from __future__ import annotations

import copy

import pytest

from engine.codes import Codes
from engine.review import information_request as ir
from engine.review.div_c import PEER_REVIEW
from engine.review.package import review_uploads
from engine.tests.package_review_fixtures import CLEAN_FORM, CLEAN_NARRATIVE, CLEAN_REPORT, package


@pytest.fixture(scope='module')
def codes():
    return Codes()


def _without(*headings, **changes):
    narrative = {k: v for k, v in copy.deepcopy(CLEAN_NARRATIVE).items() if k not in headings}
    narrative.update(changes)
    return narrative


NO_SEAL = [line for line in CLEAN_REPORT if 'P.Eng' not in line]


@pytest.mark.parametrize('form,narrative,report,key,citation', [
    (dict(CLEAN_FORM, Objective='', Function=''), _without('Code analysis'), None,
     'div_c.code_analysis:presence', '2.3.1.1.(3)'),
    (None, _without('Testing procedures'), None, 'div_c.testing_procedures:presence', '2.3.1.1.(3)'),
    (None, _without('Qualifications'), NO_SEAL, 'div_c.qualifications:presence', '2.3.1.1.(4)'),
    (None, _without('Maintenance and commissioning'), None, 'div_c.maintenance:presence', '2.3.1.1.(2)(b)'),
    (dict(CLEAN_FORM, **{'Supporting Doc2': 'SYNTHETIC structural letter', 'Name Responsible2': 'SYNTHETIC Other Eng Ltd.'}),
     None, None, 'div_c.coordinator:presence', '2.3.1.1.(6)'),
], ids=['code-analysis', 'testing', 'qualifications', 'maintenance', 'coordinator'])
def test_each_missing_div_c_item_is_a_named_finding(codes, form, narrative, report, key, citation):
    parts = review_uploads(package(form, narrative, report), codes)
    finding = next((f for f in parts.findings if f.key == key), None)
    assert finding is not None, [f.key for f in parts.findings]
    assert finding.status == 'missing' and finding.severity == 'blocking'
    assert any(citation in c for c in finding.citations), finding.citations
    item = next(i for i in ir.build(parts.findings).items if i.finding_key == key)
    assert item.text.startswith('Please include')


def test_coordinator_named_clears_the_finding(codes):
    form = dict(CLEAN_FORM, **{'Supporting Doc2': 'SYNTHETIC structural letter', 'Name Responsible2': 'SYNTHETIC Other'})
    narrative = _without(**{'Coordinator': 'SYNTHETIC J. Example co-ordinates the design and documentation.'})
    parts = review_uploads(package(form, narrative), codes)
    assert 'div_c.coordinator:presence' not in {f.key for f in parts.findings}


@pytest.mark.parametrize('narrative,key', [
    (_without('Maintenance and commissioning'), 'demonstrate.failure_conditions:not_mentioned'),
    (_without('Maintenance and commissioning'), 'demonstrate.lapsed_maintenance:not_mentioned'),
    (_without(**{'Risk assessment': 'SYNTHETIC applicant passage: fire spread from the soffit to the neighbouring '
                                    'house.', 'Assumptions and limits': 'SYNTHETIC: assumes a single-family house.'}),
     'demonstrate.emergency_response:not_mentioned'),
], ids=['failure', 'lapsed-maintenance', 'emergency-response'])
def test_demonstrate_prompts_are_requests_not_judgements(codes, narrative, key):
    parts = review_uploads(package(narrative=narrative), codes)
    finding = next((f for f in parts.findings if f.key == key), None)
    assert finding is not None, [f.key for f in parts.findings]
    assert finding.status == 'unclear' and finding.severity == 'warning'
    assert 'does not judge adequacy' in finding.message
    item = next(i for i in ir.build(parts.findings).items if i.finding_key == key)
    assert item.text.startswith('Please state') and 'inadequate' not in item.text.casefold()


def test_peer_review_signal_is_for_the_officer_only(codes):
    narrative = _without(**{'Engineering required: yes': 'SYNTHETIC statement.',
                            'Responsible professional': 'SYNTHETIC P. Engineer',
                            'Qualifications of the responsible professional': 'SYNTHETIC qualifications.'})
    report = CLEAN_REPORT + ['SYNTHETIC brochure for a proprietary soffit product.']
    parts = review_uploads(package(narrative=narrative, report=report), codes)
    signal = next(f for f in parts.findings if f.key == 'peer_review:signal')
    assert signal.message.startswith(PEER_REVIEW) and "officer's call" in signal.message
    assert 'registered professional' in signal.message and 'CCMC' in signal.message
    assert signal.routed_to == 'officer'
    assert all(i.finding_key != signal.key for i in ir.build(parts.findings).items)
    assert signal.key not in ir.open_gaps(parts.findings)


def test_part3_citation_raises_the_peer_review_signal(codes):
    form = dict(CLEAN_FORM, **{'Article(s)1': '3.2.3.6.(2)'})
    parts = review_uploads(package(form), codes)
    assert any(f.key == 'peer_review:signal' and '3.2.3.6.(2)' in f.message for f in parts.findings)


def test_clean_package_has_no_div_c_or_peer_review_findings(codes):
    keys = {f.key for f in review_uploads(package(), codes).findings}
    assert not {k for k in keys if k.startswith(('div_c.', 'demonstrate.', 'peer_review'))}


def test_information_request_items_are_addressed_to_the_applicant():
    """Finding messages speak to the officer; the request copied to the applicant must not."""
    from engine.models_review import Finding, Pointer
    from engine.review import information_request as ir
    finding = Finding(key='div_c.testing_procedures:presence', section='process', field='div_c.testing_procedures',
                      label='testing procedures', status='missing', problem='absent', severity='blocking',
                      message='No testing procedures were named. Ask the applicant to include it.',
                      pointers=[Pointer(file='case:x')])
    demo = Finding(key='demonstrate.failure_conditions:not_mentioned', section='process',
                   field='demonstrate.failure_conditions', label='performance under failure conditions',
                   status='unclear', problem='not_mentioned', severity='warning',
                   message='Failure is not mentioned. Ask the applicant to state it; the review does not judge adequacy.',
                   pointers=[Pointer(file='case:x')])
    texts = [item.text for item in ir.build([finding, demo]).items]
    # The applicant's case is filed under Section D on their screens (app audit 2026-10-29, row 5).
    assert texts == ['Please include the testing procedures (Section D). No testing procedures were named.',
                     'Please state in the documentation performance under failure conditions (Section D), or say '
                     'that it does not apply. Failure is not mentioned.']
    assert not any('Ask the applicant' in t for t in texts)


@pytest.mark.parametrize('instruction', [
    'Ask the applicant to check provision 9.10.14.4.',
    'Ask the applicant to check provision 9.10.14.4 before resubmitting.',
    'Ask the applicant to check provision 9.9.10.1.(1).',
])
def test_information_request_removes_officer_sentence_with_dotted_provision(instruction):
    from engine.models_review import Finding

    finding = Finding(key='citation:provision', section='C', field='provision', label='provision',
                      status='unclear', problem='nonexistent_provision', severity='blocking',
                      message=f'The provision could not be verified. {instruction} Please confirm the edition.')

    assert ir.build([finding]).items[0].text == (
        'Please confirm the provision number for provision (Section C). '
        'The provision could not be verified. Please confirm the edition.')
