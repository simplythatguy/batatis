#!/usr/bin/env python3
"""Recompute evaluation groups after changing source attachment membership."""

import csv
import json
import re

from corpus import BASE, cases, source_groups


def main():
    index = json.loads((BASE / "index.json").read_text())
    groups = source_groups([source for _, _, source in cases()])
    for row in index:
        row["source_group"] = groups[row["case_id"]]
    (BASE / "index.json").write_text(json.dumps(index, indent=2, ensure_ascii=False) + "\n")
    for filename, rows in (
        ("index.csv", index),
        ("Alberta Prompt Index.csv", [r for r in index if r["priority_tier"] <= 2]),
        ("Comparative Prompt Index.csv", [r for r in index if r["priority_tier"] == 4]),
    ):
        with (BASE / filename).open("w", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=list(index[0]), lineterminator="\n")
            writer.writeheader()
            writer.writerows(rows)
    count = len(set(groups.values()))
    path = BASE / "_research" / "assembly_report.json"
    report = json.loads(path.read_text())
    report.update(distinct_source_groups=count,
                  source_group_definition="connected components of all shared default-input original attachments")
    path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
    path = BASE / "README.md"
    path.write_text(re.sub(r"There are \d+ groups of shared original input sources",
                           f"There are {count} groups of shared original input sources", path.read_text()))
    print(json.dumps({"prompts": len(index), "source_groups": count}))


if __name__ == "__main__":
    main()
