# Demo Studio: script sources

The pitch lives in `web/src/studio/deck.ts` and is recorded at `/studio`. Every number it says comes from the repo:

| Said in the video | Source | Limits |
|---|---|---|
| 366 variances on 9.10.11.2. in six months ("two a day") | `docs/business-plan.md` (Safety Codes Council Data Hub, Q1–Q2 2026) | Entries per article, not distinct applications; 366 ÷ 181 days |
| About CA$3,600 per extra round trip | `docs/research/2026-10-28-bakeoff/cost-model.md` finding 2 | Estimate from published wages, fees and rates |
| The real Edmonton solution | City of Edmonton, *Alternative Solution for Secondary Suites in Rowhouses* (v02, 31 Jul 2024; Policy B23-01), `Data Prompts/.../L05-014-*` | A city demonstration, not one applicant's file; the applicant and site on the demo form are fictional |
| The deleted rule ranked first, ten runs out of ten | `docs/studio/edmonton-verification.md` (10 fresh applications, 29 Oct 2026, local app) | Our own runs on one case; Section C matched codedb in every run |
| Right article first: 26 → 54 of 64 (10 of 64 not first) | `experiments/workflow-bakeoff-v2/RESULTS.md` ranking table; shipped config `engine/identify/pipeline.json` (`model_rank_toc: 12`) | 64 real Alberta records, article numbers removed from the descriptions |
| Zero made-up articles shown | `docs/evaluations/workflow-bakeoff-v2-20261028.md` | Same 64 records |
| First-time applicant 2.0 → 5.6 of 10 | `experiments/workflow-bakeoff-v2/RESULTS.md`, `README.md` | Simulated applicants, model grader, one run |
| About a dollar twenty of AI per application (CA$1.23 average of 3 metered runs; US$0.88 × 1.4057) | `docs/studio/measured-cost.md` (29 Oct 2026) | Edmonton case only; C$1.08 without one draft our test script discarded; the officer's review uses no AI |
| 435 places mapped to their office; live in Calgary and Edmonton | `docs/verification/every-place/README.md` | 43 of the 435 are outside Alberta; other places are a draft, switched off |
| A new office is a data file, zero code changes | `docs/api/jurisdictions.md` (synthetic fourth pack test) | |
| 13,743 provisions | `codedb/README.md` | NBC(AE) 2023, 2nd printing |
| No officer has reviewed a real Batatis application | `README.md` "What we measured" | Said in the video |
| One office, ninety days, beside today's process | `docs/pilot-adoption-plan.md` §1 | A target; no partner has agreed yet |
| Better models don't keep an office's rules current | `docs/business-plan.md` (why us, jurisdiction packs) | Positioning, not a measurement |
