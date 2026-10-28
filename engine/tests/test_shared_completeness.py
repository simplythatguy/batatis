"""Regressions through applicant, exporter and officer callers, with real CodeDB/PDF bytes."""
import pytest

from engine.codes import Codes
from engine.completeness import check_completeness
from engine.completeness_report import saved_case_response
from engine.export.demo_cases import CASES, demo_case
from engine.export.scc import blockers, export_case, load_field_map
from engine.models import Case, Fact, Source
from engine.review.package import review_case, review_uploads
from engine.review.citations import compare_row, verify_citation
from engine.models import Jurisdiction
from engine.models_review import Pointer
from engine.tests.package_review_fixtures import CLEAN_NARRATIVE, package, text_pdf


def fact(key, value, *, confirmed=True, quote=None):
    return Fact(field=key, value=value, kind='pointed',
                status='confirmed' if confirmed else 'unconfirmed',
                source=Source(type='user_text', ref='SYNTHETIC applicant',
                              quote=str(value) if quote is None else quote))


def elements(case, codes):
    return {e.field: e for section in saved_case_response(case, codes).reviews[0].sections
            for e in section.elements}


def test_officer_code_analysis_testing_and_coordinator_reach_applicant_and_export():
    codes = Codes()
    case = Case(facts=[fact('pathway', 'alternative'), fact('professional_name', 'SYNTHETIC designer')])
    officer = {f.field for f in review_case(case, codes).findings}
    applicant = {g.field for g in check_completeness(case, codes)}
    assert {'div_c.code_analysis', 'div_c.testing_procedures'} <= officer
    assert {'div_c.code_analysis', 'div_c.testing_procedures'} <= applicant
    reasons = blockers(case, load_field_map(), codes)
    assert all(any(field in reason for reason in reasons)
               for field in ('div_c.code_analysis', 'div_c.testing_procedures'))


def test_case_summary_uses_value_and_preserves_unconfirmed_certainty():
    case = Case(facts=[fact('owner_name', 'SYNTHETIC actual owner',
                           quote='The owner is SYNTHETIC actual owner according to the application.'),
                       fact('mailing_address', 'SYNTHETIC unconfirmed address', confirmed=False)])
    fields = {f.field: f for f in review_case(case, Codes()).fields}
    assert fields['owner_name'].value == 'SYNTHETIC actual owner'
    assert fields['mailing_address'].status == 'not_found'
    assert fields['mailing_address'].value is None
    assert fields['mailing_address'].pointer.quote is None


@pytest.mark.parametrize('name', CASES)
def test_real_demo_export_import_agrees_on_process_gaps(name):
    codes = Codes()
    case = demo_case(name, codes)
    case.facts.append(fact('process.risk_assessment', 'low risk'))
    result = export_case(case, codes=codes, draft=True)
    uploaded = review_uploads([('application.pdf', result.pdf)], codes)
    assert any(f.field == 'risk_assessment' for f in uploaded.findings)
    assert any(g.field == 'risk_assessment' for g in check_completeness(case, codes))
    assert any('risk_assessment' in reason for reason in blockers(case, load_field_map(), codes))


@pytest.mark.parametrize('text', ['No testing procedures have been provided.',
                                'Testing procedures: not provided.', 'Testing procedures'])
def test_negated_or_heading_only_testing_does_not_establish_presence(text):
    codes = Codes()
    case = Case(facts=[fact('pathway', 'alternative'), fact('testing_procedures', text)])
    assert any(g.field == 'div_c.testing_procedures' for g in check_completeness(case, codes))
    uploaded = review_uploads(package(narrative=dict(CLEAN_NARRATIVE, **{'Testing procedures': text}), report=[]), codes)
    assert any(f.field == 'div_c.testing_procedures' for f in uploaded.findings)


@pytest.mark.parametrize('key', ['rationale', 'risk_assessment', 'mitigating_measures', 'assumptions_and_limits'])
def test_embedded_unknown_in_real_narrative_is_not_a_placeholder(key):
    text = 'SYNTHETIC wall fire spread assessment: the response interval is unknown and remains an assumption for this wall.'
    entry = elements(Case(facts=[fact('pathway', 'alternative'), fact(key, text)]), Codes())[key]
    assert entry.problem != 'placeholder'
    assert entry.value == text


