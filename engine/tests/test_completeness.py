import pytest

from engine.codes import Codes
from engine.completeness import Gap, check_completeness
from engine.models import EvidenceItem
from engine.section_c import section_c_rows
from engine.store import CaseStore
from engine.tests.case_builder_fixtures import complete_case, fact


def remove(case, field):
    case.facts = [f for f in case.facts if f.field != field]


def clean_case():
    """complete_case plus the statements the shared check warns about when they are absent."""
    case = complete_case()
    remove(case, 'alternative_description')
    case.facts += [
        fact('alternative_description', 'Synthetic test departure between two dwelling units, no technical conclusion.'),
        fact('failure_conditions', 'Synthetic applicant statement of how the departure performs if a component fails.'),
        fact('lapsed_maintenance', 'Synthetic applicant assumption if inspection or maintenance lapses.'),
        fact('emergency_response', 'Synthetic applicant assumption about the fire-service response time.')]
    return case


def preparation_only(gaps):
    """Batatis prepares pages for signing outside the app; the unread signature stays an officer check."""
    rest = [g for g in gaps if g.id != 'signature:presence']
    assert all(g.severity == 'warning' and g.routed_to == 'officer' for g in gaps if g.id == 'signature:presence')
    return rest


def test_clean_control_and_no_mutations():
    case = clean_case()
    before = case.model_dump_json()
    assert preparation_only(check_completeness(case, Codes())) == []
    assert case.model_dump_json() == before


@pytest.mark.parametrize('rule,field', [('D01', 'owner_name'), ('D02', 'application_date'),
    ('D03', 'civic_address'), ('D04', 'legal_description'), ('D09', 'risk_assessment'),
    ('D10', 'mitigating_measures'), ('D11', 'assumptions_and_limits')])
def test_missing_fields_for_each_rule_checked_planted_class(rule, field):
    case = complete_case()
    remove(case, field)
    found = [g for g in check_completeness(case, Codes()) if g.id.startswith(rule + ':')]
    assert found and found[0].field == field
    assert all(isinstance(g, Gap) and g.fix_hint and g.message.startswith('Your application appears to be missing ') for g in found)


def test_d01_blank_differs_from_not_found_and_d04_placeholder():
    case = complete_case()
    case.facts += [fact('owner_name', ''), fact('legal_description', 'TBD')]
    gaps = check_completeness(case, Codes())
    assert 'blank' in next(g.message for g in gaps if g.id.startswith('D01:'))
    assert 'placeholder' in next(g.message for g in gaps if g.id.startswith('D04:'))
    case.facts += [fact('presence.owner_name', 'not_found')]
    assert 'not found' in next(g.message for g in check_completeness(case, Codes()) if g.id.startswith('D01:'))


def test_d02_signature_date_is_located():
    case = complete_case()
    case.facts.append(fact('owner_rep_signature', 'Synthetic signature metadata'))
    gap = next(g for g in check_completeness(case, Codes()) if g.field == 'owner_rep_signature_date')
    assert gap.id.startswith('D02:')


def test_d05_nonexistent_article_is_a_gap_not_a_crash():
    case = complete_case()
    case.section_c[0].provision_id = '9.99.99.99.(99)'
    assert any(g.id.startswith('D05:') and 'was not found in NBC(AE) 2023' in g.message
               for g in check_completeness(case, Codes()))


def test_d06_superseded_label_and_explicit_historical_context():
    case = complete_case()
    case.section_c[0].citation = 'NBC(AE) 2019, Div B, Sentence 9.10.9.16.(1)'
    assert any(g.id.startswith('D06:') for g in check_completeness(case, Codes()))
    case.section_c[0].citation += ' (historical context)'
    assert not any(g.id.startswith('D06:') for g in check_completeness(case, Codes()))


def test_d06_unlabelled_old_number_heading_mismatch_uses_verified_crosswalk():
    case = complete_case(['3.1.6.5.(1)'])
    case.section_c[0].citation = 'Flame Resistance, Sentence 3.1.6.5.(1)'
    gap = next(g for g in check_completeness(case, Codes()) if g.id.startswith('D06:'))
    assert gap.citation == Codes().citation('3.1.18.5.', 'B')
    assert 'equivalence is unverified' in gap.fix_hint


def test_d07_wrong_pair_and_pair_copied_to_no_row():
    case = complete_case()
    case.section_c[0].pairs[0].objective = 'OS3.7'
    gap = next(g for g in check_completeness(case, Codes()) if g.id.startswith('D07:'))
    assert 'Division B table' in gap.message and 'F03-OS1.2' in gap.fix_hint
    case = complete_case(['9.10.14.2.(1)'])
    case.section_c[0].pairs = section_c_rows(['9.10.9.16.(1)'], Codes())[0].pairs
    assert any(g.id.startswith('D07:') for g in check_completeness(case, Codes()))


def test_d08_intent_is_national_explanatory_material():
    case = complete_case()
    assert case.section_c[0].intents
    case.section_c[0].intents[0].label = 'Alberta legal requirement'
    gap = next(g for g in check_completeness(case, Codes()) if g.id.startswith('D08:'))
    assert 'not Alberta law' in gap.message and 'explanatory only' in gap.fix_hint


