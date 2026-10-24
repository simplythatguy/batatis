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

## Opt-in candidate experiment (identify only)

Defaults remain the exhaustive shared-card screen, rerank and top-15 verifier
above. The experiment is selected only by `BATATIS_IDENTIFY_SCREEN=shortlist` (or
`screen: "shortlist"` in the identify config). It uses one **metered OpenAI JSON**
request with the complete authoritative Division B table of contents, accepts only
exact known article IDs, and interleaves those candidates with the existing fast
BM25 ranking. It takes the first 60 unique IDs by default, never an exhaustive
screen. A key or the Elephant-only live switch does not enable the text selector
or reviewer: those still require their existing OpenAI/live gates.

Settings are `shortlist_n` (default 60, maximum 120) and `shortlist_toc_n` (default
40, no larger than the pool). Their environment overrides are
`BATATIS_IDENTIFY_SHORTLIST_N` and `BATATIS_IDENTIFY_SHORTLIST_TOC_N`.
`load_config` infers `screen_model=gpt-6-luna` when omitted; direct
`IdentifyConfig` construction must set that screen pin. The existing
`verifier_effort` also selects the TOC request's effort. The shortlist supports
`rerank=elephant` or `none`, and `verifier=openai` or `none`. It does not import
the evaluation harness, use its caches, or switch scoring providers on failure.

Optional reranking scores **every pool article**, without dropping candidates.
A rerank failure retains the tentative pool and reports that reranking was
unavailable. The reviewer receives the **full text of every pool article**,
independent of `verify_n` or `rerank_n`, and labels each internally as `applies`,
`check`, or `unlikely`. These labels are model judgments. Only an `applies` with
a verbatim body quote can lead the suggestions. A missing, malformed, duplicated
or ungrounded answer becomes `check`; unknown IDs are rejected. Review failure
retains all candidates. Selector failure/empty output returns a clearly labelled,
bounded keyword fallback and skips model review.

The existing `IdentifyResult` shape is retained: **all bounded pool articles**
are returned as tentative `articles`, including unresolved and unlikely items;
the normal `top_k=10` cutoff is not applied. Quote-grounded model suggestions
lead, followed by `check`, then `unlikely`, preserving rerank order within each
group. Up to `choices_k` quoted questions are offered as before. `verifier=picked`
means a tentative model suggestion with a source quote, never verified
applicability. No full-pool recall guarantee is made. The run returns no exhaustive
score map and cannot replace or create a relevance record or trusted bands.
Automatic commits are **always disabled** for this experiment, even with an
injected matching calibration policy. Applicant confirmation remains separate.

`BATATIS_IDENTIFY_QUESTION_STYLE=self` independently opts an Elephant stage into
one self-contained `noul` question per article. State contains only `proposal`;
each question says ``A complete alternative-solution application for the proposal
in `proposal` must cite this building-code article: {card}``. The default `shared`
wire payload is unchanged. The same wire-byte admission, TLS, deadline, serial
dispatch and no-retry rules still apply to either shape. This style also disables
automatic commits. Offline fakes support both shapes and the actual TOC/pool
review path; their results provide no accuracy measurement.

Inactive experiment settings do not change historical configuration dictionaries
or hashes. `self` binds its question text into its new hash; `shortlist` binds its
selector/reviewer prompts, schemas, output bounds, pool settings and validation
policies. Existing `relevance-3` remains uncalibrated; no new relevance version,
thresholds or display bands are introduced.

The motivation is the approximately 131-request exhaustive screen versus the
50/day free allowance. Earlier **gold-injected diagnostic** pools improved AUC
from .912 to .948 and complete top-10 coverage from 80% to 95% with self-contained
questions, which does not establish end-to-end recall. Cached 57-case runs found
complete pools in 50/57 cases (87.7%) with TOC40 plus fast BM25, 52/57 with slow V3,
and 51/57 with capped graph expansion. The V3 run had 38/57 cases with every gold
article labelled `applies`, despite no further gold loss at the labeler's
`applies`/`check` boundary. These are prior measurements, not validation of this
exact engine implementation. They provide no basis for default promotion or a
100% claim. The parent must measure the exact opt-in pipeline separately.

The opt-in candidate reuses the existing API models; schema export and generated
web contract checks pass without generated-file edits. If later parent composition
changes a shared model, regenerate schema/types from that composed backend.
`web/src/calm/relevance.ts` treats uncalibrated `0..1` ranges as unrated and reserves
historical fallback bands for `relevance-1` placeholder rows. Preserve that behavior
on the integrated UI; do not replace zero with historical cutoffs.

## Primary references checked 2026-10-23

- [Elephant model/context/price](https://openrouter.ai/baseten/elephant-1%3Afree)
- [Typed Decisions request/response and routing schema](https://openrouter.ai/docs/api/api-reference/alphadecisions/submit-a-decisions-request.md)
- [OpenRouter limits](https://openrouter.ai/docs/api_reference/limits.md)
- [TypeSafe API](https://docs.typesafe.ai/api.md), [Noul](https://docs.typesafe.ai/primitives/noul.md), [Score](https://docs.typesafe.ai/primitives/score.md), [Choice](https://docs.typesafe.ai/primitives/choice.md)
- [python-dotenv release metadata](https://pypi.org/project/python-dotenv/1.2.4/)

The isolated work includes offline regressions, independent engine review, a live
60-article optional-scorer integration smoke, and the separately recorded exact-engine
retrieval panel. See the [handoff](research/2026-10-23-elephant/handoff.md) for results
and limits. Application servers and remote branches were outside the authorized work.
