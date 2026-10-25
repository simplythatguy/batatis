#!/usr/bin/env python3
"""Retrieve every exact target in the supplied DOCX and inventory its outgoing links."""
import json
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin, urlparse
from collect import fetch

BASE = Path(__file__).resolve().parents[1]


class Links(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links = []
    def handle_starttag(self, tag, attrs):
        values = dict(attrs)
        if tag in ("a", "iframe", "source", "video"):
            value = values.get("href") or values.get("src")
            if value:
                self.links.append(value)


def retrieve(row):
    record = fetch(row["url"], BASE / "_source_package" / "downloads", row["id"])
    out = {**row, **record, "outgoing_links": [], "download_links": []}
    if record.get("kind") == "html":
        parser = Links()
        parser.feed(Path(record["path"]).read_text(errors="replace"))
        links = list(dict.fromkeys(urljoin(record["final_url"], u) for u in parser.links))
        out["outgoing_links"] = [u for u in links if urlparse(u).scheme in ("https", "http")]
        out["download_links"] = [u for u in out["outgoing_links"] if re.search(r"\.(pdf|docx?|xlsx?|zip|pptx?|csv|json)(?:$|[?#])|/download/|/eng/view/(?:ft|accepted)/", u, re.I)]
    return out


def main():
    records = json.loads((BASE / "_source_package" / "links.json").read_text())
    results = []
    target = BASE / "_source_package" / "link_audit.json"
    with ThreadPoolExecutor(max_workers=5) as pool:
        jobs = {pool.submit(retrieve, row): row for row in records}
        for job in as_completed(jobs):
            row = jobs[job]
            try:
                result = job.result()
            except Exception as exc:
                result = {**row, "status": "audit_error", "error": str(exc)}
            results.append(result)
            results.sort(key=lambda r: r["id"])
            target.write_text(json.dumps(results, indent=2) + "\n")
            print(result["id"], result["status"], result.get("http_status"), result.get("kind"),
                  "child_downloads", len(result.get("download_links", [])), flush=True)
    print("AUDIT COMPLETE", len(results), flush=True)


if __name__ == "__main__":
    main()
