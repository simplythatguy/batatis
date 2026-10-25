#!/usr/bin/env python3
"""Download the file links exposed by each exact package landing page."""
import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from collect import fetch

BASE = Path(__file__).resolve().parents[1]


def main():
    audit = json.loads((BASE / "_source_package" / "link_audit.json").read_text())
    sources = {}
    for row in audit:
        for url in row.get("download_links", []):
            if url != row["url"]:
                sources.setdefault(url, []).append(row["id"])
    target = BASE / "_source_package" / "resource_audit.json"
    previous = json.loads(target.read_text()) if target.exists() else []
    by_url = {r["url"]: r for r in previous if r.get("status") == "downloaded" and Path(r.get("path", "")).is_file()}
    results = list(by_url.values())
    def retrieve(url):
        record = fetch(url, BASE / "_references" / "package")
        return {**record, "parent_package_links": sources[url]}
    with ThreadPoolExecutor(max_workers=4) as pool:
        jobs = {pool.submit(retrieve, u): u for u in sources if u not in by_url}
        for job in as_completed(jobs):
            url = jobs[job]
            try:
                row = job.result()
            except Exception as exc:
                row = {"url": url, "status": "error", "error": str(exc), "parent_package_links": sources[url]}
            results.append(row)
            target.write_text(json.dumps(results, indent=2) + "\n")
            print(len(results), "/", len(sources), row.get("kind"), row["status"], url, flush=True)
    print("RESOURCE AUDIT COMPLETE", len(results), flush=True)


if __name__ == "__main__":
    main()
