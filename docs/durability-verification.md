# Dependable saves and recoverable jobs: verification

Backend review revision: `ef6364ff` (base `661ab7e1`); timing run: `9d353442`.
The final frontend revision and independent review receipts belong in the PR's
verification comment. Local checks use synthetic
records, offline algorithms, SQLite and a private UTF8 PostgreSQL 17 database.
They do not establish production or live-provider behavior.

## Save measurements

The request/write reduction is verified. Browser end-to-end latency remains
unmeasured because the permitted app ports belong to another checkout and the
user explicitly requested that its servers remain running. No alternate app
ports or substitute screenshots were used.

Before implementation, five runs through the real FastAPI HTTP stack saved ten
changed answers among 100 existing facts: median 34.418 ms, range 33.258–55.505 ms,
ten requests and ten case updates. All 50 answers were read back correctly.

The final comparison alternates the retained per-fact endpoint with the batched
draft endpoint on the same integrated source, five runs per side:

| Measurement for ten changed answers | Per-fact endpoint | Draft PATCH |
| --- | ---: | ---: |
| HTTP requests | 10 | 1 |
| Case UPDATE statements | 10 | 1 |
| Traced UPDATE statement bytes | 289,161 | 3,715 |
| Median elapsed time | 62.115 ms | 13.432 ms |
| Observed range | 57.186–63.456 ms | 12.400–14.081 ms |
| Answers read back correctly | 50/50 | 50/50 |
| Failed HTTP responses | 0 | 0 |

Reproduce with an engine-ready Python:

```sh
BATATIS_JOBS_WORKER=0 BATATIS_LIVE=0 \
  python scripts/measure_durable_saves.py --mode compare --rounds 5
```

The transport is in-process FastAPI TestClient HTTP, with a disposable SQLite
database, warmed HTTP stack and no provider calls. Timing includes HTTP dispatch,
validation and transactions, with SQL tracing enabled on both sides. It excludes
browser rendering/debounce, network latency, uploads and AI execution. A separate
profile identified repeated HTTP/thread dispatch and full-case validation in the
legacy path. This is a shared machine (15 logical CPUs; observed load 6.87), so
the initial and final timings are not comparable speedup claims. SQL statement
bytes are neither disk bytes nor PostgreSQL WAL savings. The application now
uses one saved Case acknowledgement without the former derived-read fanout.

## Checks and remaining evidence

- Web gate after merging `main` and the independent frontend review fixes: 436 tests
  passed, none skipped (`main` removed retired surfaces and their tests), with
  `PLAYWRIGHT_MODULE` pointing at an installed playwright-core; typecheck passed.
  Mounted Chromium regressions use mocked HTTP, including newer typing during
  saves, failed flushes, refresh/rejoin, attachment bindings, retries, typing
  while sign out waits, conflicting edits from two devices, edits made during
  job acceptance, jobs started on another device and failed cancellation.
- Independent frontend review (Claude Opus 5.5; Codex was out of quota) found three
  issues, each now covered by a regression that fails on the unfixed code: a visit
  reset was dropped while editing was paused, a job finishing during the pause was
  never applied, and conflict review compared every saved document revision with
  only the latest, so it reported untouched documents as changed elsewhere.
- Full gate after merging `main` at 544b1083 (requirement identification): web 436
  passed, none skipped; engine with a private PostgreSQL 17 (`TEST_DATABASE_URL`
  without `sslmode`, as in CI) 4140 passed, 305 skipped for other environment
  gates; desktop 227 passed, one installed-runtime check skipped.
- CI's engine job has no web packages: `openCase` now loads without React, and the
  job worker tests name libpq's TLS mode for their subprocesses.
- Desktop gate: 227 tests passed; one installed-runtime check skipped because
  the pinned native Codex runtime is not prepared. Typecheck and main/preload
  build passed.
- Independent backend follow-up: 132 tests passed with no skips on SQLite and
  PostgreSQL, plus four model-boundary assertions. No reachable backend findings
  remained at `ef6364ff`. The final full-gate and frontend review results belong
  in the PR verification comment.
- Additional owned PostgreSQL/source checks: 197 passed. One existing voice-cap
  fixture failed because it expects an AI reservation without granting access.
  The identical failure was reproduced from the original `661ab7e1` source;
  the access policy, voice gate and test are unchanged by this branch.
- The local verification script could not run its optional secrets scan because
  `gitleaks` is unavailable. CI remains responsible for that scan.
- Real-app browser before/after measurements, UI smoke, screenshots and inspected
  recording remain blocked by port ownership. A visual PR must remain awaiting
  required demo evidence under `docs/agents/git-workflow.md`.
- No external worker infrastructure or live provider was deployed or exercised.
  Vercel needs the supervised worker described in [the job contract](api/jobs.md).

When ports are available, use `scripts/local-app.sh`, then exercise saves during
slow reading, refresh/rejoin, switching applications and devices, failed saves,
New application, attachment edits, legacy answers, retry/cancel and sign out.
Check the network request count, stored answer values and header acknowledgement
together. Run `node evals/ui-artifacts/smoke.mjs`, capture and inspect the actual
screenshots and recording, and attach reviewer-accessible media with the tested
commit SHA before marking the PR ready.
