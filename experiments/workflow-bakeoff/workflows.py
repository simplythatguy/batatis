"""Workflow arms. Each one may call the real fork, scope check, question planner, and rule evaluator."""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
for path in (str(HERE), str(ROOT)):
    if path not in sys.path:
        sys.path.insert(0, path)

from engine.rules.evaluator import load_rule, load_rules

from section_c_text import section_c_for
from session import PID, PROCESS_CITES, Session

BUILDING_WIDE = {
    "occupancy", "storeys", "building_area_m2", "dwelling_unit_above_another", "sprinklered",
    "fire_response_over_10_min", "adjacent_rooms_sprinklered", "industrial_hazard",
}
KEYWORDS = (
    ("glazed-openings-houses", ("glazed", "glazing", "window")),
    ("unprotected-openings", ("unprotected opening", "unprotected")),
    ("soffits-houses", ("soffit", "overhang")),
    ("firewall-suite-rowhouses", ("firewall", "secondary suite", "row house", "townhouse")),
    ("fire-dampers", ("fire damper", "damper", "duct")),
)
SIX = (
    ("rationale", "Why do you need to build it differently, and why will it work as well?"),
    ("risk_assessment", "What could go wrong if it doesn’t work as well?"),
    ("mitigating_measures", "What reduces those risks?"),
    ("assumptions_and_limits", "Under what conditions does your case hold?"),
    ("maintenance_operation", "What has to be looked after once it’s built?"),
    ("qualifications", "Who takes responsibility for this, and for which parts?"),
)
FOUR = SIX[:4]
LABELS = {
    "rationale": "rationale",
    "risk_assessment": "risk assessment",
    "mitigating_measures": "mitigating measures",
    "assumptions_and_limits": "assumptions and limits",
    "maintenance_operation": "maintenance and operation",
    "qualifications": "qualifications of the responsible people",
    "owner": "owner",
    "representative": "representative",
    "mailing_address": "mailing address",
    "municipal_address": "site address",
    "legal_description": "legal description",
    "date": "request date",
    "scope": "whether the request is one site or municipality-wide",
}
PAPER = (
    ("owner", "Owner"),
    ("representative", "Representative"),
    ("mailing_address", "Mailing address"),
    ("municipal_address", "Site address"),
    ("legal_description", "Legal description"),
    ("date", "Request date"),
)
SCOPE = ("scope", "One site, or every site in the municipality?")
PLAN_PAPER = {"owner_name", "municipal_address", "legal_description", "mailing_address"}
SHARED = (
    "manufacturer's literature",
    "existing STANDATA variance",
    "ISO 17025 test report",
    "evaluation",
    "evaluation + testing",
    "qualification",
    "ISO 17065 certification",
)
EXTRAS = (
    "CCMC evaluation",
    "ICC-ES evaluation",
    "registered professional opinion",
    "engineering review",
)
FLOW_ALT = (
    "ISO 17025 test report",
    "evaluation",
    "registered professional opinion",
    "engineering review",
    "CCMC evaluation",
    "ICC-ES evaluation",
    "code conformity assessment",
    "existing STANDATA variance",
    "qualification",
    "ISO 17065 certification",
)
STATE_PATH = {"follows": "acceptable", "departs": "alternative", "not_applicable": "not_applicable"}
CODE_QUIZ = (
    ("objectives", "What are the objectives of the applicable acceptable solution?"),
    ("functional_statements", "What are the functional statements?"),
    ("intent_statements", "What are the intent statements?"),
)


def run_w0(prompt, session: Session) -> dict:
    session.stage("design")
    scope = session.classify()
    if scope.status == "redirect":
        return _close(session, "redirect", note=scope.message)
    session.confirm_reading()
    fork = session.assess()
    path = "unresolved"
    if fork.variance_needed == "likely":
        session.ask(stage="route", field="route", kind="decision", text="You likely need a variance.")
        path = "alternative"
    elif fork.variance_needed == "not_indicated":
        session.ask(
            stage="route", field="route", kind="decision",
            text="You may not need a variance. Use the standard way, or something is different.",
        )
        path = "acceptable"
    known = set(session.stated())
    for question in session.plan(known, departure_known="alternative_description" in known):
        if question.field in PLAN_PAPER or question.field in session.obtained:
            continue
        session.ask(stage="project", field=question.field, kind="project", text=question.text)
    article = None
    message = ""
    assumptions: list[str] = []
    if path != "acceptable":
        for rule_id in _in_play(session):
            result = _resolve(session, rule_id, ask=True)
            if not _firm(result):
                continue
            if result["state"] == "departs":
                added = session.ask(
                    stage="rules", field="add_rule", kind="decision",
                    text="This rule check departs from the acceptable solution. Add it to the application?",
                )
                if added.value == "yes":
                    path = "alternative"
                    article = result["provision"]["id"]
                    message = result["message"]
                    assumptions = list(result["assumptions"])
                    break
            article = article or result["provision"]["id"]
            message = message or result["message"]
    if path == "acceptable":
        return _close(session, path, paperwork=PAPER)
    return _close(
        session, path, process=SIX, evidence=SHARED + EXTRAS, evidence_required=True,
        paperwork=PAPER + (SCOPE,), article=article, message=message, assumptions=assumptions,
    )


