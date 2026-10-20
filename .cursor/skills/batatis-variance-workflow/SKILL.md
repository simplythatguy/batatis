---
name: batatis-variance-workflow
description: Implement Batatis variance application workflow — adaptive intake, code identification, Section C attributions, Section D evidence planner, completeness review, PDF export, SCO view. Use when building product flows, APIs, state machines, or evals for the variance pipeline.
---

# Variance application workflow

## Map to official NBC(AE) process

Diagram: `../../../docs/diagrams/nbc-ae-acceptable-vs-alternative-flow.png`

Product state machine implements the **No / alternative solution** branch while detecting **Yes / acceptable** early (user may not need a variance).

| Official step (No branch) | Product mapping |
| --- | --- |
| Identify applicable acceptable solutions + compare/gaps | Code identification + ranking |
| Decision: complies? | Explicit fork; if Yes, steer to evidence-of-compliance checklist, not SSRIA |
| SSRIA Request for Specific Variance | Variance Template / SSRIA fields (A–D + extended) |
| Rationale for proposed variance | Intake + Section B narrative |
| Detailed Div B analysis (sentences, obj/func/intent) | Section C deterministic attributions + explainers |
| Risk assessment + mitigating measures | Required completeness items — **never skip** on alt path |
| Assumptions / limiting factors | Labeled assumptions in intake; surface before export |
| Demonstrate equivalent performance | Section D evidence planner using confidence ladder |
| Finalise permit application | PDF export + SCO reviewer view |

### Evidence types vs process requirements (do not conflate)

| Bucket | What it is | Contents |
| --- | --- | --- |
| **Shared evidence ladder** (confidence order) | Evidence *types* you recommend / collect | manufacturer lit → STANDATA → ISO 17025 test → evaluation → eval+testing → qualification → ISO 17065 certification |
| **Alt-path extra evidence types** | Additional evidence *types* on the No / variance fork | CCMC assessments, ICC-ES evaluations, registered professional opinion, engineering review |
| **Alt-path process requirements** | Required **workflow steps / fields** — **not** evidence-ladder rungs and **not** “extra evidence types” | **risk assessment**, **mitigating measures**, **assumptions / limiting factors** |

Recommend evidence; never invent ladder outputs (tests, STANDATA citations, CCMC/ICC-ES listings, stamped opinions). Still require the three process fields on every alternative-path draft before export.

## State loop (product flow)

1. Create project → describe proposed design / alternative.
2. Run shared NBC(AE) analysis enough to ask: **complies with applicable acceptable solution(s)?** If Yes → acceptable-path checklist (not full variance). If No → continue variance path.
3. **Enough information for useful search?** If not → ask critical missing facts → targeted intake answers → re-check.
4. Identify and rank candidate provisions (Division B sentences).
5. Verify article text and attributions (edition-correct).
6. Explain candidates and unresolved conditions; capture rationale for variance.
7. Build Section C table; require risk assessment, mitigating measures, assumptions/limits fields.
8. Build Section D documentation plan from evidence ladder (flag professional need).
9. Run completeness checks (alt path: risk/mitigation/assumptions must not be empty).
10. If gaps remain → show findings/next actions → back to intake.
11. Else → preview and export PDF → applicant prepares submission.
12. Parallel: SCO reviewer view summarizing citations, gaps, explanations.

## Backend sketch (team)

| Component | Role |
| --- | --- |
| Application API | Projects, answers, files, dual UI |
| Workflow/orchestration | Explicit state machine; resume; missing facts |
| Intake engine | NL → schema; deterministic validation |
| Code source registry | Edition/printing, article IDs, source locations |
| Code identification | Hybrid retrieval + curated mappings; LLM explains only |
| Attribution lookup | Deterministic objective/function/intent |
| Recommendation engine | Section D checklist + professional flags |
| Completeness checker | Deterministic first; semantic second |
| Document generator | Template PDF |
| Review/audit | Role-based; source versions |

Prefer grounded retrieval over memorized code text.

## Completeness language

Say: “Your application appears to be missing X.”  
Do **not** say: “Your design complies with the building code.”

## Section field checklist

- **A:** owner, representative, mailing address, date
- **B:** jurisdiction-wide flag, permit #, legal description / ATS, municipal address, clear alternative description
- **C:** code/standard, articles, objective, function, intent, per-article explainer
- **D:** document name + responsible professional/org; recommendations only until human provides files

Extended SSRIA fields (**required on alternative path**, not optional): Division B vs proposed performance, effects on other requirements, **risk assessment**, **mitigating measures**, **assumptions/limits**, test/engineering/CCMC/ICC-ES/STANDATA evidence, ops/maintenance, qualifications.
