# Safety Codes Council appeal cases (internal eval)

**Internal evaluation only. Do not redistribute.** Licence: **UNSTATED**. The Safety
Codes Council publishes these redacted Council orders, and no terms of use or reuse
licence were found on safetycodes.ab.ca (checked 2026-10-20). Treat the decisions as
all rights reserved. These files cite and link. They do not carry the decision text
or the PDFs.

Current evals are **model-checked**. The human key is unfilled. Appeal labels are
**weak**. They are not human verification and they are not NBC(AE) 2023 gold.

## What was kept

Each `cases/scc-*.json` file has the development-case fields where they fit
(`id`, `applicant_type`, `topic`, `jurisdiction`, `description`, `known_facts`,
`gold`, `authoring`) plus `edition_original`, `article_mapping`, `label_strength`,
and `source_url`.

`description` is at most two sentences of the researcher's paraphrase, with
provision numbers removed so they are not read as citations. `quotes` are at most
two sentences. `gold.must_cite` and `gold.section_c` are empty. `authoring.source`
is `scc-appeal-decision`.

Regenerate from the researcher's JSON (not from PDFs) with:

```bash
python evals_dev/appeals/convert.py /path/to/appeals-structured
```

## Caveats

None of these decisions is an appeal of a refusal on the current variance form.
They are permit refusals and s.49 order appeals. `refusal.code` is a mapping onto
the form's three reasons (R1 incorrect, R2 insufficient, R3 not equivalent).
`refusal.basis_type` is `close analog`, `analogous`, or `not applicable`.
`label_strength` is `weak` on every case.

Editions: 18 ABC 2006, 1 ABC 2014, 5 NBC(AE) 2019, and 1 unnamed (`scc-co-2024-01`).
Every source article is mapped in `article_mapping`. `nbc_ae_2023` stays null, with
`unmapped_reason`, until a comparison against the cited edition earns it. The same
identifier in codedb is not that comparison. A pre-2023 number is never stored as
a 2023 citation. Notes, tables, fire-code items, ABC 2006 Part 10, objective and
function labels, clause lists, and the likely typo in 2023-03 stay unmapped for
the reason on the row.

Four decisions were OCR'd from scans (`0015470`, `0015482`, `0015479`, `0015496`).
Their quotes have `quote_confidence: low`.

## How the deterministic report uses them

`python evals_dev/deterministic_checks.py` adds an `appeals` block with
`label_source: appeals_weak`. It is not mixed with model-graded scores.

- **Citation resolution after mapping.** Only rows with `nbc_ae_2023` set are
  resolved. With nothing mapped, a missing codedb reports `skipped: codedb missing`.
  Once codedb is present and titles or sentence text still cannot be compared, the
  skip is `no mapped NBC(AE) 2023 citations`. Same-identifier hits are counted in
  `same_identifier_not_promoted` and are not resolved as 2023 citations.
- **Section C anchor, decision 0015414.** The panel faulted the variance for not
  addressing objectives and functional statements. The quote is recorded here.
  The 2006 article numbers are not the benchmark. When codedb is present, a
  separate fixture probe checks that an empty Section C on a known benchmark is
  flagged `D16`.
- **Professional involvement.** Twelve decisions address it. Five weak flags are
  `yes` (the panel required involvement) and seven are `depends` (the point was
  not a yes/no trigger, including the two deference cases). The agreement line
  compares the engine screen with those flags and reports `x of n` with a Wilson
  95% interval. The screen only receives a `ProfessionalFacts` field the decision
  states in the engine's own vocabulary. An order to file schedules, or a panel
  conclusion, is not rewritten as `ahj_requires_professional`. Without codedb the
  agreement line is `skipped: codedb missing`. The twelve flags are still counted
  under `weak_labels`.
- **2022-06.** Close analog of insufficient information. The source provision is
  NBC(AE) 2019 Division C 2.2.10.8.(2)(b). `presented_as_2023` is false.
- **0015427.** Alternative accepted with a condition (outcome varied).
- **2024-06 and 0015432.** Opposing deference labels: `officer_not_bound` and
  `issuer_must_not_dismiss_expert_without_competing_evidence`.
