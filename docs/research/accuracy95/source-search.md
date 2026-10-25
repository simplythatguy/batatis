# Accuracy95 Calgary/Edmonton local evidence search

Date: 2026-10-25 (retrieval time for the new original: 2026-10-25 18:44:33 UTC)

## Result

The 26-query primary-source sweep found **one new local source group** containing **two named Edmonton school projects**. The source is an official Edmonton Catholic School Division preplanning / pre-schematic report by Stantec. It contains project-specific NBC(AE) 2023 building-code review sections for both projects. This is useful project engineering evidence, but it is not an alternative-solution application, variance, permit decision, or approval record.

No new Calgary project packet was verified from open public bytes. The strongest additional Calgary and Edmonton leads either matched existing source groups or remain behind the eScribe 403 access gaps already recorded in `Data Prompts/source_gaps.json`.

At this checkout, `index.json` contains 17 Calgary prompts across 12 source groups and 21 Edmonton prompts across 9 source groups. Prompt counts are not project counts; this registry snapshot therefore does not use the separate 8+17 evaluation-case count as its denominator.

## New candidate: ECSD Griesbach K-9 and Chambery K-6

- **Source / author:** Edmonton Catholic School Division; prepared by Stantec Architecture Ltd.
- **Document:** *ECSD Northwest Edmonton Schools – Griesbach K-9 School & Chambery K-6 School Pre-Planning/Pre-Schematic Design Report*, project 144217370, dated 2026-02-25.
- **Original URL:** https://www.ecsd.net/documents/1e431fd9-371a-415e-b4b2-be80c24558de/ChamberyK6_GriesbachK9_Final_PD_Report.pdf
- **Redirected final URL:** https://www.ecsd.net/documents/1e431fd9-371a-415e-b4b2-be80c24558de/ChamberyK6_GriesbachK9_Final_PD_Report.pdf?fingerprint=ppb20260416205227
- **Retrieved:** 2026-10-25 18:44:33 UTC; HTTP 302 then HTTP 200; `application/pdf`; 24,433,793 bytes; 133 pages.
- **SHA-256:** `64bdad61f8dcd0aa62bfada88f57d8336aba8c10a17722150837d6f851eb5840`
- **Saved original:** [`originals/ecsd-griesbach-chambery-preplanning-report.pdf`](../../../Data%20Prompts/_research/accuracy95-local/originals/ecsd-griesbach-chambery-preplanning-report.pdf)
- **Locality evidence:** PDF p. 5 (printed page iii) explicitly describes both the new Griesbach K-9 School and Chambery K-6 School “in Edmonton, Alberta.” The report also names “Northwest Edmonton” on the cover (PDF p. 1). No locality was inferred from the publisher.
- **Griesbach code-review evidence:** PDF p. 47 (printed page 32), section 5.1.1, “Building Code Review,” identifies NBC 2023 Alberta Edition and gives a project-specific building classification, storeys, area, sprinkler, construction, fire-separation, and related review information. PDF p. 48 continues with occupant-load, exits, and accessibility review.
- **Chambery code-review evidence:** PDF pp. 52–53 (printed pp. 35–36), section 5.2.1, contains the corresponding NBC 2023 Alberta Edition review, building classification, area, storeys, construction, fire separation, occupant load, exit, washroom, and accessibility information.
- **Suggested record type:** `documented_design_study` / project engineering record. The candidate group covers two project names but one shared original report and therefore one new source group.
- **Limits:** The report describes conceptual preplanning/pre-schematic designs. A full extracted-text scan found no occurrences of “alternative solution,” “variance,” “building permit,” or “permit application.” Treat it as project design/code-review evidence only; it does not show a submitted variance or AHJ acceptance. No applicant facts or prompt text were synthesized. Reuse / redistribution rights for the report have not been established.

## Deduplication and exclusions

The exact project names do not occur in `Data Prompts/index.json`; the exact source URL and downloaded SHA-256 do not occur in `Data Prompts/source_catalogue.jsonl`. This makes the report a new source group against the committed corpus metadata.

