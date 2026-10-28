"""Run every arm twice on the frozen prompt set and write the tables.

Usage (from the repo root): python experiments/workflow-bakeoff/run.py
"""
from __future__ import annotations

import csv
import json
import sys
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(ROOT))

from prompts import load  # noqa: E402
from score import score_run, self_check  # noqa: E402
from session import Session  # noqa: E402
from workflows import ARMS  # noqa: E402

OUT = HERE / "results"
FROZEN = HERE / "frozen" / "prompts.json"


def _one(arm, prompt, hidden) -> dict:
    session = Session(prompt, hidden.get(prompt.id, {}))
    result = arm(prompt, session)
    return result


def _public_question(question: dict) -> dict:
    return {
        "n": question["n"],
        "stage": question["stage"],
        "field": question["field"],
        "answerer": question["answerer"],
        "kind": question["kind"],
        "text": question["text"],
        "answer": question["answer"],
        "status": question["status"],
        "redundant": question.get("redundant", False),
        "redundant_reason": question.get("redundant_reason", ""),
    }


def _assert_frozen(prompts) -> None:
    previous = json.loads(FROZEN.read_text(encoding="utf-8"))
    old = [item["id"] for item in previous["prompts"]]
    new = [prompt.id for prompt in prompts]
    if old != new:
        raise SystemExit(f"prompt ids changed ({len(old)} frozen, {len(new)} loaded)")
    if len(new) != 152:
        raise SystemExit(f"expected 152 frozen prompts, found {len(new)}")


