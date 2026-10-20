# W1c precedent index progress

Last checkpoint: 2026-10-18. Deliverables ready for parent review.

## Done

- Started with all 147 resumed PDFs, rather than downloading them again.
- Built 151 records: 148 local PDFs, SCC and CCMC dataset summaries, one explicitly incomplete SPV-007 source.
- Indexed all retrieved Alberta catalogue resources: 20/25/16 variance families for 2014/2019/2023; 35 interpretation and 9 bulletin families for 2023; all three supplied errata.
- Downloaded/extracted the missing Calgary ventilation SPV-004. Retained source/version/status and topic routing for all records.
- Saved 113 selected article-number CLI searches and 96 supplemental searches. Kept nine not-found references, five topic-successor crosswalks and non-NBC references explicitly labelled.
- Retrieved SCC public Power BI schema/model/query data; saved requests, responses, decoded counts and grain/freshness/null/multiplicity checks.
- Profiled the supplied 462-assessment CCMC snapshot, MasterFormat categories and reference documents.
- Completed README.md and errata.md; rendered/inspected italic, table-border and mathematical-symbol cases.
- validate_index.py passes: zero errors; all 148 local PDF source URLs have successful current HTTP 200 checks. Hashes and current code/text fingerprint are in validation.json.

## Source gaps / unresolved evidence

- 23-BCV-015/016 not found in the official catalogue or bounded official-domain search. No content invented.
- SPV-007 live PDF returned 404 on both Calgary hosts. Search-cached first-page evidence only; local PDF unavailable and row marked partial-source.
- SPV-004 downloadable but unlisted on current Calgary SPV table; current reliance requires AHJ confirmation.
- CCMC source API host does not resolve here (curl exit 6). Analysis uses supplied snapshot; no individual product-report refresh claimed.
- SCC visible model is labelled Q1 2026; landing text mentions Q1/Q2. Counts are published article occurrences, not unique applications.
- Source conflicts: Calgary SPV-001 footing projections; second-printing Site Class E symbol versus 23-BCE-001; current STANDATA references to missing Div C 2.3.1.2.; Edmonton truss identifier typo documented in record conditions.
- Bulk extractor completed owned SPV-004 then failed on an unrelated concurrently added encrypted source due to missing cryptography. No unrelated fix attempted.

## Next

- Parent reviews the deliverables and source caveats. Future current-source clarification should update only the affected records and rerun relevant checks.
- No pending local authoring work. No evals read, subagents spawned, commits, pushes, publication, or changes to other agents' deliverables.

## Methods receipt

Full paths and actual usage are in README.md. Primary method: Matt Pocock research; supporting Data quality and PDF inspection. Jev network unavailable; local screen only. Workflow maintenance drift preserved.
