# Live OpenAI spending gate

The key and live flag stay off until the parent approves the integrated #24/#38/#41 revision. This change does not deploy or activate a provider. #38 owns service layout, rewrites, headers, and Vercel configuration; #24 owns the canonical privacy notice, retention, and deletion lifecycle.

## Configuration

The lifetime allowance is **US$20 total**, with no daily cap or reset. `BATATIS_TOTAL_BUDGET_USD` defaults to `20` only when unset. A finite value from `0` through `20` can lower the allowance. Blank, negative, nonfinite, malformed, or higher values refuse calls. `BATATIS_DAILY_SPEND_CAP_USD` is ignored.

Live calls require both `BATATIS_LIVE=1` and a server-only `OPENAI_API_KEY`. Neither a key nor a database URL is logged or returned. Never use a `VITE_` key. `GET /status/budget` reports configuration/readability, not permission to activate the key.

The shared ledger is `spend_ledger` in Postgres, selected by `DATABASE_URL`, then `POSTGRES_URL`. `postgres://` is normalized to `postgresql://`; `sslmode=require` is added when no sslmode is specified. Hosted/Vercel mode refuses SQLite URLs. Explicit SQLite files are local test doubles; the code database is a separate read-only file and is never a ledger.

A missing/unavailable ledger, invalid stored amounts/status, invalid pricing/configuration, or insufficient allowance refuses the provider before dispatch. Malformed legacy TEXT money is rejected before SQL can coerce it to zero. Reservations and charges round **up** to microdollars; the available cap rounds **down**. Postgres explicitly uses READ COMMITTED and takes an advisory transaction lock before validating the ledger and conditionally inserting. Settlement uses the same lock. Concurrent instances share settled costs and open reservations.

## The one provider request

`openai_chat_json` in `engine/spend.py` owns the production OpenAI transport. Callers supply text messages, a known model, a supported JSON response format, and an output limit. There is no arbitrary client callback. The approved GPT-4.1/mini names resolve to their dated `2025-04-14` snapshots; the request explicitly sets `service_tier=default`, `n=1`, `store=false`, and `max_completion_tokens` (1–32,768). Tools, images/audio, recursive/remote schema references, and unknown models/providers are refused.

The input reservation counts UTF-8 bytes of the **complete serialized request**, including the response schema, plus 4,096 framing tokens and 64 per message. Requests whose bound plus output exceeds the model context window are refused. This intentionally over-reserves rather than using English character averages or an incomplete tokenizer count. Standard text rates include cached input at the full input price. Sources checked 2026-10-20: [GPT-4.1 mini](https://developers.openai.com/api/docs/models/gpt-4.1-mini), [GPT-4.1](https://developers.openai.com/api/docs/models/gpt-4.1), [Chat Completions request limits and tier](https://developers.openai.com/api/reference/resources/chat/subresources/completions/methods/create).

A durable reservation precedes one HTTP attempt. The urllib transport has no SDK/HTTP retries and refuses redirects. Every timeout, HTTP error, dropped connection, cancellation, malformed/refused response, model/tier mismatch, or failed settlement conservatively keeps the reservation. A network exception is never proof that a request was not billed. A later retry needs its own reservation. Missing or invalid usage consumes the full estimate. Valid usage settles to the upward-rounded actual text cost. A reported cost above the estimate is recorded in full and makes subsequent ledger validation refuse further calls; it is never silently clamped. Such a response violates the provider request bounds and requires investigation before activation can continue.

Anthropic and Jev/TypeSafe/OpenRouter are disabled in both live and hosted execution, including the Jev transport. They are not covered by this OpenAI ledger. Offline research adapters remain separate. CI scans engine source for ungated OpenAI construction/API calls.

`POST /identify` reranks only BM25 candidate IDs that exist in the local Division B corpus. Its prompt contains the query and bounded corpus snippets; its JSON schema restricts returned IDs. The response is accepted only when complete, unique, and grounded in those candidates. A valid result has `label: model output, not verified`. Provider/validation failures return HTTP 200 with `label: keyword search, no AI`, a notice, and keyword hits. An unavailable corpus causes no paid call. This is candidate reranking, not the full #12 identification/verification pipeline. Completeness and Section D currently use rules, not model calls; future callers must use the same spending boundary.

Per-IP windows remain best-effort, in memory per instance: `/identify` defaults to 20/600 seconds and `/ccmc/search` to 60/600 seconds. Their `BATATIS_LLM_RATE_*` and `BATATIS_SEARCH_RATE_*` settings do not authorize spend or replace the shared ledger. Over the window, routes return 429 with `Retry-After`.

## Reconciling an uncertain reservation

A stranded `reserved` row remains counted forever, including across deploys and dates. **Never release it based on age or a timeout alone. Never truncate the ledger or delete settled rows.** Billing evidence for that specific attempt must establish no charge, or a smaller verified actual charge, before a human reconciles it. Otherwise retain the full reservation.

Inspect only the needed rows in a trusted database session:

```sql
SELECT id, ts, route, model, est_usd, status
FROM spend_ledger
WHERE status = 'reserved';
```

Only after provider billing evidence establishes **zero charge for one specific row**, replace the example ID and release that row:

```sql
UPDATE spend_ledger
SET status = 'released', actual_usd = NULL
WHERE status = 'reserved' AND id = 123
RETURNING id;
```

For a verified nonzero charge, retain the reservation until a reviewed reconciliation records the conservatively rounded amount. A failed/ambiguous database commit must be reread before trying again. Do not run a bulk or age-based sweep.

## Verification and integration

Offline checks fake the provider at the transport boundary. Real Postgres tests require explicit `BATATIS_TEST_POSTGRES_URL`; every test creates a unique schema with its own search_path and drops only that schema. `DATABASE_URL` alone never authorizes destructive test setup. CI supplies an isolated postgres:16 service, exercises five simultaneous connections (including a REPEATABLE READ connection default), concurrent first-use DDL, lost commit acknowledgements, failed settlements, corrupted ledger values, and timeouts. A connection-outage probe also runs without Postgres. Do not point a test at shared case/spend tables.

Key activation still requires the parent's same-head independent review, green affected CI, integrated #24 privacy/retention and #38 deployment verification, and provider acceptance evidence under the spending gate. Local fakes and Postgres accounting tests do not establish a live provider result.
