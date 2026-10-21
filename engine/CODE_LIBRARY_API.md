# Code library API handoff

Implemented on `api/code-library`, based on `5ea9297`, in the `code-library-api` checkout.
All citations use the existing NBC(AE) 2023 p2 lookup. Rankings are candidate relevance,
not technical compliance or professional approval.

| Endpoint | Behavior |
| --- | --- |
| `GET /code/toc?division=B` | Cached tree in `sort_key` order; A/C also supported. Current DB has no part headings in provisions/docs/meta, so part titles are null. Stored part-level provision headings are supported. |
| `GET /code/{id}/context?division=B` | Source path, citation, Section C objectives/functions/intent, attribution status, note excerpts (320 characters), existing full dotted references, and up to 20 backlinks in code order. Article attribution/intent is the union of its Section C sentence rows. Missing/invalid IDs use the existing lookup's 404/400 responses. |
| `POST /cases/{id}/relevance` | Explicit action: existing `identify()` screens every Division B article and reranks the top 60 with `jev-1.13.0`. No BM25 fallback. |
| `GET /cases/{id}/relevance` | Stored record only, with staleness recomputed; 404 `not scored` when absent. |

Existing HTTP middleware still adds `meta.notice` and NRC links to code prose. Arrays on
existing routes such as `/section-c` remain wrapped in `items`.

The latest `project.description` fact supplies the proposal and its exact UTF-8 SHA-256.
An empty replacement wins and POST returns 409 `Describe your project first`.
The existing identify path has no intake-answer prose composer, so this endpoint sends
only the description. GET never performs scoring. Successful relevance responses use
`Cache-Control: no-store`.

`display_probabilities()` in `engine/relevance.py` owns the display policy: rerank value
when present (including zero), otherwise screen value. Bands come only from
`engine/identify/relevance_bands.json`; current values are x=0.3, y=0.85,
`status=benchmark-derived, not field-calibrated` (see `docs/research/relevance-bands.md`).
The smoke receipt below was recorded with the earlier placeholders x=0.2, y=0.6.
Changing that file needs no scoring-policy edit.

## Storage and gates

A typed optional `Case.relevance` field uses the existing JSON payload in both SQLite
and Postgres. No migration or duplicate backend methods were needed. Finishing a run
re-reads the case and uses versioned `put()` with up to five conflict retries; concurrent
facts/description edits survive, changed descriptions mark the result stale, and deleted
or expired cases are not recreated. Other case fields and confirmed provision selections
are preserved. The generic Case response now also includes `relevance` (null until scored).

Live HTTP scoring requires `BATATIS_LIVE=1` and a TypeSafe key resolved through the existing
jevkit keystore (environment, OS keychain, then credentials file). It does not require an
unrelated OpenAI key. Missing credentials, a disabled switch, and provider failures return
503 `Relevance scoring unavailable`; technical categories appear only in logs. Provider
bodies, descriptions, and credentials are not logged.

`llm_gate.SlidingWindow` supplies a per-IP limit (`BATATIS_RELEVANCE_RATE_LIMIT`, default 2;
`BATATIS_RELEVANCE_RATE_WINDOW_SECONDS`, default 600) and a shared daily run cap
(`BATATIS_RELEVANCE_DAILY_RUNS`, default 20, resets at UTC midnight). Provider failures
consume a run. Limits return 429 with `Retry-After`. These gates and the same-case lock
are per process and reset on restart; no distributed cap/lock is claimed. Jev's run budget
is separate from the existing OpenAI USD/token ledger because no Jev dollar price is assumed.
Concurrent POSTs for one case return 409 `Relevance scoring already in progress` with
`Retry-After: 1`; other cases can score independently. `create_app(relevance_judge_factory=...)`
accepts factories for `Judge(ask=fake_ask)`, so acceptance tests use no network.

## Verification

The requested Python 3.14 venv works with `-I` after adding pytest's `-o pythonpath=.`;
without it, the unchanged base cannot import `engine` during collection.

```sh
BATATIS_CODEDB=<path-to>/codedb.sqlite \
  /private/tmp/batatis-deploy-venv-20261020/bin/python -I -m pytest engine/tests -q -o pythonpath=.
```

