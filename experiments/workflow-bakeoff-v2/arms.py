"""Assemble each workflow's final application from the same inputs, then count friction and score quality.

Every arm reads the same case, the same stage-0 engine output, the same model responses and the same
simulated applicant. Arms differ only in what they ask the applicant and what the app does itself.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from common import article_of, codes, is_division_b, normalize_pid, section_c_summary, article_text
from engine.intake.review import sentences, verdict
from requests import DRAFT_FIELDS

UNKNOWN = re.compile(r"^\s*(i\s*don'?t\s*know|not\s*sure|unknown|n/?a)\b", re.I)
CLAIM = re.compile(r'\b(complies|compliant with|is safe|are safe|meets the (?:code|requirements?)|'
                   r'is approved|will be approved|equivalent performance is (?:demonstrated|achieved)|'
                   r'performs (?:at least )?as well as|provides equal or better)\b', re.I)
PROCESS_Q = {'rationale': 'rationale', 'risk_assessment': 'risk', 'mitigating_measures': 'mitigation',
             'assumptions_and_limits': 'assumptions', 'maintenance_operation': 'maintenance',
             'qualifications': 'qualifications'}
SHARED_LADDER = ("manufacturer's literature", 'existing STANDATA variance', 'ISO 17025 test report', 'evaluation',
                 'evaluation + testing', 'qualification', 'ISO 17065 certification')
ALT_TYPES = ('CCMC evaluation', 'ICC-ES evaluation', 'registered professional opinion', 'engineering review')
FLOWCHART_EVIDENCE = ("manufacturer's published literature", 'existing STANDATA variance', 'test report (ISO 17025 lab)',
                 'evaluation', 'evaluation + testing (ISO 17025 lab)', 'qualification',
                 'certification (ISO 17065 body)', 'registered professional opinion', 'engineering review',
                 'CCMC listing', 'ICC-ES acceptance criteria', 'code conformity assessment (ISO 17065 body)')
# Minutes per input; stated assumptions, reported beside the raw counts.
MINUTES = {'confirm': 0.25, 'choice': 0.5, 'fact': 0.5, 'review': 1.0, 'essay': 4.0, 'expert': 6.0}
SKIP_MINUTES = 0.5          # reading a question you can't answer and moving on


def unknown(answer) -> bool:
    if isinstance(answer, list):
        return not answer
    return not str(answer or '').strip() or bool(UNKNOWN.match(str(answer)))


GUIDANCE = re.compile(r'^\s*(?:the application|it|this field|the applicant|the designer|the engineer)\s+'
                      r'(?:should|must|needs? to|will need to)\b', re.I)


def substantive(text) -> bool:
    """Content an officer can read as the applicant's statement, not only a prompt about what to write."""
    if unknown(text):
        return False
    sentences = [x for x in re.split(r'(?<=[.!?])\s+', str(text).strip()) if x]
    return any(not GUIDANCE.match(x) for x in sentences)


def words(answer) -> int:
    if isinstance(answer, list):
        return len(answer)
    return 0 if unknown(answer) else len(str(answer).split())


@dataclass
class Run:
    arm: str
    persona: str
    inputs: list[dict] = field(default_factory=list)
    package: dict = field(default_factory=dict)
    package_drafts: dict = field(default_factory=dict)
    diamond_guessed: bool = False

    def ask(self, stage: str, kind: str, answer=None, typed: bool = False) -> object:
        self.inputs.append({'stage': stage, 'kind': kind, 'unknown': unknown(answer) if answer is not None else False,
                            'words': words(answer) if typed else 0})
        return answer


def valid_picks(case: dict, s0: dict, r1: dict | None) -> list[dict]:
    """R1 picks that are pool articles, real Division B articles, with a quote found in the article text."""
    out, seen = [], set()
    for pick in (r1 or {}).get('picks', []):
        pid = article_of(normalize_pid(pick.get('id', '')))
        if pid in seen or pid not in s0['pool'] or not is_division_b(pid):
            continue
        quote = _norm(pick.get('quote', ''))
        if len(quote) < 12 or quote not in _norm(article_text(pid, None)):
            continue
        seen.add(pid)
        out.append({'id': pid, 'quote': pick.get('quote', ''), 'reason': pick.get('reason', '')})
    return out


def _norm(text: str) -> str:
    text = re.sub(r'[‘’]', "'", text or '')
    text = re.sub(r'[“”]', '"', text)
    return re.sub(r'\s+', ' ', text).strip().lower().rstrip('.')


