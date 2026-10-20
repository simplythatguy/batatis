# Officer timing protocol: manual vs Batatis completeness review

**Round:** 1b (1–2 real officers). Applicant think-alouds are Round 1 (3 applicants), in `session-script.md`.
**Question:** Does Batatis help a Safety Codes Officer (or permit reviewer) find **administrative completeness** gaps faster and more completely than a manual checklist?
**Scope, said out loud to the officer:** "Please judge only whether each submission is *complete*: required fields, signatures, attributions, mandatory alternative-solution items and evidence listed. Don't judge whether the design is technically correct or would perform. That decision isn't part of this exercise." Write any technical comments in a separate column. They don't count as gaps or as false positives.

## Materials
These packages are defined in this protocol. They are not files in this repo. The planted-gap SCO package and its answer key will be added under evals/demo-cases/ in a separate PR.
- **First package:** three fictional submissions, labelled EXAMPLE DATA, with the gaps in the key below. Only the runner sees the answer key.
- **Second package:** an equivalent package, defined under "Building the second package" below, with its own answer key written in that same separate PR. You need it whenever one officer does both conditions. Only the runner sees the key.
- **Manual checklist** (on paper or as a PDF form, one per submission):
  - A: owner · representative · mailing address · date · signature
  - B: permit # or "pending" · legal description · municipal address · project description
  - C: for each article: citation · objective · functional statement · intent
  - Alternative solution: risk assessment · mitigating measures · assumptions/limits
  - D: evidence listed and attached, or planned with a responsible party
  - Overall: ☐ admin-complete ☐ return to applicant

## Planted key for the first package (11 items, defined here)

| Sub | Planted gap | Type |
|---|---|---|
| A (VR-2026-031) | none; should be classed admin-complete | control |
| B (VR-2026-034) | 1 Risk assessment blank · 2 Assumptions/limits blank · 3 Mitigations thin ("sprinklers" only) · 4 Section D has no evidence ("fire test to follow") | hard, hard, soft, hard |
| C (VR-2026-037) | 5 Owner blank · 6 Date blank · 7 Not signed · 8 Legal description blank · 9 Article 2 intent blank · 10 Section B says "under 3 storeys" and an attachment states a different storey count (name both; do not pick one) · 11 Evidence is a brochure only | hard ×5, soft, soft |

"Soft" items depend on the officer's judgment. Report recall on the 8 hard items and on all 11.

## Design
- **One officer per condition (between-subjects, first package only):** split officers so that half review manually and half review with Batatis. Use this if you only have the first package.
- **Each officer does both (within-subjects, preferred):** the officer reviews the first package in one condition and the second package in the other. Counterbalance both the **order** and the **package** across officers:

| Officer | First | Second |
|---|---|---|
| O1 | Manual · first package | Batatis · second package |
| O2 | Batatis · first package | Manual · second package |
| O3 | Manual · second package | Batatis · first package |
| O4 | Batatis · second package | Manual · first package |

Repeat the cycle for O5 and beyond. Take a 2-minute break between conditions.

**Building the second package:** copy the first package's structure exactly, with three submissions of the same length and layout, the same banner and the same article placeholders. Use new fictional projects and owners (for example a rammed-earth garage, a container home, a mass-timber shed). Keep the **same gap count per type**: 1 clean submission, 1 missing all three alternative-solution items or with thin ones plus no evidence, and 1 missing four Section A/B fields, one Section C intent, one Section B fact that contradicts an attachment, and brochure-only evidence. **Change the position** of the clean submission and the order of the gaps so recall can't carry over from memory. Write its key in the same numbered format. Pilot both packages manually with one non-participant. If their manual times differ by more than about 20%, rebalance the packages.

## Timing rules
- **Training (not timed):** 2 minutes before **each** condition, on material that is not in either scored package. Manual: the officer reads the checklist and reviews one practice submission. Batatis: 2 minutes of orientation on a different sample. The clock starts only after that preparation.
- **Start:** the moment the package is open on screen (manual) or the moment the officer starts the upload (Batatis). Processing time counts.
- **Stop:** when the officer says "done" and has written the final deficiency list and a complete/return call for each submission. In the Batatis condition, the final list is the items the officer **confirms**. Items the tool shows but the officer rejects don't count.
- **Cap:** 15 minutes per condition. If the cap is reached, write "15:00 cap". That value is censored, not an observed time.
- Use one stopwatch and record mm:ss. The moderator stays silent apart from the scope statement.

**Confidence:** right after each condition, ask: "How confident are you that your list catches every completeness gap? (1 = not at all, 5 = completely)."

## Scoring
Planted items keep the numbers in the key (1–11). The clean submission has none.
- **Planted found:** a listed deficiency matches exactly one numbered item when it names that submission and that missing or contradictory field. A synonym counts ("unsigned" matches 7). One broad note matches only the items it names; it does not cover several items at once. A partial mention that does not name the gap does not match. Count each item once.
- **False positive:** a listed item that matches no numbered item and isn't a real completeness gap in the text. The runner checks each one against the package. A real gap that wasn't planted is logged as "valid, unplanted" and doesn't count as a false positive. Technical-correctness comments are logged separately.
- **Classification:** whether each submission was called complete or return correctly (3 per package).

| Officer | Order | Cond. | Pkg | Time (mm:ss) | Hard found /8 | All found /11 | Recall (all) | FP | Valid unplanted | Classif. /3 | Confidence 1–5 | Technical comments (not scored) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| O1 | 1 | Manual | first | | | | | | | | | |
| O1 | 2 | Batatis | second | | | | | | | | | |

## Computing results
- **Recall** = planted gaps found ÷ planted total (11, and separately 8 hard).
- **Speed-up** (per officer, within-subjects) = manual time ÷ Batatis time. **Time saved** = (manual − Batatis) ÷ manual. Use only officers whose **both** times are uncapped. If either time is a 15:00 cap, leave speed-up and time saved blank for that officer and report the capped row separately. Report each uncapped officer's value and the median of those values. In the between-subjects design, compare the median uncapped times of the two groups, and report capped rows separately.
- Also report the change in recall, false positives and confidence alongside time. A faster review that misses gaps isn't an improvement.

**Caveat:** with only a few officers, these numbers are **indicative only**. They aren't statistically significant, the packages are fictional and condensed, and the officers are self-selected. Report raw per-officer rows and don't extrapolate to real caseloads.