@pytest.mark.parametrize('division,pid', [('A', '1.2.1.1.(1)(b)'), ('C', '2.3.1.1.(3)')])
def test_citation_division_is_resolved_as_written(division, pid):
    checks = verify_citation(f'NBC(AE) 2023, Division {division}, {pid}', Pointer(file='source.pdf'), Codes())
    assert len(checks) == 1 and checks[0].exists is True
    assert not any(issue.code == 'nonexistent_provision' for issue in checks[0].issues)


def test_note_reference_resolves_in_any_division():
    # 2.2.1.1.(1) exists in Divisions A and C; the exported objective text cites its Note.
    checks = verify_citation('OS3.7 persons being delayed (see Note A-2.2.1.1.(1))',
                             Pointer(file='application.pdf'), Codes())
    assert len(checks) == 1 and checks[0].exists is True and not checks[0].issues
    # "A-" is the note prefix in every division; a Division B note stays a Division B provision.
    checks = verify_citation('see Note A-9.9.10.1.(1)', Pointer(file='application.pdf'), Codes())
    assert checks[0].exists is True and 'Division B' in checks[0].canonical_citation


def test_partial_attribution_codes_never_claim_a_match():
    codes = Codes()
    from engine.section_c import section_c_rows
    pid = '9.27.3.2.(1)'
    row = section_c_rows([pid], codes)[0]
    assert len({pair.function for pair in row.pairs}) > 1
    pair = row.pairs[0]
    check = compare_row(1, pid, pair.objective, pair.function, Pointer(file='form.pdf'), codes)
    assert check.status == 'mismatch'


def test_named_missing_attachment_is_not_closed_by_a_similar_unrelated_title():
    parts = review_uploads(package()[:-1], Codes())
    assert any(f.problem == 'missing_attachment' for f in parts.findings)
    case = Case()
    from engine.models import EvidenceItem
    case.evidence.append(EvidenceItem(id='named', description='SYNTHETIC named report', status='evidence_listed'))
    assert any(g.field.startswith('attachment.') and 'SYNTHETIC named report' in g.message
               and g.severity == 'blocking' for g in check_completeness(case, Codes()))


def test_harmless_city_notice_is_consumable_and_never_export_blocking():
    case = demo_case('b-contractor-firestop-nonconformance', Codes())
    response = saved_case_response(case, Codes())
    notice = next(item for item in response.policy.items if item.key.startswith('info:'))
    assert notice.severity == 'info' and not notice.export_blocking


def test_source_failure_is_uncertainty_not_a_false_missing_provision():
    class Failed:
        db_path = '/unavailable'
        def provision(self, *_args):
            raise OSError('source unavailable')
    check = verify_citation('Div C 2.3.1.1.(3)', Pointer(file='source.pdf'), Failed())[0]
    assert check.exists is None
    assert {issue.code for issue in check.issues} == {'source_unresolved'}


def test_hidden_or_conflicting_process_answer_is_whole_field_uncertainty():
    uploads = package() + [('conflict.pdf', text_pdf(['Risk assessment', 'SYNTHETIC conflicting wall fire assessment.',
                                                    'Mitigating measures']))]
    parts = review_uploads(uploads, Codes())
    reading = next(f for f in parts.fields if f.field == 'risk_assessment')
    assert reading.status == 'not_found' and reading.value is None and reading.pointer.quote is None
    item = next(item for item in parts.policy.items if item.field == 'risk_assessment')
    assert item.certainty == 'not_found' and item.value is None
    assert len(item.pointers) == 2 and all(pointer.quote is None for pointer in item.pointers)


@pytest.mark.parametrize('field', ['demonstrate.failure_conditions', 'demonstrate.lapsed_maintenance',
                                  'demonstrate.emergency_response'])
