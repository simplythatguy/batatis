"""Section D issues recommend evidence. They do not certify a design or invent a citation."""
import json
import re
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from engine.api import create_app
from engine.models import Case, Source
from engine.section_d import ALTERNATIVE_EVIDENCE_TYPES, CONFIDENCE_LADDER
from engine.section_d_flag_eval import RULE_IDS, main
from engine.section_d_issues import PROCESS_RULES, PROFESSIONAL_RULES, section_d_issues
from engine.store import CaseStore
from engine.tests.case_builder_fixtures import fact

# Recommendation text must not claim compliance or safety. Objective titles from the
# code ("Safety") are not copied into these strings; the test scans the whole payload.
CLAIM_PHRASES = (
    r'\bcomplies\b', r'\bcompliant\b', r'\bcompliance\b', r'\bsafe\b', r'\bsafety\b',
    r'meets the code', r'meets code', r'satisfies the code', r'\bwe conclude\b',
    r'has been approved', r'\bis approved\b', r'performance is achieved',
    r'equivalent performance is', r'design is acceptable', r'this design complies',
)

BENCHMARK = '9.10.15.5.(8)'
NO_ROW = '9.10.14.2.(1)'
UNKNOWN = '9.99.99.99.(1)'


class FakeCodes:
    """In-memory stand-in. Every citation string is recorded when it is handed out."""

    def __init__(self):
        """Initialize empty in-memory rule rows and issued-citation tracking."""
        self.rows = {}
        self.issued: set[str] = set()

    def add(self, division, provision_id, **extra):
        """Register a synthetic provision row and return this fixture for chaining."""
        citation = extra.pop('citation', f'fixture:{division}:{provision_id}')
        row = {'id': provision_id, 'division': division, 'citation': citation, 'level': 'sentence',
               'children': [], 'attributions': [], 'attribution_status': {'status': 'none', 'root_provision': None,
               'root_method': None}, 'intents': [], 'intent_comparison': []}
        row.update(extra)
        self.rows[(division, provision_id)] = row
        return self

    def provision(self, provision_id, division='B'):
        """Resolve a fixture row and record any citation returned to the caller."""
        row = self.rows.get((division, provision_id))
        if row:
            self.issued.add(row['citation'])
        return row

    def citation(self, provision_id, division='B'):
        """Return a resolved fixture citation, or None for an unknown provision."""
        row = self.provision(provision_id, division)
        return row['citation'] if row else None

    def definition(self, code):
        """Supply no definition text for these recommendation-only fixture checks."""
        return None


def codes_with_rules():
    """Build declared rule fixtures plus benchmarks with and without attribution rows."""
    codes = FakeCodes()
    for division, provision_id in RULE_IDS:
        codes.add(division, provision_id)
    codes.add('B', BENCHMARK, attribution_status={'status': 'direct', 'root_provision': None, 'root_method': None},
              attributions=[{'bracket': '[F03-OP3.1]', 'clauses': [], 'application_note': None,
                             'table_id': 'Table 9.38.1.1.', 'pdf_page': 1, 'fs': ['F03'], 'objectives': ['OP3.1']}])
    codes.add('B', NO_ROW)
    return codes


def _strings(payload):
    """Walk nested response values and yield each string for claim scanning."""
    if isinstance(payload, str):
        yield payload
    elif isinstance(payload, dict):
        for value in payload.values():
            yield from _strings(value)
    elif isinstance(payload, list):
        for value in payload:
            yield from _strings(value)


def _citations(payload):
    """Walk nested response objects and yield only citation field values."""
    if isinstance(payload, dict):
        for key, value in payload.items():
            if key == 'citation' and isinstance(value, str):
                yield value
            else:
                yield from _citations(value)
    elif isinstance(payload, list):
        for value in payload:
            yield from _citations(value)


def _house_facts():
    """Provide confirmed single-family facts that resolve all professional component questions."""
    values = dict(occupancy='single_family', part4_design=False, preserved_wood_foundation_part4=False,
                  roof_trusses=False, prescriptive_route_confirmed=True, ahj_requires_professional=False,
                  special_safety_concerns=False, professional_judgement_required=False,
                  professional_scope_resolved=True, fire_suppression=False, fire_alarm=False)
    return [fact(key, value) for key, value in values.items()]


