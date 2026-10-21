# Code identification API (`/cases/{id}/identify`)

Code identification ranks the Division B articles that govern an applicant's description. A ranking is a candidate list, not a code determination. The service never says a design complies or is safe, and it never writes provisions on its own: only the applicant's `yes` (or `confirm`) does.

Source: `engine/routes_identify.py`, `engine/identify/` (pipeline, config, commit policy, providers, fakes), `engine/models_identify.py`, `engine/process_refs.py`.

## Pipeline

| Stage | Default | Checked |
|---|---|---|
| screen | Jev `jev-1.13.0` judges every Division B article (700-character cards, about 20 requests) | exactly 2,080 scores, none missing, or the run falls back |
| rerank | the top 60 re-judged by Jev in one request | request count recorded in `trace.stages` |
| verify | OpenAI `gpt-6-luna`, reasoning effort `medium`, standard tier, reads the full text of the top 15 | every pick's quote must occur word for word in that article; failures are dropped and counted in `trace.dropped`, and the pipeline checks again before display |
| commit | Part 9 only, verifier picked it, rerank probability at least the calibrated threshold, at most 3 | `engine/identify/calibration.json` must say it is calibrated for this config (below) |
| choices | the top three uncommitted articles, any Part, as quoted choices | quotes come from the code database or a checked verifier quote |
| fallback | keyword search (`bm25`, or `bm25_v3` from #33) when any model stage fails | labelled, `mode: bm25_fallback`, commits nothing, verifier not run |

Every run also returns the two process references, Div A Article 1.2.1.1. and Div C Article 2.3.1.1., read from the code database and marked `read_only: true`.

### Configuration (the hand-off from the benchmark, WP-11/12)

`IdentifyConfig` (`engine/identify/config.py`) names every choice that changes results. Resolution: defaults, then a JSON file (`BATATIS_IDENTIFY_CONFIG`, else `engine/identify/pipeline.json` if present), then `BATATIS_IDENTIFY_<FIELD>` variables.

| Field | Default | Allowed |
|---|---|---|
| `screen` / `screen_model` | `jev` / `jev-1.13.0` | `jev`, `bm25`, `bm25_v3` (lexical arms are not exhaustive) |
| `card_chars` | 700 | at least 1 |
| `rerank` / `rerank_model` | `jev` / `jev-1.13.0` | `jev`, `openai`, `none` |
| `rerank_n` | 60 | |
| `verifier` / `verifier_model` | `openai` / `gpt-6-luna` | `openai`, `anthropic` (off by default; `claude-sonnet-5-5`), `none` |
| `verifier_effort` | `medium` | OpenAI: `low`, `medium`, `high` |
| `verify_n` | 15 | at most `rerank_n` |
| `fallback` | `bm25` | `bm25`, `bm25_v3` |
| `top_k` / `choices_k` | 10 / 3 | |

Haiku models are refused. Jev stages must use the pinned `jev-1.13.0`. The result records `trace.config` and `trace.config_hash` (16 hex characters of the sorted config JSON); the benchmark writes the winner as `pipeline.json`.

### Commit calibration

With `engine/identify/calibration.json` absent, unreadable, or not matching, nothing is committed: every article is a candidate or a quoted choice. That is the honest default. The 0.75 placeholder in `engine/cli_sut.py` was never fitted. The file the calibration-fold fit writes:

```json
{
  "status": "calibrated",
  "validated_on": "validation",
  "config_hash": "<trace.config_hash of the pipeline that was fitted>",
  "max_commits": 3,
  "parts": {"9": {"status": "calibrated", "threshold": 0.82}}
}
```

A threshold fitted for one config is never applied to another (`config_hash` must match). Only Part 9 can commit, whatever the file says, and `max_commits` cannot exceed 3.

## Providers, spend and privacy

- Every provider call (Jev, OpenAI, Anthropic) goes through `engine/llm_gate.py`: `reserve` the worst-case cost before the call, `settle` with the tokens the provider reported, `release` if it fails. A shut gate (`BATATIS_LIVE` off, credential absent, daily cap reached) makes the run take the labelled fallback. Cost per case is in `trace.spend` (per provider) and `trace.usd`.
- Prices (USD per million tokens, input/output): `jev-1.13.0` 0.042/0.042 (input price from the jev-benchmark README; no output price published, so the same); `gpt-6-luna` 0.20/0.75 (OpenAI's long-context list price, used for every call as an over-estimate; the short-context list price is 0.10/0.50); `claude-sonnet-5-5` 2/10; `claude-opus-5-5` 4/20; `gpt-4.1-2025-04-14` 2/8; `gpt-4.1-mini-2025-04-14` 0.40/1.60.
- Per-IP limit: one slot per run, `BATATIS_IDENTIFY_RATE_LIMIT` (default 6) per `BATATIS_IDENTIFY_RATE_WINDOW_SECONDS` (default 600), per instance. Daily cap: `BATATIS_DAILY_SPEND_CAP_USD` (default 5).
- Live switch: `BATATIS_LIVE=1` plus `OPENAI_API_KEY` (verifier) and the Jev credential. The Jev credential is `TYPESAFE_API_KEY` or `JEV_API_KEY` in the environment, then the keychain, then `~/.config/jev/credentials`. The engine does not read `.env` itself; load it in the shell (`set -a; . ./.env; set +a`).
- Outbound text is the description with personal details removed (`engine/redact.py`: `scrub` with `known_values` and `people_names`), as for `/relevance`. The stored `description_sha256` is of the applicant's own text.
- `BATATIS_PROVIDER=fake` swaps every transport for the deterministic offline fakes in `engine/identify/fakes.py` (still metered under the same model ids), including the default adapters (`Judge()`, `jev_ask()`, `ClaudeVerifier(db)`) used by `/relevance` and `cli_sut.py`. Nothing reaches the network in fake mode, even with `BATATIS_LIVE=1` and keys set (tested with sockets and HTTP blocked). Results are labelled `mode: fake` and "not a measurement". Refused when `VERCEL` is set.
- Live providers are OpenAI and Jev. An Anthropic client is built only when `verifier: anthropic` is configured (`BATATIS_IDENTIFY_VERIFIER=anthropic` or `pipeline.json`); `ANTHROPIC_API_KEY` alone never reaches Anthropic.

## Routes

Owner writes; reviewers read (`engine/access.py`: every POST here is mode `edit`, so a reviewer gets 404 or 409 and a submitted case is read-only).

**Versions.** Every write is one compare-and-swap (docs/api-contract.md): a concurrent write returns 409 `case was updated concurrently` and is never retried on a newer case. Each POST body accepts an optional `expected_version` (the `Case.version` or `case_version` the client last read), as `POST /cases/{id}/section-d` does; a supplied version that is not the stored one is a 409 and nothing is written. Every identify response carries `case_version`, the version after that read or write. An identify run writes its result with one CAS against the version it started from, so any write to the case during the run makes the run a 409 (`error` event with `status: 409` on the stream).

### `POST /cases/{id}/identify`

Body (all optional): `{"prose": "...", "answers": [{"question_id": "...", "field": "...", "answer": "..."}], "expected_version": 7}`. Without `prose`, the case's latest `project.description` fact is used; with neither, 409 `Describe your project first`.

An answer must name a question this case's stored identification asked (`open_questions[].id`) and can only fill that question's own field (`identify.choice.<article>`; `field` may be omitted). Anything else, including a field such as `project.description`, `citation.*` or `evidence.*.file_ref`, is a 422 and nothing is written, so an answer can never replace a confirmed fact. Accepted answers are stored as unconfirmed facts (an unknown answer has no value).

- `Accept: application/json` returns the `IdentifyResult`.
- `Accept: text/event-stream` streams one event per stage, in this order: `start`, `screen`, `rerank`, `verify`, `questions`, `done`. Each stage event's data carries status and counts only (`{"stage": "screen", "status": "done", "method": "jev", "articles": 2080}`), never prose or code text. `done` carries the full result, the same body as the JSON response. A failure sends `error` with `{"message", "status"}`. Events are not buffered by the HTTP guard.
- Errors: 404 case not found, 409 no description or a run already in progress (`Retry-After: 1`), 429 rate limit (`Retry-After`), 503 code database missing or config invalid.

The run stores the result on the case (`case.identify`) and writes the relevance rings (`case.relevance`) from the same Jev screen, so the code library's rings match the identification. It also sets a short title when the case has none.

### `GET /cases/{id}/identify`

The stored result with decisions overlaid and `stale: true` when the description changed since the run. It never calls a provider. 404 `identify result not found` before the first run.

### `IdentifyResult` (main fields)

| Field | Meaning |
|---|---|
| `mode`, `source`, `label` | `live`, `fake` or `bm25_fallback`, and a sentence saying what ran |
| `narrowed`, `message` | false when no verifier pick survived; then `message` is "I could not narrow this down..." |
| `articles[]` | `rank`, `provision` (article), `provision_id` (sentence, when the quote sits in exactly one), `title`, `part`, `citation`, `quote`, `quote_source` (`verifier` or `codedb`), `reason` (verifier line, dropped if it claims compliance or safety), `probability`, `screen_probability`, `verifier` (`picked`, `not_picked`, `not_run`), `status` (`committed`, `choice`, `candidate`, `fallback`), `commit_reason`, `objectives[]`, `functions[]`, `decision`, `open_question_id` |
| `committed[]` | articles committed under the calibrated Part 9 rule (empty until calibrated) |
| `choices[]` | quoted choices: `quote` and `question` ("The code says: \"...\" Does your design do something different from this?"); show the article id behind a disclosure |
| `questions[]`, `open_questions[]` | the same choices as questions with `field` `identify.choice.<article>` |
| `benchmark` | the benchmark acceptable solution: `provision`, `provision_id`, `citation`, `sentence` (verbatim), `departure`, `departure_status` (`none`, `proposed`, `confirmed`), `objectives[]`, `functions[]` by lookup, `basis` (`committed`, `top_choice`, `applicant`, `none`), `requirement` (numeric requirement against confirmed facts) |
| `process_refs[]` | Div A 1.2.1.1. and Div C 2.3.1.1., `read_only: true` |
| `model_ids`, `commit_policy` | pinned ids per stage; the policy status and reason |
| `case_version` | the case version after this read or write; send it back as `expected_version` |
| `trace` | `config`, `config_hash`, `exhaustive`, `articles_expected` (2080), `articles_scored`, `ranker`, `fallback_reason`, `verifier`, `picks`, `dropped[]`, `stages[]` (seconds, requests, tokens per stage), `spend`, `usd`, `seconds` |

### `POST /cases/{id}/identify/{provision}/decision`

`{"decision": "yes" | "no" | "not_sure", "expected_version": 8}`. `yes` adds the article to `provisions`, rebuilds Section C by lookup and records a confirmed `citation.<article>` user-click fact; `no` and `not_sure` remove it. `not_sure` gives the card an `open_question_id` and an item in the information request. Returns the `IdentifyResult` plus `section_c`, the Section C rows a `yes` wrote for that article (empty otherwise). 404 when there is no stored result or the article is not in it; 409 on a stale `expected_version`. A `yes` stops showing once a reference withdrawal (`POST /cases/{id}/section-d`) removes the provision.

### `POST /cases/{id}/identify/confirm`

`{"provisions": ["9.10.15.5.(8)", ...], "expected_version": 8}`. Each id must exist in Division B (404 lists the missing ones). Writes provisions and Section C. Returns the `Case`.

### `POST /cases/{id}/identify/benchmark`

`{"provision": "9.10.15.5.(8)", "departure": "one line", "expected_version": 8}`. The applicant names the requirement the design departs from and confirms the departure. The sentence, citation and objective and function codes are looked up; a departure that claims compliance, safety or approval is refused with 422 ("departs from the acceptable solution by ..." is fine). Returns the `IdentifyResult` with `benchmark.basis: applicant` and `departure_status: confirmed`.

### `GET /cases/{id}/information-request`

`{"case_id", "items": [{"id", "provision_id", "text"}]}`: one item per `not_sure` decision, for the officer.

### `GET /cases/{id}/process-refs`

The two read-only process rows (wrapped as `{"items": [...]}` by the HTTP guard, like every array response).

## Verification

```bash
# offline, no keys
BATATIS_PROVIDER=fake BATATIS_CODEDB=codedb/build/codedb.sqlite python -m pytest -q engine/tests/test_identify_service.py engine/tests/test_identify_policy.py
BATATIS_PROVIDER=fake python -m uvicorn engine.api:app --port 8061
curl -N -X POST localhost:8061/cases/$CASE/identify -H 'Accept: text/event-stream' -H 'Content-Type: application/json' -d '{}'
```
