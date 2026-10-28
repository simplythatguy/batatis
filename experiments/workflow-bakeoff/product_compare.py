"""Score the frozen 152 prompts from the code that actually chooses the path.

BEFORE calls origin/main (the product before this branch): classify, assess,
alternative_path, and process_fields. The deck on that revision strips the
variance package only when the applicant takes the standard route. An unknown
fork leaves alternative_path true, so the six process fields and the full
evidence list still open.

FLOWCHART and FLOWCHART+LOOKUP are the attached drawing. The second one still
uses the drawing's diamond and replaces the objective/function/intent quiz
with the code-database lookup.

AFTER calls decide_path, process_fields, and the Section D evidence tuples on
this branch. A firm check chooses the path. Process fields open only when that
path is alternative. The shared ladder opens on acceptable. Unresolved, not
applicable, and redirect open no package.

The procedures do not branch on randomness. Pass 2 is the same code.
"""
from __future__ import annotations

import csv
import inspect
import json
import sys
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
OLD_ROOT = Path("/tmp/origin-main")
OLD_REVISION = "e34b4e4f390f47e320d1befa46cf6f36f4d0fb09"


def _snapshot_origin_main() -> dict:
    if "engine" in sys.modules or "engine.process_fields" in sys.modules:
        raise SystemExit("refusing to snapshot origin/main after the current engine was imported")
    marker = OLD_ROOT / "engine" / "process_fields.py"
    text = marker.read_text(encoding="utf-8")
    if "def alternative_path" not in text or "decide_path" in text:
        raise SystemExit(f"{marker} is not the pre-W2 process_fields.py")
    if "not in ('acceptable', 'acceptable_solution')" not in text:
        raise SystemExit(f"{marker} does not contain the pre-W2 alternative_path predicate")
    sys.path.insert(0, str(OLD_ROOT))
    import engine.intake.fork as old_fork
    import engine.intake.scope as old_scope
    import engine.process_fields as old_pf
    import engine.section_d as old_sd

    snap = {
        "alternative_path": old_pf.alternative_path,
        "process_fields": old_pf.process_fields,
        "ladder": tuple(old_sd.CONFIDENCE_LADDER),
        "extras": tuple(old_sd.ALTERNATIVE_EVIDENCE_TYPES),
        "assess": old_fork.assess,
        "classify": old_scope.classify,
    }
    source = inspect.getsource(snap["alternative_path"])
    if "decide_path" in source or "acceptable_solution" not in source:
        raise SystemExit(f"loaded the wrong alternative_path:\n{source}")
    for key in list(sys.modules):
        if key in {"engine", "codedb"} or key.startswith("engine.") or key.startswith("codedb."):
            del sys.modules[key]
    sys.path.remove(str(OLD_ROOT))
    return snap


OLD = _snapshot_origin_main()

sys.path.insert(0, str(HERE))
sys.path.insert(0, str(ROOT))

from engine.codes import Codes  # noqa: E402
from engine.models import Case, Fact, Source  # noqa: E402
from engine.path_decision import decide_path  # noqa: E402
from engine.process_fields import alternative_path, process_fields  # noqa: E402
from engine.section_d import ALTERNATIVE_EVIDENCE_TYPES, CONFIDENCE_LADDER  # noqa: E402
from prompts import load  # noqa: E402
from run import _markdown, _summary  # noqa: E402
from score import score_run, self_check  # noqa: E402
from section_c_text import section_c_for  # noqa: E402
from session import Session  # noqa: E402
from workflows import (  # noqa: E402
    PAPER,
    PLAN_PAPER,
    SCOPE,
    run_w0,
    run_w1,
    run_w1l,
    run_w2,
    _close,
    _in_play,
    _resolve,
    _select_rule,
)

OUT = HERE / "results"
FROZEN = HERE / "frozen" / "prompts.json"
_CODES: Codes | None = None


def codes() -> Codes:
    global _CODES
    if _CODES is None:
        _CODES = Codes()
    return _CODES


def _fact(field: str, value) -> Fact:
    shown = str(value)
    return Fact(
        field=field, value=value, kind="pointed", status="confirmed",
        source=Source(type="user_text", ref="prompt", quote=shown[:500] or shown),
    )