def ids_in(answer) -> list[str]:
    items = answer if isinstance(answer, list) else re.findall(r'\d{1,2}\.\d{1,2}\.\d{1,2}\.\d{1,2}\.?(?:\(\d+\))*', str(answer or ''))
    out = []
    for item in items:
        m = re.search(r'\d{1,2}\.\d{1,2}\.\d{1,2}\.\d{1,2}\.?(?:\(\d+\))*', str(item))
        if m:
            out.append(normalize_pid(m.group(0)))
    return list(dict.fromkeys(out))


def lookup_rows(pids: list[str]) -> list[dict]:
    rows = []
    for pid in pids:
        sc = section_c_summary(pid)
        if sc is not None:
            rows.append({**sc, 'source': 'lookup'})
    return rows


def expert_pick(case: dict, shown: list[str], persona: dict) -> tuple[str | None, bool]:
    """An expert shown candidates keeps a referenced one; otherwise searches the library for their own answer."""
    gold = set(case['gold'])
    hit = next((p for p in shown if p in gold), None)
    if hit:
        return hit, False
    own = ids_in(persona.get('benchmark_article'))
    own = [article_of(p) for p in own if is_division_b(article_of(p))]
    return (own[0] if own else (shown[0] if shown else None)), True


def drafts_for(r2: dict | None) -> dict:
    return {f: ((r2 or {}).get('drafts') or {}).get(f) or {'text': '', 'open_questions': []} for f in DRAFT_FIELDS}


def professional_flag(desc_case, provisions: list[str]) -> str:
    from engine.professional import professional_involvement
    try:
        return professional_involvement(desc_case, codes(), provisions=tuple(provisions)).required
    except Exception:
        return 'depends'


# ---------------------------------------------------------------------------------------------- arms

def ours(case, s0, r1, r2, persona, kind, shell) -> Run:
    run = Run('ours', kind)
    run.ask('understood', 'confirm')
    for i, q in enumerate(s0['planner']):
        answers = persona.get('planner_answers') or []
        run.ask('planner', 'fact', answers[i] if i < len(answers) else "I don't know", typed=True)
    path = s0['path']['path']
    if path == 'not_applicable':
        return _dead(run, 'not_applicable', 'A coded rule that does not apply stopped the path; a firm check outranks a variance request.')
    if path == 'redirect':
        run.ask('scope', 'confirm', 'yes')            # "It is a building-code question" override
        path = 'unresolved'
    if path == 'unresolved':
        run.ask('route', 'choice', persona.get('meets_acceptable_solution'))
        path = 'acceptable' if persona.get('meets_acceptable_solution') == 'yes' else 'alternative'
    shown = s0['prod_rank'][:3]
    if kind == 'novice':
        benchmark = run.ask('benchmark', 'choice', shown[0] if shown else None)
        searched = False
    else:
        benchmark, searched = expert_pick(case, shown, persona)
        run.ask('benchmark', 'expert' if searched else 'choice', benchmark)
    run.ask('departure', 'essay', persona.get('design'), typed=True)
    articles = [benchmark] if benchmark else []
    if kind != 'novice':
        run.ask('ledger', 'review')
        articles += [p for p in s0['prod_rank'][:10] if p in set(case['gold']) and p not in articles]
    process, sources = _process(run, path, r2, persona, cards=True)
    run.ask('section_d', 'review')
    rows = lookup_rows(articles)
    plan = [f"{r['provision']}: compare with the acceptable-solution performance for "
            f"{', '.join(r['pairs']) or 'no attribution row'}" for r in rows]
    evidence = list(SHARED_LADDER) + (list(ALT_TYPES) if path == 'alternative' else [])
    return _package(run, case, path=path, benchmark=benchmark, articles=articles, section_c=rows,
                    comparison=None, process=process, process_source=sources, evidence_plan=plan,
                    evidence_types=evidence, professional=professional_flag(shell, articles))


