#!/usr/bin/env python3
"""Follow the actual PDF viewer URLs found in saved CCMC assessment pages."""
import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from urllib.parse import urljoin
from audit_package import Links
from collect import fetch

BASE = Path(__file__).resolve().parents[1]


def main():
    pages = json.loads((BASE / "_source_package" / "ccmc_document_audit.json").read_text())
    sources = {}
    for page in pages:
        if page.get("kind") != "html":
            continue
        parser = Links()
        parser.feed(Path(page["path"]).read_text(errors="replace"))
        for link in parser.links:
            if "pdf.html?" in link:
                url = urljoin(page["final_url"], link)
                sources.setdefault(url, []).append(page["ccmc_id"])
    target = BASE / "_source_package" / "ccmc_pdf_audit.json"
    previous = json.loads(target.read_text()) if target.exists() else []
    good = {r["url"]: r for r in previous if r.get("kind") == "pdf" and Path(r.get("path", "")).is_file()}
    results = list(good.values())
    def retrieve(url):
        return {**fetch(url, BASE / "_references" / "ccmc-registry", "CCMC-" + sources[url][0] + "-assessment"),
                "ccmc_ids": sources[url], "parent_package_link": "PKG-07"}
    with ThreadPoolExecutor(max_workers=4) as pool:
        jobs = {pool.submit(retrieve, u): u for u in sources if u not in good}
        for job in as_completed(jobs):
            url = jobs[job]
            try:
                row = job.result()
            except Exception as exc:
                row = {"url": url, "status": "error", "error": str(exc)}
            results.append(row)
            target.write_text(json.dumps(results, indent=2) + "\n")
            if len(results) % 25 == 0 or row.get("kind") != "pdf":
                print(len(results), "/", len(sources), row["status"], row.get("kind"), flush=True)
    print("CCMC PDF AUDIT COMPLETE", len(results), "of", len(pages), "pages inspected", flush=True)


if __name__ == "__main__":
    main()
