# Officer timing protocol: manual vs Batatis completeness review

**Round:** 1b (real officers). Applicant think-alouds are Round 1, in `session-script.md`.
**Question:** Does Batatis help a Safety Codes Officer (or permit reviewer) find **administrative completeness** gaps faster and more completely than a manual checklist?
**Scope, said out loud to the officer:** "Please judge only whether each submission is *complete*: required fields, signatures, attributions, mandatory alternative-solution items and evidence listed. Don't judge whether the design is technically correct or would perform. That decision isn't part of this exercise." Write any technical comments in a separate column. They don't count as gaps or as false positives.

## Materials
- **Package P-03:** a planted-gap SCO sample package and its answer key (to be added under evals/demo-cases/). Three submissions, fictional, labelled EXAMPLE DATA. Only the runner sees the answer key.
- **Package P-03b:** an equivalent second package (see below), with its own answer key in the same place. You need it whenever one officer does both conditions. Only the runner sees the key.
- **Manual checklist** (on paper or as a PDF form, one per submission):
  - A: owner · representative · mailing address · date · signature
  - B: permit # or "pending" · legal description · municipal address · project description
  - C: for each article: citation · objective · functional statement · intent
  - Alternative solution: risk assessment · mitigating measures · assumptions/limits
  - D: evidence listed and attached, or planned with a responsible party
  - Overall: ☐ admin-complete ☐ return to applicant

## Planted key for P-03 (11 items)

| Sub | Planted gap | Type |
|---|---|---|
| A (VR-2026-031) | none; should be classed admin-complete | control |
| B (VR-2026-034) | 1 Risk assessment blank · 2 Assumptions/limits blank · 3 Mitigations thin ("sprinklers" only) · 4 Section D has no evidence ("fire test to follow") | hard, hard, soft, hard |
| C (VR-2026-037) | 5 Owner blank · 6 Date blank · 7 Not signed · 8 Legal description blank · 9 Article 2 intent blank · 10 "Under 3 storeys" stated as fact, unverified · 11 Evidence is a brochure only | hard ×5, soft, soft |

"Soft" items depend on the officer's judgment. Report recall on the 8 hard items and on all 11.

## Design
- **One officer per condition (between-subjects, P-03 only):** split officers so that half review manually and half review with Batatis. Use this if you only have P-03.
- **Each officer does both (within-subjects, preferred):** the officer reviews P-03 in one condition and P-03b in the other. Counterbalance both the **order** and the **package** across officers:

| Officer | First | Second |
|---|---|---|
| O1 | Manual · P-03 | Batatis · P-03b |
| O2 | Batatis · P-03 | Manual · P-03b |
| O3 | Manual · P-03b | Batatis · P-03 |
| O4 | Batatis · P-03b | Manual · P-03 |

Repeat the cycle for O5 and beyond. Take a 2-minute break between conditions.

**Building P-03b:** copy P-03's structure exactly, with three submissions of the same length and layout, the same banner and the same `[ARTICLE-X]` placeholders. Use new fictional projects and owners (e.g. a rammed-earth garage, a container home, a mass-timber shed). Keep the **same gap count per type**: 1 clean submission, 1 missing all three alternative-solution items or with thin ones plus no evidence, and 1 missing four Section A/B fields, one Section C intent, one unverified fact and brochure-only evidence. **Change the position** of the clean submission and the order of the gaps so recall can't carry over from memory. Write its key in the same format. Pilot both packages manually with one non-participant. If their manual times differ by more than about 20%, rebalance the packages.

## Timing rules
- **Training (not timed):** 2 minutes of Batatis orientation on a different sample before the Batatis condition. In the manual condition, the officer reads the checklist first.
- **Start:** the moment the package is open on screen (manual) or the moment the officer starts the upload (Batatis). Processing time counts.
- **Stop:** when the officer says "done" and has written the final deficiency list and a complete/return call for each submission. In the Batatis condition, the final list is the items the officer **confirms**. Items the tool shows but the officer rejects don't count.
- **Cap:** 15 minutes per condition. Record the cap if it's reached.
- Use one stopwatch and record mm:ss. The moderator stays silent apart from the scope statement.

**Confidence:** right after each condition, ask: "How confident are you that your list catches every completeness gap? (1 = not at all, 5 = completely)."

## Scoring
- **Planted found:** items on the officer's list that match the key.
- **False positive:** a listed item that isn't in the key and isn't a real completeness gap in the text. The runner checks each one against the package. A real gap that wasn't planted is logged as "valid, unplanted" and doesn't count as a false positive. Technical-correctness comments are logged separately.
- **Classification:** whether each submission was called complete or return correctly (3 per package).

| Officer | Order | Cond. | Pkg | Time (mm:ss) | Hard found /8 | All found /11 | Recall (all) | FP | Valid unplanted | Classif. /3 | Confidence 1–5 | Technical comments (not scored) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| O1 | 1 | Manual | P-03 | | | | | | | | | |
| O1 | 2 | Batatis | P-03b | | | | | | | | | |

## Computing results
- **Recall** = planted gaps found ÷ planted total (11, and separately 8 hard).
- **Speed-up** (per officer, within-subjects) = manual time ÷ Batatis time. **Time saved** = (manual − Batatis) ÷ manual. Report each officer's value and the median. In the between-subjects design, compare the median times of the two groups.
- Also report the change in recall, false positives and confidence alongside time. A faster review that misses gaps isn't an improvement.

**Caveat:** with only a few officers, these numbers are **indicative only**. They aren't statistically significant, the packages are fictional and condensed, and the officers are self-selected. Report raw per-officer rows and don't extrapolate to real caseloads.