def flowchart_form(case, s0, r1, r2, persona, kind, shell, lookup: bool = False) -> Run:
    run = Run('flowchart_lookup' if lookup else 'flowchart_form', kind)
    named = run.ask('identify', 'expert', persona.get('benchmark_article'), typed=True)
    named_ids = [article_of(p) for p in ids_in(named)]
    if not lookup:
        run.ask('objectives', 'expert', persona.get('objectives'), typed=True)
        run.ask('functions', 'expert', persona.get('functional_statements'), typed=True)
        run.ask('intent', 'expert', persona.get('intent'), typed=True)
    run.ask('performance', 'expert', persona.get('performance_level'), typed=True)
    run.ask('compare', 'essay', persona.get('comparison'), typed=True)
    run.ask('gaps', 'essay', persona.get('gaps'), typed=True)
    diamond = run.ask('diamond', 'choice', persona.get('meets_acceptable_solution'))
    if diamond not in ('yes', 'no'):
        run.diamond_guessed = True      # the drawing has only yes and no; unsure takes the variance branch
    path = 'acceptable' if diamond == 'yes' else 'alternative'
    if path == 'acceptable':
        run.ask('complete_analysis', 'expert', persona.get('code_analysis'), typed=True)
        run.ask('evidence', 'essay', persona.get('equivalent_performance'), typed=True)
        extra_ids = []
        process = {f: None for f in DRAFT_FIELDS}
    else:
        rationale = run.ask('rationale', 'essay', persona.get('rationale'), typed=True)
        run.ask('detailed_analysis', 'expert', persona.get('code_analysis'), typed=True)
        provisions = run.ask('division_b', 'expert', persona.get('division_b_provisions'), typed=True)
        risk = run.ask('risk', 'essay', persona.get('risk'), typed=True)
        mitigation = run.ask('mitigation', 'essay', persona.get('mitigation'), typed=True)
        assumptions = run.ask('assumptions', 'essay', persona.get('assumptions'), typed=True)
        run.ask('equivalent_performance', 'essay', persona.get('equivalent_performance'), typed=True)
        extra_ids = [article_of(p) for p in ids_in(provisions)]
        process = {'rationale': rationale, 'risk_assessment': risk, 'mitigating_measures': mitigation,
                   'assumptions_and_limits': assumptions, 'maintenance_operation': None, 'qualifications': None}
    run.ask('evidence_types', 'choice')
    articles = list(dict.fromkeys(named_ids + extra_ids))
    benchmark = named_ids[0] if named_ids else None
    if lookup:
        articles = [a for a in articles if is_division_b(a)]
        benchmark = benchmark if benchmark and is_division_b(benchmark) else None
        rows = lookup_rows([benchmark] if benchmark else [])
    else:
        rows = [{'provision': benchmark, 'objectives': sorted(set(persona.get('objectives') or [])),
                 'functions': sorted(set(persona.get('functional_statements') or [])), 'source': 'applicant'}] if benchmark else []
    comparison = ' '.join(str(x) for x in (persona.get('comparison'), persona.get('gaps')) if not unknown(x)) or None
    plan = [persona.get('equivalent_performance')] if not unknown(persona.get('equivalent_performance')) else []
    return _package(run, case, path=path, benchmark=benchmark, articles=articles, section_c=rows,
                    comparison=comparison, process=process, process_source='applicant', evidence_plan=plan,
                    evidence_types=list(FLOWCHART_EVIDENCE), professional=None)


def flowchart_app(case, s0, r1, r2, persona, kind, shell) -> Run:
    run = Run('flowchart_app', kind)
    picks = [p['id'] for p in valid_picks(case, s0, r1)]
    if kind == 'novice':
        benchmark = run.ask('benchmark', 'choice', picks[0] if picks else None)
    else:
        benchmark, searched = expert_pick(case, picks[:3], persona)
        run.ask('benchmark', 'expert' if searched else 'choice', benchmark)
    path = _diamond(run, r2, persona)
    articles = list(dict.fromkeys(([benchmark] if benchmark else []) + picks))
    if path == 'alternative':
        process = {'rationale': run.ask('rationale', 'essay', persona.get('rationale'), typed=True),
                   'risk_assessment': run.ask('risk', 'essay', persona.get('risk'), typed=True),
                   'mitigating_measures': run.ask('mitigation', 'essay', persona.get('mitigation'), typed=True),
                   'assumptions_and_limits': run.ask('assumptions', 'essay', persona.get('assumptions'), typed=True),
                   'maintenance_operation': None, 'qualifications': None}
    else:
        process = {f: None for f in DRAFT_FIELDS}
    run.ask('equivalent_performance', 'review')
    return _package(run, case, path=path, benchmark=benchmark, articles=articles, section_c=lookup_rows(articles),
                    comparison=_comparison(r2), process=process, process_source='applicant',
                    evidence_plan=_plan(r2), evidence_types=list(FLOWCHART_EVIDENCE), professional=_professional(r2))


