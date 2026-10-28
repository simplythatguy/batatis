"""Frozen prompt set. Gold stays in a side table the workflows never receive."""
from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

CASES = ROOT / "evals_dev" / "cases"
VECTORS = ROOT / "evals_dev" / "rules" / "vectors.json"
DEMOS = (
    (
        "demo-a",
        ROOT / "evals/demo-cases/a-manufacturer-nailbase-sheathing/input/project-brief.md",
        "alternative",
        "README route table: vinyl on the nail-base panel is a departure from the cladding fastening rule.",
    ),
    (
        "demo-b",
        ROOT / "evals/demo-cases/b-contractor-firestop-nonconformance/input/project-brief.md",
        "unresolved",
        "README: remediate to a tested system first; a variance is only where no tested system exists, which this brief does not establish.",
    ),
    (
        "demo-c",
        ROOT / "evals/demo-cases/c-homebuilder-infill-house/input/project-brief.md",
        "alternative",
        "README: the bedroom window is the departure.",
    ),
)

RULE_PATH = {
    "follows": "acceptable",
    "departs": "alternative",
    "needs_info": "unresolved",
    "not_applicable": "not_applicable",
}


@dataclass(frozen=True)
class Prompt:
    id: str
    kind: str
    source: str
    text: str
    rule_id: str | None = None
    fact_text: str = ""


def _case_path(gold: dict) -> str:
    if gold.get("intake_action") == "redirect" or gold.get("out_of_scope"):
        return "redirect"
    if (gold.get("departure") or "").strip():
        return "alternative"
    if gold.get("intake_action") == "ask":
        return "unresolved"
    raise ValueError("unlabeled case path")


def load() -> tuple[list[Prompt], dict[str, dict], dict[str, dict]]:
    prompts: list[Prompt] = []
    gold: dict[str, dict] = {}
    hidden: dict[str, dict] = {}

    for path in sorted(CASES.glob("dev-*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        facts = "\n".join(f"- {line}" for line in data.get("known_facts") or [])
        text = data["description"].strip()
        if facts:
            text = f"{text}\n\nAlready stated:\n{facts}"
        prompts.append(Prompt(data["id"], "case", str(path.relative_to(ROOT)), text, None, text))
        gold[data["id"]] = {
            "path": _case_path(data["gold"]),
            "basis": "evals_dev case: nonempty gold.departure → alternative; empty departure with intake_action ask → unresolved; redirect or out_of_scope → redirect.",
            "slice": "application",
        }

    vectors = json.loads(VECTORS.read_text(encoding="utf-8"))["vectors"]
    from engine.rules.evaluator import load_rule

    for row in vectors:
        rule = load_rule(row["rule"])
        fact = row["description"].strip()
        text = f"{rule['title']}. Article {rule['article']}. {fact}"
        prompts.append(Prompt(row["id"], "rule", "evals_dev/rules/vectors.json", text, row["rule"], fact))
        gold[row["id"]] = {
            "path": RULE_PATH[row["expect"]["state"]],
            "basis": f"vector expect.state {row['expect']['state']} → {RULE_PATH[row['expect']['state']]}",
            "slice": "rule",
            "expect_provision": row["expect"].get("provision"),
        }
        hidden[row["id"]] = dict(row["inputs"])

    for pid, path, label, basis in DEMOS:
        body = path.read_text(encoding="utf-8").strip()
        prompts.append(Prompt(pid, "case", str(path.relative_to(ROOT)), body, None, body))
        gold[pid] = {"path": label, "basis": basis, "slice": "application"}

    return prompts, gold, hidden
