"""Human-key harness tests. Fixtures are fake and live under tests/, never in human_key/."""
import json
import sqlite3
from pathlib import Path

from evals_dev.deterministic_checks import AB_FIELDS
from evals_dev.human_key.score import _canon_field, calibrate, score_keys
from evals_dev.human_key.select import SEED, persona_of, select_cases
from evals_dev.human_key.validate import key_errors, page_warnings, validate_keys
from evals_dev.stats import wilson_interval

ROOT = Path(__file__).resolve().parents[1]
CASES = ROOT / 'cases'
KEYS = ROOT / 'human_key'
FIXTURES = Path(__file__).resolve().parent / 'fixtures' / 'human_key'
ANSWER = (
    'section_ab_required_fields', 'expected_top_articles', 'benchmark_acceptable_solution',
    'engineer_needed', 'intake_action', 'verifier_name', 'date_verified', 'source_page_refs', 'notes',
)


def cases():
    """Load development cases used to verify subset selection and blank keys."""
    return [json.loads(p.read_text()) for p in sorted(CASES.glob('dev-*.json'))]


def test_canon_field_reads_engine_names():
    assert _canon_field('application_date') == 'date_of_request'
    assert _canon_field('owner_rep_name') == 'representative'
    assert _canon_field('owner_name') == 'owner'
    assert _canon_field('scope') == 'scope'
    assert _canon_field('jurisdiction_wide') == 'jurisdiction_wide'


def test_selection_is_reproducible_and_balanced():
    """Verify selection is reproducible and balanced."""
    first = [c['id'] for c in select_cases(cases(), seed=SEED)]
    second = [c['id'] for c in select_cases(cases(), seed=SEED)]
    assert first == second and len(first) == 15
    selected = select_cases(cases(), seed=SEED)
    counts = {}
    for case in selected:
        counts[persona_of(case)] = counts.get(persona_of(case), 0) + 1
    assert counts == {'manufacturer': 5, 'general contractor': 5, 'homebuilder': 5}
    assert len({c['topic'] for c in selected}) >= 3
    assert {c['gold']['intake_action'] for c in selected} == {'ask', 'proceed_conditionally', 'redirect'}
    listed = [line.split('`')[1] for line in (KEYS / 'SELECTION.md').read_text().splitlines() if line.startswith('| `dev-')]
    assert listed == first


def test_blank_keys_carry_the_scenario_and_no_gold():
    """Verify blank keys carry the scenario and no gold."""
    by_id = {c['id']: c for c in cases()}
    files = sorted(KEYS.glob('dev-*.json'))
    assert len(files) == 15
    for path in files:
        data = json.loads(path.read_text())
        case = by_id[data['case_id']]
        assert data['status'] == 'unverified'
        assert data['scenario'] == case['description']
        assert all(data[field] is None for field in ANSWER)
        assert 'gold' not in data and 'must_cite' not in data and 'seed_provision' not in data
        text = path.read_text()
        assert case.get('seed_provision', '___missing___') not in text
        assert key_errors(data, case) == []


def test_verified_key_requires_verifier_name_and_date():
    """Verify verified key requires verifier name and date."""
    filled = json.loads((FIXTURES / 'fake-verified.json').read_text())
    assert 'FAKE' in filled['_fixture']
    case = {'id': 'dev-901', 'description': filled['scenario'], 'applicant_type': 'homebuilder',
            'topic': 'part9-spatial-separation'}
    body = {k: v for k, v in filled.items() if k != '_fixture'}
    assert key_errors(body, case) == []
    missing = json.loads((FIXTURES / 'fake-missing-verifier.json').read_text())
    errors = key_errors({k: v for k, v in missing.items() if k != '_fixture'}, None)
    assert any('verifier name' in e for e in errors)
    assert any('verifier date' in e for e in errors)


def test_page_warning_does_not_fail_the_key(tmp_path):
    """Verify page warning does not fail the key."""
    db = tmp_path / 'codedb.sqlite'
    con = sqlite3.connect(db)
    con.execute('CREATE TABLE provisions (doc TEXT, division TEXT, id TEXT, pdf_page INT, pdf_page_end INT)')
    con.execute("INSERT INTO provisions VALUES ('NBC-AE', 'B', '9.99.99.99.(1)', 10, 12)")
    con.commit()
    key = {
        'case_id': 'dev-901',
        'expected_top_articles': [{
            'provision': '9.99.99.99.(1)', 'division': 'B',
            'citation': 'FAKE', 'page': 99,
        }],
    }
    warnings = page_warnings(key, con)
    con.close()
    assert warnings and 'warning' in warnings[0]
    errors, warns = validate_keys([], {}, db)
    assert errors == [] and warns == []


