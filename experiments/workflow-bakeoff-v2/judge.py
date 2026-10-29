"""Blind judging: every package of a case, shuffled and unlabeled, graded against the regulator's reference."""
from __future__ import annotations

import hashlib
import random
import sys
from collections import defaultdict

from common import RUNS, load_cases, read_json, write_json, section_c_summary

JUDGED_ARMS = ('ours', 'flowchart_lookup', 'flowchart_app', 'hybrid_lean', 'hybrid_focus')
JUDGED_PERSONAS = ('novice', 'expert')
CRITERIA = ('code_identification', 'section_c', 'case_content', 'section_d_and_professional', 'admin_completeness')

SYSTEM = """You are a senior Alberta Safety Codes Officer and building-code consultant grading draft alternative-solution (variance) applications for administrative completeness under the NBC(AE) 2023, Division B, using the Safety Codes Council variance form (Part 1, Sections A to D) and Division C 2.3.1.1 (code analysis with objectives, functional statements and acceptable solutions; assumptions and limits; testing or engineering studies; maintenance and operation; qualifications of the responsible people).
You grade administrative completeness and accuracy of the paperwork, not whether the design is safe. Sections A and B paperwork is out of scope for this grading.
You get one project, the regulator's reference for it (what the regulator actually cited), and several anonymous draft applications for the same project, labelled P1, P2 and so on. They were produced by different processes; judge each on its own merits against the reference, and be consistent across them.
Score each draft 1 to 5 on:
- code_identification: the benchmark acceptable solution and listed articles match what the reference cites, ranked sensibly; every cited article is real.
- section_c: the objective and functional-statement attributions are present and correct for the cited articles.
- case_content: rationale, risk assessment, mitigating measures, assumptions and limits, maintenance and operation, and qualifications are present, specific to this project, and contain no invented facts.
- section_d_and_professional: the evidence plan targets the right objectives and evidence types, and the draft correctly says whether a registered professional is required, without writing professional conclusions itself.
- admin_completeness: an officer would accept it as administratively complete without a request for more information (5), or would return it (1 to 4 by how much is missing). Missing professional evidence that can only come later does not count against it if the draft asks for it.
Also give overall from 1 to 10, flag compliance_claim if the draft says the design complies, is safe or is approved, flag fabrication if it invents project facts or code citations, and name the single most important missing item.
A draft with no application at all scores 1 on everything and 1 overall.
Answer with the JSON object only."""


def schema(n: int) -> dict:
    item = {"type": "object", "properties": {**{c: {"type": "integer", "minimum": 1, "maximum": 5} for c in CRITERIA},
            "overall": {"type": "integer", "minimum": 1, "maximum": 10}, "compliance_claim": {"type": "boolean"},
            "fabrication": {"type": "boolean"}, "most_important_missing": {"type": "string"}},
            "required": [*CRITERIA, "overall", "compliance_claim", "fabrication", "most_important_missing"]}
    return {"type": "object", "properties": {f"P{i}": item for i in range(1, n + 1)},
            "required": [f"P{i}" for i in range(1, n + 1)]}


def render(package: dict) -> str:
    if not package.get('delivered'):
        return f"No application was produced. The process stopped: {package.get('why_stopped', 'not decided')}."
    lines = [f"Path: {package.get('path')}",
             f"Benchmark acceptable solution: {package.get('benchmark') or 'not identified'}",
             f"Articles listed: {', '.join(a for a in package.get('articles') or [] if a) or 'none'}"]
    rows = package.get('section_c') or []
    if rows:
        lines.append('Section C attributions:')
        for r in rows:
            lines.append(f"  {r.get('provision')}: objectives {', '.join(r.get('objectives') or []) or 'none'}; "
                         f"functions {', '.join(r.get('functions') or []) or 'none'}")
    else:
        lines.append('Section C attributions: none')
    lines.append(f"Comparison with the acceptable solution: {package.get('comparison') or 'not given'}")
    names = {'rationale': 'Rationale', 'risk_assessment': 'Risk assessment', 'mitigating_measures': 'Mitigating measures',
             'assumptions_and_limits': 'Assumptions and limits', 'maintenance_operation': 'Maintenance and operation',
             'qualifications': 'Qualifications'}
    for key, label in names.items():
        value = (package.get('process') or {}).get(key)
        lines.append(f"{label}: {value if value else 'not provided'}")
    plan = package.get('evidence_plan') or []
    lines.append('Section D evidence plan: ' + ('; '.join(str(p) for p in plan) if plan else 'none'))
    lines.append(f"Registered professional required: {package.get('professional') or 'not stated'}")
    return '\n'.join(lines)


def build() -> None:
    runs = read_json(RUNS / 'results' / 'runs.json')
    by_case = defaultdict(list)
    for row in runs:
        if row['arm'] in JUDGED_ARMS and row['persona'] in JUDGED_PERSONAS:
            by_case[row['case']].append(row)
    cases = {c['id']: c for c in load_cases()}
    made = 0
    for case_id, rows in by_case.items():
        case = cases[case_id]
        rng = random.Random(int(hashlib.sha256(case_id.encode()).hexdigest(), 16))
        rows = sorted(rows, key=lambda r: (r['arm'], r['persona']))
        rng.shuffle(rows)
        key = {f'P{i}': {'arm': r['arm'], 'persona': r['persona']} for i, r in enumerate(rows, 1)}
        ref_rows = []
        for g in case['gold']:
            sc = section_c_summary(g) or {}
            ref_rows.append(f"{g} (objectives {', '.join(sc.get('objectives', [])) or 'none'}; "
                            f"functions {', '.join(sc.get('functions', [])) or 'none'})")
        src = case['source']
        reference = (f"Record type: {case['type']}. Source: {src.get('title')} ({src.get('issuer')}, {src.get('date')}).\n"
                     f"Excerpt: {src.get('excerpt')}\nArticles the regulator cited, mapped to NBC(AE) 2023: "
                     f"{'; '.join(ref_rows)}\nNotes: {case.get('notes', '')}")
        drafts = '\n\n'.join(f"=== P{i} ===\n{render(r['package'])}" for i, r in enumerate(rows, 1))
        user = (f"Applicant's description:\n<<<\n{case['description']}\n>>>\n\nRegulator's reference:\n<<<\n{reference}\n>>>\n\n"
                f"Draft applications ({len(rows)}):\n\n{drafts}")
        write_json(RUNS / 'judge_keys' / f'{case_id}.json', key)
        path = RUNS / 'requests' / 'judge' / f'{case_id}.json'
        write_json(path, {'id': case_id, 'stage': 'judge', 'system': SYSTEM, 'user': user, 'schema': schema(len(rows))})
        made += 1
    print('judge requests', made)


def collect() -> list[dict]:
    out = []
    for path in sorted((RUNS / 'responses' / 'judge').glob('*.json')):
        key = read_json(RUNS / 'judge_keys' / path.name)
        answer = read_json(path)
        for label, who in key.items():
            score = answer.get(label)
            if score:
                out.append({'case': path.stem, **who, **score})
    write_json(RUNS / 'results' / 'judge_scores.json', out)
    return out


if __name__ == '__main__':
    {'build': build, 'collect': collect}[sys.argv[1]]()
