# Deploying Batatis

One Vercel project serves the Vite app in `web/` and the FastAPI engine. Public `/api/*` is rewritten to the engine. Everything else goes to the static app. Vercel Services is in beta on all plans.

This repository does not deploy or create accounts. A person with the existing Vercel project connects the Git repository and sets the variables below. Do not commit the NRC PDF, `codedb/build/codedb.sqlite`, `.env`, or uploads.

## What the build does

`vercel.json` builds two services from one project:

- `web` — Vite, root `web/`, output `web/dist`. `VITE_API_BASE` defaults to `/api`.
- `engine` — FastAPI entrypoint `engine.api:app`. Its build runs `scripts/vercel_build_engine.sh`.

That script runs `scripts/build_codedb.sh` when that file exists (`backend/codedb-repro`). Otherwise it runs `scripts/fetch_sources.py` and then `python -m codedb build`. The build fails if `codedb/build/codedb.sqlite` is missing. The sqlite is pulled into the engine function with `includeFiles`. It is not part of the web output, and no static route serves it. Tests, evals, fixtures, and `reference/` (the PDFs) are excluded from the function bundle.

The engine also accepts paths with or without the `/api` prefix, so a service rewrite that strips `/api` and a request that still has the prefix both work.

The engine runtime is Python 3.12, the same version CI installs. Dependencies come from `engine/requirements.txt` and `codedb/requirements.txt`: FastAPI, uvicorn, pydantic, httpx, psycopg with the binary wheel, pypdf, pypdfium2, and reportlab. No extra system packages are required. `psycopg[binary]` bundles libpq, and the PDF fetch uses `curl`, which is already on the build image.

Every response sets `X-Robots-Tag: noindex, nofollow`. `web/public/robots.txt` disallows every path.

## Code database: official URL or a private object

The builder needs the NBC(AE) 2023 2nd-printing PDF and the NBC 2020 intent-statements PDF. Both are sha256-checked. A mismatch is deleted. Nothing is committed.

1. **Official publications (default).** The build downloads from `nrc-publications.canada.ca` with retries (`curl --retry`). Use this when the Vercel builder can reach that host.
2. **Private object (when the builder cannot reach NRC).** Upload each PDF once to a private Vercel Blob or a Neon object. The object must not be publicly readable. Put the signed or otherwise authenticated URLs in:
   - `CODEDB_PDF_URL` — NBC(AE) PDF
   - `CODEDB_INTENT_PDF_URL` — intent-statements PDF

   The build still tries the official URL first. Set `CODEDB_SKIP_OFFICIAL=1` to skip the NRC host when both private URLs are set. A private URL is never printed in the build log. If both the official download and the private URL fail, or a file is not sha256-checked, the engine build fails and the deployment does not go out.

Do not work around a failed download by committing the PDF or the sqlite.

The same build downloads the Safety Codes Council variance form from `https://ebs.safetycodes.ab.ca/documents/webdocs/PI/Variance%20Template%20final.pdf`. The pinned sha256 is `f44640ca005c957c11a2387d2768fffc35ef93c97125dcca37436fcc0b9afc1d` (334580 bytes), the same digest as `engine/export/field_maps/scc_2026-10.json`. The file lands at `codedb/build/SCC-Variance-Form.pdf` and is included in the engine bundle. It is not committed. If that host is unreachable, set `SCC_FORM_URL` to a private object. `CODEDB_SKIP_OFFICIAL=1` skips the official URL when the private one is set. A missing form at runtime makes `POST /cases/{id}/export` return 503 with `SCC variance form not found`. The server log says the export is unavailable on this deployment. A form whose sha256 does not match the field map returns 500 with `The SCC variance form could not be exported.` The response does not include the form path.

## Environment variables

Set these on the Vercel project for Preview and Production. Leave the project Root Directory at the repository root so both services build. Do not set a dashboard Output Directory that would override `web/dist`.

| Variable | Where | Purpose |
| --- | --- | --- |
| `BATATIS_STORE` | engine runtime | `file` locally (default). `postgres` on Vercel. If `VERCEL` is set and this is unset or `file`, the process refuses to start. |
| `DATABASE_URL` | engine runtime | Neon (or any Postgres) URL. `sslmode=require` is added when the URL omits it. |
| `BATATIS_LIVE` | engine runtime | Unset or anything other than `1` keeps the offline path. Live calls also need `OPENAI_API_KEY`. |
| `OPENAI_API_KEY` | engine runtime, sensitive | Server only. Do not use a `VITE_` name. The process never logs the value. |
| `BATATIS_DAILY_SPEND_CAP_USD` | engine runtime | Default `5`. Over the cap, model calls return the offline path with `source: "offline-cap"`. On Vercel this cap requires `BATATIS_STORE=postgres`. The per-instance memory ledger is not used there: if `VERCEL` is set and the store is not postgres, live calls stay on `offline-cap` and do not spend from memory. Off Vercel, the file store keeps the cap in memory for that process. |
| `BATATIS_LLM_RATE_LIMIT` | engine runtime | Default `20` live model calls per IP per window. The window is in memory on that engine instance. |
| `BATATIS_LLM_RATE_WINDOW_SECONDS` | engine runtime | Default `600`. |
| `BATATIS_SEARCH_RATE_LIMIT` | engine runtime | Default `60` searches per IP per window, per engine instance. `GET /code/search` and `GET /ccmc/search` share this window. The client IP is the first hop of `x-vercel-forwarded-for`, then `X-Forwarded-For`, then the peer address. |
| `BATATIS_SEARCH_RATE_WINDOW_SECONDS` | engine runtime | Default `600` (10 minutes). A 429 body is `Search limit reached; try again in N seconds` and sets `Retry-After`. The search window and the model window are each an in-memory `SlidingWindow` on one process. They are not a cap shared across instances. The shared cap is the Postgres daily spend ledger. |
| `BATATIS_SCC_FORM` | engine runtime | Optional filesystem path to the SCC variance form. The build's copy is `codedb/build/SCC-Variance-Form.pdf`. |
| `SCC_FORM_URL` | engine build | Optional private URL for the SCC variance form. Still sha256-checked. |
| `CODEDB_PDF_URL` | engine build | Optional private URL for the NBC(AE) PDF. |
| `CODEDB_INTENT_PDF_URL` | engine build | Optional private URL for the intent PDF. |
| `CODEDB_SKIP_OFFICIAL` | engine build | `1` skips the NRC host when the private URL for that file is set. |
| `VITE_API_BASE` | web build | Optional. Defaults to `/api`. |
| `TEST_DATABASE_URL` | engine CI | Set on the engine job to the `postgres:16` service. Omit locally to skip the Postgres store test. |