Focused checks: **56 passed, 3 skipped** (live Jev, live verifier, optional Postgres).
Full suite: **647 passed, 217 skipped, 15 failed**. Untouched base `5ea9297`:
**613 passed, 216 skipped, 15 failed**. The same 15 failure node IDs occur in both runs;
there are no new failures. New endpoint tests add 34 passes and one optional Postgres skip.
`TEST_DATABASE_URL` was absent; real Postgres operation is not live-verified.
Schema/type generation and both staleness checks passed using `engine/schema_export.py`
and `web/scripts/gen-types.mjs`. Only `web/src/api/engine.schema.json` and
`web/src/api/types.gen.ts` were changed under web.

The pre-existing failures concern evidence withdrawal/acknowledgments, version retention,
privacy/docs drift, and Vercel configuration. Exact IDs and full output are in the local
receipts `/tmp/code-library-test-comparison.json`, `/tmp/code-library-base-tests.log`,
and `/tmp/code-library-engine-tests.log`. They remain outside this implementation scope.

## Single live smoke receipt (2026-10-20)

The server ran on 127.0.0.1:8030 with `BATATIS_CASES=/tmp/code-library-cases.json`,
`BATATIS_LIVE=1`, and `SSL_CERT_FILE=/etc/ssl/cert.pem`. The case description fact was
posted through the public facts route using the same field and provenance as the web:

> We make NorthCore CX, a foil-faced rigid board that goes on the outside of the studs as continuous insulation and replaces the housewrap. We want builders to use it on houses and townhomes anywhere in Alberta.

One relevance POST returned HTTP 200 in **8.993 seconds**: **2,080 articles**, **60 reranked**, **21 outbound HTTP requests**, zero transport failures. The stored GET exactly matched and made no provider requests. The server was stopped and port 8030 has no listener.

Placeholder band counts: **1,896** low (p < 0.2), **144** middle (0.2 <= p < 0.6), **40** high (p >= 0.6). These thresholds remain uncalibrated.

| Article | Database title | Display p |
| --- | --- | ---: |
| 9.27.3.4. | Insulating Sheathing in lieu of Sheathing Membrane | 0.88 |
| 9.25.1.1. | Scope and Application | 0.85 |
| 9.25.3.3. | Continuity of the Air Barrier System | 0.85 |
| 9.27.2.1. | Minimizing and Preventing Ingress and Damage | 0.85 |
| 9.25.3.1. | Required Barrier to Air Leakage | 0.84 |
| 9.36.2.10. | Construction of Air Barrier Details | 0.83 |
| 5.6.1.1. | Required Protection from Precipitation | 0.82 |
| 9.27.3.3. | Required Sheathing Membrane and Installation | 0.82 |
| 5.1.4.1. | Structural and Environmental Loads | 0.81 |
| 5.3.1.1. | Required Resistance to Heat Transfer | 0.80 |

| Requested article | Display p | High with placeholder y=0.6? |
| --- | ---: | --- |
| 9.27.3.2. | 0.47 (not reranked) | No |
| 9.25.5.2. | 0.76 | Yes |
| 9.23.17.3. | 0.71 | Yes |
| 9.27.3.4. | 0.88 | Yes |

`9.27.3.2.` missed the top-60 rerank set and remains in the middle band. This is a recorded
ranking result, not corrected by a heuristic. Threshold/ranking calibration remains with
the benchmark owner. One local live run does not establish calibration or deployment acceptance.

Raw fixture: `/tmp/code-library-live-relevance.json`. Additional local receipts:
`/tmp/code-library-live-summary.json`, `/tmp/code-library-live-requests.json`, and
`/tmp/code-library-live-server.log`. No keys are included.

## Files and methods

New implementation: `engine/code_library.py`, `engine/relevance.py`,
`engine/relevance_models.py`, `engine/routes_relevance.py`, and the bands JSON.
Integration: `engine/api.py`, `engine/models.py`, `engine/llm_gate.py`,
`engine/identify/screen.py` (safe failure-cause propagation), and `engine/schema_export.py`.
Tests: `engine/tests/test_code_library.py` and `engine/tests/test_relevance.py`.
The only web changes are the two generated API artifacts listed above.

Methods used: T3 workflow feature routing; pstack `poteto-mode/playbooks/feature.md`
(scoped, verifiable commits); Batatis hackathon and variance-workflow skills
(source-backed attribution and administrative boundaries); Matt Pocock `code-review`
(separate local standards/spec passes, adapted to the explicit no-delegation instruction).
The workflow maintenance check found existing global model-preference drift and left it
untouched. This backend work has no visual UI surface; no screenshot or demo was staged.
No subagents, other branch/worktree edits, pushes, or PRs were used.