The official search surfaced **8 already-indexed local source groups** that were not counted as new. These include Calgary standing-variance records (L04), Edmonton’s Point Access Block example set and secondary-suite alternative-solution example (L05), and the already-indexed city-specific appeal orders 2021-09, 2023-03, 2024-06, and 2025-02 (L06). One additional already-indexed Alberta appeal, Council Order 2022-06 (L06-016), is explicitly classified as **Unspecified locality**. Its “Signed at the City of Edmonton” footer is not project-locality evidence, so it remains outside the Calgary/Edmonton count.

Generic city guidance, permit checklists, standing variances, and policy pages were not counted as individual applicant cases. A search-indexed student project copy was not admitted because it was not a primary official project record.

## Counts and search limits

| Measure | Count | Meaning |
| --- | ---: | --- |
| New eligible local source groups | 1 | One original report with explicit Edmonton evidence |
| Distinct new named projects | 2 | Griesbach K-9 and Chambery K-6, sharing the report |
| Existing local duplicate source groups | 8 | Previously indexed Calgary/Edmonton project or source groups surfaced by the searches |
| Existing Alberta record excluded for locality | 1 | Council Order 2022-06; project city not established |
| Newly blocked candidate sources | 0 | The new ECSD PDF downloaded and passed content inspection |
| Pre-existing eScribe 403 gaps | 24 unique URLs | 18 Calgary and 6 Edmonton URLs, already in `Data Prompts/source_gaps.json`; not retried |

The 26 focused search queries covered official Calgary and Edmonton alternative-solution, code-analysis, building-project, school-facility, and permit sources; Safety Codes Council decisions; Alberta sources; and official access-to-records routes. Search results and snippets were leads only. The candidate was admitted after downloading the original PDF and reading its actual text. The web preview declined to fetch the 24.4 MB PDF because of a content-length limit, so the original was retrieved directly from the official ECSD URL instead.

## Best next official access route

For the application/variance evidence that public searches did not expose, request a narrowly defined, disclosable **technical report, variance request/report, deficiency correspondence, and decision record** for a named project and time range through the City’s formal access process. Do not treat a permit-register entry or meeting-search snippet as an attachment.

- **Calgary:** use the City’s [Access to information request process](https://www.calgary.ca/info-requests/access-and-privacy/access-request.html), which accepts requests for records under City custody/control and requests specificity about records, business unit, and date range. Existing property-plan access notes remain restrictive; do not purchase or reproduce plans for this task.
- **Edmonton:** use the [City’s ATI request process](https://www.edmonton.ca/city_government/city_organization/access-to-information-request) for records not otherwise public. The [official forms listing](https://www.edmonton.ca/business_economy/form-listing) says a property/building plan or file search request must be made by the owner or an acting agent. For a non-owner researcher, ask only for disclosable City technical reports / variance records through ATI and expect privacy review; no request was filed.

No fee was paid and no person or City office was contacted. The source search found no better open route to authentic site-specific Calgary applicant attachments than the blocked eScribe and restricted property-record paths already documented.

## Methods and verification

- Read the workspace `AGENTS.md`, T3 workflow router and routes, then applied **Matt Pocock research** as a bounded primary-source scan; no nested agents or API calls were used.
- Retrieved the official original without credentials or access-control workarounds. `file`, byte count, SHA-256, and macOS PDFKit confirmed a readable 133-page PDF. PDFKit text extraction inspected the cover, city evidence, and both code-review sections; a keyword scan covered all 133 pages.
- Read `Data Prompts/index.json`, `source_catalogue.jsonl`, and the existing source-gap ledger to check project names, URLs, hashes, known duplicates, and access gaps. No corpus index or main corpus file was edited.
- **Methods used:** Matt Pocock research — `/Users/aamia/.agents/skill-libraries/mattpocock/skills/engineering/research/SKILL.md`.

Parent verification matched original bytes/hash/page count and visually inspected PDF pages 5, 47 and 52. The original stays local and outside Git. The source remains quarantined from tuning/retrieval and has not been scored.
