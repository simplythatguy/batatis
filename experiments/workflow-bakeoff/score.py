"""Deterministic judge. The ten checks are the ones named in RUBRIC.md."""
from __future__ import annotations

import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

from section_c_text import section_c_for
from session import CCMC, PID, STANDATA

SIX = {
    "rationale", "risk_assessment", "mitigating_measures", "assumptions_and_limits",
    "maintenance_operation", "qualifications",
}
EXTRAS = {
    "CCMC evaluation", "ICC-ES evaluation", "registered professional opinion", "engineering review",
}
PROCESS_EVIDENCE = {"risk assessment", "mitigating measures", "assumptions and limits", "assumptions/limits"}
OPEN = {"unresolved", "redirect", "not_applicable"}
CLAIM = re.compile(r"\b(complies|compliant|is safe|approved|meets the code|satisfies the code)\b", re.I)
PAIR = re.compile(r"F\d{2,3}-O[A-Z]{1,3}\d+(?:\.\d+)?")
BRACKET = re.compile(r"\[[A-Z]\d{2}[^\]]*\]")
CODE_FIELDS = {"objectives", "functional_statements", "intent_statements"}


def _invented_pairs(text: str, source: str, spec) -> list[str]:
    allowed = set(spec.pairs) | set(PAIR.findall(source))
    invented = [token for token in sorted(set(PAIR.findall(text)) - allowed)]
    for match in BRACKET.finditer(text):
        token = match.group(0)
        if token not in source and token not in spec.text:
            invented.append(token)
    return invented


def _ids(text: str) -> list[str]:
    return PID.findall(text) + STANDATA.findall(text) + CCMC.findall(text)


def score_run(result: dict, gold_path: str) -> dict:
    draft = result["draft_text"] + "\n" + result["completeness_text"]
    allowed = set(result["allowed_ids"]) | set(result["process_cites"])
    fabricated = [token for token in _ids(draft) if token not in allowed]
    section_c = section_c_for(result.get("article"))
    invented = _invented_pairs(draft, result.get("source_text") or "", section_c)
    if invented:
        fabricated.append("invented attribution pair")
    claims = bool(CLAIM.search(draft))
    asked = set(result["process_asked"])
    evidence = set(result["evidence_types"])
    questions = result["questions"]
    stated = set(result["stated_fields"])
    seen: set[str] = set()
    necessary = redundant = 0
    for question in questions:
        reasons = []
        field = question["field"]
        kind = question.get("kind", "other")
        if field in seen:
            reasons.append("repeat")
        seen.add(field)
        if field in stated and kind != "confirm":
            reasons.append("already in the prompt")
        if kind == "code_analysis" or field in CODE_FIELDS:
            reasons.append("objective, function, or intent asked of the applicant")
        if field in SIX and gold_path != "alternative":
            reasons.append("process field off the alternative path")
        if kind in {"paperwork", "evidence"} and gold_path in OPEN:
            reasons.append("package question before a path is chosen")
        question["redundant"] = bool(reasons)
        question["redundant_reason"] = "; ".join(reasons)
        if reasons:
            redundant += 1
        else:
            necessary += 1
    checks = {
        "path": result["path"] == gold_path,
        "no_fabrication": not fabricated and not result["professional_judgment"],
        "process_fields": (
            (SIX <= asked and not result["process_system_filled"])
            if gold_path == "alternative"
            else asked.isdisjoint(SIX) and not result["process_system_filled"]
        ),
        "process_not_evidence": evidence.isdisjoint(PROCESS_EVIDENCE),
        "evidence_matches_path": (
            EXTRAS <= evidence if gold_path == "alternative"
            else evidence.isdisjoint(EXTRAS) if gold_path == "acceptable"
            else not result["evidence_required"]
        ),
        "section_c": (
            section_c.text in result["draft_text"]
            and "lookup unavailable" not in draft.lower()
            and not invented
        ),
        "no_judgment": not result["professional_judgment"] and not claims,
        "no_silent_fills": not result["silent_fills"],
        "admin_review": result["completeness_text"].startswith("Administrative review only.") and not claims,
        "no_code_quiz": not any(q.get("kind") == "code_analysis" or q["field"] in CODE_FIELDS for q in questions),
    }
    quality = sum(checks.values())
    missed = [name for name, ok in checks.items() if not ok]
    reason = "All ten checks passed." if not missed else "Missed " + ", ".join(missed) + "."
    by_who = {"applicant": 0, "designer": 0, "office": 0}
    for question in questions:
        by_who[question["answerer"]] = by_who.get(question["answerer"], 0) + 1
    return {
        "path": result["path"],
        "path_match": checks["path"],
        "quality": quality,
        "checks": checks,
        "reason": reason,
        "questions": len(questions),
        "applicant_questions": by_who.get("applicant", 0),
        "designer_questions": by_who.get("designer", 0),
        "office_questions": by_who.get("office", 0),
        "necessary": necessary,
        "redundant": redundant,
        "fabricated": len(fabricated),
        "fabricated_ids": fabricated,
        "claims_compliance": claims,
        "silent_fills": len(result["silent_fills"]),
        "quality_per_question": quality / max(len(questions), 1),
    }