Local file runs ignore `DATABASE_URL`. Uploaded PDF bytes go in `case_files` (Postgres `bytea`, or sqlite blob locally), capped at 4 MB. A larger PDF is HTTP 413 with `{"detail": "PDF too large: the limit is 4 MB. Try compressing the file or splitting it."}`.

Every JSON response returns code text in full, with its citation and the NRC publication link. Search still returns at most 20 hits. No route serves `codedb.sqlite`. The exported PDF uses the same rule: form cells carry provision ids and objective/function codes, and the appendix carries citations, objective and functional-statement titles, application notes, the full provision text, and NBC 2020 intent statements and notes, each with the NRC link.

Do not upload personal information. In live mode, text you enter is sent to OpenAI (US) for processing and is retained by OpenAI under its API data policy (https://openai.com/policies/api-data-usage-policies); Batatis deletes its own stored case data and files after 7 days or on request. That sentence is `meta.notice` and the default `X-Batatis-Notice` header; a route-specific header is preserved. Cases and their files expire 7 days after `created_at`, or sooner on `DELETE /cases/{case_id}`. The sqlite store and Neon Postgres both remove expired cases and files on access, including between sweeps. Case create and the per-request sweep run the bulk purge at most once every 10 minutes per instance. `python -m engine.retention` runs it immediately, and so does the Hobby cron `GET /api/retention/purge` (`0 6 * * *`, once a day). A second purge deletes nothing. A failed purge returns `503` detail `case purge failed`, with no connection string in the response or log.

## Preview

Push an integration branch. The connected Vercel project builds a Preview deployment of both services. Measure it with:

```sh
scripts/e2e_smoke.sh https://<preview-host>/api
```

The script prints one latency line per request, twice (cold, then warm):

```text
cold POST /cases 201 1.204s
cold GET /cases/<id> 200 0.080s
cold GET /code/search?q=egress&limit=5 200 0.110s
warm POST /cases 201 0.040s
```

`BASE_URL` may be the first argument or the environment variable. Locally that is `http://127.0.0.1:8000` (no `/api` prefix). On Vercel include `/api`.

## Production

Production tracks `dev`, and only after #12 and `backend/case-api` have merged there. This branch is the deploy shape. It is not the production promotion by itself.

`backend/case-api` is also making `CaseStore` writes atomic. The overlap is `put(..., expected_version=)` and `VersionConflict` (retry inside `add_fact`, HTTP 409 if the retry is exhausted). Keep one optimistic-update implementation when the branches merge.

```text
#12 owns engine/identify; this branch does not change it.
Call engine.llm_gate.authorize before a provider request and record after with the actual token counts.
Keep the citation and the NRC publication link on code quotes. Do not shorten them.
Live only when BATATIS_LIVE=1 and OPENAI_API_KEY are both set; otherwise stay offline and do not contact a provider.
```

## Accounts and plan limits

The existing Vercel project uses the dedicated free Neon resource `batatis-db`
(`free_v3`). Keep `BATATIS_STORE=postgres` and its private `DATABASE_URL`
configured. Hosted startup refuses a missing Postgres configuration; there is
no temporary-disk fallback. Keep `BATATIS_LIVE=0` and the OpenAI key unset until
the US$20 total cap in #41 is integrated and passes its gate. The daily ledger
in this branch does not satisfy that gate.

Configure an independent, random server-only `CRON_SECRET` for the scheduled
retention purge (at least 16 characters). Vercel sends it as
`Authorization: Bearer <CRON_SECRET>`; see
[Securing cron jobs](https://vercel.com/docs/cron-jobs/manage-cron-jobs#securing-cron-jobs).
Without that secret a hosted purge returns `503` detail
`retention purge not configured`; a missing or incorrect bearer token returns
`401` detail `unauthorized`. Neither response triggers a bulk purge. Responses
are not cached, and tokens are never logged. The operator CLI remains available
as `python -m engine.retention`. Local HTTP runs require bearer auth when
`CRON_SECRET` is set, and allow unauthenticated purges when it is unset.

Other prerequisites:

- An OpenAI key, only if live model calls are turned on. Offline works without one.
- A private Blob or Neon object for the two PDFs, only if the Vercel builder cannot reach `nrc-publications.canada.ca`.

The Vercel project is on the Hobby plan. Vercel Services is in beta on all plans, including Hobby. The engine function includes a sqlite on the order of 26 MB plus Python dependencies. If the Hobby plan's function bundle limit rejects that, the limit is the Hobby plan's, and the fix is not to commit the database. Confirm the limit in the Vercel dashboard before the first production build.