def make_case(session: Session) -> Case:
    """Facts the path functions are allowed to see: the prompt, plus answers already given."""
    facts = [_fact("project.description", session.prompt.text)]
    inputs = session._index["inputs"]
    for field, value in session.obtained.items():
        if field in inputs and value is not None:
            facts.append(_fact(field, value))
    return Case(facts=facts)


def _process_questions(fields) -> list[tuple[str, str]]:
    return [(field.id, field.prompt) for field in fields]


def _evidence(on_alternative: bool, ladder, extras) -> tuple[str, ...]:
    return tuple(ladder) + (tuple(extras) if on_alternative else ())


def run_before(prompt, session: Session) -> dict:
    """origin/main path, process fields, and evidence, with that deck's standard-route filter."""
    session.stage("design")
    scope = OLD["classify"](session.prompt.text)
    current = session.classify()
    if scope.status != current.status:
        raise SystemExit(f"classify diverged on {prompt.id}: old {scope.status} current {current.status}")
    if scope.status == "redirect":
        case = make_case(session)
        if OLD["alternative_path"](case) is not True:
            raise SystemExit("redirect case unexpectedly cleared the old alternative_path")
        return _close(session, "redirect", note=getattr(scope, "message", "") or "")

    session.confirm_reading()
    fork = OLD["assess"](session.prompt.text)
    if fork.variance_needed != session.assess().variance_needed:
        raise SystemExit(f"assess diverged on {prompt.id}")

    path = "unresolved"
    usual = False
    if fork.variance_needed != "unknown":
        answer = session.ask(
            stage="route", field="route", kind="decision",
            text="You likely need a variance." if fork.variance_needed == "likely"
            else "You may not need a variance. Use the standard way, or something is different.",
        )
        if answer.value == "standard":
            usual = True
            path = "acceptable"
        elif answer.value == "variance":
            path = "alternative"

    known = set(session.stated())
    for question in session.plan(known, departure_known="alternative_description" in known):
        if question.field in PLAN_PAPER or question.field in session.obtained:
            continue
        answer = session.ask(stage="project", field=question.field, kind="project", text=question.text)
        if question.field == "product_scope" and answer.value == "product_acceptance":
            usual = True
            path = "acceptable"

    article = None
    message = ""
    assumptions: list[str] = []
    if not usual:
        for rule_id in _in_play(session):
            result = _resolve(session, rule_id, ask=True)
            if result["state"] not in {"follows", "departs", "not_applicable"} or result["assumptions"]:
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

    case = make_case(session)
    on_alternative = bool(OLD["alternative_path"](case))
    opened = _process_questions(OLD["process_fields"](case, codes())) if on_alternative else []
    types = _evidence(on_alternative, OLD["ladder"], OLD["extras"])
    # web/src/calm/deck.ts on origin/main drops case and proof cards when the route is standard.
    if usual:
        return _close(session, "acceptable", paperwork=PAPER, article=article, message=message, assumptions=assumptions)
    if not on_alternative:
        return _close(session, path, paperwork=PAPER, article=article, message=message, assumptions=assumptions)
    return _close(
        session, path, process=opened, evidence=types, evidence_required=True,
        paperwork=PAPER + (SCOPE,), article=article, message=message, assumptions=assumptions,
    )


def run_after(prompt, session: Session) -> dict:
    """Packaged decide_path. Process fields and evidence types come from the engine."""
    session.stage("design")
    scope = session.classify()
    if scope.status == "redirect":
        decision = decide_path(make_case(session))
        if decision.path != "redirect":
            raise SystemExit(f"decide_path missed a redirect on {prompt.id}: {decision.path}")
        return _close(session, "redirect", note=scope.message)

    session.obtained.update(session.stated())
    for question in session.plan(set(session.stated()), departure_known=True):
        if question.field == "product_scope":
            session.ask(stage="route", field="product_scope", kind="decision", text=question.text)

    rule_id = _select_rule(session)
    result = _resolve(session, rule_id, ask=True) if rule_id else None
    case = make_case(session)
    decision = decide_path(case)
    if decision.path == "alternative" and not alternative_path(case):
        raise SystemExit(f"alternative_path disagreed with decide_path on {prompt.id}")
    if decision.path != "alternative" and alternative_path(case):
        raise SystemExit(f"alternative_path stayed open on {decision.path} for {prompt.id}")

    article = decision.article if decision.firm else None
    message = ""
    assumptions: list[str] = []
    if result and decision.firm and decision.rule_id == result.get("rule_id", rule_id):
        message = result["message"]
        assumptions = list(result["assumptions"])
    elif result and decision.source != "coded_check":
        assumptions = list(result["assumptions"])

    if decision.path in {"unresolved", "not_applicable", "redirect"}:
        return _close(session, decision.path, article=article, message=message, assumptions=assumptions)

    opened = _process_questions(process_fields(case, codes()))
    if decision.path == "acceptable":
        if opened:
            raise SystemExit(f"process fields opened on acceptable for {prompt.id}")
        return _close(
            session, decision.path, evidence=CONFIDENCE_LADDER, evidence_required=True, paperwork=PAPER,
            article=article, message=message, assumptions=assumptions,
        )
    types = _evidence(True, CONFIDENCE_LADDER, ALTERNATIVE_EVIDENCE_TYPES)
    if [field for field, _text in opened] != [
        "rationale", "risk_assessment", "mitigating_measures", "assumptions_and_limits",
        "maintenance_operation", "qualifications",
    ]:
        raise SystemExit(f"unexpected process fields on {prompt.id}: {opened}")
    return _close(
        session, decision.path, process=opened, evidence=types, evidence_required=True,
        paperwork=PAPER + (SCOPE,), article=article, message=message, assumptions=assumptions,
    )


