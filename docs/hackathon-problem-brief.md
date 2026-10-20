# Batatis — Building Codes Challenge problem brief

> Mirror of the Project Context brief. Keep in sync with team Context `docs/hackathon-problem-brief.md` when either changes.

Hackathon: **Building Codes Challenge**, Built World Tech — Venture Pilots 2026 (Alberta).

## One-sentence problem

Innovators must submit **alternative solution / variance applications** that prove equivalent-or-better performance vs prescribed code; most fail first-pass because submissions are **incomplete or administratively non-compliant**, burning weeks–months across **430+ Alberta jurisdictions**.

## Required product (near-term prototype)

AI tool that:

1. Guides completion of the **Safety Codes Variance Template Part 1, Sections A–D**.
2. Identifies and ranks relevant building-code articles.
3. Completes **Section C** via **deterministic lookup** of objectives, functional statements, and intent statements.
4. Flags **engineering / licensed professional** need; recommends Section D evidence topics — does **not** invent professional judgment.
5. Reviews applications for **completeness**, not technical correctness.
6. Exports PDF matching the template; keeps data **portable** across jurisdictions.
7. Provides an **SCO reviewer** interface.

Pipeline: `Intake → Code identification → Supplemental case-building`. Start with **NBC(AE) 2023, 2nd printing**.

## Variance template (Part 1)

| Section | Purpose |
| --- | --- |
| A | Applicant info |
| B | Proposed alternative + site/jurisdiction details |
| C | Article ↔ objective / function / intent + explainers |
| D | Supporting docs + responsible professionals |

## Agent watch-outs

1. Completeness ≠ compliance/safety certification.
2. No fabricated article numbers.
3. Section C is lookup, not LLM memory.
4. Do not complete Section D as the engineer.
5. Division C (esp. §2.3) is the admin documentation bottleneck.
6. Jurisdiction portability — don’t hard-code one municipality.
7. Ambiguity → ask clarifying questions.
8. Label assumptions vs facts.

## Judging weights

Intake 20% · Code ID 20% · Recommendations 10% · Review 10% · Applicability 5% · Implementation 10% · Business 10% · Usability/portability 10% · X-factor 5%.

## Primary sources

Challenge Scope PDF (Edmonton Unlimited / team Research pack), Data Package docx, SCC variance template, Calgary/Edmonton alternative-solution guides, team Omar solution + EU Hack notes. See `.cursor/skills/batatis-hackathon/references/data-package-index.md`.
