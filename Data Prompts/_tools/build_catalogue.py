#!/usr/bin/env python3
"""Index saved original downloads and preserve research/access gaps separately."""
import csv
import hashlib
import json
from collections import Counter
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]


def main():
    sources, issues, gaps, leads, evidence_gaps, rejected = [], [], [], [], [], []
    seen = set()
    for receipt in sorted(BASE.rglob("*.source.json")):
        try:
            data = json.loads(receipt.read_text())
            path = Path(data.get("path", ""))
            if not path.is_file():
                path = receipt.with_name(receipt.name.removesuffix(".source.json"))
            if not path.is_file():
                issues.append({"receipt": str(receipt.relative_to(BASE)), "error": "saved source path absent"})
                continue
            actual = hashlib.sha256(path.read_bytes()).hexdigest()
            if data.get("sha256") and actual != data["sha256"]:
                issues.append({"receipt": str(receipt.relative_to(BASE)), "error": "source hash mismatch"})
                continue
            if path.stat().st_size == 0:
                rejected.append({"receipt": str(receipt.relative_to(BASE)), "url": data.get("url"), "reason": "empty HTTP response capture; not a source document"})
                continue
            url = data.get("url", "")
            key = (url, actual)
            if key in seen:
                continue
            seen.add(key)
            relative = str(path.relative_to(BASE)) if path.is_relative_to(BASE) else str(path)
            sources.append({"path": relative, "url": url, "final_url": data.get("final_url", url),
                            "retrieved_at": data.get("retrieved_at", "not recorded"), "sha256": actual,
                            "bytes": path.stat().st_size, "kind": data.get("kind", path.suffix.lstrip(".")),
                            "receipt": str(receipt.relative_to(BASE)), "entity_extraction": data.get("entity_extraction", ""),
                            "possible_block_page": data.get("possible_block_page", False),
                            "reuse_status": "rights_review_required" if "nrc-publications.canada.ca" in url else "publisher_terms_apply"})
        except Exception as exc:
            issues.append({"receipt": str(receipt.relative_to(BASE)), "error": str(exc)})
    for manifest in sorted((BASE / "_research" / "workers").glob("*/candidates.json")):
        try:
            data = json.loads(manifest.read_text())
            for entry in data.get("blocked", []):
                gaps.append({"worker": manifest.parent.name, "entry": entry})
            for entry in data.get("unvisited_leads", []):
                leads.append({"worker": manifest.parent.name, "entry": entry})
            for entry in data.get("gaps", []):
                evidence_gaps.append({"worker": manifest.parent.name, "entry": entry})
        except Exception as exc:
            issues.append({"manifest": str(manifest.relative_to(BASE)), "error": str(exc)})
    with (BASE / "downloads.csv").open("w", newline="") as stream:
        if sources:
            writer = csv.DictWriter(stream, fieldnames=list(sources[0]))
            writer.writeheader()
            writer.writerows(sources)
    (BASE / "source_catalogue.jsonl").write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in sources))
    (BASE / "source_gaps.json").write_text(json.dumps({"access_gaps": gaps, "evidence_gaps": evidence_gaps, "unvisited_leads": leads, "rejected_empty_captures": rejected,
             "note": "Worker gaps preserve the attempt history. Another worker may have recovered a source later; consult downloads.csv and the package audit before treating a gap as unresolved."}, indent=2, ensure_ascii=False) + "\n")
    summary = {"source_url_hash_records": len(sources), "unique_source_hashes": len({r["sha256"] for r in sources}),
               "formats": dict(Counter(r["kind"] for r in sources)), "access_gap_records": len(gaps),
               "unvisited_lead_records": len(leads), "rejected_empty_captures": len(rejected), "integrity_issues": issues}
    (BASE / "_research" / "catalogue_validation.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
