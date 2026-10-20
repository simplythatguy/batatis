# UI-B05 — Export / PDF preview

Build the export and PDF preview screen for the variance application.

## Required capabilities (do not omit)

- Preview of the Safety Codes Variance Template Part 1 (A–D) as it will export.
- Completeness gate before download: block or prominently warn when alternative-path **risk assessment**, **mitigating measures**, or **assumptions/limits** are missing.
- Unconfirmed **inferred owner** is a listed gap; preview marks the owner until Confirm clears it (do not print as an unmarked fact).
- Unconfirmed articles are labeled as not exported in the preview; gate text names them.
- Section D shown as a **documentation plan** (document name + responsible org) — not invented engineering conclusions.
- Actions: Download PDF (enabled only when gate passes, or with explicit override that still lists gaps — including inferred owner), Back to fix gaps.
- Show remaining administrative gaps next to the preview (same shared source as intake / SCO).
- Navigation to other workflow steps.