def run_w1(prompt, session: Session, *, force_no: bool = False) -> dict:
    """Boxes in the flowchart order. The drawing has a yes edge and a no edge."""
    session.stage("design")
    identified = session.ask(
        stage="identify", field="applicable_solution", kind="decision",
        text="Which acceptable solution in the NBC (AE) applies?",
    )
    for field, text in CODE_QUIZ:
        session.ask(stage="code_analysis", field=field, kind="code_analysis", text=text)
    session.ask(
        stage="performance", field="minimum_performance", kind="performance",
        text="What minimum performance level does that acceptable solution require?",
    )
    session.ask(stage="compare", field="compare", kind="compare", text="How does the proposed design compare with that acceptable solution?")
    session.ask(stage="gaps", field="gaps", kind="gaps", text="What gaps do you see between them?")
    diamond = session.ask(
        stage="diamond", field="diamond", kind="decision",
        text="Does the proposed design meet or exceed the applicable acceptable solution?",
    )
    article = identified.value if identified.status == "answered" else None
    if diamond.value == "yes":
        path = "acceptable"
    elif diamond.value == "no" or force_no:
        path = "alternative"
    else:
        path = "unresolved"
    if path == "unresolved":
        return _close(session, path, article=article)
    if path == "acceptable":
        session.stage("complete_analysis")
        return _close(
            session, path, evidence=SHARED, evidence_required=True, paperwork=PAPER, article=article,
        )
    session.stage("no_branch")
    note = "Key Attributes: Rationale for Proposed Variance (required)"
    session.ask(stage="analysis", field="detailed_code_analysis", kind="code_analysis",
                text="Provide the detailed code analysis for the variance.")
    session.ask(stage="performance", field="equivalent_performance", kind="performance",
                text="How will you demonstrate equivalent performance?")
    session.ask(stage="identify", field="division_b", kind="code_analysis",
                text="Identify the applicable Division B sentences, objectives, functional statements, and intent statements.")
    return _close(
        session, path, process=FOUR, evidence=FLOW_ALT, evidence_mode="flow_alt",
        evidence_required=True, paperwork=PAPER + (SCOPE,), article=article, note=note,
    )


def run_w2(
    prompt, session: Session, *, confirm: bool = False, ask_inputs: bool = True,
    package_when_unresolved: bool = False, code_quiz: bool = False, process=SIX,
    trust_assumptions: bool = False, hold_without_rule: bool = False, ask_diamond: bool = False,
) -> dict:
    session.stage("design")
    scope = session.classify()
    if scope.status == "redirect":
        return _close(session, "redirect", note=scope.message)
    if confirm:
        session.confirm_reading()
    else:
        session.obtained.update(session.stated())
    if code_quiz:
        for field, text in CODE_QUIZ:
            session.ask(stage="code_analysis", field=field, kind="code_analysis", text=text)
    for question in session.plan(set(session.stated()), departure_known=True):
        if question.field == "product_scope":
            session.ask(stage="route", field="product_scope", kind="decision", text=question.text)
    rule_id = _select_rule(session)
    result = _resolve(session, rule_id, ask=ask_inputs) if rule_id else None
    article = None
    message = ""
    assumptions: list[str] = []
    decided = _decided(result, trust_assumptions)
    if result and decided:
        path = STATE_PATH[result["state"]]
        article = result["provision"]["id"]
        message = result["message"]
        assumptions = list(result["assumptions"])
        if trust_assumptions and assumptions:
            session.silent_fills.extend(assumptions)
    elif hold_without_rule:
        path = "unresolved"
        if result:
            assumptions = list(result["assumptions"])
    elif ask_diamond:
        diamond = session.ask(
            stage="diamond", field="diamond", kind="decision",
            text="Does the proposed design meet or exceed the applicable acceptable solution?",
        )
        if diamond.value == "yes":
            path = "acceptable"
        elif diamond.value == "no":
            path = "alternative"
        else:
            path = "unresolved"
        if result:
            assumptions = list(result["assumptions"])
    else:
        path = _fork_path(session)
        if result:
            assumptions = list(result["assumptions"])
    if path == "unresolved" and package_when_unresolved:
        return _close(
            session, path, process=process, evidence=SHARED + EXTRAS, evidence_required=True,
            paperwork=PAPER + (SCOPE,), assumptions=assumptions,
        )
    if path in {"unresolved", "not_applicable", "redirect"}:
        return _close(session, path, article=article, message=message, assumptions=assumptions)
    if path == "acceptable":
        return _close(
            session, path, evidence=SHARED, evidence_required=True, paperwork=PAPER,
            article=article, message=message, assumptions=assumptions,
        )
    return _close(
        session, path, process=process, evidence=SHARED + EXTRAS, evidence_required=True,
        paperwork=PAPER + (SCOPE,), article=article, message=message, assumptions=assumptions,
    )


