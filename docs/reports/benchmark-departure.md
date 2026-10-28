# The departure now reaches the appendix

A variance application makes two claims. The code requires something (the **benchmark** acceptable solution), and this design does something else (the **departure**). Batatis built the first claim properly and had an engine route for the second. No screen called that route, so the applicant was never asked for the departure and the exported appendix never stated one. This change adds the missing question and makes one engine call record the whole claim.

## What the applicant sees

After answering **Yes** to a code card, the deck asks one more thing in the applicant's own words.

> What does your design do instead?

The answer, one sentence, is saved with the card's article. The card does not appear again once the engine has confirmed the departure.

## Why it mattered

The application could name the acceptable solution it departs from and stay silent about the departure itself. Section C listed rows. The appendix stopped there.

The engine already had the safeguard this breaks. `requirement_decisions.record` refuses to give a requirement the `varied` role unless the benchmark and its departure are confirmed. The code-check card went around that guard by assigning `varied` directly, with a canned reason in nobody's words ("Applicant confirmed that the design departs from this requirement"). The guard now describes a state the app can actually reach.

## One correction to the earlier diagnosis

The gap was described earlier as the appendix printing "not yet confirmed by the applicant". That string exists, but the live profile uses `screen=requirements`, and that path builds `BenchmarkRecord(identified=False)`. With no identified benchmark the appendix returns `None` for the whole block, so the real symptom was stronger: **the appendix had no benchmark section and no departure line at all**. The disclaimer only appears on a path that had already identified a benchmark. The demo below shows the true before state.

## What changed, in the engine

`POST /cases/{id}/identify/benchmark` used to record only the benchmark fields and mark the requirement varied. It now also adds the article to `case.provisions`, writes its citation fact, rebuilds Section C, records the article decision and applies the applicant's reason to the varied requirement. It returns the rows it wrote, so the client shows the new Section C row without another read.

Both that route and the code-check card now go through one helper, `record_departure`, in `engine/identify/decisions.py`. A departure therefore leaves identical state whichever route recorded it.

The alternative was to have the browser call the decision route and then the benchmark route, in that order. That needs two compare-and-swap writes per answer, leaves a window where the Section C row exists without the departure, and silently loses the applicant's reason if the calls run the other way round, because the decision route overwrites it with the canned sentence. One call avoids all three.

## What changed, in the browser

The deck builds a `departure` card for the first card answered Yes while the stored benchmark is unconfirmed. The card carries the article's citation chip, a two-line field and Continue. Saving calls `confirmDeparture` in the store, which posts the benchmark route, acknowledges the case version, updates the local Section C row and pushes the returned result into the shared case extras so the card disappears.

`web/src/calm/caseExtras.ts` now reads `GET /cases/{id}/identify` alongside the rule and checklist reads. That is the one source the deck, Review and the appendix gate can share for the benchmark state.

## Evidence

A scripted run drove the real routes and rendered the real appendix PDF against a synthetic code database.

Before the fix, with the card answered Yes:

```
POST decision -> 200
benchmark.identified=False departure_status='none'
appendix says 'Benchmark acceptable solution': False
appendix states the departure: False
```

After one call to the benchmark route:

```
POST identify/benchmark -> 200
benchmark.identified=True status='confirmed'
departure stored='Doors open 100 mm wider than the sentence allows, with a 900 mm clear width.'
section C rows written by the call: ['9.1.1.1.(1)']
case provisions=['9.1.1.1.'] section_c=['9.1.1.1.(1)']
appendix says 'Benchmark acceptable solution': True
appendix states the departure: True
appendix labels it confirmed: True
```

The appendix text gained this block:

```
Benchmark acceptable solution
Benchmark: NBC(AE) 2023 p2, Div B, Sentence 9.1.1.1.(1)
Quoted sentence: An egress window must open.
Departure: Doors open 100 mm wider than the sentence allows, with a 900 mm clear width. (confirmed by the applicant)
```

Checks run here. The identify service tests pass (144 tests), including the extended benchmark case, plus a new unit test for the shared helper. Web typecheck, 570 unit tests and the production build pass. `evals/ui-artifacts/smoke.mjs` passes the P0 contract checks. The full engine, code-database and eval suite runs in CI and locally in parallel; its count is recorded on the pull request.

The demo output and both draft exports are kept with the repository's other demo evidence.

- `docs/demo/benchmark-departure-20261028-before.pdf`
- `docs/demo/benchmark-departure-20261028-after.pdf`
- `docs/demo/benchmark-departure-20261028-output.txt`

The run used a synthetic Division B source and a draft export, so the pages carry the draft stamp. No screen recording accompanies this change. The port 3000 development server belongs to another worktree and was left running, and this checkout has no code database, so the card itself was verified by typecheck, the deck unit test and the build rather than in a browser.

## What this leaves out

- **`journey.departure`** still stores the answer to "What will be different?" and is still read by nothing. Deleting it means changing the route card, which is a separate change.
- **One benchmark per application.** The record is singular by design, and the deck asks on the first Yes card. Answering Yes on several cards asks again for the newest one, and the appendix names the most recent confirmed departure while every departed article stays a Section C row.
- **The requirement-ledger gate** still rejects a `varied` include without a confirmed benchmark. That is now reachable rather than bypassed, and it needs no change.