def main() -> None:
    self_check()
    prompts, gold, hidden = load()
    _assert_frozen(prompts)

    runs = []
    for pass_n in (1, 2):
        for name, arm in ARMS.items():
            print(f"pass {pass_n} {name}", file=sys.stderr, flush=True)
            for prompt in prompts:
                result = _one(arm, prompt, hidden)
                scored = score_run(result, gold[prompt.id]["path"])
                runs.append({
                    "pass": pass_n,
                    "workflow": name,
                    "prompt_id": prompt.id,
                    "slice": gold[prompt.id]["slice"],
                    "source": prompt.source,
                    "gold_path": gold[prompt.id]["path"],
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
                    "questions_detail": [_public_question(q) for q in result["questions"]] if pass_n == 1 else [],
                    "draft_text": result["draft_text"] if pass_n == 1 else "",
                    "completeness_text": result["completeness_text"] if pass_n == 1 else "",
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
    csv_path = OUT / "per_prompt.csv"
    fields = [
        "workflow", "prompt_id", "slice", "source", "gold_path", "path", "path_match",
        "quality", "reason", "questions", "necessary", "redundant",
        "applicant_questions", "designer_questions", "office_questions",
        "quality_per_question", "fabricated", "fabricated_ids", "claims_compliance",
        "silent_fills", "stages", "process_asked", "evidence_required", "article",
    ]
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

    detail_path = OUT / "per_prompt.json"
    detail_path.write_text(json.dumps(rows, indent=2), encoding="utf-8")
    passes_path = OUT / "both_passes.csv"
    with passes_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["pass", "workflow", "prompt_id", "quality", "questions"])
        writer.writeheader()
        for row in runs:
            writer.writerow({key: row[key] for key in ("pass", "workflow", "prompt_id", "quality", "questions")})

    summary = _summary(rows, max_quality_delta, max_question_delta, len(prompts))
    (OUT / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    (OUT / "summary.md").write_text(_markdown(summary), encoding="utf-8")
    print(_markdown(summary))
    if max_quality_delta or max_question_delta:
        raise SystemExit(f"inter-run variation quality={max_quality_delta} questions={max_question_delta}")
    bad = [row for row in rows if row["fabricated"]]
    if bad:
        sample = bad[0]
        raise SystemExit(
            f"fabrication: {sample['workflow']} {sample['prompt_id']} ids={sample['fabricated_ids']}"
        )


def _summary(rows: list[dict], quality_delta: int, question_delta: int, n: int) -> dict:
    by_workflow: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        by_workflow[row["workflow"]].append(row)
    workflows = []
    for name, items in by_workflow.items():
        def mean(key, subset=items):
            return sum(item[key] for item in subset) / len(subset)

        app = [item for item in items if item["slice"] == "application"]
        rule = [item for item in items if item["slice"] == "rule"]
        balanced_quality = 0.5 * mean("quality", app) + 0.5 * mean("quality", rule)
        balanced_questions = 0.5 * mean("questions", app) + 0.5 * mean("questions", rule)
        workflows.append({
            "workflow": name,
            "n": len(items),
            "n_application": len(app),
            "n_rule": len(rule),
            "balanced_quality": round(balanced_quality, 4),
            "balanced_questions": round(balanced_questions, 4),
            "quality_per_balanced_question": round(balanced_quality / max(balanced_questions, 1), 4),
            "mean_quality": round(mean("quality"), 4),
            "mean_questions": round(mean("questions"), 4),
            "mean_necessary": round(mean("necessary"), 4),
            "mean_redundant": round(mean("redundant"), 4),
            "mean_quality_application": round(mean("quality", app), 4),
            "mean_quality_rule": round(mean("quality", rule), 4),
            "mean_questions_application": round(mean("questions", app), 4),
            "mean_questions_rule": round(mean("questions", rule), 4),
            "path_match_rate": round(mean("path_match"), 4),
            "fabricated_total": sum(item["fabricated"] for item in items),
            "prompts_with_fabrication": sum(1 for item in items if item["fabricated"]),
            "claims_compliance": sum(1 for item in items if item["claims_compliance"]),
            "silent_fills_total": sum(item["silent_fills"] for item in items),
            "eligible": sum(item["fabricated"] for item in items) == 0,
            "check_fail_counts": _fails(items),
        })
    eligible = [item for item in workflows if item["eligible"]]
    ranked = sorted(eligible, key=lambda item: (-item["balanced_quality"], item["balanced_questions"]))
    winner = None
    if ranked:
        top = ranked[0]
        tied = [item for item in ranked if abs(item["balanced_quality"] - top["balanced_quality"]) <= 0.25]
        winner = min(tied, key=lambda item: item["balanced_questions"])["workflow"]
    return {
        "n_prompts": n,
        "inter_run_max_abs_quality_delta": quality_delta,
        "inter_run_max_abs_question_delta": question_delta,
        "workflows": workflows,
        "winner_by_frozen_rule": winner,
    }


def _fails(items: list[dict]) -> dict:
    counts: dict[str, int] = defaultdict(int)
    for item in items:
        for name, ok in item["checks"].items():
            if not ok:
                counts[name] += 1
    return dict(counts)


def _markdown(summary: dict) -> str:
    lines = [
        "| workflow | balanced quality | balanced questions | quality / question | path match | fabricated prompts | eligible |",
        "|---|---:|---:|---:|---:|---:|---|",
    ]
    for item in summary["workflows"]:
        lines.append(
            f"| {item['workflow']} | {item['balanced_quality']:.3f} | {item['balanced_questions']:.2f} | "
            f"{item['quality_per_balanced_question']:.3f} | {item['path_match_rate']:.3f} | "
            f"{item['prompts_with_fabrication']} | {item['eligible']} |"
        )
    lines.append("")
    lines.append(f"Winner by the frozen rule: {summary['winner_by_frozen_rule']}")
    lines.append(
        f"Inter-run max |Δ quality| = {summary['inter_run_max_abs_quality_delta']}, "
        f"|Δ questions| = {summary['inter_run_max_abs_question_delta']}. n = {summary['n_prompts']}."
    )
    lines.append("")
    lines.append("| workflow | application quality | rule quality | application questions | rule questions | redundant | fails |")
    lines.append("|---|---:|---:|---:|---:|---:|---|")
    for item in summary["workflows"]:
        fails = ", ".join(f"{key} {value}" for key, value in sorted(item["check_fail_counts"].items()))
        lines.append(
            f"| {item['workflow']} | {item['mean_quality_application']:.3f} | {item['mean_quality_rule']:.3f} | "
            f"{item['mean_questions_application']:.2f} | {item['mean_questions_rule']:.2f} | "
            f"{item['mean_redundant']:.2f} | {fails} |"
        )
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    main()
