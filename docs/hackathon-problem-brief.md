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

## NBC(AE) acceptable vs alternative flow

Official process diagram (repo): [`docs/diagrams/nbc-ae-acceptable-vs-alternative-flow.png`](./diagrams/nbc-ae-acceptable-vs-alternative-flow.png)

**Shared path:** Design → identify applicable acceptable solutions → code analysis (objectives / functional / intent) → establish minimum performance → compare proposed vs acceptable → identify gaps → **decision: complies with applicable acceptable solution(s)?**

| Fork | Path |
| --- | --- |
| **Yes (acceptable)** | Complete code analysis → evidence of compliance (confidence ladder below) → finalise building permit application |
| **No (alternative / variance)** | Use **SSRIA Request for Specific Variance** → rationale → detailed code analysis (**Division B** sentences + objectives / functional / intent) → **risk assessment** → **mitigating measures** → **assumptions / limiting factors** *(process requirements — not ladder rungs)* → demonstrate equivalent performance (evidence ladder + **extra evidence types**: CCMC, ICC-ES, registered professional opinion, engineering review) → finalise permit application |

**Evidence confidence ladder** (lower → higher; evidence *types* only): manufacturer’s published literature → existing STANDATA variance → ISO 17025 test report → evaluation → evaluation + testing → qualification → ISO 17065 certification.

Do **not** list risk / mitigations / assumptions as ladder rungs or “extra evidence types.”

Batatis product flow maps onto the **No** branch (variance) while still helping users discover when they are actually on the **Yes** branch.

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
4. Do not complete Section D as the engineer / invent professional judgment.
5. Division C (esp. §2.3) is the admin documentation bottleneck.
6. Jurisdiction portability — don’t hard-code one municipality (**data-model / judging**, not an SCO UX rule).
7. Ambiguity → ask clarifying questions.
8. Label assumptions vs facts.
9. **Respect the NBC(AE) decision fork** — if the proposal is an alternative solution, do **not** skip rationale, risk assessment, mitigating measures, or assumptions/limits (**process** fields).
10. **Evidence ladder** — recommend evidence types by confidence; never invent test results, CCMC listings, STANDATA cites, or professional opinions. Keep process fields separate from ladder types.
11. Map Omar/product UI flow to this official process (variance path = SSRIA + Div B attributions + risk/mitigation + equivalent-performance evidence).
12. Attribute UX rules by surface: Applicant = confidence / no silent fills / novice clarity; SCO = distinct code text vs AI; portability stays with schema/judging.

## Judging weights

Intake 20% · Code ID 20% · Recommendations 10% · Review 10% · Applicability 5% · Implementation 10% · Business 10% · Usability/portability 10% · X-factor 5%.

Verbatim source: [docs/judging-rubric.md](./judging-rubric.md).

## Primary sources

Challenge Scope PDF (Edmonton Unlimited / team Research pack), Data Package docx, SCC variance template, Calgary/Edmonton alternative-solution guides, team Omar solution + EU Hack notes, **NBC(AE) acceptable-vs-alternative flow diagram**. See `.cursor/skills/batatis-hackathon/references/data-package-index.md`.
