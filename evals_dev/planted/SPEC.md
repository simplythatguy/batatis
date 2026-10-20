# Planted-defect specification for officer review

Purpose: measure whether the **Review an application** path catches administrative gaps in a
completed Safety Codes Variance Template, Part 1, Sections A to D, and its attachments. Review
checks completeness and source consistency, never technical correctness. Generating the seeded
PDFs waits for the form export (day 4). This file fixes the defect classes and the expected
detections now, so the checker cannot be tuned to whatever the generator happens to produce.

## Seeding protocol

1. Start from a **clean base application**: a development case (`evals_dev/cases/`, `proceed_conditionally`
   only) carried through Batatis to a complete Sections A to D, then exported. A base must pass review with
   zero findings. If it does not, fix the base or the checker before seeding.
2. Plant **one to three defects per application**, drawn from the classes below, recorded in a sidecar
   `planted/<app-id>.json`: `{base_case, defects: [{class, location (section/row/field/attachment), planted_value, original_value}]}`.
   The sidecar is judge-only and never goes to the checker.
3. Target 20 seeded applications (plan: "Review catches gaps"). Every class appears at least once;
   rule-checked classes at least twice.
4. **Half the applications are seeded by an author who has not read the checker's code or prompts.**
   Record the author per application.
5. Also include 2 clean applications as controls; any finding on them is a false positive.
6. Export each seeded application through the same fillable-PDF path and a flattened copy, so the
   uploaded-form reader is tested on both.

## Scoring

- **Detection:** a planted defect is caught when the review names the right section/row/field (or
  attachment) and the right problem. Naming the section with a different problem is a miss.
- Report caught / planted per class and overall, with 95% Clopper-Pearson bounds; list every miss.
- **False positives:** findings on clean controls, and findings on seeded applications that match no
  planted defect and are not a genuine pre-existing gap (adjudicated, logged).
- **Information request:** each caught defect must appear in the drafted information request as a
  request to the applicant, not a fix made by Batatis.
- **Never acceptable:** the review fills in a missing item itself, says the design complies, or
  writes the risk assessment, mitigating measures or the officer's decision.

`Check` says how a correct reviewer can catch the defect: **rule** (deterministic: field
presence, database lookup, citation validator, table comparison) or **judgement** (needs reading the
description and attachments; an LLM step that must point to the evidence span).

## Defect classes

| # | Class | How to plant | Expected detection | Check |
|---|---|---|---|---|
| D01 | Missing owner | Blank the owner name (Section A). | "Owner name is blank" in Section A; information request asks for it. Blank (certain) is reported differently from not found (flattened form, unreadable). | rule |
| D02 | Missing date | Blank the application date, or a signature date. | Missing date flagged at the right field. | rule |
| D03 | Missing civic address | Blank the project address. | Missing address flagged; not guessed from attachments. | rule |
| D04 | Missing legal description | Blank lot/block/plan, or leave a placeholder ("TBD"). | Missing or placeholder legal description flagged. A placeholder counts as missing. | rule |
| D05 | Nonexistent article in Section C | Change a Section C row's provision to an id that does not exist in NBC(AE) 2023 2nd printing (for example add a sentence number past the article's last sentence). | "Provision not found in NBC(AE) 2023, 2nd printing" at that row. | rule (database lookup) |
| D06 | Superseded edition number presented as current | Replace a citation with the number the requirement had in an earlier Alberta edition (NBC(AE) 2019 or ABC 2014), taken from a precedent in `research/precedents/index.json` whose `articles_varied` records the edition change, without an edition label or labelled as current. Do not invent the old number. | "Cites a superseded edition as current"; name the 2023 provision if the precedent record maps it, otherwise ask. Explicit historical mentions are not defects. | rule (citation validator edition check) when labelled; rule (lookup/heading mismatch) when unlabelled |
| D07 | Wrong objective/function pair | Swap a Section C pair for a pair that exists in the attribution tables but not for this provision, or move a pair from the root sentence onto an exception with no row. | "Pair not attributed to this provision in the Division B table"; shows the table's pairs. | rule (table comparison) |
| D08 | Intent presented as Alberta law | State the national 2020 intent statement as the "Alberta intent" or as a requirement, without the explanatory label. | "Intent statement is national 2020 explanatory material, not Alberta law"; asks for the label. | rule (citation validator label check) plus judgement for unlabelled paraphrase |
| D09 | Empty risk assessment | Leave the risk assessment blank or one generic line ("low risk"). | Flagged as missing or not specific to the departure. Batatis does not draft it. | rule for blank; judgement for generic |
| D10 | Empty mitigating measures | Blank the mitigating measures, or measures that do not relate to the Section C objective. | Flagged; points to the objective/function the measures must address. | rule for blank; judgement for unrelated |
| D11 | Empty assumptions and limits | Blank the assumptions, limiting or restricting factors. | Flagged as required documentation of the Code analysis (Div C, Sentence 2.3.1.1.(3)). | rule |
| D12 | Professional required but none named | On a case whose gold `engineering_required` is `yes`, leave the responsible professional, seal and qualifications blank. | "A registered professional is required for this work and none is named"; cites the Division C trigger (for example Div C, Article 2.4.1.1. or Sentence 2.4.1.2.(1)) and asks for qualifications (Div C, Sentence 2.3.1.1.(4)). | rule (case flag + field presence) |
| D13 | Supporting document without a responsible person | Attach a test report or analysis with no author, issuer, seal or date in the supporting-documents list. | Supporting-documents panel marks it "no responsible person"; information request asks who is responsible. | rule (field presence) on the documents list; judgement when reading the attachment |
| D14 | Section B contradicts attachments | Change a fact in Section B (for example limiting distance, storeys, sprinklered, product thickness) so it disagrees with the drawings or report attached. | Names both values and both locations; asks which is correct. Does not pick one. | judgement (must quote both spans) |
| D15 | Article irrelevant to the described design | Replace the benchmark with a real provision on an unrelated topic (for example a stair dimension provision on a cladding variance). | "Cited provision does not address the described departure"; suggests asking the applicant, shows the provision's heading. | judgement (heading/topic mismatch can pre-screen) |
| D16 | Section C row missing for a cited benchmark | Delete the Section C row for one benchmark sentence named in Section B. | "Benchmark cited in Section B has no Section C row." | rule |

Classes D01 to D04 cover the administrative core; D05 to D08 citation integrity; D09 to D11 the
alternative-solution process fields that must never be skipped; D12 and D13 responsibility; D14
and D15 consistency, which only judgement can catch and which the plan reports separately.

## Report

Per class: planted, caught, missed (with application and location), false positives on controls, and
the split by seeding author (checker-aware vs checker-blind). Rule-checked classes should reach full
detection; any miss there is a bug, not a measured rate.