def test_demonstration_assumptions_are_shared_administrative_prompts(field):
    case = Case(facts=[fact('pathway', 'alternative'),
                       fact('alternative_description', 'SYNTHETIC dwelling wall departure.')])
    codes = Codes()
    gap = next(gap for gap in check_completeness(case, codes) if gap.field == field)
    saved = next(item for item in saved_case_response(case, codes).policy.items if item.field == field)
    officer = next(item for item in review_case(case, codes).policy.items if item.field == field)
    assert gap.severity == saved.severity == officer.severity == 'warning'
    assert saved == officer and 'does not judge adequacy' in saved.reason


def test_signature_preparation_stage_is_shared_and_started_signature_requires_date():
    codes = Codes()
    case = Case(facts=[fact('owner_name', 'SYNTHETIC owner')])
    assert not any(gap.field.endswith('signature_date') for gap in check_completeness(case, codes))
    case.facts.append(fact('owner_signature', 'SYNTHETIC signed by owner'))
    assert any(gap.field == 'owner_signature_date' and gap.severity == 'blocking'
               for gap in check_completeness(case, codes))
    assert saved_case_response(case, codes).policy.stage == review_case(case, codes).policy.stage == 'preparation'
    uploaded = review_uploads(package(), codes)
    assert uploaded.policy.stage == 'preparation'
    assert not any(item.export_blocking and item.field.endswith('signature_date') for item in uploaded.policy.items)


def test_jurisdiction_wide_scope_is_a_shared_single_location_gap():
    codes = Codes()
    saved = saved_case_response(Case(facts=[fact('pathway', 'alternative'),
                                          fact('municipal_address', 'SYNTHETIC one street'),
                                          fact('scope', 'jurisdiction')]), codes)
    from engine.tests.package_review_fixtures import CLEAN_FORM
    uploaded = review_uploads(package(dict(CLEAN_FORM, **{'Check Box': '/Yes'})), codes)
    for policy in (saved.policy, uploaded.policy):
        item = next(item for item in policy.items if item.field == 'single_location')
        assert item.reason_code == 'multiple_locations' and item.export_blocking


def test_full_saved_summary_never_promotes_unconfirmed_or_unsupported_document_metadata():
    case = Case(facts=[fact('storeys', 2), fact('sprinklered', 'unknown', confirmed=False),
        Fact(field='evidence.report.file_ref', value='report.pdf', kind='exact', status='confirmed',
             source=Source(type='file', ref='report.pdf')),
        fact('evidence.report.title', 'SYNTHETIC pending title', confirmed=False),
        Fact(field='evidence.report.responsible_party', value='SYNTHETIC wrong reader value', kind='pointed',
             status='confirmed', source=Source(type='file', ref='report.pdf', quote='A different author is printed.'))])
    parts = review_case(case, Codes())
    fields = {item.field: item for item in parts.fields}
    assert fields['storeys'].value == '2'
    for key in ('sprinklered', 'evidence.report.title', 'evidence.report.responsible_party'):
        assert fields[key].status == 'not_found' and fields[key].value is None
        assert fields[key].pointer.quote is None
    document = next(row for row in parts.documents if row.id == 'report')
    assert not document.title.known and not document.responsible.known


def test_owner_without_representative_and_lot_block_plan_agree_on_both_paths():
    from engine.tests.case_builder_fixtures import complete_case, fact as saved_fact
    codes = Codes()
    case = complete_case()
    case.facts = [f for f in case.facts if f.field not in ('legal_description', 'representative')]
    case.facts += [saved_fact('lot', '12'), saved_fact('block', '3'), saved_fact('plan', '1234567')]
    applicant = saved_case_response(case, codes).policy
    officer = review_uploads([('same.pdf', export_case(case, codes=codes, draft=True).pdf)], codes).policy
    for report in (applicant, officer):
        items = {item.field: item for item in report.items}
        assert items['representative'].verdict == 'present'
        assert items['legal_description'].verdict == 'present'
        assert items['legal_description'].value == 'Lot 12, Block 3, Plan 1234567'
        assert report.export_reasons == []
