"""C5 boundary: the package review never fills a missing item, never states compliance, and never writes
risk, mitigation or the officer's decision. Also: request determinism and diff counts."""
from __future__ import annotations

import re

import pytest

from engine.models_review import EditedItem, Finding, Pointer
from engine.review import information_request as ir
from engine.review.package import review_uploads
from engine.tests.package_review_fixtures import CLEAN_FORM, CLEAN_NARRATIVE, package

VERDICT = re.compile(r'\b(?:complies|compliant|in compliance|code-compliant|conforms to|is safe|are safe|'
                     r'approved|meets the code|satisfies the code|acceptable solution is met|variance is granted)\b', re.I)


def _generated_text(parts, request):
    for finding in parts.findings:
        yield finding.message
    for check in parts.section_c:
        yield check.message
    for item in request.items:
        yield item.text
    yield request.intro


@pytest.mark.parametrize('flat', [False, True])
def test_no_compliance_language_in_any_generated_text(flat):
    planted = dict(CLEAN_FORM, Owner='', Lot='TBD', Objective='OS1.2', Function='F02',
                   **{'Article(s)': '9.10.15.5.(99)', 'Name Responsible': ''})
    narrative = dict(CLEAN_NARRATIVE, **{'Risk assessment': 'low risk', 'Mitigating measures': ''})
    parts = review_uploads(package(planted, narrative, flat=flat), None)
    request = ir.build(parts.findings)
    for text in _generated_text(parts, request):
        assert not VERDICT.search(text), text


def test_never_fills_a_blank_from_elsewhere_in_the_package():
    # The owner name is blank in Section A but printed under the signature: the review must not copy it.
    values = dict(CLEAN_FORM, Owner='', **{'Owner Print': 'SYNTHETIC Printed Owner Name'})
    parts = review_uploads(package(values), None)
    owner = next(f for f in parts.fields if f.field == 'Owner')
    assert owner.status == 'blank' and owner.value is None
    request = ir.build(parts.findings)
    item = next(i for i in request.items if i.field == 'owner_name')
    assert 'SYNTHETIC Printed Owner Name' not in item.text
    assert item.text.startswith('Please provide')


def test_never_writes_risk_mitigation_or_assumptions():
    narrative = dict(CLEAN_NARRATIVE, **{'Risk assessment': '', 'Mitigating measures': '',
                                         'Assumptions and limits': ''})
    parts = review_uploads(package(narrative=narrative), None)
    by_field = {f.field: f for f in parts.fields}
    for key in ('risk_assessment', 'mitigating_measures', 'assumptions_and_limits'):
        assert by_field[key].status == 'blank' and by_field[key].value is None
    request = ir.build(parts.findings)
    for item in request.items:
        if item.field in ('risk_assessment', 'mitigating_measures', 'assumptions_and_limits'):
            assert item.text.startswith('Please provide the ')
            assert 'The field is blank.' in item.text
            # A request names the gap; it carries no drafted passage.
            assert len(item.text) < 200


def test_officer_decision_and_registration_duties_are_not_asked_of_the_applicant():
    finding = Finding(key='division_c_2_3_1:presence', section='B', field='division_c_2_3_1',
                      label='Division C Section 2.3.1 documentation', status='missing', message='x')
    officer = Finding(key='file:a:unreadable', section='D', field='file.a', label='file', status='not_found',
                      routed_to='officer', message='x')
    assert ir.build([finding, officer]).items == []


def test_request_is_deterministic_and_not_found_items_wait_for_the_officer():
    findings = review_uploads(package(dict(CLEAN_FORM, Owner='')), None).findings
    first, second = ir.build(findings), ir.build(findings)
    assert first == second
    assert [item.id for item in first.items] == [ir.item_id(item.finding_key) for item in first.items]
    signature = next(item for item in first.items if item.finding_key == 'signature:presence')
    assert signature.officer_check and not signature.included
    assert 'Please' in first.text and signature.text not in first.text


def test_edit_keeps_links_marks_officer_text_and_rejects_unknown_ids():
    findings = review_uploads(package(dict(CLEAN_FORM, Owner='')), None).findings
    request = ir.build(findings)
    owner = next(item for item in request.items if item.field == 'owner_name')
    edited = ir.edit(request, [EditedItem(id=owner.id, text=owner.text, included=True),
                               EditedItem(text='Please send the site plan.')], None)
    assert edited.items[0].authored_by == 'batatis' and edited.items[0].finding_key == owner.finding_key
    assert edited.items[1].authored_by == 'officer' and edited.items[1].finding_key is None
    reworded = ir.edit(request, [EditedItem(id=owner.id, text='Owner, please.')], 'Intro')
    assert reworded.items[0].authored_by == 'officer' and reworded.intro == 'Intro'
    assert reworded.text == 'Intro\n\n1. Owner, please.'
    with pytest.raises(KeyError):
        ir.edit(request, [EditedItem(id='ir_missing', text='x')], None)


def _finding(key, status='blank'):
    return Finding(key=key, section='A', field=key.split(':')[0], label=key, status=status, message=key,
                   pointers=[Pointer(file='f')])


def test_diff_counts_resolved_still_open_and_new():
    before = [_finding('a:presence'), _finding('b:presence'), _finding('c:presence'), _finding('d:presence'),
              _finding('sig:presence', status='not_found')]
    after = [_finding('c:presence'), _finding('e:presence'), _finding('sig:presence', status='not_found')]
    diff = ir.diff(1, before, after)
    assert diff.previous_gaps == 4   # not-found officer checks are not counted as applicant gaps
    assert [e.key for e in diff.resolved] == ['a:presence', 'b:presence', 'd:presence']
    assert [e.key for e in diff.still_open] == ['c:presence']
    assert [e.key for e in diff.new] == ['e:presence']
    assert diff.statement == '3 of 4 gaps resolved, 1 still open, 1 new'
    assert ir.diff(2, [], []).statement == '0 of 0 gaps resolved'
    assert ir.diff(3, before, []).statement == '4 of 4 gaps resolved'
