#!/usr/bin/env python3
"""Consolidate the direct DOCX audit, linked resource sweep and detailed package worker."""
import json
from collections import defaultdict
from pathlib import Path
from urllib.parse import quote

BASE = Path(__file__).resolve().parents[1]


def link(path, label="saved file"):
    path = Path(path)
    relative = path.relative_to(BASE) if path.is_absolute() else path
    return f"[{label}]({quote(str(relative), safe='/')})"


def main():
    audit = json.loads((BASE / "_source_package" / "link_audit.json").read_text())
    resources = json.loads((BASE / "_source_package" / "resource_audit.json").read_text())
    detailed = json.loads((BASE / "_research" / "workers" / "H19" / "candidates.json").read_text())
    by_package = defaultdict(list)
    for reference in detailed.get("references", []):
        if reference.get("kind") == "pdf":
            for identifier in reference.get("package_ids", []):
                by_package[identifier].append(reference)
    child_counts = {row["id"]: sum(row["id"] in child.get("parent_package_links", []) for child in resources) for row in audit}
    rows = ["# Supplied package audit", "", "The DOCX contains 38 external hyperlink relationships pointing to 37 unique targets, with no embedded files. Every unique target was retrieved and its outgoing document links were inventoried. Original DOCX bytes, hyperlink IDs, display labels, source paragraphs and retrieval metadata are preserved under `_source_package/`.", "",
            "## Download coverage", "",
            f"- Direct package targets: {len(audit)} / 37 retrieved (PDFs and landing pages are distinguished below).",
            f"- Document URLs exposed by those target landing pages: {len(resources)} attempted; {sum(r.get('status') == 'downloaded' for r in resources)} downloaded. The obsolete HTTP SCC FAQ link was recovered from its official HTTPS equivalent, with the failed attempt retained.",
            "- CCMC registry: all 462 linked assessment pages and their 462 PDF viewer targets were downloaded. All 462 PDFs passed SHA-256 and page-tree checks (4,904 pages). These are product assessments, not individual building applications.",
            "- Supplemental package audit: H19 retained 66 records, including archive continuations, legislation PDFs, newer printings, rights pages and training/video metadata. See the [38-link detail table](_research/workers/H19/package-audit.md) and [audit report](_research/workers/H19/report.md).",
            "- YouTube webinar: watch/oEmbed metadata and availability checked; video bytes were not downloaded. CSA training requires registration and returned 403; no registered training video was retrieved. Account portals were not accessed.", "",
            "This is a bounded audit of the supplied links, directly exposed document resources, and the complete registry-linked assessment set. The NRC Publications Archive is a large research repository; the case researchers searched relevant families, and this audit does not claim to have downloaded its entire corpus or every external reference cited inside code books.", "",
            "## Every unique package target", "", "| ID | Package label | Original target / saved target | Linked file URLs downloaded | Supplemental PDFs |", "| --- | --- | --- | ---: | --- |"]
    for item in audit:
        contexts = item.get("document_context", [])
        labels = "; ".join(dict.fromkeys(c.get("label", "") for c in contexts)) or item["url"]
        labels = labels.replace("|", "/")
        direct = f"[original URL]({item['url']}) · {link(item['path'], item.get('kind', 'target'))}"
        supplements = "; ".join(link(r["path"], r.get("ref_id", "PDF")) for r in by_package[item["id"]]) or "—"
        rows.append(f"| {item['id']} | {labels} | {direct} | {child_counts[item['id']]} | {supplements} |")
    rows += ["", "## Edition and source distinctions", "",
             "The package's NBC(AE) 2023 and NECB 2020 downloads are second printings. The supplied NFC(AE) 2023 and NPC 2020 PDF URLs resolve through archive notices to first printings; both original first printings were recovered using the archive notice's own Continue link. Official second printings were also retained and separately labeled by H19. They were not silently substituted for the original package files.", "",
             "The linked intent-statement supplements identify 2020 code editions. No matching 2023 Alberta supplement was located in the bounded search. Do not infer current-edition equivalence from a title or matching article number.", "",
             "STANDATA, Calgary standing posted variances and Edmonton policy/design documents are regulator references or published illustrative designs. They are not confidential applicant files. The PAB overview is eight pages; its companion design guide supplies examples A–M. The three expanded studies correspond to existing catalogue examples and were not counted twice.", "",
             "The SCC page linked as Guideline to the Variance Form did not expose a document with that exact title. The actual available form, documentation bulletins, refusal template, FAQs and notices were retained as general references.", "",
             "## Access and reuse limits", "",
             "Blocked and unvisited source attempts remain in [source_gaps.json](source_gaps.json) and individual worker reports. Search snippets, permit-register entries and empty/error responses were not substituted for original technical case attachments. Calgary and Edmonton agenda attachment hosts returned 403 in the attempted clients; the local reports record the strongest unverified leads. Calgary DMap reuse terms and property-record access restrictions are preserved in the A02 report.", "",
             "The [NRC archive terms](https://nrc-publications.canada.ca/eng/copyright/) restrict the viewing licence to personal noncommercial use and state that systematic downloading is not permitted. Source downloads are retained locally for the requested research audit; permission for product use, redistribution, model training or benchmark redistribution has not been established. NRC archive attachments are marked `rights_review_required` in case metadata. This is not a blanket licensed training dataset. CCMC and other publishers' rights must be considered under their own terms; the archive terms are not automatically attributed to every Canadian government source.", "",
             "## Machine-readable evidence", "",
             "- `_source_package/links.json` and `link_audit.json`: exact unique targets, relationships, document labels and page/file receipts.",
             "- `_source_package/resource_audit.json`: all 273 exposed document URL attempts and the SCC HTTPS recovery.",
             "- `_source_package/ccmc_document_audit.json` and `ccmc_pdf_audit.json`: all registry assessment pages and actual PDF viewer URLs.",
             "- `_source_package/file_validation.json` and `ccmc_file_validation.json`: original-byte hashes and PDF readability checks.",
             "- `_research/workers/H19/candidates.json`: detailed edition, reference, rights and access records for the package audit slice.", ""]
    (BASE / "SOURCE_PACKAGE_AUDIT.md").write_text("\n".join(rows))
    print("Wrote package audit:", len(audit), "unique targets;", len(resources), "exposed file URLs")


if __name__ == "__main__":
    main()
