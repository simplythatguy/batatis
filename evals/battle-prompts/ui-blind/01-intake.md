# UI-B01 — Applicant intake

Build the applicant intake screen for a variance application project.

## Required capabilities (do not omit)

- Collect Safety Codes Variance Template Part 1 **Section A** fields: owner, representative, mailing address, date.
- Collect **Section B** fields: jurisdiction-wide flag, permit #, legal description / ATS, municipal address, clear description of the proposed alternative.
- Show **confidence** on fields the system inferred; never silently fill required blanks.
- Let the user mark statements as **assumption** vs known fact.
- Show a completeness gap list for missing A/B items.
- Primary actions: Save draft, Continue to code identification.
- Navigation must make this project reachable alongside other workflow steps (intake → codes → Section C → evidence → export).

## Out of scope for this screen

Do not implement the full Section C table or SCO reviewer here — only links/nav to those steps.