ARMS = {
    "BEFORE": run_before,
    "FLOWCHART": run_w1,
    "FLOWCHART+LOOKUP": run_w1l,
    "AFTER": run_after,
}
SHADOW = {"BEFORE": run_w0, "AFTER": run_w2}


def _assert_frozen(prompts) -> None:
    previous = json.loads(FROZEN.read_text(encoding="utf-8"))
    old = [item["id"] for item in previous["prompts"]]
    new = [prompt.id for prompt in prompts]
    if old != new or len(new) != 152:
        raise SystemExit(f"frozen prompt ids changed ({len(old)} frozen, {len(new)} loaded)")


def _public_question(question: dict) -> dict:
    return {key: question[key] for key in ("n", "stage", "field", "answerer", "kind", "text", "answer", "status")} | {
        "redundant": question.get("redundant", False),
        "redundant_reason": question.get("redundant_reason", ""),
    }


def _row(pass_n: int, name: str, prompt, gold: dict, result: dict, scored: dict, *, keep_text: bool) -> dict:
    return {
        "pass": pass_n,
        "workflow": name,
        "prompt_id": prompt.id,
        "slice": gold["slice"],
        "source": prompt.source,
        "gold_path": gold["path"],
        "path": scored["path"],
        "path_match": scored["path_match"],
        "quality": scored["quality"],
        "reason": scored["reason"],
        "questions": scored["questions"],
        "necessary": scored["necessary"],
        "redundant": scored["redundant"],
        "applicant_questions": scored["applicant_questions"],
        "designer_questions": scored["designer_questions"],
        "office_questions": scored["office_questions"],
        "quality_per_question": round(scored["quality_per_question"], 4),
        "fabricated": scored["fabricated"],
        "fabricated_ids": scored["fabricated_ids"],
        "claims_compliance": scored["claims_compliance"],
        "silent_fills": scored["silent_fills"],
        "checks": scored["checks"],
        "stages": result["stages"],
        "process_asked": result["process_asked"],
        "evidence_types": result["evidence_types"],
        "evidence_required": result["evidence_required"],
        "article": result["article"],
        "questions_detail": [_public_question(q) for q in result["questions"]] if keep_text else [],
        "draft_text": result["draft_text"] if keep_text else "",
        "completeness_text": result["completeness_text"] if keep_text else "",
    }