def test_confirmed_provision_recommends_ladder_and_lists_empty_process_fields():
    """Verify confirmed provision recommends ladder and lists empty process fields."""
    codes = codes_with_rules()
    issue = section_d_issues(Case(provisions=[BENCHMARK]), codes)[0]
    assert issue.provision.provision_id == BENCHMARK and issue.provision.citation == codes.rows[('B', BENCHMARK)]['citation']
    assert issue.objective == 'OP3.1' and issue.function == 'F03'
    assert issue.recommended_evidence_types == CONFIDENCE_LADDER + ALTERNATIVE_EVIDENCE_TYPES
    empty = [field.id for field in issue.empty_process_fields]
    assert {'risk_assessment', 'mitigating_measures', 'assumptions_and_limits'} <= set(empty)
    assert not set(empty) & set(issue.recommended_evidence_types)
    assert issue.status == 'open' and issue.practice_of_engineering.value == 'unknown'
    assert issue.practice_of_engineering.question


def test_unknown_reference_has_no_citation_and_missing_attribution_asks():
    """Verify unknown reference has no citation and missing attribution asks."""
    codes = codes_with_rules()
    issues = section_d_issues(Case(provisions=[UNKNOWN, NO_ROW]), codes)
    missing = next(issue for issue in issues if issue.entered_reference == UNKNOWN)
    assert missing.provision is None and missing.question
    assert UNKNOWN not in ''.join(_citations(missing.model_dump()))
    assert not re.search(r'NBC\(AE\).{0,80}' + re.escape(UNKNOWN), missing.model_dump_json())
    blank = next(issue for issue in issues if issue.provision and issue.provision.provision_id == NO_ROW)
    assert blank.objective is None and blank.function is None and blank.question
    assert blank.provision.citation == codes.rows[('B', NO_ROW)]['citation']


def test_no_issue_text_claims_compliance_or_safety_and_citations_stay_inside_codedb():
    """Verify no issue text claims compliance or safety and citations stay inside codedb."""
    codes = codes_with_rules()
    cases = [
        Case(provisions=[BENCHMARK, UNKNOWN, NO_ROW]),
        Case(provisions=[BENCHMARK], facts=[fact('part4_design', True)]),
        Case(provisions=[BENCHMARK], facts=_house_facts()),
        Case(provisions=[BENCHMARK], facts=[fact('span_m', 18)]),
        Case(provisions=[BENCHMARK], facts=[fact('pathway', 'acceptable')]),
    ]
    for case in cases:
        payload = [issue.model_dump() for issue in section_d_issues(case, codes)]
        blob = json.dumps(payload)
        for pattern in CLAIM_PHRASES:
            assert re.search(pattern, blob, re.I) is None, pattern
        for citation in _citations(payload):
            assert citation in codes.issued
        assert 'NBC(AE)' not in blob


def test_span_is_part4_and_cites_only_the_existing_division_c_rule():
    """Verify span is part4 and cites only the existing division c rule."""
    codes = codes_with_rules()
    issue = section_d_issues(Case(provisions=[BENCHMARK], facts=[fact('span_m', 18)]), codes)[0]
    assert issue.practice_of_engineering.value is True
    assert issue.practice_of_engineering.rule == '2.4.1.2.(1)'
    assert issue.practice_of_engineering.citation == 'fixture:C:2.4.1.2.(1)'
    assert issue.practice_of_engineering.citation in codes.issued
    assert '9.23.1.1' not in issue.model_dump_json()


def test_status_addressed_by_applicant_item_and_needs_professional_without_one():
    """Verify status addressed by applicant item and needs professional without one."""
    codes = codes_with_rules()
    bare = section_d_issues(Case(provisions=[BENCHMARK], facts=[fact('part4_design', True)]), codes)[0]
    assert bare.status == 'needs_professional' and bare.practice_of_engineering.value is True
    assert bare.practice_of_engineering.division == 'C' and bare.practice_of_engineering.citation in codes.issued
    file = Source(type='file', ref='applicant-report.pdf', quote='Applicant report metadata.')
    case = Case(provisions=[BENCHMARK], facts=[fact('part4_design', True)])
    case.facts += [fact(f'evidence.{bare.id}.file_ref', file.ref, source=file),
                   fact(f'evidence.{bare.id}.responsible_party', 'Named applicant professional')]
    supplied = section_d_issues(case, codes)[0]
    assert supplied.status == 'addressed' and supplied.practice_of_engineering.value is True
    house = section_d_issues(Case(provisions=[BENCHMARK], facts=_house_facts()), codes)[0]
    assert house.practice_of_engineering.value is False and house.status == 'open'
    assert house.practice_of_engineering.citation in codes.issued
    from types import SimpleNamespace
    from engine.section_d_issues import PracticeOfEngineering, _status
    unknown = PracticeOfEngineering(value='unknown', reason='missing fact', question='Which occupancy applies?')
    linked = [SimpleNamespace(responsible_party='Named person', professional_seal=None)]
    assert _status(unknown, linked) == 'open'