def test_scorer_uses_only_verified_keys_and_keeps_gold_separate():
    """Verify scorer uses only verified keys and keeps gold separate."""
    key = {k: v for k, v in json.loads((FIXTURES / 'fake-verified.json').read_text()).items() if k != '_fixture'}
    unverified = dict(key, case_id='dev-903', status='unverified', intake_action=None)
    system = {'dev-901': {'case_id': 'dev-901', 'intake_action': 'ask',
                          'engineer_needed': 'no',
                          'benchmark_acceptable_solution': 'FAKE acceptable solution',
                          'section_ab_required_fields': ['owner', 'municipal address'],
                          'articles': [{'provision': '9.99.99.99.(1)', 'division': 'B', 'committed': True,
                                        'probability': 0.9}]}}
    case = {'missing_info': [{'field': 'owner name'}],
            'gold': {'intake_action': 'proceed_conditionally', 'engineering_required': 'yes',
                     'departure': 'a different sentence', 'must_cite': []}}
    report = score_keys([key, unverified], system, {'dev-901': case})
    assert report['n'] == 1
    assert report['evals'] == 'human-key-filled'
    assert report['accuracy']['intake_action']['label'] == '1 of 1'
    assert report['model_grader_agreement']['intake_action']['label'] == '0 of 1'
    assert report['accuracy']['intake_action']['x'] != report['model_grader_agreement']['intake_action']['x']
    assert 'model_grader_agreement' not in report['accuracy']


def test_unfilled_directory_is_model_checked():
    """Verify unfilled directory is model checked."""
    keys = [json.loads(p.read_text()) for p in KEYS.glob('dev-*.json')]
    report = score_keys(keys, {}, {})
    blob = json.dumps(report)
    assert report['human_key'] == 'unfilled'
    assert report['evals'] == 'model-checked'
    assert report['n'] == 0
    assert report['subset'] == 'human-key'
    assert 'human-verified' not in blob
    assert 'not human verification' in report['note']


def test_calibration_sweep_counts_committed_picks():
    """Verify calibration sweep counts committed picks."""
    key = {k: v for k, v in json.loads((FIXTURES / 'fake-verified.json').read_text()).items() if k != '_fixture'}
    system = {'dev-901': {'articles': [
        {'provision': '9.99.99.99.(1)', 'division': 'B', 'probability': 0.90},
        {'provision': '9.99.99.99.(2)', 'division': 'B', 'probability': 0.80},
        {'provision': '9.99.99.99.(3)', 'division': 'B', 'probability': 0.40},
    ]}}
    report = calibrate([key], system)
    by_t = {row['threshold']: row for row in report['thresholds']}
    assert len(by_t) == 10
    assert by_t[0.75]['label'] == '1 of 2'
    assert by_t[0.75]['auto_commit_placeholder'] is True
    assert by_t[0.95]['label'] == '0 of 0'
    assert by_t[0.50]['label'] == '1 of 2'
    assert wilson_interval(1, 2) == by_t[0.75]['wilson_95']
    empty = calibrate([dict(key, status='unverified')], system)
    assert empty['human_key'] == 'unfilled' and empty['n_cases'] == 0


def test_required_field_scoring_accepts_engine_vocabulary():
    """System accuracy and gold agreement use the same A/B field aliases."""
    expected = ['owner', 'date_of_request', 'municipal_address', 'legal_description',
                'representative', 'mailing_address', 'alternative_description', 'scope']
    for fields in (list(AB_FIELDS), [name.replace('_', '-') for name in AB_FIELDS],
                   ['application_date', 'owner_rep_name', 'owner_rep_email', 'scope']):
        vocabulary = expected if len(fields) == len(AB_FIELDS) else [
            'date_of_request', 'representative', 'scope']
        key = {'case_id': 'fake-fields', 'status': 'verified', 'section_ab_required_fields': vocabulary}
        system = {'fake-fields': {'section_ab_required_fields': fields}}
        cases_by_id = {'fake-fields': {'missing_info': [{'field': name} for name in fields]}}
        report = score_keys([key], system, cases_by_id)
        for block in ('accuracy', 'model_grader_agreement'):
            assert report[block]['section_ab_required_fields']['label'] == '1 of 1'
