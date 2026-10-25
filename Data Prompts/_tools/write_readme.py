#!/usr/bin/env python3
"""Write the corpus navigation from verified, assembled case metadata."""
import csv
import json
from collections import Counter
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]


def main():
    index = json.loads((BASE / "index.json").read_text())
    validation = json.loads((BASE / "validation.json").read_text())
    counts = Counter(row["priority"] for row in index)
    kinds = Counter(row["case_type"] for row in index)
    groups = len({r["source_group"] for r in index})
    city = [r for r in index if r["priority_tier"] == 1]
    alberta = [r for r in index if r["priority_tier"] in (1, 2)]
    comparative = [r for r in index if r["priority_tier"] == 4]
    for filename, rows in [("Alberta Prompt Index.csv", alberta), ("Comparative Prompt Index.csv", comparative)]:
        with (BASE / filename).open("w", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=list(index[0]))
            writer.writeheader()
            writer.writerows(rows)
    lines = ["# Data Prompts", "", f"{len(index)} numbered source-backed attachment exercises, organized around Calgary and Edmonton first, then other Alberta records. There are {groups} groups of shared original input sources; prompt count is not a count of complete applications or independent projects.", "",
             "| Priority | Prompts |", "| --- | ---: |"]
    lines += [f"| {label} | {count} |" for label, count in sorted(counts.items(), key=lambda item: next(r["priority_tier"] for r in index if r["priority"] == item[0]))]
    lines += ["", "Start with [Calgary and Edmonton cases](CITY_CASES.md) and [Alberta Prompt Index.csv](Alberta%20Prompt%20Index.csv). [index.csv](index.csv) and [index.json](index.json) include everything. [Comparative Prompt Index.csv](Comparative%20Prompt%20Index.csv) contains outside-Alberta records for attachment format/content comparisons only.", "",
              "## Run a prompt", "", "1. Open a numbered folder and use its `prompt.txt` as the test message.",
              "2. Attach the source files listed at the bottom of that prompt. Original downloaded PDFs are preserved. For web-only records, a source-text `.txt` extraction is supplied alongside the original HTML; the extraction contains source text rather than invented content.",
              "3. Keep `source.json`, `evaluation.json`, and any `_evaluation/` folder out of the model input. They contain provenance, source locators, known published outcomes, limitations, and review notes. Separate outcome-reference attachments are held in `_evaluation/`; a decision inside the main source PDF remains explicitly flagged as leaked.",
              "4. Record the system's output against the cited source facts and have the appropriate human reviewer assess unresolved technical questions. Do not treat a published outcome as complete expert ground truth for a new project.", "",
              "## What the record types mean", "", "| Type | Meaning |", "| --- | --- |",
              "| actual_application | Original project submission components, such as consultant reports, response letters or drawings. This label does not establish that a complete application packet is present. |",
              "| issued_variance | Regulator-issued STANDATA or municipal standing variance, including historical versions. Not an individual applicant submission. |",
              "| appeal_decision | A real code dispute and published decision; original drawings or application evidence may be missing. |",
              "| documented_design_study | A published project/design study, experiment or illustrative design. Check the source notes to distinguish built projects from concepts. |",
              "| documented_case_summary | A staff report or case account describing a real submission or inspection, without the complete original application. |",
              "| published_worked_example | An expert-authored teaching/example document. It may use fictional products or illustrative buildings; it is not a real applicant record. |",
              "| regulatory_guidance | Official interpretation or bulletin used as a reference-document exercise, not a project application. |",
              "| product_evidence / research_evidence | Supporting assessment, test or research documentation. It is not a Calgary/Edmonton approval. |", "",
              "| Record type | Prompts |", "| --- | ---: |"]
    lines += [f"| {kind} | {count} |" for kind, count in sorted(kinds.items())]
    lines += ["", "## Evaluation boundaries", "",
              "Calgary and Edmonton are the primary target. Other Alberta records are second priority. Preserve the stated AHJ, source code edition, date, conditions, and superseded/withdrawn status. A province-wide STANDATA may inform a local case but is not evidence of a site-specific municipal decision.", "",
              "Outside-Alberta cases are retained for file layout, drawing, report, table, evidence and attachment-processing comparisons. Do not move their designs into Alberta by changing the prompt's place name, apply their code numbers as Alberta requirements, or count them as Alberta acceptance evidence.", "",
              "Some Alberta appeal records concern the Fire Code or a related discipline. Keep that discipline and its historical edition explicit; they are adjacent administrative/evidence examples rather than new NBC design approvals. Original image files are retained as images. Upload behavior for those image formats was not exercised here.", "",
              "Every prompt is a reconstructed evaluation request based on published material, not an original applicant message. No application, drawing, test report, signature, professional opinion or approval was fabricated. Published illustrative examples remain labeled as illustrative.", "",
              "Published decisions, issued variances and some technical reports reveal their outcomes in the attached source. `outcome_leakage` marks these retrospective exercises. They can test extraction and administrative evidence handling; they cannot demonstrate blind design adjudication accuracy. Keep records sharing `source_group` together when selecting development and holdout sets, and additionally group separate reports about the same project.", "",
              "Public permit registers without technical design content were retained as leads rather than included as numbered cases. Public source availability does not imply that complete private application files are accessible.", "",
              "## Downloads, audit and verification", "",
              "- [SOURCE_PACKAGE_AUDIT.md](SOURCE_PACKAGE_AUDIT.md) maps every supplied package link to its saved targets and follow-on files.",
              "- [downloads.csv](downloads.csv) and [source_catalogue.jsonl](source_catalogue.jsonl) inventory original downloads and retrieval receipts, including unused reference documents.",
              "- [source_gaps.json](source_gaps.json) preserves blocked sources and unvisited leads. Individual worker reports include recovery attempts and scope limits.",
              f"- [validation.json](validation.json) records {validation['prompt_count']} prompt folders, {validation['unique_pdfs_parsed']} unique PDFs parsed, {validation['pdf_pages']} PDF pages and {len(validation['errors'])} structural/integrity errors. These checks establish file integrity/readability and metadata consistency; they do not establish technical correctness, current code equivalence or professional approval.",
              "- `_research/agent_registry.json` records the original 40 requested max-effort workers and the 16 later Alberta-focused workers. `_research/curation_overrides.json` records parent classification/exclusion decisions without changing the workers' originals.",
              "- [Alberta Jurisdiction Sources.json](Alberta%20Jurisdiction%20Sources.json) preserves the official municipal/accreditation source inventory and access routes. Municipal rows, accredited organizations and building AHJs are different counts; this is not a claim that every municipality was scraped.",
              "- `_source_package/` preserves the supplied DOCX, all 37 unique hyperlink targets, and audit ledgers. `_references/` holds general reference downloads, including the full registry-linked CCMC assessment set.", "",
              "NRC codes, guides and assessments retain their publisher's rights. NRC archive sources are marked `rights_review_required`; the archive viewing terms restrict systematic downloading and commercial use, and permission for product/training reuse has not been established. Local download is not a blanket licence to redistribute sources or embed full text in the product. See the source audit for the saved terms and source-specific rights notes.", ""]
    # Keep navigation factual and tied to actual case locations.
    (BASE / "README.md").write_text("\n".join(lines))
    city_lines = ["# Calgary and Edmonton", "", "Primary local attachment exercises. Original submission components appear before design studies and issued/appeal reference records. Illustrative material and historical decisions remain explicitly labeled. Province-wide and other Alberta records are in [Alberta Prompt Index.csv](Alberta%20Prompt%20Index.csv).", "",
                  "| Prompt | Record | Source type | Code edition |", "| --- | --- | --- | --- |"]
    for row in city:
        title = row["title"].replace("|", "/")
        edition = str(row["code_edition"]).replace("|", "/")
        city_lines.append(f"| [Prompt {row['prompt']}](Prompt%20{row['prompt']}/prompt.txt) | {title} | {row['case_type']} | {edition} |")
    (BASE / "CITY_CASES.md").write_text("\n".join(city_lines) + "\n")
    print(json.dumps({"prompts": len(index), "city_prompts": len(city), "alberta_prompts": len(alberta), "comparative_prompts": len(comparative)}, indent=2))


if __name__ == "__main__":
    main()
