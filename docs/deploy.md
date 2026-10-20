# Deploy notes for the live OpenAI spend cap

Service layout and `vercel.json` are a separate change. This page is the spend cap those functions have to have before a key is turned on.

The engine on Vercel Hobby is a set of stateless functions. They do not share memory, so the running total cannot live in the process. It is one Postgres table, `spend_ledger`, on Neon. Neon's free tier is enough for that table: one row per keyed call. The code database is a separate read-only sqlite file. The ledger never opens `codedb.sqlite`. Pointing `DATABASE_URL` at that file is refused, and a read-only bundle stays read-only.

## Environment

Set these on the Vercel project for the engine runtime. Do not commit values. `OPENAI_API_KEY` is set in Vercel only after this cap is on `dev`. Until then leave `BATATIS_LIVE` unset. Offline mode does not call a model and does not need a key.

| Variable | Purpose |
| --- | --- |
| `BATATIS_LIVE` | `1` turns live mode on. Any other value, including unset, stays offline. Live mode also needs `OPENAI_API_KEY`. |
| `OPENAI_API_KEY` | Server only. Do not use a `VITE_` name. The process does not log it, and `GET /status/budget` does not return it. |
| `BATATIS_TOTAL_BUDGET_USD` | Total cap in USD for every keyed OpenAI call. Default `20` when unset. There is no daily cap. |
| `DATABASE_URL` | Neon (or any Postgres) URL for the spend ledger. Preferred over `POSTGRES_URL`. A `postgres://` scheme is rewritten to `postgresql://`. `sslmode=require` is added when the URL does not already set `sslmode`. |
| `POSTGRES_URL` | Used only when `DATABASE_URL` is empty. Same rewriting rules. |

`BATATIS_DAILY_SPEND_CAP_USD` is ignored if it is set. The earlier $5-a-day cap is not used. The cap is one total, default 20, stored in Postgres.

`POST /identify` counts toward `BATATIS_LLM_RATE_LIMIT` (default 20) per IP per `BATATIS_LLM_RATE_WINDOW_SECONDS` (default 600). `GET /ccmc/search` counts toward `BATATIS_SEARCH_RATE_LIMIT` (default 60) per IP per `BATATIS_SEARCH_RATE_WINDOW_SECONDS` (default 600). The client IP is the first hop of `x-vercel-forwarded-for`, then `X-Forwarded-For`, then the peer address. A request over the limit is HTTP 429 with `Retry-After` and a detail that says which limit was reached. Both windows are in memory on one process. They are per instance unless a later change stores them in Postgres. They are not the spend cap.

`BATATIS_LLM_PROVIDER=anthropic` is refused when `BATATIS_LIVE=1`. Live calls are OpenAI only. The only request function is `openai_chat_json` in `engine/spend.py`. It estimates input tokens from the messages (tiktoken `o200k_base` when that package is installed, otherwise `ceil(character_count / 3)`, which reserves high), always sends `max_completion_tokens`, and reserves the input rate times that estimate plus the output rate times `max_completion_tokens`.

Over the spend cap, or when the ledger cannot be checked, `POST /identify` stays HTTP 200. `label` is `keyword search, no AI`, `notice` is set, and `hits` are the BM25 list. A provider error also stays HTTP 200: the reservation is released, `label` is `API fallback`, and `hits` are that same BM25 list. A live model result uses `label` `model output, not verified` and does not carry an accuracy or score field.

## Releasing a stuck reservation

A row left at `reserved` still counts against the cap. `GET /status/budget` includes it in `remaining_usd`. That happens when a process stops after the insert and before settle or release. Release it in the Neon SQL editor, or with `psql`, after listing the open rows:

```sql
SELECT id, ts, route, model, est_usd, status
FROM spend_ledger
WHERE status = 'reserved';
```

Release one row by id:

```sql
UPDATE spend_ledger
SET status = 'released', actual_usd = NULL
WHERE status = 'reserved' AND id = 123;
```

Or every open reservation older than a UTC cutoff (`ts` is `YYYY-MM-DDTHH:MM:SS.ffffffZ`):

```sql
UPDATE spend_ledger
SET status = 'released', actual_usd = NULL
WHERE status = 'reserved' AND ts < '2026-10-20T00:00:00.000000Z';
```

Leave `settled` rows in place. They are the spent total.

`X-Batatis-Notice` and the engine `X-Robots-Tag` header belong to #24 (`http_guard`, `PII_NOTICE`). This branch does not set those headers. `web/index.html` carries the robots meta tag, and every `vercel.json` route sends `X-Robots-Tag: noindex, nofollow`.

The code database is not a public file. `vercel.json` answers `/codedb.sqlite`, `/codedb/build/codedb.sqlite`, and `/api/codedb/build/codedb.sqlite` with 404, ahead of any later rewrite. Those routes have to stay. The service layout itself is a separate change. The web build's `dist/` does not contain `codedb.sqlite`.

No database, a database error, an unknown model, or a full cap refuses the provider call and serves the offline path with the `notice` strings in `docs/api-contract.md`. Those refusals are HTTP 200, not 5xx.

`GET /status/budget` reports `live`, `cap_usd`, `spent_usd`, and `remaining_usd`.
