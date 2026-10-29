# Workflow bakeoff v2: the official NBC(AE) flowchart against our workflow, on real Alberta records

Measured on 2026-10-28. The numbers are in [RESULTS.md](RESULTS.md), which `report.py` writes from the saved runs.

## The question

An industry practitioner drew the official NBC(AE) process as a flowchart (`docs/diagrams/nbc-ae-acceptable-vs-alternative-flow.png`). The question was whether Batatis should follow it, and which workflow gives the most complete application for the least applicant effort.

The first bakeoff (`experiments/workflow-bakeoff/`, 27 October) said our path won. It used 152 prompts the team wrote, called no model, and answered most of the flowchart's questions with "Not sure". That was not a fair test of the flowchart, so this one starts again.

## What changed from the first bakeoff

- **Real records.** The 64 Alberta records in `docs/research/2026-10-23-elephant/cases-alberta.json`: 24 STANDATA and municipal variances, 22 interpretations, 11 appeals, 6 bulletins and 1 worked example. Each has an applicant-style description with the article numbers removed, and the articles the regulator actually cited, mapped to NBC(AE) 2023.
- **A model in the loop.** Claude Haiku 5.5 at medium effort answered every model request, through the Claude subscription instead of the paid API (`requests.py`, answered by T3 tasks).
- **Simulated applicants.** Haiku 5.5 played a novice (a homebuilder who has never read the code) and an expert consultant. Each answered the same questionnaire for each project. The expert has two variants: one with the code book open (identification and attributions are right by construction) and one answering from memory.
- **The flowchart, three ways.** As a form the applicant fills in, the same form with a code lookup for Section C, and with the app doing the flowchart's analysis boxes.
- **Outcome scoring.** Every workflow's final application is scored the same way: deterministic checks (cited article, Section C codes, coverage of Division C 2.3.1.1, compliance wording, invented citations) and a blind grader (Claude Opus 5.5, medium effort) that saw all drafts for a project unlabelled and shuffled, beside the regulator's citations.

## The workflows

| Name | What the applicant does | What the app does |
|---|---|---|
| Ours today (`ours`) | Confirms the reading, answers the planner's 5 questions, confirms a variance when the path is not decided, picks the benchmark from the first 3 ledger rows, writes the departure, reviews 6 drafts and answers their gaps | Today's code: deterministic path, deterministic ledger order, drafts |
| Official flowchart as a form (`flowchart_form`) | Every box: names the acceptable solution, its objectives, functions and intent, the performance level, the comparison, the gaps, then yes or no, then the variance boxes | Nothing |
| Flowchart form + lookup (`flowchart_lookup`) | The same, without the objectives, functions and intent | Section C from the code's tables for the article the applicant named |
| Flowchart's steps done by the app (`flowchart_app`) | Confirms the benchmark and the comparison, writes rationale, risk, mitigation and assumptions | Ranks articles, looks up Section C, compares with the acceptable solution, plans the evidence |
| Hybrid (`hybrid`) | Ours, with the comparison and the ranking | Ranks articles, compares, drafts all six statements |
| Hybrid lean (`hybrid_lean`) | No planner questions, one review screen for the drafts, answers every gap | Same as hybrid |
| Hybrid focus (`hybrid_focus`) | Confirms the benchmark and the comparison, reviews the drafts, answers at most 3 gaps (rationale, assumptions and limits, maintenance) | Same as hybrid; other gaps go to the professional as Section D requests |

## Fairness choices

- The flowchart has only yes and no at its diamond. An applicant who is not sure takes the variance branch, and the run counts that as a forced guess instead of a dead end.
- The expert with the code book identifies the right article and copies the right attributions; the flowchart's form arms get that benefit in full.
- Every arm that shows the applicant a list lets the expert keep a regulator-cited article from it, so no arm's list quality is hidden by the persona.
- App-written text and applicant-written text are scored apart. A compliance claim counts only in text the app wrote, checked with the product's own wording filter (`engine/intake/review.verdict`).
- Process fields the flowchart does not draw (maintenance and operation, qualifications) count against it in the coverage score, because Division C 2.3.1.1.(2)(b) and (4) require them.

## Reproduce

```sh
export BAKEOFF2_RUNS=/path/to/runs          # requests, responses and results live outside git
python experiments/workflow-bakeoff-v2/stage0.py                 # product intake, path and ranking, no model
python experiments/workflow-bakeoff-v2/requests.py r1 persona_novice persona_expert
#   answer requests/*/ with Haiku 5.5 medium, then:
python experiments/workflow-bakeoff-v2/requests.py r2 r0 r1x
python experiments/workflow-bakeoff-v2/run_arms.py
python experiments/workflow-bakeoff-v2/judge.py build            # answer requests/judge with Opus 5.5 medium
python experiments/workflow-bakeoff-v2/report.py
```

`batches.py <stage> <n>` lists pending requests in batches for the answering tasks. The code database must be built (`codedb/build/codedb.sqlite`).

## What these numbers are not

- No Safety Codes Officer graded these drafts. The grader is a model with the regulator's citations beside it.
- The applicants are simulated. Real novices may know more or less than the novice persona, and a real consultant would open the code book; the two expert variants bracket that.
- The descriptions are applicant-style rewrites of published records, not original applications. Several records publish their own outcome, and the grader flagged invented facts where drafts restated a later ruling, so the fabrication flag separates workflows weakly.
- Minutes are an estimate from fixed weights per kind of input (`arms.MINUTES`), reported beside the raw counts.
- Haiku answered through T3 tasks, not the API. The tasks run inside Claude Code with project instructions, so the answers approximate what the API returns.
- One run per arm. The drafts and rankings come from one model call each, so a rerun can move a case.
