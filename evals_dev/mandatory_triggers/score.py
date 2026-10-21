"""Score the 12 mandatory-trigger cases on the shipped Section D screen.

The screen is not retuned to this file. Label: model-checked, not human-verified.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from engine.models import Case
from engine.professional import professional_confirmed
from engine.section_d_issues import section_d_issues
from engine.tests.case_builder_fixtures import fact
from engine.tests.test_section_d_issues import codes_with_rules

CASES_PATH = Path(__file__).with_name('cases.json')
_OCCUPANCY = {
    'residential, multiple-family dwelling': 'multi_family',
    'residential, single-family dwelling': 'single_family',
}
_SKIP_KEYS = frozenset({
    'element', 'uses', 'climate_source', 'location', 'crp_name', 'owner_grounds',
    'request', 'intake_action', 'jurisdiction', 'schedule_a_provided', 'schedule_b_provided',
})
_DROP_KEYS = frozenset({'cite', 'quote', 'act', 'citation'})
_BANNED = (
    r'\bcomplies\b', r'\bcompliant\b', r'\bcompliance\b', r'\bapproved\b', r'\bgranted\b',
    r'will be granted', r'is not needed', r'will be accepted',
    r'no professional is needed', r'no professional needed', r'no engineer needed',
)
_FIRE_PROVISION = {
    'HR-05': '9.23.3.5.(4)',
    'HR-06': '9.15.3.3.(2)',
    'HR-07': '9.24.1.1.(2)',
}


def load_cases(path: Path | None = None) -> dict:
    return json.loads((path or CASES_PATH).read_text())


def case_from_facts(raw: dict) -> Case:
    """Map one fixture input onto the fact names the shipped screen already reads."""
    facts = []
    provisions: list[str] = []
    for key, value in raw.items():
        if value is None or key in _SKIP_KEYS:
            continue
        if key == 'occupancy':
            facts.append(fact('occupancy', _OCCUPANCY.get(value, value)))
        elif key == 'dwelling_units':
            facts.append(fact('principal_dwelling_units', value))
        elif key == 'truss_unsupported_span_m':
            facts.append(fact('unsupported_span_m', value))
        elif key == 'structural_elements':
            text = value[0] if isinstance(value, list) and len(value) == 1 else value
            if isinstance(text, str):
                facts.append(fact('structural_elements', text))
        elif key == 'provisions_varied':
            for item in value:
                if '3.8' in item:
                    provisions.append('3.8.1.1.(1)')
                elif '3.1.9.1.(1)' in item:
                    provisions.append('3.1.9.1.(1)')
        elif key == 'scope':
            facts.append(fact('variance_scope', value))
        elif key == 'variance_requested':
            facts.append(fact('variance_requested', bool(value)))
        else:
            facts.append(fact(key, value))
    return Case(provisions=provisions, facts=facts)


def _ids(issue) -> list[str]:
    return [row.trigger_id for row in issue.human_review]


def _cites(issue, trigger_id: str | None = None) -> list[str]:
    rows = issue.human_review
    if trigger_id is not None:
        rows = [row for row in rows if row.trigger_id == trigger_id]
    return [row.cite for row in rows]


def _scanned(issue) -> str:
    payload = issue.model_dump()

    def drop(node):
        if isinstance(node, dict):
            return {key: drop(value) for key, value in node.items() if key not in _DROP_KEYS}
        if isinstance(node, list):
            return [drop(value) for value in node]
        return node

    return json.dumps(drop(payload))


def must_not_failures(test: dict, issue, case: Case) -> list[str]:
    """Compliance language, an officer yes or no, or a closed professional gap."""
    failures = []
    scanned = _scanned(issue)
    for pattern in _BANNED:
        if re.search(pattern, scanned, re.I):
            failures.append(pattern)
    value = issue.practice_of_engineering.value
    if test['trigger'] in {'HR-30', 'HR-32'} and value is not None and value != 'unknown':
        failures.append('officer-side yes/no')
    if issue.status == 'evidence_listed' or (
            value is True and issue.status != 'needs_professional'):
        failures.append('needs_professional closed without a confirmed role and seal or number')
    if issue.status == 'needs_professional' and professional_confirmed(case):
        failures.append('needs_professional closed without a confirmed role and seal or number')
    if value is False:
        failures.append('final ruling that a professional is not required')
    return failures


def outcome(test: dict, issue) -> tuple[bool, str]:
    """Whether this fire or near-miss matches the shipped screen. See NOTES.md."""
    trigger = test['trigger']
    kind = test['kind']
    present = trigger in _ids(issue)
    cites = ' '.join(_cites(issue))
    value = issue.practice_of_engineering.value
    if trigger in _FIRE_PROVISION:
        provision = _FIRE_PROVISION[trigger]
        fired = present and any(provision in cite for cite in _cites(issue, trigger))
        if kind == 'fires':
            ok = fired and value is True and issue.status == 'needs_professional'
            return ok, f'{trigger} {"cited " + provision if fired else "absent"}; status {issue.status}'
        ok = not present and value is not True
        return ok, f'{trigger} {"absent" if not present else "still present"}'
    if trigger == 'HR-02':
        schedules = '2.4.2.2.(1)' in cites
        authentication = '2.4.1.1.(3)' in cites
        if kind == 'fires':
            ok = schedules and authentication and value is True and issue.status == 'needs_professional'
            return ok, f'2.4.1.1.(3) {"in" if authentication else "not in"} cites; 2.4.2.2.(1) {"in" if schedules else "not in"} cites'
        ok = not present and not schedules
        return ok, 'HR-02 absent' if ok else 'HR-02 or the schedules sentence is present'
    if trigger == 'HR-30':
        site = 'Safety Codes Act s.38(1)' in cites
        province = '2.2.1.2.(1)' in cites
        routed = issue.routed_to == 'officer' and value == 'unknown'
        if kind == 'fires':
            ok = site and routed and issue.status == 'open'
            return ok, f'site row {"present" if site else "absent"}; value {value}; routed {issue.routed_to}'
        ok = province and not site and routed
        return ok, f'province cite {"present" if province else "absent"}; site row {"present" if site else "absent"}'
    # HR-32. Routing is the pass. The discretionary id is not a human-review row.
    routed = issue.routed_to == 'officer' and value == 'unknown'
    if kind == 'fires':
        ok = routed and not present and issue.status != 'needs_professional'
        return ok, f'routed {issue.routed_to}; value {value}; HR-32 {"present" if present else "absent"}'
    site = 'Safety Codes Act s.38(1)' in cites
    ok = routed and not present and site
    return ok, f'HR-32 {"absent" if not present else "present"}; site row {"present" if site else "absent"}'


def score_cases(payload: dict | None = None) -> list[dict]:
    payload = payload or load_cases()
    codes = codes_with_rules()
    rows = []
    for test in payload['cases']:
        case = case_from_facts(test['input_facts'])
        issue = section_d_issues(case, codes)[0]
        passed, detail = outcome(test, issue)
        failures = must_not_failures(test, issue, case)
        rows.append({
            'id': test['id'],
            'trigger': test['trigger'],
            'kind': test['kind'],
            'pass': passed and not failures,
            'outcome': passed,
            'must_not': not failures,
            'must_not_failures': failures,
            'detail': detail,
            'value': issue.practice_of_engineering.value,
            'status': issue.status,
            'routed_to': issue.routed_to,
            'triggers': _ids(issue),
        })
    return rows


def report(rows: list[dict] | None = None) -> str:
    rows = rows if rows is not None else score_cases()
    lines = [
        'label: model-checked, not human-verified',
        'trigger  kind       outcome  must_not  detail',
    ]
    for row in rows:
        lines.append(
            f"{row['trigger']}  {row['kind']:<9}  {'pass' if row['outcome'] else 'fail':<7}  "
            f"{'pass' if row['must_not'] else 'FAIL':<8}  {row['detail']}")
    outcome_pass = sum(row['outcome'] for row in rows)
    must_pass = sum(row['must_not'] for row in rows)
    lines.append(f'outcome {outcome_pass}/{len(rows)}  must_not {must_pass}/{len(rows)}')
    return '\n'.join(lines)


def main() -> None:
    print(report())


if __name__ == '__main__':
    main()