def run_w1b(prompt, session: Session) -> dict:
    return run_w1(prompt, session, force_no=True)


def run_w1l(prompt, session: Session) -> dict:
    """Flowchart order. The objective, function, and intent quiz is a database lookup."""
    session.stage("design")
    identified = session.ask(
        stage="identify", field="applicable_solution", kind="decision",
        text="Which acceptable solution in the NBC (AE) applies?",
    )
    session.ask(
        stage="performance", field="minimum_performance", kind="performance",
        text="What minimum performance level does that acceptable solution require?",
    )
    session.ask(
        stage="compare", field="compare", kind="compare",
        text="How does the proposed design compare with that acceptable solution?",
    )
    session.ask(
        stage="gaps", field="gaps", kind="gaps",
        text="What gaps do you see between them?",
    )
    diamond = session.ask(
        stage="diamond", field="diamond", kind="decision",
        text="Does the proposed design meet or exceed the applicable acceptable solution?",
    )
    article = identified.value if identified.status == "answered" and isinstance(identified.value, str) else None
    rule_id = _select_rule(session)
    result = _resolve(session, rule_id, ask=False) if rule_id else None
    message = ""
    assumptions: list[str] = []
    if result and _firm(result):
        article = result["provision"]["id"]
        message = result["message"]
        assumptions = list(result["assumptions"])
    if diamond.value == "yes":
        path = "acceptable"
    elif diamond.value == "no":
        path = "alternative"
    else:
        path = "unresolved"
    if path == "unresolved":
        return _close(session, path, article=article, message=message, assumptions=assumptions)
    if path == "acceptable":
        session.stage("complete_analysis")
        return _close(
            session, path, evidence=SHARED, evidence_required=True, paperwork=PAPER,
            article=article, message=message, assumptions=assumptions,
        )
    session.stage("no_branch")
    note = "Key Attributes: Rationale for Proposed Variance (required)"
    session.ask(
        stage="performance", field="equivalent_performance", kind="performance",
        text="How will you demonstrate equivalent performance?",
    )
    return _close(
        session, path, process=FOUR, evidence=FLOW_ALT, evidence_mode="flow_alt",
        evidence_required=True, paperwork=PAPER + (SCOPE,), article=article,
        message=message, assumptions=assumptions, note=note,
    )


def run_w3(prompt, session: Session) -> dict:
    return run_w2(prompt, session, code_quiz=True)


def run_w2c(prompt, session: Session) -> dict:
    """W2 plus the product's reading-confirmation card before any other question."""
    return run_w2(prompt, session, confirm=True)


def run_w2s(prompt, session: Session) -> dict:
    """W2 using only facts written in the prompt. Hidden inputs are not asked."""
    return run_w2(prompt, session, ask_inputs=False)


def run_w2a(prompt, session: Session) -> dict:
    """W2 treats a labeled rule assumption as a firm diamond and records it as a silent fill."""
    return run_w2(prompt, session, trust_assumptions=True)


def run_w2f(prompt, session: Session) -> dict:
    """W2 with only the four process boxes drawn on the flowchart."""
    return run_w2(prompt, session, process=FOUR)


def run_w2h(prompt, session: Session) -> dict:
    """W2 does not open a path from wording alone. No firm rule means unresolved."""
    return run_w2(prompt, session, hold_without_rule=True)


def run_w2q(prompt, session: Session) -> dict:
    """W2 asks the diamond out loud when no coded rule is firm."""
    return run_w2(prompt, session, ask_diamond=True)