def test_acceptable_path_drops_variance_process_fields_and_extra_evidence_types():
    """Verify acceptable path drops variance process fields and extra evidence types."""
    case = Case(provisions=[BENCHMARK], facts=[fact('pathway', 'acceptable')])
    issue = section_d_issues(case, codes_with_rules())[0]
    assert issue.empty_process_fields == ()
    assert issue.recommended_evidence_types == CONFIDENCE_LADDER


@pytest.mark.parametrize('named', [False, True])
def test_unknown_practice_stays_open_with_applicant_attachment(tmp_path, named):
    """Supplying a document cannot resolve an unknown practice flag in the API."""
    codes = codes_with_rules()
    case = Case(provisions=[BENCHMARK])
    issue = section_d_issues(case, codes)[0]
    file = Source(type='file', ref='applicant-report.pdf', quote='Applicant report metadata.')
    case.facts.append(fact(f'evidence.{issue.id}.file_ref', file.ref, source=file))
    if named:
        case.facts.append(fact(f'evidence.{issue.id}.responsible_party', 'Named professional'))
    store = CaseStore(tmp_path / 'cases.sqlite')
    store.put(case)
    response = TestClient(create_app(store, codes)).get(f'/cases/{case.id}/section-d/issues')
    assert response.status_code == 200
    supplied = response.json()[0]
    assert supplied['practice_of_engineering']['value'] == 'unknown'
    assert supplied['status'] == 'open'


def test_known_nonprofessional_flag_is_addressed_by_an_attachment():
    """A resolved negative flag still allows an applicant attachment to address the issue."""
    codes = codes_with_rules()
    case = Case(provisions=[BENCHMARK], facts=_house_facts())
    issue = section_d_issues(case, codes)[0]
    file = Source(type='file', ref='applicant-report.pdf', quote='Applicant report metadata.')
    case.facts.append(fact(f'evidence.{issue.id}.file_ref', file.ref, source=file))
    supplied = section_d_issues(case, codes)[0]
    assert supplied.practice_of_engineering.value is False
    assert supplied.status == 'addressed'


def test_no_benchmark_asks_and_does_not_invent_a_provision():
    """Verify no benchmark asks and does not invent a provision."""
    issue = section_d_issues(Case(), codes_with_rules())[0]
    assert issue.provision is None and issue.question and issue.status == 'open'


def test_route_is_read_only_and_missing_case_is_404(tmp_path):
    """Verify route is read only and missing case is 404."""
    store = CaseStore(tmp_path / 'cases.sqlite')
    client = TestClient(create_app(store, codes_with_rules()))
    assert client.get('/cases/missing/section-d/issues').status_code == 404
    case = store.put(Case(provisions=[BENCHMARK, UNKNOWN]))
    before = store.get(case.id).model_dump_json()
    response = client.get(f'/cases/{case.id}/section-d/issues')
    assert response.status_code == 200
    body = response.json()
    assert body[0]['entered_reference'] == UNKNOWN and body[0]['provision'] is None
    assert body[1]['provision']['citation']
    assert store.get(case.id).model_dump_json() == before


def test_rule_table_uses_only_provisions_already_in_the_repo():
    """Verify rule table uses only provisions already in the repo."""
    professional = Path('engine/professional.py').read_text()
    process = Path('engine/process_fields.py').read_text()
    for _division, provision_id, source in (*PROFESSIONAL_RULES, *PROCESS_RULES):
        if source.startswith('engine/professional.py'):
            assert provision_id in professional, provision_id
        elif source.startswith('engine/process_fields.py'):
            assert provision_id in process, provision_id
        else:
            raise AssertionError(source)
    for path in ('engine/section_d_issues.py', 'engine/section_d_flag_eval.py', 'docs/api-contract.md'):
        assert '9.23.1.1' not in Path(path).read_text()