def test_valid_citation_for_another_article_is_still_wrong():
    case = complete_case(['9.25.2.2.(1)'])
    case.section_c[0].citation = Codes().citation('9.9.10.1.(1)', 'B')
    assert any(g.id.startswith('citation_binding:') for g in check_completeness(case, Codes()))


@pytest.mark.parametrize('field,value', [('intents', ['Fabricated intent content']), ('pdf_page', 1),
    ('brackets', ['[F03-OS1.2]']), ('provision_id', '9.9.10.1.(1)')])
def test_canonical_intent_checks_all_payload_fields(field, value):
    case = complete_case(['9.25.2.2.(1)'])
    setattr(case.section_c[0].intents[0], field, value)
    assert any(g.id.startswith('intent_payload:') for g in check_completeness(case, Codes()))


@pytest.mark.parametrize('field,value', [('differs', True), ('intent_comparison', 'invented'),
    ('only_in_ae', ['invented']), ('only_in_intent', ['invented']), ('related_root', '9.99.99.99.(1)')])
def test_canonical_intent_checks_comparison_metadata(field, value):
    case = complete_case(['9.25.2.2.(1)'])
    setattr(case.section_c[0], field, value)
    assert any(g.id.startswith('intent_payload:') for g in check_completeness(case, Codes()))


def test_d12_professional_required_but_none_named_or_authenticated():
    case = complete_case()
    case.facts.append(fact('part4_design', True))
    gaps = [g for g in check_completeness(case, Codes()) if g.id.startswith('D12:')]
    assert {g.field for g in gaps} >= {'responsible_professional', 'professional_authentication'}
    assert next(g for g in gaps if g.field == 'responsible_professional').citation == Codes().citation('2.4.1.2.(1)', 'C')
    remove(case, 'qualifications')
    assert any(g.field == 'professional_qualifications' for g in check_completeness(case, Codes()))


def test_d12_explicit_required_case_flag_is_respected():
    case = complete_case()
    case.facts.append(fact('engineering_required', 'yes'))
    assert any(g.id.startswith('D12:') for g in check_completeness(case, Codes()))


def test_d13_attached_document_missing_responsible_party(tmp_path):
    case = complete_case()
    remove(case, 'evidence.synthetic.responsible_party')
    # The attachment itself names no responsible person either; the check reads the actual bytes.
    store = CaseStore(tmp_path / 'cases.sqlite')
    store.put(case)
    saved = store.put_file(case.id, 'synthetic.txt', b'SYNTHETIC TEST ATTACHMENT - no test was performed.\n', 'text/plain')
    for f in case.facts:
        if f.field == 'evidence.synthetic.file_ref':
            f.value, f.source = saved['id'], f.source.model_copy(update={'ref': saved['id']})
    store.put(case)
    gap = next(g for g in check_completeness(case, Codes(), store=store) if g.id.startswith('D13:'))
    assert gap.field == 'document.synthetic-test-attachment.responsible_party'
    assert 'responsible person' in gap.message and gap.severity == 'blocking'


def test_d16_every_confirmed_benchmark_requires_a_row():
    case = complete_case(['9.10.9.16.'])
    removed = case.section_c.pop()
    gap = next(g for g in check_completeness(case, Codes()) if g.id.startswith('D16:'))
    assert removed.provision_id in gap.field and 'Section B' in gap.message


def test_latest_unconfirmed_alias_never_uses_earlier_confirmed_value():
    case = complete_case()
    case.facts += [fact('owner', 'Unconfirmed new owner', status='unconfirmed'),
                   fact('process.risk', 'New assessment', kind='proposed', status='unconfirmed')]
    found = {g.field for g in check_completeness(case, Codes())}
    assert {'owner_name', 'risk_assessment'} <= found


def test_provided_flag_without_attachment_or_responsibility_still_has_gaps():
    case = complete_case()
    case.evidence.append(EvidenceItem(id='unattached', description='Claimed report', status='provided'))
    fields = {g.field for g in check_completeness(case, Codes())}
    # Fields name the document by the title the outgoing form shows.
    assert {'attachment.claimed-report', 'document.claimed-report.responsible_party'} <= fields


def test_current_process_aliases_and_structured_legal_description():
    case = clean_case()
    for f in case.facts:
        f.field = {'assumptions_and_limits': 'assumptions_limits', 'maintenance_operation': 'operation_maintenance'}.get(f.field, f.field)
    remove(case, 'legal_description')
    case.facts += [fact('lot', '1'), fact('block', '2'), fact('plan', '3')]
    assert preparation_only(check_completeness(case, Codes())) == []


def test_checker_does_not_claim_compliance_or_write_process_answers():
    case = complete_case()
    remove(case, 'risk_assessment')
    before = case.model_dump_json()
    gaps = check_completeness(case, Codes())
    assert before == case.model_dump_json()
    assert 'design complies' not in ' '.join(g.message for g in gaps).lower()
