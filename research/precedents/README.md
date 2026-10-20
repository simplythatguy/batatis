# Alberta alternative-solution precedent index

Verified 2026-10-18. `index.json` is a JSON array with **151 records**: 148 local source PDFs,
two dataset summaries, and one explicitly incomplete/inaccessible Calgary source. The 147 resumed PDFs were
indexed before the additional ventilation PDF was downloaded. The index is checkpointed on disk; see `PROGRESS.md`.

This is a source-navigation and citation-identity resource. It does not establish technical equivalence, approve
an alternative solution, or replace the professional/AHJ review of a complete submission.

## Coverage

| Collection | Files/records | Distinct numbered families | Coverage limit |
|---|---:|---:|---|
| ABC 2014 building variances | 23 PDFs | 20 | All downloaded/listed 14-BCV-001–020 families, including retained revisions and withdrawn entries. Historical only. |
| NBC(AE) 2019 building variances | 33 PDFs | 25 | 19-BCV-001–025 families and listed retained revisions. Historical only. |
| NBC(AE) 2023 building variances | 19 PDFs | 16 | All resources in the retrieved official 2023 variance catalogue, including superseded versions. Families 001–014, 017 and 018. **015/016 were not listed/retrieved; no content is invented for them.** |
| 2023 interpretations | 40 PDFs | 35 | All resources in the retrieved official publication, including superseded versions and 23-BCI-018 on hold. Numbering is not contiguous. |
| 2023 bulletins | 11 PDFs | 9 | All resources in the retrieved official publication, including archived 002/002R1, archived joint electrical item 003 and superseded 007. |
| Errata | 3 PDFs | 3 | 23-BCE-001 plus historical 19-BCE-001/002. All ten correction rows in 23-BCE-001 are paraphrased in `errata.md`. |
| Calgary | 9 records | — | Five SPV records (001/003/004/006/007), SPV procedure, request form, transition advisory and plumbing advisory. SPV-007 has no valid local PDF and live URLs return 404. |
| Edmonton | 9 PDFs | — | B14-01, B14-01G, B19-03, B19-04, B23-01/02/03/05 plus the B23-01 supporting report. |
| SCC | 2 records | — | Variance FAQs and public dashboard summary. The Alberta notice linked by SCC is counted among the 151 records as a separate Alberta-issued guidance record. |
| CCMC | 1 summary | 462 assessments in supplied snapshot | One registry summary; these are not 462 accepted alternative-solution applications. |

The official current Calgary index lists SPV-001, SPV-003 and SPV-006. SPV-004 is still downloadable from an official
URL but absent from that list; its 2019-edition text needs current AHJ confirmation. SPV-007 appears in a search cache
but live downloads on both official hosts returned 404. Its row is deliberately `partial-source` /
`unverified-source-gap`, with `local_path: null` and an explicit reason.

## Schema and evidence semantics

Every record includes the fields required by the brief: `id`, `issuer`, `type`, `code_edition`, `title`, `summary`,
`articles_varied`, `objectives_functions_stated`, `conditions`, `applies_to`, `date`, `url`, `local_path` and `topics`.
Additional fields retain source hashes, page-text paths, access dates, publication URLs, source/use status,
family/revision identity, source conflicts and verification receipts. Dates are source issue/revision dates where assigned;
null dates carry a reason. The SCC record explicitly identifies its date as model refresh time.

- `articles_varied` contains source-selected varied benchmarks for variance/SPV records. Contextual/condition references are separated into `articles_referenced`. Some sources describe an integrated package, broad section, definition or standard rather than a precise article; their empty article list has an explicit scope note. Do not invent one.
- `original_citation` preserves the precedent's numbering/edition. `original_division` distinguishes A/B/C; another code is explicitly labelled. Sentence numbers are retained from the source.
- `pdf_page` is **one-based PDF page in the complete NBC(AE) 2023 second-printing code**, not the precedent PDF or printed code-page number. `source_pdf_pages` points into the precedent.
- `same-number-present` verifies the current substantive **article heading and division**, with a `tools/codesearch.py` receipt. It does not certify each sentence/clause's current wording.
- `same-number-present-equivalence-unverified` is an older-edition number match only. Even identical titles do not prove unchanged technical requirements.
- `topic-successor-found-equivalence-unverified` identifies a specific successor topic using the later provincial variance and a separately verified current heading. Both original and current numbers are retained. This is not automatic approval to reuse the old solution.
- `not-found` means a substantive heading in the stated division was not verified. Matches in another division, attribution tables, notes or an index do not repair it.
- `outside-nbc-scope` preserves a fire/plumbing/other-code reference without falsely mapping it to an NBC number. Non-NBC provisions are not validated against their own full current code here.
- `objectives_functions_stated` contains only identifiers actually printed in the source, with source pages. An empty list means none extracted. These are **not reconstructed current attribution pairs**; use the current Division B attribution table separately for Section C.
- Conditions are paraphrased navigation summaries. Diagrams, tables, standards, permit-specific incorporation and all detailed source conditions still control. Do not turn an omitted detail into permission.
- `review_status` distinguishes `source-indexed` from `partial-source`; it is not an engineering approval. `source_status` retains listed/withdrawn/archived/superseded/on-hold/unlisted evidence.

