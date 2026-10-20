# Sync regressions

These checks use the production reducer, sync client, CaseProvider and real engine
HTTP routes with a disposable SQLite store. They never authorize provider calls.

From `web/`, with an engine-ready Python environment and a built code database:

```sh
BATATIS_CODEDB=/absolute/path/to/codedb.sqlite python3 scripts/test-sync.py
```

The runner strips provider credentials, sets `BATATIS_LIVE=0`, blocks external
connections from the engine and removes its temporary case database on exit.
It runs `tests/sync.integration.mts` using the existing Node TypeScript loader.
`npm run test:sync` invokes the same runner with `python3` on PATH.

For mounted React provider regressions, also start the usual Vite dev server on
an unused loopback port, and install/use the repository UI smoke's
`playwright-core` dependency and browser. Then:

```sh
BATATIS_CODEDB=/absolute/path/to/codedb.sqlite \
SYNC_WEB_BASE=http://127.0.0.1:15126 \
python3 scripts/test-sync.py --browser
```

`CHROME_PATH` optionally selects the browser executable. The test harness rewrites
its API requests to the disposable engine; it does not use the Vite server's
configured API. It mounts the actual CaseProvider in `provider.html`, delays real
requests/responses and inspects persisted facts and provider state. This harness
is a separate Vite development entry and is not included in the production build.

The regressions cover withdrawn professional/process/detail answers, retries,
returning to a previous value, overlapping saves, creation/jurisdiction reset
races, stale provider completions, and evidence replacement/deletion generations.
They do not certify PostgreSQL, provider execution, deployment, official export
eligibility, or the separately queued explicit-check and guided-flow UX changes.
