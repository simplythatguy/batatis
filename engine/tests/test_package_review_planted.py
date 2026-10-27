"""Planted defects (evals_dev/planted/SPEC.md D01-D16) on SYNTHETIC fillable and flattened SCC forms.

Each case plants one defect into a clean package and checks the review names the
right field and problem, and that the information request asks the applicant.
"""
from __future__ import annotations

import copy

import pytest

from engine.codes import Codes
from engine.review.information_request import build
from engine.review.package import review_uploads
from engine.tests.package_review_fixtures import CLEAN_FORM, CLEAN_NARRATIVE, CLEAN_REPORT, package


@pytest.fixture(scope='module')
def codes():
    return Codes()


def _form(**changes):
    values = copy.deepcopy(CLEAN_FORM)
    values.update(changes)
    return values


def _narrative(**changes):
    values = copy.deepcopy(CLEAN_NARRATIVE)
    values.update(changes)
    return values


# class, form values, narrative, report, expected (field prefix, status or None, problem or None)
PLANTED = [
    ('D01', _form(Owner=''), None, None, ('owner_name', 'blank', None)),
    ('D02', _form(**{'Date of Reqeuest': ''}), None, None, ('application_date', 'blank', None)),
    ('D03', _form(**{'Municipal Address': ''}), None, None, ('civic_address', 'blank', None)),
    ('D04', _form(Lot='TBD'), None, None, ('legal_description', 'missing', 'placeholder')),
    ('D04', _form(Lot='', Block='', Plan=''), None, None, ('legal_description', 'blank', None)),
    ('D05', _form(**{'Article(s)': '9.10.15.5.(99)'}), None, None, ('section_c.row1.article', 'missing',
                                                                    'nonexistent_provision')),
    ('D06', _form(**{'Code or Standard': 'NBC(AE) 2019, Division B'}), None, None,
     ('section_c.edition', 'unclear', 'superseded_edition')),
    ('D07', _form(Objective='OS1.2', Function='F02'), None, None, ('section_c.row1.pair', 'unclear', 'pair_mismatch')),
    ('D08', _form(**{'Intent statement': 'Alberta intent: limit fire spread through roof soffits.'}), None, None,
     ('section_c.row1.intent', 'unclear', 'intent_label')),
    ('D09', None, _narrative(**{'Risk assessment': 'low risk'}), None, ('risk_assessment', 'unclear', 'generic')),
    ('D09', None, _narrative(**{'Risk assessment': ''}), None, ('risk_assessment', 'blank', None)),
    ('D10', None, _narrative(**{'Mitigating measures': ''}), None, ('mitigating_measures', 'blank', None)),
    ('D11', None, _narrative(**{'Assumptions and limits': ''}), None, ('assumptions_and_limits', 'blank', None)),
    ('D12', None, _narrative(**{'Engineering required: yes': 'SYNTHETIC: stated by the applicant.'}), None,
     ('responsible_professional', None, 'professional_unnamed')),
    ('D13', _form(**{'Name Responsible': ''}), None, None, ('document.', 'missing', 'no_responsible')),
    ('D14', None, None, [line.replace('0.40 m', '0.90 m') for line in CLEAN_REPORT],
     ('section_b.consistency', 'unclear', 'contradiction')),
    ('D15', _form(**{'Article(s)': '9.8.2.1.(1)', 'Objective': 'OS3.1', 'Function': 'F30'}), None, None,
     ('section_c.relevance', 'unclear', 'topic_mismatch')),
    ('D16', None, _narrative(**{'Description of the proposed alternative':
                                CLEAN_NARRATIVE['Description of the proposed alternative']
                                + ' Benchmarks 9.10.15.5.(8) and 9.10.15.5.(9).'}), None,
     ('section_c.missing_row', 'missing', 'missing_row')),
]
IDS = [f'{row[0]}-{i}' for i, row in enumerate(PLANTED)]


@pytest.mark.parametrize('flat', [False, True], ids=['fillable', 'flattened'])
def test_clean_control_has_no_applicant_gap(codes, flat):
    parts = review_uploads(package(flat=flat), codes)
    applicant_gaps = [f for f in parts.findings if f.status != 'not_found' and f.routed_to != 'officer']
    assert applicant_gaps == [], [(f.key, f.message) for f in applicant_gaps]
    # Officer checks only: a signature and the professional requirement, which text cannot establish, and on a
    # flattened form the jurisdiction-wide check box, which cannot be read reliably.
    allowed = {'signature:presence', 'professional_requirement:requirement_unresolved'}
    assert {f.key for f in parts.findings} <= allowed | ({'single_location:presence'} if flat else set())
    assert [check.status for check in parts.section_c] == ['match']


@pytest.mark.parametrize('flat', [False, True], ids=['fillable', 'flattened'])
@pytest.mark.parametrize('defect,form,narrative,report,expected', PLANTED, ids=IDS)
def test_planted_defect_is_caught_and_asked(codes, flat, defect, form, narrative, report, expected):
    parts = review_uploads(package(form, narrative, report, flat=flat), codes)
    field, status, problem = expected
    hits = [f for f in parts.findings if f.field.startswith(field)
            and (status is None or f.status == status) and (problem is None or f.problem == problem)]
    assert hits, [(f.key, f.status, f.problem) for f in parts.findings]
    finding = hits[0]
    assert finding.defect_class == defect or defect in ('D02', 'D04') and finding.defect_class in ('D02', 'D04', None)
    assert finding.pointers, 'every finding points to its source'
    request = build(parts.findings)
    if defect == 'D15':
        # A keyword screen cannot decide relevance: the officer reviews the benchmarks, the applicant is not asked.
        assert finding.routed_to == 'officer' and not any(i.finding_key == finding.key for i in request.items)
        return
    item = next(i for i in request.items if i.finding_key == finding.key)
    assert item.text.startswith('Please ')
    assert item.included


@pytest.mark.parametrize('flat', [False, True], ids=['fillable', 'flattened'])
def test_blank_signature_date_without_a_readable_signature_is_an_officer_check(codes, flat):
    # Preparation stage: only a started signature requires its date. An unread signature stays the officer's check.
    parts = review_uploads(package(_form(Date1=''), flat=flat), codes)
    assert not any(f.field.endswith('signature_date') for f in parts.findings)
    signature = next(f for f in parts.findings if f.key == 'signature:presence')
    assert signature.status == 'not_found'
    item = next(i for i in build(parts.findings).items if i.finding_key == signature.key)
    assert item.officer_check and not item.included


def test_planted_d07_names_both_values(codes):
    parts = review_uploads(package(_form(Objective='OS1.2', Function='F02')), codes)
    finding = next(f for f in parts.findings if f.problem == 'pair_mismatch')
    assert 'OS1.2' in finding.message and 'F02' in finding.message
    assert 'F03-OP3.1' in finding.message


def test_planted_d14_quotes_both_spans(codes):
    report = [line.replace('0.40 m', '0.90 m') for line in CLEAN_REPORT]
    parts = review_uploads(package(report=report), codes)
    finding = next(f for f in parts.findings if f.problem == 'contradiction')
    assert 'limiting distance' in finding.message