def main() -> None:
    self_check()
    current_source = inspect.getsource(alternative_path)
    if "decide_path" not in current_source:
        raise SystemExit("current alternative_path does not call decide_path")
    if tuple(CONFIDENCE_LADDER) != OLD["ladder"] or tuple(ALTERNATIVE_EVIDENCE_TYPES) != OLD["extras"]:
        raise SystemExit("evidence tuples diverged from origin/main; the gate is the only intended change")
    prompts, gold, hidden = load()
    _assert_frozen(prompts)

    runs = []
    shadow_mismatch = []
    for pass_n in (1, 2):
        for name, arm in ARMS.items():
            print(f"pass {pass_n} {name}", file=sys.stderr, flush=True)
            for prompt in prompts:
                session = Session(prompt, hidden.get(prompt.id, {}))
                result = arm(prompt, session)
                scored = score_run(result, gold[prompt.id]["path"])
                runs.append(_row(pass_n, name, prompt, gold[prompt.id], result, scored, keep_text=pass_n == 1))
                if pass_n == 1 and name in SHADOW:
                    shadow = SHADOW[name](prompt, Session(prompt, hidden.get(prompt.id, {})))
                    if shadow["path"] != result["path"] or shadow["process_asked"] != result["process_asked"] or bool(shadow["evidence_required"]) != bool(result["evidence_required"]):
                        shadow_mismatch.append({
                            "workflow": name,
                            "prompt_id": prompt.id,
                            "function_path": result["path"],
                            "harness_path": shadow["path"],
                            "function_process": list(result["process_asked"]),
                            "harness_process": list(shadow["process_asked"]),
                            "function_evidence": bool(result["evidence_required"]),
                            "harness_evidence": bool(shadow["evidence_required"]),
                        })

    first = {(row["workflow"], row["prompt_id"]): row for row in runs if row["pass"] == 1}
    second = {(row["workflow"], row["prompt_id"]): row for row in runs if row["pass"] == 2}
    max_quality_delta = 0
    max_question_delta = 0
    for key, row in first.items():
        other = second[key]
        max_quality_delta = max(max_quality_delta, abs(row["quality"] - other["quality"]))
        max_question_delta = max(max_question_delta, abs(row["questions"] - other["questions"]))

    rows = [row for row in runs if row["pass"] == 1]
    OUT.mkdir(parents=True, exist_ok=True)
    fields = [
        "workflow", "prompt_id", "slice", "source", "gold_path", "path", "path_match",
        "quality", "reason", "questions", "necessary", "redundant",
        "applicant_questions", "designer_questions", "office_questions",
        "quality_per_question", "fabricated", "fabricated_ids", "claims_compliance",
        "silent_fills", "stages", "process_asked", "evidence_required", "article",
    ]
    csv_path = OUT / "per_prompt.csv"
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow({
                **{key: row[key] for key in fields if key not in {"fabricated_ids", "stages", "process_asked"}},
                "fabricated_ids": "; ".join(row["fabricated_ids"]),
                "stages": "; ".join(row["stages"]),
                "process_asked": "; ".join(row["process_asked"]),
            })
    with (OUT / "both_passes.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["pass", "workflow", "prompt_id", "quality", "questions", "path"])
        writer.writeheader()
        for row in runs:
            writer.writerow({key: row[key] for key in ("pass", "workflow", "prompt_id", "quality", "questions", "path")})

    summary = _summary(rows, max_quality_delta, max_question_delta, len(prompts))
    summary["origin_main"] = OLD_REVISION
    summary["shadow_mismatches"] = shadow_mismatch
    summary["confusion"] = _confusion(rows)
    dev = next(row for row in rows if row["workflow"] == "AFTER" and row["prompt_id"] == "dev-001")
    summary["dev_001_after"] = {
        "path": dev["path"],
        "article": dev["article"],
        "quality": dev["quality"],
        "questions": dev["questions"],
        "reason": dev["reason"],
        "section_c": section_c_for(dev["article"]).text,
        "checks": dev["checks"],
    }
    (OUT / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    (OUT / "summary.md").write_text(_markdown(summary), encoding="utf-8")
    (OUT / "dev-001.json").write_text(json.dumps({
        "after": summary["dev_001_after"],
        "rows": [
            {key: row[key] for key in ("workflow", "path", "gold_path", "quality", "questions", "reason", "article", "process_asked", "evidence_required", "checks")}
            for row in rows if row["prompt_id"] == "dev-001"
        ],
    }, indent=2), encoding="utf-8")
    print(_markdown(summary))
    print(f"shadow mismatches: {len(shadow_mismatch)}", file=sys.stderr)
    if shadow_mismatch[:5]:
        print(json.dumps(shadow_mismatch[:5], indent=2), file=sys.stderr)
    if max_quality_delta or max_question_delta:
        raise SystemExit(f"inter-run variation quality={max_quality_delta} questions={max_question_delta}")


def _confusion(rows: list[dict]) -> dict:
    out: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for row in rows:
        out[row["workflow"]][f"{row['gold_path']}->{row['path']}"] += 1
    return {name: dict(sorted(counts.items())) for name, counts in out.items()}


if __name__ == "__main__":
    main()