def run_w2d(prompt, session: Session) -> dict:
    """The diamond is asked before the coded rule. Yes stops there."""
    session.stage("design")
    scope = session.classify()
    if scope.status == "redirect":
        return _close(session, "redirect", note=scope.message)
    session.obtained.update(session.stated())
    diamond = session.ask(
        stage="diamond", field="diamond", kind="decision",
        text="Does the proposed design meet or exceed the applicable acceptable solution?",
    )
    if diamond.value == "yes":
        return _close(session, "acceptable", evidence=SHARED, evidence_required=True, paperwork=PAPER)
    rule_id = _select_rule(session)
    result = _resolve(session, rule_id, ask=True) if rule_id else None
    article = None
    message = ""
    assumptions: list[str] = []
    if result and _firm(result):
        path = STATE_PATH[result["state"]]
        article = result["provision"]["id"]
        message = result["message"]
        assumptions = list(result["assumptions"])
    elif diamond.value == "no":
        path = "alternative"
        if result:
            assumptions = list(result["assumptions"])
    else:
        path = "unresolved"
        if result:
            assumptions = list(result["assumptions"])
    if path in {"unresolved", "not_applicable", "redirect"}:
        return _close(session, path, article=article, message=message, assumptions=assumptions)
    if path == "acceptable":
        return _close(
            session, path, evidence=SHARED, evidence_required=True, paperwork=PAPER,
            article=article, message=message, assumptions=assumptions,
        )
    return _close(
        session, path, process=SIX, evidence=SHARED + EXTRAS, evidence_required=True,
        paperwork=PAPER + (SCOPE,), article=article, message=message, assumptions=assumptions,
    )


ARMS = {
    "W0": run_w0,
    "W1": run_w1,
    "W1b": run_w1b,
    "W1l": run_w1l,
    "W2": run_w2,
    "W3": run_w3,
    "W2c": run_w2c,
    "W2s": run_w2s,
    "W2a": run_w2a,
    "W2f": run_w2f,
    "W2h": run_w2h,
    "W2q": run_w2q,
    "W2d": run_w2d,
}


def _fork_path(session: Session) -> str:
    needed = session.assess().variance_needed
    if needed == "likely":
        return "alternative"
    if needed == "not_indicated":
        return "acceptable"
    session.stage("diamond")
    return "unresolved"


def _firm(result: dict | None) -> bool:
    return _decided(result, False)


def _decided(result: dict | None, trust_assumptions: bool) -> bool:
    if not result or result["state"] not in STATE_PATH:
        return False
    if trust_assumptions:
        return True
    return not result["assumptions"]


def _keyword_hit(text: str, token: str) -> bool:
    if " " in token:
        return token in text
    return re.search(rf"\b{re.escape(token)}s?\b", text) is not None


def _select_rule(session: Session) -> str | None:
    text = session.prompt.text
    by_title = [rule["id"] for rule in load_rules() if rule["title"] in text]
    if len(by_title) == 1:
        session.stage("identify")
        return by_title[0]
    low = text.lower()
    scores = [(sum(_keyword_hit(low, token) for token in tokens), rule_id) for rule_id, tokens in KEYWORDS]
    scores = [(score, rule_id) for score, rule_id in scores if score]
    if not scores:
        return None
    best = max(score for score, _ in scores)
    tied = [rule_id for score, rule_id in scores if score == best]
    if len(tied) == 1:
        session.stage("identify")
        return tied[0]
    return None


def _in_play(session: Session) -> list[str]:
    known = set(session.stated()) | set(session.obtained)
    found = []
    for rule in load_rules():
        if any(field not in BUILDING_WIDE and field in known for field in rule["inputs"]):
            found.append(rule["id"])
    return found


def _asked(session: Session, field: str) -> bool:
    return any(item["field"] == field for item in session.questions)


def _resolve(session: Session, rule_id: str, *, ask: bool) -> dict:
    rule = load_rule(rule_id)
    facts = {}
    for key in rule["inputs"]:
        if key in session.obtained:
            facts[key] = session.obtained[key]
        elif key in session.stated():
            facts[key] = session.stated()[key]
            session.obtained[key] = facts[key]
    if not ask:
        return session.evaluate_rule(rule_id, facts)
    result = session.evaluate_rule(rule_id, facts)
    for _ in range(len(rule["inputs"]) + 1):
        if _firm(result):
            return result
        missing = [item["field"] for item in result["missing"]]
        if result["assumptions"]:
            missing.extend(key for key in rule["inputs"] if key not in facts)
        progressed = False
        for key in dict.fromkeys(missing):
            if key in facts or _asked(session, key):
                continue
            spec = session._index["inputs"][key]
            answer = session.ask(stage="rules", field=key, kind="rules", text=spec["question"])
            if answer.status == "answered":
                facts[key] = answer.value
                progressed = True
        if not progressed:
            return result
        result = session.evaluate_rule(rule_id, facts)
    return result


