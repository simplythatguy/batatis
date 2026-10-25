#!/usr/bin/env python3
"""Validate committed metadata; optionally verify restored attachment bytes."""

import argparse
import json
import re
from collections import Counter

from corpus import BASE, attachment_files, cases, check_file, child


def require(condition, message):
    if not condition:
        raise ValueError(message)


def verify(base=BASE, numbers=None, attachments=False):
    report = {"prompts": 0, "attachment_files": 0, "priorities": {}, "errors": []}
    counts = Counter()
    for row, folder, source in cases(base, numbers):
        report["prompts"] += 1
        counts[row["priority_tier"]] += 1
        try:
            require(row["folder"] == f"Prompt {row['prompt']}", "folder numbering mismatch")
            require(source["prompt_number"] == row["prompt"], "source numbering mismatch")
            require(source["id"] == row["case_id"], "case ID mismatch")
            require(source["priority_tier"] == row["priority_tier"], "priority mismatch")
            require(source["case_type"] == row["case_type"], "case type mismatch")
            require(len(source["attachments"]) == row["attachments"], "attachment count mismatch")
            require(source["facts"] and all(f.get("text") and f.get("locator")
                                           for f in source["facts"]), "fact locator missing")
            evaluation = json.loads((folder / "evaluation.json").read_text())
            require(type(evaluation["outcome_leakage"]) is bool, "invalid outcome-leakage flag")
            require(evaluation["outcome_leakage"] == row["outcome_leakage"], "leakage mismatch")
            require(evaluation["evaluator_only"] is True, "evaluation must be held back")
            prompt = (folder / "prompt.txt").read_text()
            listed = prompt.split("\nAttachments:\n", 1)[1].split("\n\n", 1)[0].splitlines()
            expected = ["- " + a.get("derived_text", a)["filename"]
                        for a in source["attachments"] if a["included_in_default_input"]]
            require(listed == expected and expected, "default input list mismatch")
            require(not any("_evaluation/" in value for value in expected), "evaluator input leaked")
            for item, original, derived in attachment_files(source):
                path = child(folder, item["filename"])
                require(re.fullmatch(r"[0-9a-f]{64}", item["sha256"]), "invalid hash")
                require(original["url"].startswith(("http://", "https://")), "source URL missing")
                if attachments:
                    check_file(path, item)
                    report["attachment_files"] += 1
        except (OSError, ValueError, KeyError, IndexError) as exc:
            report["errors"].append({"prompt": row["prompt"], "error": str(exc)})
    index = json.loads((base / "index.json").read_text())
    if [row["prompt"] for row in index] != list(range(1, len(index) + 1)):
        report["errors"].append({"error": "index numbering is not contiguous"})
    report["priorities"] = dict(sorted(counts.items()))
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prompt", action="append", type=int)
    parser.add_argument("--attachments", action="store_true", help="also require all originals and evaluator references")
    args = parser.parse_args()
    try:
        report = verify(BASE, args.prompt, args.attachments)
    except (OSError, ValueError) as exc:
        parser.error(str(exc))
    print(json.dumps(report, indent=2))
    return bool(report["errors"])


if __name__ == "__main__":
    raise SystemExit(main())
