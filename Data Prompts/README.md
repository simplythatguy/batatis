# Data Prompts

653 source-backed attachment exercises, organized around Calgary and Edmonton first, then other Alberta records. There are 592 groups of shared original input sources; prompt count is not a count of complete applications or independent projects.

| Priority | Prompts |
| --- | ---: |
| Calgary / Edmonton | 38 |
| Other Alberta / province-wide | 121 |
| Canadian supporting evidence | 73 |
| Outside Alberta - attachment comparison only | 421 |

Start with [Calgary and Edmonton cases](CITY_CASES.md) and [Alberta Prompt Index.csv](Alberta%20Prompt%20Index.csv). [index.csv](index.csv) and [index.json](index.json) include everything. [Comparative Prompt Index.csv](Comparative%20Prompt%20Index.csv) contains outside-Alberta records for attachment format/content comparisons only.

## Folder structure

Browse [locations](GEOGRAPHY_INDEX.md) or open the matching country, province/state and city/town:

```text
Data Prompts/
└── Canada/
    └── Alberta/
        └── Calgary/
            └── Prompts/
                └── A03-001-historic-fire-hall-no-1-adaptive-reuse-concepts-in-city-technical-feasib/
                    ├── prompt.txt
                    ├── source.json
                    ├── evaluation.json
                    └── original attachments (local)
```

Case folders use stable case IDs and descriptive titles. `geography.json` records the source evidence for every location. National and province-wide references, multiple-location studies, and undisclosed municipalities have explicit scope folders. Publisher or tribunal office addresses are not treated as project locations. Numeric `prompt` values remain stable index references; they do not name folders.

## Restore local attachments

Git stores the 653 prompt texts, provenance, evaluator notes, source catalogues, audits and collection tools. The 7 GB original research collection remains local. Publisher files, extracted full texts, raw web captures and contact-bearing registry snapshots are excluded by `.gitignore`; this repository does not redistribute them.

A new checkout has metadata only. Restore the original attachment files from your existing `Data Prompts` collection, then verify their recorded hashes:

The portable tools require Python 3.11 or newer. Network restoration also uses `curl` with certificate verification enabled, matching the original collector.

```sh
python3 'Data Prompts/_tools/restore_attachments.py' --from '/path/to/existing/Data Prompts' --include-evaluation
python3 'Data Prompts/_tools/verify_corpus.py' --attachments
```

Restore a single case by adding `--case A03-001`. To retrieve a selected public source again, after checking its publisher terms:

```sh
python3 'Data Prompts/_tools/restore_attachments.py' --download --case A03-001
```

Network restoration requires explicit case IDs or prompt index numbers. Archive captures use the recorded capture URL. Files marked `rights_review_required` require a permitted local copy. Any changed response, missing source, access challenge, or hash mismatch is reported as a failure; no replacement attachment is invented. Existing files with unexpected hashes are preserved and reported. Separate evaluator references are restored only with `--include-evaluation`.

HTML and DOCX text inputs are regenerated from the original bytes and checked against the recorded extraction hash. Use `organize_by_geography.py` to apply an updated geography map and `regroup_sources.py` to update shared-evidence groups. The collectors in `_tools/` document the original research process; their full audit/reassembly commands require the complete local worker collection. `verify_corpus.py` works on a fresh metadata checkout without those raw files.

## Run a prompt

1. Browse a location and open a named case folder; use its `prompt.txt` as the test message.
2. Attach the source files listed at the bottom of that prompt. Restored original PDFs retain their recorded bytes. For web-only records, a source-text `.txt` extraction is supplied alongside the original HTML; the extraction contains source text rather than invented content.
3. Keep `source.json`, `evaluation.json`, and any `_evaluation/` folder out of the model input. They contain provenance, source locators, known published outcomes, limitations, and review notes. Separate outcome-reference attachments are held in `_evaluation/`; a decision inside the main source PDF remains explicitly flagged as leaked.
4. Record the system's output against the cited source facts and have the appropriate human reviewer assess unresolved technical questions. Do not treat a published outcome as complete expert ground truth for a new project.

## What the record types mean