def hybrid(case, s0, r1, r2, persona, kind, shell, lean: bool = False, focus: bool = False) -> Run:
    run = Run('hybrid_focus' if focus else 'hybrid_lean' if lean else 'hybrid', kind)
    if not focus:
        run.ask('understood', 'confirm')
    if not lean:
        for i, q in enumerate(s0['planner']):
            answers = persona.get('planner_answers') or []
            run.ask('planner', 'fact', answers[i] if i < len(answers) else "I don't know", typed=True)
    if s0['scope'] == 'redirect' and (r1 or {}).get('scope') == 'other':
        return _dead(run, 'redirect', 'Both the keyword scope check and the model read another safety code.')
    picks = [p['id'] for p in valid_picks(case, s0, r1)]
    coded = s0['path'] if s0['path']['source'] == 'coded_check' and s0['path']['path'] in ('acceptable', 'alternative') else None
    lead = ([article_of(coded['article'])] if coded and coded.get('article') else []) + picks
    lead = list(dict.fromkeys(p for p in lead if p))
    if kind == 'novice':
        benchmark = run.ask('benchmark', 'choice', lead[0] if lead else None)
    else:
        benchmark, searched = expert_pick(case, lead[:3], persona)
        run.ask('benchmark', 'expert' if searched else 'choice', benchmark)
    path = coded['path'] if coded else _diamond(run, r2, persona)
    if coded:
        run.ask('route', 'confirm')
    if not focus:
        run.ask('articles', 'review')
    articles = list(dict.fromkeys(([benchmark] if benchmark else []) + picks))
    if kind != 'novice':
        gold = set(case['gold'])
        articles = [a for a in articles if a == benchmark or a in gold]
    process, sources = _process(run, path, r2, persona, cards=not lean, focus=focus)
    run.ask('section_d', 'review')
    return _package(run, case, path=path, benchmark=benchmark, articles=articles, section_c=lookup_rows(articles),
                    comparison=_comparison(r2), process=process, process_source=sources, evidence_plan=_plan(r2),
                    evidence_types=list(SHARED_LADDER) + (list(ALT_TYPES) if path == 'alternative' else []),
                    professional=_professional(r2))


ARMS = {
    'ours': ours,
    'flowchart_form': flowchart_form,
    'flowchart_lookup': lambda *a: flowchart_form(*a, lookup=True),
    'flowchart_app': flowchart_app,
    'hybrid': hybrid,
    'hybrid_lean': lambda *a: hybrid(*a, lean=True),
    'hybrid_focus': lambda *a: hybrid(*a, lean=True, focus=True),
}


# ---------------------------------------------------------------------------------------------- pieces

def _diamond(run: Run, r2: dict | None, persona: dict) -> str:
    decision = ((r2 or {}).get('comparison') or {}).get('decision')
    if decision == 'departs':
        run.ask('route', 'confirm')
        return 'alternative'
    if decision == 'follows':
        run.ask('route', 'confirm')
        return 'acceptable'
    run.ask('missing_fact', 'fact', persona.get('design'), typed=True)
    answer = run.ask('route', 'choice', persona.get('meets_acceptable_solution'))
    return 'acceptable' if answer == 'yes' else 'alternative'


FOCUS = ('rationale', 'assumptions_and_limits', 'maintenance_operation')


def _process(run: Run, path: str, r2: dict | None, persona: dict, *, cards: bool, focus: bool = False):
    if path != 'alternative':
        return {f: None for f in DRAFT_FIELDS}, 'none'
    drafts = drafts_for(r2)
    if not cards:
        run.ask('drafts', 'review')
    run.package_drafts = {f: (drafts[f].get('text') or '').strip() for f in DRAFT_FIELDS}
    out = {}
    for f in DRAFT_FIELDS:
        draft = drafts[f]
        if cards:
            run.ask(f, 'review')
        text = (draft.get('text') or '').strip()
        if (draft.get('open_questions') or not text) and (not focus or f in FOCUS):
            extra = run.ask(f'{f}_gap', 'essay', persona.get(PROCESS_Q[f]), typed=True)
            if not unknown(extra):
                text = f'{text} {extra}'.strip()
        out[f] = text or None
    return out, 'draft+applicant'


def _comparison(r2: dict | None) -> str | None:
    c = (r2 or {}).get('comparison')
    if not c:
        return None
    return f"Requires: {c.get('requires', '')} \"{c.get('requires_quote', '')}\" Proposed: {c.get('proposed', '')} " \
           f"\"{c.get('proposed_quote', '')}\" Gap: {c.get('gap', '')}"


