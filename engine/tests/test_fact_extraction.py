"""Persona, negation, and cfx-001–cfx-005 extraction checks.

Labels are agent-authored, model-checked, and not human-verified.
"""
import json
import re
from pathlib import Path

import pytest

from engine.completeness import check_completeness
from engine.fact_extraction import (
    EJ_ROUTE, REVIEW_LABEL, _supports, extract, html_to_text, officer_gaps, record_description,
    render_results, score_eval, score_prediction, departure_ok,
)
from engine.models import Case

ROOT = Path(__file__).resolve().parents[2]
CASES = ROOT / 'evals/fact-extraction/cases.json'
RESULTS = ROOT / 'evals/fact-extraction/RESULTS.md'
LABEL = 'agent-authored, model-checked, not human-verified'
BRIEF = ROOT / 'evals/demo-cases/b-contractor-firestop-nonconformance/input/project-brief.md'
EMAIL = ROOT / 'evals/demo-cases/b-contractor-firestop-nonconformance/input/manufacturer-ej-draft-EXAMPLE.md'
NCR = ROOT / 'evals/demo-cases/b-contractor-firestop-nonconformance/input/ncr-firestop-EXAMPLE.md'
DANA = ROOT / 'evals/demo-cases/tester-samples/01-hartley-garden-suite-brief.html'


def load():
    return json.loads(CASES.read_text())


def by_id():
    return {item['id']: item for item in load()['cases']}


def _walk_quotes(obj, text, errors):
    if isinstance(obj, dict):
        quote, span = obj.get('source_quote'), obj.get('source_span')
        if isinstance(quote, str):
            if quote not in text:
                errors.append(quote[:80])
            if span is not None and text[span[0]:span[1]] != quote:
                errors.append(('span', quote[:80]))
        for value in obj.values():
            _walk_quotes(value, text, errors)
    elif isinstance(obj, list):
        for value in obj:
            _walk_quotes(value, text, errors)


class _FakeCodes:
    db_path = Path('/tmp/not-a-codedb')

    def provision(self, pid, division=None):
        return {'id': pid, 'division': division or 'C',
                'citation': f'NBC(AE) 2023 Div {division or "C"} {pid}',
                'text': 'short', 'article_title': 'Title'}

    def citation(self, pid, division=None):
        return self.provision(pid, division)['citation']


def test_every_case_is_labelled_and_not_the_backing_file():
    payload = load()
    assert payload['label'] == LABEL
    assert payload['source_commit'] == '914b8ec'
    assert 'part3_fact_extraction_cases' not in payload
    for item in payload['cases']:
        assert item['label'] == LABEL
        assert 'app_answer' not in json.dumps(item)
        assert 'must_not_substrings' not in item


def test_cfx_slices_are_the_case_files_at_914b8ec():
    cases = by_id()
    brief, email, ncr = BRIEF.read_text().splitlines(), EMAIL.read_text().splitlines(), NCR.read_text().splitlines()
    assert cases['cfx-001']['text'] == '\n'.join(brief[7:15])
    assert cases['cfx-002']['text'] == brief[17] + '\n\n' + brief[19]
    assert cases['cfx-003']['text'] == '\n'.join(brief[21:25])
    assert cases['cfx-004']['text'] == '\n'.join(email[3:6])
    assert cases['cfx-005']['text'] == brief[19] + '\n' + ncr[12]
    assert cases['carlos-brief']['text'] == BRIEF.read_text()
    assert cases['dana']['text'] == html_to_text(DANA.read_text())
    assert 'This isn\'t a real engineering judgment.' not in cases['cfx-004']['text']


def test_classifier_matches_extraction_gold():
    for item in load()['cases']:
        if item['split'] == 'approach_dev':
            continue
        facts = extract(item['text'])
        scores = score_prediction(item['expect'], facts)
        bad = {field: counts for field, counts in scores.items() if counts[1] or counts[2]}
        assert not bad, (item['id'], bad)
        assert departure_ok(facts, item['departure']) is True
        dump = facts.model_dump_json().lower()
        for phrase in ("not an engineering judgment", "isn't a real engineering judgment", 'not an ej'):
            assert phrase not in dump
        if item['id'] == 'cfx-005':
            for phrase in ('3.1.9.1', 'nfpa', 'escutcheon'):
                assert phrase not in dump
        errors = []
        _walk_quotes(facts.model_dump(mode='json'), item['text'], errors)
        assert not errors