def _blank(**overrides) -> dict:
    result = {
        "draft_text": "",
        "completeness_text": "Administrative review only.",
        "allowed_ids": set(),
        "process_cites": set(),
        "process_asked": [],
        "process_system_filled": [],
        "evidence_types": [],
        "evidence_required": False,
        "professional_judgment": [],
        "silent_fills": [],
        "questions": [],
        "stated_fields": [],
        "path": "unresolved",
        "article": None,
        "source_text": "",
    }
    result.update(overrides)
    return result


def self_check() -> None:
    bogus = _blank(draft_text="The wall complies. See 9.99.9.9.(1) and CCMC 99999.")
    scored = score_run(bogus, "unresolved")
    if scored["fabricated"] < 2:
        raise SystemExit(f"fabrication detector failed: {scored['fabricated_ids']}")
    spec = section_c_for("9.10.15.5.(8)")
    if "F03-OP3.1" not in spec.text or "direct" not in spec.text or "intent objectives OP3" not in spec.text:
        raise SystemExit(f"Section C for 9.10.15.5.(8) did not match the database: {spec.text}")
    if "lookup unavailable" in spec.text:
        raise SystemExit("lookup renderer still uses the unavailable sentence")
    good = _blank(
        draft_text=spec.text,
        article="9.10.15.5.(8)",
        allowed_ids={"9.10.15.5.(8)"},
    )
    scored = score_run(good, "unresolved")
    if not scored["checks"]["section_c"] or scored["fabricated"]:
        raise SystemExit(f"real lookup failed the judge: {scored}")
    skipped = _blank(
        draft_text="No Division B sentence was committed. Section C is empty.",
        article="9.10.15.5.(8)",
        allowed_ids={"9.10.15.5.(8)"},
    )
    scored = score_run(skipped, "unresolved")
    if scored["checks"]["section_c"]:
        raise SystemExit("skipping a lookup the database can answer must fail Section C")
    if scored["fabricated"]:
        raise SystemExit("a skipped lookup is not a fabricated citation")
    invented = _blank(
        draft_text=spec.text + "\nF99-OS9.9",
        article="9.10.15.5.(8)",
        allowed_ids={"9.10.15.5.(8)"},
    )
    scored = score_run(invented, "unresolved")
    if "invented attribution pair" not in scored["fabricated_ids"] or scored["checks"]["section_c"]:
        raise SystemExit(f"invented pair was not rejected: {scored}")
    missed = section_c_for("9.99.99.99.(1)")
    if not missed.text.startswith("Section C lookup missed 9.99.99.99.(1)"):
        raise SystemExit(missed.text)
    stale = _blank(
        draft_text="Section C: lookup unavailable. Objective, function, and intent are not filled from memory.",
        article="9.10.15.5.(8)",
        allowed_ids={"9.10.15.5.(8)"},
    )
    scored = score_run(stale, "unresolved")
    if scored["checks"]["section_c"]:
        raise SystemExit("the old lookup-unavailable line must fail Section C")