def _plan(r2: dict | None) -> list[str]:
    return [f"{i.get('addresses', '')}: {i.get('evidence', '')} ({i.get('why', '')})" for i in (r2 or {}).get('evidence_plan', [])]


def _professional(r2: dict | None) -> str | None:
    return ((r2 or {}).get('professional') or {}).get('required')


def _dead(run: Run, path: str, why: str) -> Run:
    run.package = {'delivered': False, 'path': path, 'why_stopped': why, 'benchmark': None, 'articles': [],
                   'section_c': [], 'comparison': None, 'process': {f: None for f in DRAFT_FIELDS},
                   'process_source': 'none', 'evidence_plan': [], 'evidence_types': [], 'professional': None}
    return run


def _package(run: Run, case, **kw) -> Run:
    run.package = {'delivered': True, 'app_drafts': run.package_drafts, **kw}
    return run


# ---------------------------------------------------------------------------------------------- scoring

def friction(run: Run) -> dict:
    kinds = [i['kind'] for i in run.inputs]
    return {
        'inputs': len(run.inputs),
        'expert': kinds.count('expert'),
        'essay': kinds.count('essay'),
        'light': sum(kinds.count(k) for k in ('confirm', 'choice', 'fact', 'review')),
        'unknown': sum(i['unknown'] for i in run.inputs),
        'words': sum(i['words'] for i in run.inputs),
        'minutes': round(sum(SKIP_MINUTES if i['unknown'] and i['kind'] in ('essay', 'expert', 'fact') else MINUTES[i['kind']]
                             for i in run.inputs), 2),
        'dead_end': not run.package.get('delivered'),
        'diamond_guessed': run.diamond_guessed,
    }


def quality(run: Run, case: dict) -> dict:
    p = run.package
    gold = set(case['gold'])
    arts = [a for a in p.get('articles') or [] if a]
    valid = [a for a in arts if is_division_b(a)]
    found = gold & set(valid)
    bench = p.get('benchmark')
    sc_rows = p.get('section_c') or []
    sc_exact = None
    sc_invented = 0
    if bench and sc_rows:
        truth = section_c_summary(bench)
        row = sc_rows[0]
        if truth is None:
            sc_exact = False
        elif row.get('source') == 'lookup':
            sc_exact = True
        else:
            claimed_o, claimed_f = set(row.get('objectives') or []), set(row.get('functions') or [])
            sc_exact = claimed_o == set(truth['objectives']) and claimed_f == set(truth['functions'])
            sc_invented = len(claimed_o - set(truth['objectives'])) + len(claimed_f - set(truth['functions']))
    process = p.get('process') or {}
    alt = p.get('path') == 'alternative'
    filled = {f: bool(process.get(f)) and substantive(process.get(f)) for f in DRAFT_FIELDS}
    app_texts = [] if run.arm in ('flowchart_form', 'flowchart_lookup') else (
        [p.get('comparison') or ''] + list(p.get('evidence_plan') or []) + list((p.get('app_drafts') or {}).values()))
    coverage = {
        'code_analysis': bool(bench) and bool(sc_rows),
        'comparison': bool(p.get('comparison')),
        'rationale': filled['rationale'], 'risk': filled['risk_assessment'],
        'mitigation': filled['mitigating_measures'], 'assumptions': filled['assumptions_and_limits'],
        'maintenance': filled['maintenance_operation'], 'qualifications': filled['qualifications'],
        'evidence_plan': bool(p.get('evidence_plan')),
        'professional_flag': p.get('professional') in ('yes', 'no', 'depends'),
    } if p.get('delivered') else {k: False for k in ('code_analysis', 'comparison', 'rationale', 'risk', 'mitigation',
                                                   'assumptions', 'maintenance', 'qualifications', 'evidence_plan',
                                                   'professional_flag')}
    return {
        'delivered': bool(p.get('delivered')),
        'path': p.get('path'),
        'path_correct': (p.get('path') == case['gold_path']) if case['gold_path'] else None,
        'benchmark_hit': bool(bench) and bench in gold,
        'article_recall': len(found) / len(gold),
        'articles_listed': len(arts),
        'invalid_citations': len(arts) - len(valid),
        'section_c_exact': sc_exact,
        'section_c_invented_codes': sc_invented,
        'process_complete': sum(filled.values()) if alt else None,
        'coverage': coverage,
        'coverage_score': sum(coverage.values()),
        'app_claims': sum(verdict(x) for text in app_texts for x in sentences(text or '')),
        'app_claims_regex': sum(len(CLAIM.findall(text or '')) for text in app_texts),
    }