def test_cfx_005_does_not_answer_the_exemption_and_opens_a_gap():
    item = by_id()['cfx-005']
    case = Case()
    facts = record_description(case, item['text'])
    exemption = facts.claimed_exemptions[0]
    assert exemption.status == 'applicant_asserted'
    assert exemption.by == 'The sub'
    assert exemption.question == 'What evidence supports this exemption claim?'
    assert exemption.officer_gap == 'applicant claim not supported by a citation'
    assert facts.sprinklered.value is None
    assert not any(p.entered.startswith('3.1.9') for p in facts.claimed_provisions)
    gaps = officer_gaps(case)
    assert any(gap.section == 'B' and gap.field == 'claimed_exemptions'
               and gap.message == 'applicant claim not supported by a citation' for gap in gaps)
    for gap in gaps:
        assert not re.search(r'\b(yes|no)\b', gap.message, re.I)
        assert not re.search(r'\b(yes|no)\b', gap.fix_hint, re.I)
    assert not re.search(r'\b(yes|no)\b', exemption.question, re.I)
    assert all('exempt' not in str(fact.value).lower() for fact in case.facts)


def test_cfx_004_lists_the_email_without_judging_it():
    facts = extract(by_id()['cfx-004']['text'])
    item = facts.evidence_items[0]
    assert item.review_status == 'listed_not_reviewed'
    assert item.review_label == REVIEW_LABEL
    assert item.missing_items == ['signature', 'tested system', 'job name and location', 'issuer qualifications']
    assert item.author_type == 'vendor'
    assert item.stated_role == 'sales rep'
    assert item.professional_confirmed is False
    assert item.question == EJ_ROUTE
    assert item.signed is False
    case = Case()
    record_description(case, by_id()['cfx-004']['text'])
    gaps = officer_gaps(case)
    assert any(gap.section == 'D' and 'signature' in gap.message and EJ_ROUTE in gap.message for gap in gaps)
    assert all('not an engineering judgment' not in gap.message.lower() for gap in gaps)


def test_full_email_file_drops_the_planted_verdict():
    facts = extract(EMAIL.read_text())
    blob = facts.model_dump_json().lower()
    assert "isn't a real engineering judgment" not in blob
    assert 'not an engineering judgment' not in blob
    assert facts.evidence_items[0].review_status == 'listed_not_reviewed'
    assert facts.claims and facts.claims[0].status == 'applicant_asserted'


def test_building_sprinklered_survives_the_exempt_claim():
    facts = extract(BRIEF.read_text())
    assert facts.sprinklered.value == 'yes'
    assert facts.claimed_exemptions[0].status == 'applicant_asserted'
    assert 'sprinkler branch lines' in facts.claimed_exemptions[0].text


def test_case_b_admin_fields_are_unconfirmed_and_the_departure_is_not_the_paste():
    """Issue #14 Case B. Admin cells stay unconfirmed, with a quote. The paste is not the departure."""
    text = BRIEF.read_text()
    case = Case()
    facts = record_description(case, text)
    present = {
        'owner_name': 'Example Commons Holdings Inc.',
        'municipal_address': '0000 Example Avenue SW, Calgary, AB',
        'legal_description': 'Lot 0, Block 0, Plan 0000000',
        'permit_number': 'BP-0000-00000',
        'sprinklered': 'yes',
    }
    for field, value in present.items():
        cell = getattr(facts, field)
        assert cell.status == 'extracted'
        assert cell.value == value
        assert cell.source_quote and cell.source_quote in text and cell.source_quote != text
        ledger = [fact for fact in case.facts if fact.field == field]
        assert ledger
        fact = ledger[-1]
        assert fact.status == 'unconfirmed'
        assert fact.value == value
        assert fact.source.quote == cell.source_quote
        assert fact.source.quote in text and fact.source.quote != text
    assert facts.mailing_address.status == 'missing'
    assert facts.mailing_address.value is None
    assert facts.mailing_address.source_quote is None
    assert not any(fact.field == 'mailing_address' for fact in case.facts)
    assert facts.proposed_alternative.value is None
    assert facts.proposed_alternative.value != text
    assert all(fact.value != text for fact in case.facts)
    assert not any(fact.field == 'alternative_description' and fact.value == text for fact in case.facts)


