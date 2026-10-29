# Which workflow should Batatis use? Tested on 64 real Alberta records

28 October 2026. Method and limits: [experiments/workflow-bakeoff-v2/README.md](../../experiments/workflow-bakeoff-v2/README.md). Every number: [RESULTS.md](../../experiments/workflow-bakeoff-v2/RESULTS.md).

## The answer

The official NBC(AE) flowchart is the right checklist of what an application must contain. It is the wrong list of questions to put to an applicant. Asked as a form, a first-time applicant cannot answer its code questions and has to guess at its yes/no step in 45 of 64 cases; an expert with the code book needs about 50 minutes and still produces a weaker application than our flow.

The best workflow keeps the flowchart's analysis steps but lets the app do them: rank the code articles, look up Section C, compare the design with the acceptable solution, and draft the six statements for the applicant to review on one screen. On the same 64 records it produced the best applications for both kinds of applicant, with about 40% fewer inputs than our flow today.

## Results

A blind grader (Claude Opus 5.5) scored each finished application out of 10 against what the regulator actually cited. It did not know which workflow wrote which draft.

| Workflow | First-time applicant: inputs | minutes | grade | Expert with the code book: inputs | minutes | grade |
|---|---:|---:|---:|---:|---:|---:|
| Our flow today | 20.5 | 29 | 3.4 | 21.5 | 38 | 5.9 |
| The flowchart as a form, with Section C looked up | 13.0 (4 code questions) | 24 | 2.0 | 12.9 (4 code questions) | 51 | 4.9 |
| The flowchart's steps done by the app | 7.7 | 16 | 4.4 | 7.6 | 19 | 5.8 |
| **App does the analysis, applicant reviews drafts on one screen** | 12.7 | 21 | **5.6** | 12.5 | 27 | **7.5** |
| Same, with at most 3 gap questions | 7.7 | 12 | 5.2 | 7.6 | 16 | 6.4 |

Minutes are an estimate from fixed weights per kind of input. The grades are a model's judgment, not an officer's.

## Code identification on real records

The answer key is the article the regulator cited, mapped to NBC(AE) 2023. The descriptions leave the article numbers out.

| Ranking | Cited article first | Cited article in the first 3 |
|---|---:|---:|
| Today's deterministic search | 26 of 64 | 32 of 64 |
| Same search, then Claude Haiku 5.5 ranks the leading 60 with word-for-word quotes (shipped in this PR) | 46 of 64 | 55 of 64 |
| Haiku first reads all 2,080 Division B titles to add up to 12 candidates, then ranks (measured, not shipped) | 54 of 64 | 58 of 64 |

The table-of-contents step raises the share of cited articles that reach the candidate list from 94 of 111 to 106 of 111, and adds about US$0.005 per application.

## Mistakes the workflow does not let through

- **Invented code articles shown to the applicant: 0.** Every AI pick carries a quote. The quote check threw out 5 of 236 picks in the shipped ranking, and 1 of 287 in the table-of-contents version.
- **Compliance claims in text the app wrote: 0**, checked with the product's own wording filter.
- **Quotes in the comparison step: 64 of 64** found word for word in the article, and 64 of 64 in the applicant's description.
- **Dead ends fixed.** On real records, a keyword picked a coded rule the building was outside of ("no glazing" picked the house glazing rule for a ten-storey building) and the application stopped with no package. That happened on 2 of 64 records and on the README's own demo house. A rule that does not apply no longer decides the path.
- **Wrong turns fixed.** Two building-code questions were sent to another safety code: photoluminescent exit signs on their own charging circuit, where "circuit" outweighed "exit", and the energy rules for small equipment shelters (Section 9.36). One variance read as following the code, because "would meet the minimum" matched and "can the stretcher-size rule be set aside" did not. Exit signs, emergency power and small-building energy rules now count as building-code words, and setting a rule aside, waiving or relaxing it count as departure words. Tests now check that none of the 64 records is redirected and none of the 24 variances reads as following the code.
- **Applicants who write code citations themselves get them wrong.** An expert answering from memory named a cited article in 6 of 64 cases. None of their 64 Section C entries matched the code's tables, and 16 named objective or function codes the article does not carry. The app looks Section C up instead.

## Cost

The AI costs cents per application; people's time is the cost. Full model with sources: [cost model](../research/2026-10-28-bakeoff/cost-model.md).

- About US$0.57 of model calls per application with tonight's models (intake, document review and drafting on Claude Sonnet 5.5), and about US$0.05 if they all move to Claude Haiku 5.5. Finding and ranking the code articles adds about US$0.008 a search, most of it the table-of-contents step. These use the cost model's token assumptions; no applicant has run the full flow with metering on.
- An extra "more information" round on a custom application costs about C$3,600, most of it the builder's carrying cost while the project waits.
- Batatis pays for itself if it saves one extra round in every 60 custom applications.

## Tools we considered

LangChain, LangGraph, LangSmith and Deep Agents would not move any of these numbers. Batatis has no agent loop for them to improve, and they would add about 42 MB and a slower cold start. Details: [tools memo](../research/2026-10-28-bakeoff/langchain-and-tools.md).

## Shipped, and next

Shipped in this pull request: the Haiku ranking of code articles, the fix for rules that do not apply, and the fixes for the three wrong turns above.

Shipped in the follow-up pull request:

1. The comparison step on screen: the code text, the design's departure, and the drafted difference, with Confirm.
2. The six drafts on one review screen with Accept all, and the planner's article-narrowing questions skipped once the AI ranking has read the description.
3. The table-of-contents step before the ranking. The engine sends the measured requests, except that the table of contents goes inline instead of as a file and its candidates are capped at 12.

Next: run the 64-record test again on the app's own flow, end to end.

## What these numbers are not

- No Safety Codes Officer graded these applications.
- The applicants were simulated by Claude Haiku 5.5, a novice and an expert, on applicant-style rewrites of published records.
- One run per workflow; a rerun can move individual cases.
- Several records publish their own outcome, so drafts sometimes restated a later ruling as a known fact; the grader's fabrication flag is noisy for that reason.
