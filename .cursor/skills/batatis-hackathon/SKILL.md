---
name: batatis-hackathon
description: Full Alberta Building Codes Challenge understanding for Batatis — problem, variance template A–D, data sources, judging, and agent pitfalls. Use at thread start, when planning features, answering domain questions, or before writing code that touches applications/codes.
---

# Batatis hackathon understanding

## Mission

Build an AI-powered tool so innovators/builders submit a **complete, code-referenced alternative solution application** before it reaches a Safety Codes Officer (SCO), and so SCOs can quickly check **administrative** compliance.

## Problem (why this exists)

- Building codes are mostly prescriptive; innovation needs an **alternative solution / variance**.
- Applicants struggle to find right articles, objectives/functional statements, and supporting analysis.
- Incomplete submissions drive **weeks-to-months** of rework across **430+ Alberta jurisdictions**.
- Tool reviews **completeness**, not technical correctness.

## Prototype scope

Variance Template **Part 1 Sections A–D** (Appendix of challenge scope). Pipeline:

`Intake → Code identification → Supplemental case-building`

| Area | Expectation |
| --- | --- |
| Intake | Prompt for A–B fields; confidence; don’t invent facts |
| Code ID | Rank articles; benchmark acceptable solution; real edition citations |
| Section C | Deterministic attribution lookup (objective, function, intent) + explainer |
| Section D | Recommend evidence questions; flag engineers; don’t fill as professional |
| Review | Gap list for applicant or SCO |
| Design | PDF export; portable jurisdiction-ready data model |

Expand beyond NBC only after NBC(AE) path works.

## Code mental model

One **article** ≈ one rule = **acceptable solution** (default recipe) + **objective** (why) + **function** (what must be achieved). Alternative solution = different recipe, same-or-better performance vs those objectives/functions. **Division C** (esp. **2.3**) documents how to argue that administratively.

## NBC(AE) decision fork (official process)

Diagram: `../../../docs/diagrams/nbc-ae-acceptable-vs-alternative-flow.png`

Shared: Design → identify applicable acceptable solutions → code analysis (objectives / functional / intent) → min performance → compare → gaps → **complies with applicable acceptable solution(s)?**

- **Yes:** complete analysis → evidence of compliance (ladder) → finalise permit application.
- **No (our product focus):** SSRIA Request for Specific Variance → rationale → detailed Div B analysis (sentences + objectives / functional / intent) → **risk assessment** → **mitigating measures** → **assumptions/limits** → demonstrate equivalent performance → finalise permit application.

**Evidence confidence ladder** (lower → higher; evidence *types*): manufacturer lit → STANDATA variance → ISO 17025 test → evaluation → eval+testing → qualification → ISO 17065 certification.

**Alt-path extra evidence types** (still evidence, not process): CCMC, ICC-ES, registered professional opinion, engineering review.

**Alt-path process requirements** (never call these “evidence types” or ladder rungs): risk assessment → mitigating measures → assumptions/limits.

## Data priorities

NBC – 2023 Alberta Edition **2nd printing**; Intent Statements; Safety Codes Act + Building Code / Permit / Exemption regulations; STANDATA; SCC variance form; Calgary/Edmonton alt-solution guides; CCMC registry. See `references/data-package-index.md`.

## Judging (weight what you build)

Intake 20% · Code identification 20% · Recommendations 10% · Review 10% · Applicability 5% · Implementation plan 10% · Business plan 10% · Usability/portability 10% · X-factor 5%.

## Pitfalls

1. Saying “this complies” / “this is safe.”
2. Fabricated article numbers.
3. LLM-memorized Section C attributions instead of lookup.
4. Completing Section D as if the model were the engineer / inventing professional judgment.
5. Ignoring Division C documentation requirements.
6. Hard-coding one municipality’s form forever.
7. Skipping clarifying questions when interpretation is ambiguous.
8. Mixing assumptions into “known facts” without labeling.
9. On the alternative fork: skipping risk assessment, mitigating measures, or assumptions/limits.
10. Inventing evidence ladder outputs (tests, CCMC, STANDATA, certifications).
11. Building product UX that ignores the official NBC(AE) yes/no fork.
12. Showing NRC code text without NRC attribution and a link to the source (no word cap for the hackathon, per aamia, Oct 20; STANDATA is OGL-Alberta).
13. Treating completeness review as a safety/compliance certification for SCOs.
14. Mis-attributing **jurisdiction portability** as an SCO-surface UX rule (it is data-model / judging Usability & portability).
15. Calling risk / mitigations / assumptions “evidence types” or ladder rungs (they are alt-path **process** requirements).

## Related

- Workflow skill: `../batatis-variance-workflow/SKILL.md`
- UI (Opus 5.5): `../batatis-ui-opus/SKILL.md`
- Full brief: `../../../docs/hackathon-problem-brief.md`
- Process diagram: `../../../docs/diagrams/nbc-ae-acceptable-vs-alternative-flow.png`
