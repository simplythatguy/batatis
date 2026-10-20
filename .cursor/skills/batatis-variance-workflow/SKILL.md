---
name: batatis-variance-workflow
description: Implement Batatis variance application workflow — adaptive intake, code identification, Section C attributions, Section D evidence planner, completeness review, PDF export, SCO view. Use when building product flows, APIs, state machines, or evals for the variance pipeline.
---

# Variance application workflow

## State loop (product flow)

1. Create project → describe proposed alternative.
2. **Enough information for useful search?** If not → ask critical missing facts → targeted intake answers → re-check.
3. Identify and rank candidate provisions.
4. Verify article text and attributions (edition-correct).
5. Explain candidates and unresolved conditions.
6. Build Section C table + Section D documentation plan.
7. Run completeness checks.
8. If gaps remain → show findings/next actions → back to intake.
9. Else → preview and export PDF → applicant prepares submission.
10. Parallel: SCO reviewer view summarizing citations, gaps, explanations.

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

Extended SSRIA fields (optional stretch): Division B vs proposed performance, effects on other requirements, risk/mitigation, assumptions, test/engineering/CCMC/STANDATA evidence, ops/maintenance, qualifications.