def _close(
    session: Session,
    path: str,
    *,
    process=(),
    evidence=(),
    evidence_required: bool = False,
    evidence_mode: str = "one",
    paperwork=(),
    article: str | None = None,
    message: str = "",
    assumptions: list[str] | None = None,
    note: str = "",
) -> dict:
    session.stage("draft")
    assumptions = assumptions or []
    answers = {}
    for field, text in process:
        session.process_asked.append(field)
        answer = session.ask(stage="case", field=field, kind="process", text=text)
        answers[field] = answer.text if answer.status == "answered" else ""
    if evidence_required and evidence_mode == "flow_alt":
        session.ask(stage="proof", field="evidence_test", kind="evidence", text="What test report will you provide?")
        session.ask(
            stage="proof", field="evidence_evaluation", kind="evidence",
            text="What evaluation will you provide? Registered professional opinion, engineering review, CCMC, ICC-ES, code conformity assessment, or an existing STANDATA variance.",
        )
        session.ask(stage="proof", field="evidence_qualification", kind="evidence", text="What qualification will you provide?")
        session.ask(stage="proof", field="evidence_certification", kind="evidence", text="What certification will you provide?")
    elif evidence_required:
        session.ask(
            stage="proof", field="evidence", kind="evidence",
            text="Which of these documents do you already have? " + "; ".join(evidence),
        )
    gaps = [LABELS[field] for field, text in process if not answers[field]]
    for field, text in paperwork:
        if field in session.stated():
            session.take(field)
            continue
        answer = session.ask(stage="paperwork", field=field, kind="paperwork", text=text)
        if answer.status != "answered":
            gaps.append(LABELS[field])
    if evidence_required:
        gaps.append("supporting documents for the evidence types you will rely on")
    section_c = section_c_for(article)
    if article and not section_c.answered:
        gaps.append(f"Section C lookup missed {article}")
    session.allow_process_cites()
    session.allowed_ids.update(PID.findall(section_c.text))
    if article:
        session.allowed_ids.add(str(article))
    completeness = _review(path, gaps, note)
    draft = _draft(
        path, article, message, assumptions, answers, evidence if evidence_required else (),
        completeness, note, section_c.text,
    )
    return {
        "path": path,
        "stages": list(session.stages),
        "questions": session.questions,
        "process_asked": list(session.process_asked),
        "process_system_filled": [],
        "evidence_types": list(evidence) if evidence_required else [],
        "evidence_required": evidence_required,
        "article": article,
        "silent_fills": list(session.silent_fills),
        "professional_judgment": [],
        "completeness_text": completeness,
        "draft_text": draft,
        "allowed_ids": set(session.allowed_ids),
        "process_cites": {PROCESS_CITES[field] for field in session.process_asked if field in PROCESS_CITES},
        "stated_fields": list(session.stated()),
        "source_text": session.prompt.text,
    }


def _review(path: str, gaps: list[str], note: str) -> str:
    lines = ["Administrative review only. This does not decide technical correctness or approval."]
    if path == "redirect" and note:
        lines.append(note)
    elif path == "unresolved":
        lines.append("Your application appears to be missing a determined path. The comparison with the acceptable solution is not finished.")
    elif path == "not_applicable":
        lines.append("This acceptable solution does not apply to the facts given. No variance package is opened from this rule.")
    elif path == "acceptable":
        lines.append("The coded check follows the acceptable solution, or the description gives no departure. This is not an officer's decision.")
    for gap in gaps:
        lines.append(f"Your application appears to be missing {gap}.")
    if path in {"acceptable", "alternative"} and not gaps:
        lines.append("No blocking administrative items were found in the fields this workflow collects.")
    return "\n".join(lines)


def _draft(path, article, message, assumptions, answers, evidence, completeness, note, section_c: str) -> str:
    lines = [f"Path chosen: {path}."]
    if note and path != "redirect":
        lines.append(note)
    if message:
        lines.append("Rule check, not yet reviewed by an expert: " + message)
    for item in assumptions:
        lines.append("Labeled assumption from the rule check: " + item)
    if article:
        lines.append(f"Provision used for this check: {article}.")
    lines.append(section_c)
    for field, text in answers.items():
        if text:
            lines.append(f"{LABELS[field]}, in the applicant's words: {text}")
        else:
            lines.append(f"{LABELS[field]}: the applicant has not provided this.")
    if evidence:
        lines.append("Evidence types to discuss, not results: " + "; ".join(evidence))
    lines.append(completeness)
    return "\n".join(lines)
