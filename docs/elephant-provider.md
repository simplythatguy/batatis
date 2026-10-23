# Elephant article scoring

Screening and the top-60 rerank default to `elephant`. The existing full-text
verifier, assistant and voice configurations keep their own settings and gates.
Scoring runs only for the existing explicit identify/relevance actions; constructing
the app, saving a description and reading stored results do not score anything.

## Server configuration

Set `OPENROUTER_API_KEY` privately in the server environment. To enable only this
scorer while keeping unrelated providers disabled, use:

```dotenv
BATATIS_LIVE=0
BATATIS_LIVE_ELEPHANT=1
```

An absent/empty Elephant override inherits `BATATIS_LIVE`; `0` explicitly disables
Elephant. A credential alone never enables a live call. `BATATIS_PROVIDER=fake`
uses the offline wire fake and requires no key; fake mode is refused on Vercel.
Never prefix a provider credential with `VITE_`.

`scripts/local-app.sh start` passes the worktree's root `.env` to **Uvicorn only**
when the file exists. Install `engine/requirements.txt` first; it pins
`python-dotenv==1.2.4`. The parser preserves existing process environment overrides
and does not execute shell syntax. The launcher does not source `.env` or export
its values to the web process. An isolated worktree does not borrow another
checkout's private `.env`. The parent owns private configuration and server restart.

Existing config-file and `BATATIS_IDENTIFY_*` overrides still take precedence.
Remove obsolete overrides or explicitly set both `BATATIS_IDENTIFY_SCREEN` and
`BATATIS_IDENTIFY_RERANK` to `elephant`. Their model pins must both be
`baseten/elephant-1:free`. Jev and legacy Luna Decisions remain explicit opt-ins;
missing credentials or scoring failures never select them automatically.

## Wire and failure policy

- One POST to `https://openrouter.ai/api/alpha/decisions`, with genuine typed
  `state`/`questions` (`noul`, `choice`, `score`). No Chat Completions prompting.
- Request model: `baseten/elephant-1:free`. Routing allows Baseten only, disables
  provider fallbacks and caps prompt/completion/request prices at zero.
- Accepted response model: **only** `baseten/elephant-1-20261021`. The free request
  alias, other dates and other model ids are refused. Usage must contain valid
  token counts and numeric zero cost.
- Strict answer names/types, finite probabilities, complete normalized
  distributions, on-rubric Score means/legends and winning Choice validation.
  Missing/refused/duplicate/malformed answers never become scores.
- Verified certifi roots, hostname checking, no environment proxies, no redirects,
  no transport retries, a total deadline of at most 60 seconds per batch and a
  1 MB response ceiling. The verified TLS cleanup contract requires HTTPcore
  `1.0.9` (tested with HTTPX `0.28.1`); version drift fails before dispatch.
- One active Elephant call per process. Batches are serial; the first error
  aborts the remaining batches without retries or queued fan-out. Existing
  identify/relevance per-IP and daily run budgets remain in force. A 429 is a
  failure, not permission to try another provider/model.

Relevance failures return the existing neutral 503 and retain the prior record.
Identify falls back to labelled keyword results, commits nothing, and does not
persist a partial exhaustive scoring record. Valid reported usage is retained
even when answers are unusable; unknown usage is recorded as unknown, never as
successful zero-token work. The zero price applies only to the exact free route.
If full-text verification is disabled/unavailable, its label reports that state.

## Context, quotas and calibration

The model has a 16,384-token context. Batching counts the actual UTF-8 wire body,
including **all state, questions and routing**, conservatively at one token per
byte, plus 2,048 framing tokens and an answer allowance. This is a local admission
bound, not a measured tokenizer. The existing explicit 700-character article-card
projection is preserved; proposals/cards are never shortened further to fit.
An oversized single item rejects the entire planned screen before the first call.
Both the 2,080-article screen and the top-60 rerank are split as necessary; partial
coverage is never labelled exhaustive.

An offline real-corpus batching check with a short synthetic description required
131 screening requests and 4 rerank requests. Counts depend on the description
and selected articles. OpenRouter currently documents 20 requests/minute and a
50/day or 1,000/day free-model allowance depending on account history; some
endpoints/accounts are exempt. This implementation does not inspect/change the
account, purchase credits, retry quota failures or claim an exhaustive live run
will fit its allowance. The parent must assess that operational limit separately.

Elephant has public scoring version **`relevance-3`** and a configuration hash that
includes its stable response pin, endpoint and context policy. Historical Jev/Luna
hashes and thresholds remain historical. No Elephant calibration is supplied:
bands are `{x: 0, y: 1, status: "uncalibrated; display range only"}`, and automatic
commits remain off without an exact-config validated fit. A single smoke does not
establish calibration, technical equivalence, safety or professional approval.

Integration must regenerate the shared API schema/types **after** parent composition.
The new backend model enum includes `relevance-3`; this worker deliberately leaves
generated web files untouched. At base `6274b8be`, `web/src/calm/relevance.ts:26-35`
already treats uncalibrated `0..1` ranges as unrated and reserves historical fallback
bands for `relevance-1` placeholder rows. Preserve and test that behavior on the
actual integrated UI; do not replace zero with historical cutoffs.

## Primary references checked 2026-10-23

- [Elephant model/context/price](https://openrouter.ai/baseten/elephant-1%3Afree)
- [Typed Decisions request/response and routing schema](https://openrouter.ai/docs/api/api-reference/alphadecisions/submit-a-decisions-request.md)
- [OpenRouter limits](https://openrouter.ai/docs/api_reference/limits.md)
- [TypeSafe API](https://docs.typesafe.ai/api.md), [Noul](https://docs.typesafe.ai/primitives/noul.md), [Score](https://docs.typesafe.ai/primitives/score.md), [Choice](https://docs.typesafe.ai/primitives/choice.md)
- [python-dotenv release metadata](https://pypi.org/project/python-dotenv/1.2.4/)

This worker used offline synthetic peers only. The parent owns one tiny integrated
adapter smoke with the real credential, independent review, restart and verified
dev publication. No provider accuracy or browser/production signoff is implied.