| Type | Meaning |
| --- | --- |
| actual_application | Original project submission components, such as consultant reports, response letters or drawings. This label does not establish that a complete application packet is present. |
| issued_variance | Regulator-issued STANDATA or municipal standing variance, including historical versions. Not an individual applicant submission. |
| appeal_decision | A real code dispute and published decision; original drawings or application evidence may be missing. |
| documented_design_study | A published project/design study, experiment or illustrative design. Check the source notes to distinguish built projects from concepts. |
| documented_case_summary | A staff report or case account describing a real submission or inspection, without the complete original application. |
| published_worked_example | An expert-authored teaching/example document. It may use fictional products or illustrative buildings; it is not a real applicant record. |
| regulatory_guidance | Official interpretation or bulletin used as a reference-document exercise, not a project application. |
| product_evidence / research_evidence | Supporting assessment, test or research documentation. It is not a Calgary/Edmonton approval. |

| Record type | Prompts |
| --- | ---: |
| actual_application | 49 |
| appeal_decision | 259 |
| documented_case_summary | 22 |
| documented_design_study | 71 |
| issued_variance | 100 |
| product_evidence | 71 |
| published_worked_example | 12 |
| regulatory_guidance | 55 |
| research_evidence | 14 |

## Evaluation boundaries

Calgary and Edmonton are the primary target. Other Alberta records are second priority. Preserve the stated AHJ, source code edition, date, conditions, and superseded/withdrawn status. A province-wide STANDATA may inform a local case but is not evidence of a site-specific municipal decision.

Outside-Alberta cases are retained for file layout, drawing, report, table, evidence and attachment-processing comparisons. Do not move their designs into Alberta by changing the prompt's place name, apply their code numbers as Alberta requirements, or count them as Alberta acceptance evidence.

Some Alberta appeal records concern the Fire Code or a related discipline. Keep that discipline and its historical edition explicit; they are adjacent administrative/evidence examples rather than new NBC design approvals. Original image files are retained as images. Upload behavior for those image formats was not exercised here.

Every prompt is a reconstructed evaluation request based on published material, not an original applicant message. No application, drawing, test report, signature, professional opinion or approval was fabricated. Published illustrative examples remain labeled as illustrative.

Published decisions, issued variances and some technical reports reveal their outcomes in the attached source. `outcome_leakage` marks these retrospective exercises. They can test extraction and administrative evidence handling; they cannot demonstrate blind design adjudication accuracy. Keep records sharing `source_group` together when selecting development and holdout sets, and additionally group separate reports about the same project.

Public permit registers without technical design content were retained as leads rather than included as numbered cases. Public source availability does not imply that complete private application files are accessible.

## Downloads, audit and verification

- [SOURCE_PACKAGE_AUDIT.md](SOURCE_PACKAGE_AUDIT.md) maps every supplied package link to its saved targets and follow-on files.
- [downloads.csv](downloads.csv) and [source_catalogue.jsonl](source_catalogue.jsonl) inventory original downloads and retrieval receipts, including unused reference documents.
- [source_gaps.json](source_gaps.json) preserves blocked sources and unvisited leads. Individual worker reports include recovery attempts and scope limits.
- [validation.json](validation.json) records the original local collection check: 653 prompt folders, 1174 unique PDFs parsed, 25473 PDF pages and 0 structural/integrity errors. These checks establish file integrity/readability and metadata consistency; they do not establish technical correctness, current code equivalence or professional approval.
- The original collection used 40 requested max-effort workers and 16 later Alberta-focused workers; all 56 completed. Their detailed task receipts remain in the local collection. `_research/curation_overrides.json` records parent classification/exclusion decisions.
- [Alberta Jurisdiction Sources.json](Alberta%20Jurisdiction%20Sources.json) preserves the official municipal/accreditation source inventory and access routes. Municipal rows, accredited organizations and building AHJs are different counts; this is not a claim that every municipality was scraped.
- `_source_package/` commits the 37 unique hyperlink targets and audit ledgers. The supplied DOCX, original target downloads and `_references/` assessment files remain in the local collection.

NRC codes, guides and assessments retain their publisher's rights. NRC archive sources are marked `rights_review_required`; the archive viewing terms restrict systematic downloading and commercial use, and permission for product/training reuse has not been established. Local download is not a blanket licence to redistribute sources or embed full text in the product. See the source audit for the saved terms and source-specific rights notes.

Check committed metadata with `python3 'Data Prompts/_tools/verify_corpus.py'`. This is a nonvisual research/data change; it does not change the product runtime.