## Citation checks

The build ran the required `.venv/bin/python -I tools/codesearch.py find ... --doc NBC-AE` CLI for 113 unique
selected article numbers, then matched substantive headings in the correct division. Raw command/output receipts are in
`citation-receipts/`. Another 96 searches cover the errata register and building-article strings in the SCC data. Counts/statuses are reported by `validation.json`.

Two explicit crosswalk examples prevent misleading number reuse:

- Older greenhouse-film Article 3.1.6.5. now collides with a different current topic (encapsulation ratings). The later greenhouse-film variance points to current Div B Article 3.1.18.5. See the source-linked crosswalk in the old record.
- Older off-site-review Div C Article 2.4.5.1. has no current same-number heading; current 23-BCV-002 identifies Div C Article 2.5.1.1. These records retain their original citations and label equivalence unverified.

Some current STANDATA cite Div C 2.3.1.2.; it was **not found** in the supplied second printing. The verified documentation
article is 2.3.1.1. Both the source reference and this discrepancy are retained instead of manufacturing a current provision.

## Most-varied provisions: SCC publication

Source: https://www.safetycodes.ab.ca/data-hub/variance-data/ (accessed 2026-10-18).
The page embeds a public Power BI report. The schema, report metadata, exact query bodies and responses are saved in
`source-catalog/`; decoded results are in `scc-article-counts.json`, quality checks in `scc-quality.json`.

The visible model is `Variances2026q1`, and report pages identify **2026 Q1**. The landing page says publication starts
with Q1/Q2 2026; the retrieved entity does **not** establish Q2 coverage. Model last refresh was
2026-08-14T19:51:02.753. This is a bounded published dataset, not an all-time Alberta census.

The query returned 95 discipline/code/article groups, with published `Article Count` summing to 3,118
(3,088 building-discipline occurrences). The distinct ID/article query returned 2,386 combinations and 1,876 non-null
variance IDs (1,845 building IDs). Six grouped counts differ from distinct-ID/article counts; four combinations have
missing IDs and four have missing code/article values. **Published article occurrences are not unique applications.**
The cause of multiplicity is not established by the public model; it is not assumed to be a data-entry error.

Top raw entries under the main **NBC(AE) 2023** label:

| Raw provision in SCC data | Published article occurrences | Current article page (p2) |
|---|---:|---|
| 9.10.15.5.(8) | 1,501 | 902; sentence wording requires direct check. |
| 9.10.11.2. | 366 | 889. |
| 9.10.13.13. | 251 | 893. |
| 9.10.14.2. | 218 | 894. |
| 9.10.14.5. | 167 | 897. |
| 9.10.14.5.(9) | 153 | 897; separate raw sentence group, potentially overlapping applications. |
| 9.10.15.3. | 134 | 900; substantive heading separately read after the search. |
| 9.9.4.4. | 73 | 865. |

Use the raw groups to prioritize routing/evidence work around spatial separation, rowhouse firewalls, dampers and exterior
egress protection. That prioritization is an inference, not technical acceptance evidence. The SCC page expressly excludes
supporting materials/alternative solutions and says the publication is not guaranteed or precedent-setting.
Do not infer the actual accepted assembly, mitigating measures, jurisdictional scope or reason for approval from the counts.

## CCMC product-specific path

`ccmc-summary.json` profiles the supplied `reference/data/ccmc-registry.json` snapshot:

- 462 entries, 462 distinct internal IDs, 462 distinct CCMC numbers; all are labelled Active in the snapshot.
- All rows have reference-document data. 27 lack MasterFormat classifications. Nested JSON list fields parse without errors.
- Leading MasterFormat division prefixes: 07 (281 assessments), 06 (112), 09 (31), 33 (16), 31 (12).
- Leading exact category codes: `07 20 00` (82), `07 21 13` (81), `07 21 00` (73), `07 21 13.13` (39), `07 25 00` (37).
- Reference-document strings include CCMC technical guides and CSA, CAN/ULC, CAN/CGSB and other standards. Examples include `CCMC-TG-072510.03-15` (19), `CSA O112.9:10` (17), and `CSA-S347-14` (10).

An assessment can have several classifications/reference documents, so category counts overlap. Strings preserve
edition, amendment, type and class suffixes; they are not silently collapsed into a supposedly current standard.
The source API link embedded in the snapshot could not be resolved live (`curl` exit 6); these counts are **snapshot findings**,
not a newly refreshed registry claim. Individual product assessment reports were not downloaded in this task.

Tool route: match product/manufacturer/CCMC number → fetch the actual assessment → verify current status, assessment type,
evaluated editions and scope → compare exact assembly/use/installation limitations → request the identified test/report evidence
and professional responsibility in Section D. The registry row does not itself prove equal performance or establish a universally
accepted alternative solution. Verify current Alberta code references and AHJ requirements independently.

## Use by the product and agents