def test_eval_script_prints_in_sample_wilson_table(capsys):
    """Verify eval script prints in sample wilson table."""
    assert main() == 0
    out = capsys.readouterr().out
    assert out.startswith(
        'Engineer-needed flag, rules_only baseline: 55/60 agreement on the model-checked dev set (in-sample), '
        '1 under-flag, 13 unknowns sent to the applicant.\n')
    assert 'gold: model-checked' in out
    assert 'split: dev (in-sample; pending out-of-sample confirmation)' in out
    assert 'rules_plus_unknown on this dev table is in-sample and pending out-of-sample confirmation' in out
    assert 'out_of_sample: evals_dev/appeals (built on another branch; not scored here)' in out
    assert 'held-out: evals_dev/section_d_heldout' in out
    assert 'held-out gold: model-checked' in out
    assert 'held-out rules_only: 6/8 [0.4093, 0.9285]' in out
    assert 'held-out rules_plus_unknown: 7/8 [0.5291, 0.9776]' in out
    assert 'held-out always_unknown: 1/8 [0.0224, 0.4709]' in out
    assert 'held-out misses rules_plus_unknown: hold-004 gold=depends system=no' in out
    assert 'dev-050' in Path('engine/section_d_flag_eval.py').read_text()
    assert 'winner: rules_plus_unknown' in out
    assert 'under_flag_target: 0' in out
    assert 'note: rules_only abstains with depends; that label is counted in the unknown column' in out
    plus = next(line for line in out.splitlines() if line.startswith('rules_plus_unknown'))
    assert '60/60 [' in plus and ', 1.0]' in plus
    assert re.search(r'\]\s+0\s+17\s+0\s*$', plus)
    only = next(line for line in out.splitlines() if line.startswith('rules_only '))
    assert '55/60 [' in only
    assert re.search(r'\]\s+1\s+13\s+0\s*$', only)
    baseline = next(line for line in out.splitlines() if line.startswith('always_unknown'))
    assert '17/60 [' in baseline
    assert re.search(r'\]\s+0\s+60\s+0\s*$', baseline)
    assert 'unknown_rate rules_only: 13/60 [' in out
    assert 'unknown_rate rules_plus_unknown: 17/60 [' in out
    assert 'unknown_rate always_unknown: 60/60 [' in out and ', 1.0]' in out
    assert 'confident_wrong rules_only: 5/60 [' in out
    assert 'confident_wrong rules_plus_unknown: 0/60 [' in out
    assert 'confident_wrong always_unknown: 0/60 [' in out
    assert 'confusion rules_only  rows=gold  columns=system yes unknown no' in out
    assert 'confusion rules_plus_unknown  rows=gold  columns=system yes unknown no' in out
    assert 'confusion always_unknown  rows=gold  columns=system yes unknown no' in out
    assert re.search(r'confusion rules_only.*\n  yes\s+32\s+0\s+1\n  depends\s+0\s+13\s+4\n  no\s+0\s+0\s+10\n', out)
    assert re.search(
        r'confusion rules_plus_unknown.*\n  yes\s+33\s+0\s+0\n  depends\s+0\s+17\s+0\n  no\s+0\s+0\s+10\n', out)
    assert re.search(
        r'confusion always_unknown.*\n  yes\s+0\s+33\s+0\n  depends\s+0\s+17\s+0\n  no\s+0\s+10\s+0\n', out)
    assert 'gold_yes_as_unknown rules_plus_unknown: none' in out
    assert 'gold_yes_as_unknown rules_only: none' in out
    assert 'gold_yes_as_unknown always_unknown: dev-002' in out
    assert 'under_flag rules_only: dev-050:' in out
    assert 'span_m=18' in out
    assert 'under_flag rules_plus_unknown: none' in out
    assert 'under_flag always_unknown: none' in out


def test_heldout_gold_was_written_from_repo_limits():
    """Verify heldout gold was written from repo limits."""
    folder = Path('evals_dev/section_d_heldout')
    cases = [json.loads(path.read_text()) for path in sorted(folder.glob('hold-*.json'))]
    assert len(cases) == 8
    expected = {
        'hold-001': 'no', 'hold-002': 'yes', 'hold-003': 'no', 'hold-004': 'depends',
        'hold-005': 'yes', 'hold-006': 'yes', 'hold-007': 'no', 'hold-008': 'no',
    }
    for case in cases:
        assert case['gold']['engineering_required'] == expected[case['id']]
        source = case['gold']['limit_source']
        assert 'engine/professional.py' in source or 'PART9_MAX_SPAN_M' in source
        assert '9.23.1.1' not in json.dumps(case)
        assert case['authoring']['gold_written'] == 'before any system run'
        assert case['authoring']['label'] == 'model-checked'


def test_claim_blocklist_matches_compliance_and_safety_claims():
    """Verify claim blocklist matches compliance and safety claims."""
    sample = 'The design complies, is safe, meets the code, and performance is achieved.'
    assert any(re.search(pattern, sample, re.I) for pattern in CLAIM_PHRASES)
    assert re.search(r'\bsafe\b', 'is safe', re.I) and re.search(r'\bcompliance\b', 'compliance', re.I)