def test_mailing_address_is_its_own_unconfirmed_fact():
    text = (
        'Owner: Example Commons Holdings Inc.\n'
        'Address: 0000 Example Avenue SW, Calgary, AB\n'
        'Mailing address: PO Box 12, Edmonton, AB\n'
        'Building permit BP-1111, issued. The building is sprinklered.\n'
        'We propose to omit the firestop collar.\n'
    )
    case = Case()
    facts = record_description(case, text)
    cell = facts.mailing_address
    assert cell.status == 'extracted'
    assert cell.value == 'PO Box 12, Edmonton, AB'
    assert cell.source_quote == 'PO Box 12, Edmonton, AB'
    assert cell.source_quote in text and cell.source_quote != text
    fact = next(item for item in case.facts if item.field == 'mailing_address')
    assert fact.status == 'unconfirmed'
    assert fact.source.quote == cell.source_quote
    assert facts.municipal_address.value == '0000 Example Avenue SW, Calgary, AB'
    assert facts.municipal_address.value != facts.mailing_address.value
    assert facts.proposed_alternative.value == 'We propose to omit the firestop collar.'
    assert facts.proposed_alternative.value != text
    assert not _supports(
        'mailing_address', '0000 Example Avenue SW, Calgary, AB',
        '0000 Example Avenue SW, Calgary, AB', text)


def test_cfx_001_reads_identity_and_does_not_confirm_a_rating_or_group():
    item = by_id()['cfx-001']
    case = Case()
    facts = record_description(case, item['text'])
    assert facts.occupancy.value is None
    assert 'major occupancy' in facts.occupancy.question
    assert facts.proposed_alternative.value is None
    assert all(fact.value != '1 h' for fact in case.facts)
    gaps = check_completeness(case, _FakeCodes())
    for field in ('owner_name', 'civic_address', 'legal_description'):
        message = next(gap.message for gap in gaps if gap.field == field)
        assert 'has not been confirmed' in message
        assert 'not found' not in message


def test_factory_bonded_is_not_industrial_and_exempt_is_not_sprinklered():
    assert extract('The panel is factory-bonded OSB.').occupancy.value is None
    facts = extract('The sub says sprinklers are "exempt".')
    assert facts.sprinklered.value is None
    assert facts.sprinklered.method == 'rules'
    assert facts.claimed_exemptions[0].status == 'applicant_asserted'


def test_model_cannot_override_a_rules_hit_or_an_exempt_abstention(monkeypatch):
    monkeypatch.setenv('BATATIS_LIVE', '1')
    monkeypatch.setenv('OPENAI_API_KEY', 'sk-test')

    def suggest(text, fields):
        return {
            'sprinklered': {'value': 'no', 'quote': text},
            'owner_name': {'value': 'Pat Example', 'quote': 'Pat Example'},
        }

    monkeypatch.setattr('engine.fact_extraction._model_suggest', suggest)
    ruled = extract('The building is 5 storeys, sprinklered. Owner name: Pat Example.')
    assert ruled.sprinklered.value == 'yes' and ruled.sprinklered.method == 'rules'
    assert ruled.owner_name.value == 'Pat Example' and ruled.owner_name.method == 'model'
    held = extract('The sub says sprinklers are "exempt".')
    assert held.sprinklered.value is None and held.sprinklered.method == 'rules'
    assert not _supports('sprinklered', 'no', 'The sub says sprinklers are "exempt".', held_text())


def held_text():
    return 'The sub says sprinklers are "exempt".'


def test_regex_loses_the_held_out_departure_and_the_shop_normalisation():
    payload = load()
    scored = score_eval(payload['cases'])
    assert scored['winner'] == 'classifier'
    assert scored['departure_held_classifier'] == '2/2'
    assert scored['departure_held_regex'] == '0/2'
    assert scored['approach'] == {
        'classifier_storeys': 2, 'classifier_area': 185.81,
        'regex_storeys': None, 'regex_area': None,
    }
    note = render_results(scored)
    assert 'model-checked, not human-verified' in note
    assert RESULTS.read_text() == note


def test_user_value_is_kept_when_the_description_is_posted_again():
    case = Case()
    record_description(case, 'The owner is Pat Example.')
    from engine.fact_extraction import apply_patch
    apply_patch(case, {'owner_name': 'Kept Name'})
    record_description(case, 'The owner is Pat Example.')
    assert case.intake_facts['owner_name']['value'] == 'Kept Name'
    assert case.intake_facts['owner_name']['method'] == 'user'
    assert case.facts[-1].field in ('owner_name',) or any(
        fact.field == 'owner_name' and fact.value == 'Kept Name' and fact.status == 'confirmed' for fact in case.facts)


@pytest.mark.parametrize('phrase', ['not an engineering judgment', "isn't a real engineering judgment", 'not an ej'])
def test_results_and_cases_do_not_carry_a_verdict_phrase(phrase):
    assert phrase not in CASES.read_text().lower()
    assert phrase not in RESULTS.read_text().lower()