1. Route intake by topic, project signals, product identity, jurisdiction and applicable code edition.
2. Filter source status/version before offering a candidate precedent. Keep historical/withdrawn/on-hold/unlisted records available for research with their limitations visible.
3. Verify the candidate's precise project scope and all source conditions. A provincewide STANDATA, municipal SPV, policy, interpretation, bulletin and product assessment have different roles.
4. Use original/current provision fields to propose a benchmark lookup. Complete current objective/function attributions and intent from their authoritative sources; do not copy pairs across editions.
5. Request drawings, testing/evaluation reports, operational controls and professional involvement indicated by the source. Record responsibility and evidence in Section D.
6. Flag missing evidence, wrong editions, scope mismatch, source conflicts and citation failures. Leave engineering adequacy and the acceptance decision to professionals/AHJ.

## Material source issues and limits

- Calgary SPV-001: footing projection differs between source pages 4 and 5 (0.3 m versus 0.6 m). Needs issuer clarification.
- 23-BCE-001: the corrected overbar symbol in Site Class E is not visibly carried into the supplied second-printing table. See `errata.md` and inspected source renders.
- Edmonton B23-03: opening STANDATA identifier differs from the correct identifier used in its body; the index records the typo and authoritative source.
- 23-BCI-018 is on hold under review. Archived truss bulletins must not override the current interpretation/municipal implementation.
- 2023 variance families 015/016 are not in the retrieved official catalogue. No missing publication is asserted to exist or not exist beyond that evidence.
- Calgary SPV-007 lacks a valid live/local source; ventilation SPV-004 lacks current index listing. They must not be offered as confirmed current authorization.
- SCC counts lack application/supporting-document content, have mixed labels/multiplicity, and do not establish Q2/all-time coverage.
- CCMC analysis uses the supplied snapshot; live API DNS resolution failed. Product report status, editions and limitations remain to be checked per product.
- Sentence/clause wording and complete cross-edition semantic equivalence are outside the automated heading check. These limits are stored in the records.
- Bulk `tools/extract_text.py` successfully extracted the new owned SPV-004 PDF, then failed on an unrelated concurrently added AES-encrypted PDF because the shared environment lacks `cryptography`. No source/extractor was changed; the required owned text file exists.

## Verification and reproducibility

Run from repository root:

```sh
.venv/bin/python research/precedents/build_index.py
.venv/bin/python research/precedents/verify_citations.py
.venv/bin/python research/precedents/finalize_index.py
.venv/bin/python research/precedents/verify_supplemental.py
.venv/bin/python research/precedents/validate_index.py
```

Reviewed notes and original PDF/text files are build inputs. `annotate_variances.py`, `annotate_guidance.py` and
`annotate_local.py` preserve the initial source-reviewed summaries; later reviewed notes/corrections remain in
`reviewed-notes.json`. Do not rerun those annotation scripts over deliberate manual note changes without review.
`fetch_scc.py` and `analyze_scc.py` retain the public read-only request/decoding method; the saved grain request is
also an input to the quality reconciliation. No background refresh, publication, commit or technical acceptance is implied.

## Primary web sources checked

All accessed 2026-10-18; exact per-file PDF URLs and local hashes are in `index.json`.

- https://www.alberta.ca/building-standata — document roles, edition limits and official publication links.
- The six Alberta publication pages plus the historical errata page saved in `source-catalog/` — complete retrieved resource lists, titles, source status and download URLs.
- https://www.calgary.ca/development/permits/building-regulation-advisories.html — current listed SPVs/advisories and download links; PDF issue/revision date takes precedence over a conflicting listing date.
- https://www.edmonton.ca/residential_neighbourhoods/application-requirements-house-permits — policy-solution links; `curl` retrieved the page even though the web reader initially failed.
- https://www.safetycodes.ab.ca/permits-inspections/variances/ — official forms/FAQ/notice links and route to the data hub.
- https://www.safetycodes.ab.ca/data-hub/variance-data/ — published scope/frequency/exclusions and public Power BI embed.

## Methods used

- T3 workflow router: `/Users/aamia/.codex/skills/t3-workflow/SKILL.md`; route selection: `/Users/aamia/.codex/skills/t3-workflow/references/routes.md`.
- Matt Pocock, primary-source research: `/Users/aamia/.agents/skill-libraries/mattpocock/skills/engineering/research/SKILL.md` (no further delegation, per task contract).
- Data index and scoped data quality: `/Users/aamia/.codex/plugins/cache/openai-curated-remote/data-analytics/1.0.11/skills/index/SKILL.md` and `/Users/aamia/.codex/plugins/cache/openai-curated-remote/data-analytics/1.0.11/skills/analyze-data-quality/SKILL.md`.
- PDF source rendering/inspection: `/Users/aamia/.codex/plugins/cache/openai-primary-runtime/pdf/26.1017.11052/skills/pdf/SKILL.md`.
- Search triage: `/Users/aamia/.codex/skills/jev-search/SKILL.md`; Jev network was unavailable, so only its local screen ran. No ranking/sufficiency judgment is claimed.
- Workflow drift safety: `/Users/aamia/.agents/t3-workflow/UPDATE-SAFETY.md`; read-only maintenance check reported model-role file drift, preserved unchanged.

No user interface feature was implemented; screenshots/demos are not a feature acceptance surface for this research task.
