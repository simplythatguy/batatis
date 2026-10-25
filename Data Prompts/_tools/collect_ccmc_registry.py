#!/usr/bin/env python3
"""Collect every document explicitly linked by the supplied live CCMC registry."""
import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from urllib.parse import parse_qs, urlparse
from collect import fetch

BASE = Path(__file__).resolve().parents[1]


def main():
    audit = json.loads((BASE / "_source_package" / "link_audit.json").read_text())
    registry = next(row for row in audit if row["id"] == "PKG-07")
    urls = [url for url in registry["outgoing_links"] if "/document.html?" in url]
    target = BASE / "_source_package" / "ccmc_document_audit.json"
    previous = json.loads(target.read_text()) if target.exists() else []
    good = {r["url"]: r for r in previous if r.get("status") == "downloaded" and Path(r.get("path", "")).is_file()}
    results = list(good.values())
    def retrieve(url):
        identifier = parse_qs(urlparse(url).query).get("id", ["unknown"])[0]
        record = fetch(url, BASE / "_references" / "ccmc-registry", "CCMC-" + identifier + "-certificate")
        return {**record, "parent_package_link": "PKG-07", "ccmc_id": identifier,
                "source_role": "registry-linked product assessment certificate; not an individual building application"}
    with ThreadPoolExecutor(max_workers=4) as pool:
        jobs = {pool.submit(retrieve, url): url for url in urls if url not in good}
        for job in as_completed(jobs):
            url = jobs[job]
            try:
                row = job.result()
            except Exception as exc:
                row = {"url": url, "status": "error", "error": str(exc)}
            results.append(row)
            target.write_text(json.dumps(results, indent=2) + "\n")
            if len(results) % 25 == 0 or row["status"] != "downloaded":
                print(len(results), "/", len(urls), row["status"], row.get("kind"), flush=True)
    print("CCMC DOCUMENT AUDIT COMPLETE", len(results), flush=True)


if __name__ == "__main__":
    main()
