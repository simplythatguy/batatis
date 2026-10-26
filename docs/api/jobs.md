# Durable background jobs

The frontend contract is `engine/models_jobs.py`. `kind` is a registered string
matching `^[a-z][a-z0-9_]{0,63}$`, not a closed enum. Applicant UI can filter the
two initial kinds, `intake` and `identify`.
The standard engine HTTP guard also adds `meta.notice` to JSON responses; this
cross-cutting notice is not a Job field.

## HTTP contract

- `POST /cases/{case_id}/intake/jobs`: existing `IntakeRequest` JSON.
- `POST /cases/{case_id}/identify/jobs`: existing optional `IdentifyRequest` JSON.
- Both accept `Idempotency-Key` (1–200 visible ASCII characters, without spaces). Keep the same
  key for a retried HTTP submission. If omitted, semantic duplicate joining still
  works. A supplied key with a different normalized body returns 409.
- Both return **202** with a persisted `Job`, including when rejoining a terminal
  job. No AI computation happens in this request. `Location` identifies its status
  URL. Poll `GET /cases/{case_id}/jobs/{job_id}`; reload/cross-device recovery uses
  `GET /cases/{case_id}/jobs`, returning `{"items": [Job, ...]}` newest first.
  The listing accepts `kind` and `limit` (default 50, maximum 100).
- `POST /cases/{case_id}/jobs/{job_id}/cancel` returns `Job` (200). Cancelling a
  queued/running job fences its result immediately. Terminal jobs are unchanged.
- `POST /cases/{case_id}/jobs/{job_id}/retry` returns `Job` (202). It requeues the
  same identity without resetting its attempt budget. Queued/running/succeeded
  jobs rejoin unchanged. Superseded inputs require a new submission. Changed
  semantic inputs or an exhausted attempt budget return 409.

All these responses are `Cache-Control: no-store`. Normal case authorization
applies on every read/write; an unrelated case/job combination returns 404.
Cancellation/retry/start require applicant editing permission. Existing synchronous
intake and identification endpoints, including identification SSE, remain supported.

Every Job field below is present; nullable fields are JSON `null`:

```json
{
  "id": "job_0123456789abcdef",
  "case_id": "case_0123456789ab",
  "kind": "intake",
  "state": "queued",
  "stage": "queued",
  "attempts": 0,
  "max_attempts": 3,
  "base_version": 4,
  "result_version": null,
  "created_at": "2026-10-26T18:00:00+00:00",
  "updated_at": "2026-10-26T18:00:00+00:00",
  "started_at": null,
  "finished_at": null,
  "next_attempt_at": "2026-10-26T18:00:00+00:00",
  "heartbeat_at": null,
  "lease_expires_at": null,
  "error": null,
  "can_retry": false,
  "result_url": null
}
```

`state` is `queued | running | succeeded | failed | cancelled | superseded`.
Timestamps are UTC ISO 8601. `result_version` is the case version committed with
success. On success `result_url` is `/cases/{case_id}/intake` or
`/cases/{case_id}/identify`. The applicant client fetches the canonical
`GET /cases/{case_id}` once: its embedded intake/identify records use the same
derived freshness and decision views as those individual endpoints. A later case
edit can make that saved result stale under the existing result contract.
`base_version` records acceptance, not a promise to overwrite that version.

`stage` reports actual work, without percentages or fabricated substeps. Common
stages are `queued`, `preparing`, `applying`, `completed`. Intake adds `reading`;
identification adds `screen`, `rerank`, `verify`, `questions`. Stages may be skipped
or revisited on retry. `queued` with a future `next_attempt_at` is backoff;
`queued` without an available worker remains queued, never simulated progress.
Pipeline stages can finish with the existing labelled fallback or unavailable
model result. Job success means that result was committed; it does not claim a
successful live AI call, narrowed identification or technical correctness.

`GET /cases/{case_id}/jobs/health` uses the same case read authorization and
`no-store` policy. It returns this exact shape:

```json
{
  "worker_available": false,
  "last_heartbeat_at": null,
  "queued": 1,
  "running": 0,
  "execution": "external_required"
}
```

`execution` is `in_process | external | external_required`. Counts cover only
the authorized case. Availability means a worker heartbeat was received within
the API's lease window (60 seconds by default), not a guarantee of immediate
execution. Both idle polling and running-job heartbeats renew worker presence.
Graceful worker shutdown removes its presence; abrupt death ages out. The UI
should show unavailable background processing when `worker_available` is false,
keep accepted jobs recoverable, and offer cancel/retry where appropriate. On
Vercel, explain that an external worker is required while it is unavailable.

Errors contain only a bounded public code, fixed generic message, stage and
automatic-retry classification:

```json
{
  "code": "processing_failed",
  "message": "Processing could not be completed.",
  "stage": "reading",
  "retryable": true
}
```

Other codes: `worker_lost`, `access_changed`, `input_changed`, `invalid_input`,
`handler_unavailable`. `can_retry` means a failed/cancelled job has attempts left;
retry still checks current permissions and semantic inputs. No request text,
file names, code quotations, provider payloads, raw exceptions, actor IDs,
idempotency keys, worker IDs or lease fencing tokens appear in Job responses.

## Consistency and privacy

Jobs use the **same case database**, via `store.account_db()` and its portable
SQL adapter. Each case deletion cascades to its jobs and request-key aliases;
deleting an actor account also cascades its jobs. Retention deletes the same rows.
The private job input is the original request JSON and referenced file IDs, under
the case's existing retention/access boundary. Uploaded bytes are not duplicated.
No new input is sent to AI: the shared handlers use the original intake/identify
algorithms and their existing redaction, access-code and spend gates.

The worker reads the current account and case before execution and again under
the commit transaction. It reconstructs access/redaction context from that account,
never from an old HTTP context. AI access revoked after acceptance/execution
prevents an originally authorized AI result from committing. Browser logout does
not cancel already accepted work; cancellation, account/application deletion and
current capability checks control it. Deterministic handlers do not acquire an
AI capability requirement. An AI handler cannot silently drop the acceptance
host's access-code policy when it runs on an external host with missing
configuration.

A handler fingerprints its actual read inputs and protected write footprint.
Raw `applicant_draft`, messages,
timestamps and unrelated metadata do not invalidate AI work. If those alone change,
the handler applies its computed output to the latest locked case and updates only
its declared write fields, preserving current editors and unrelated changes. A
changed substantive read input (including facts) safely produces `superseded`.
Case update and job success commit together after checking the current lease fence.
A lost/expired lease, cancellation or deletion cannot apply a late result.

Superseded computation is discarded; the runtime does not retain another private
copy of provider results for forced application onto changed inputs.

Idempotency keys are hashed and scoped to case, kind and actor. Equivalent
semantic inputs rejoin the same identity even with different keys, after raw
editor-only saves, or after failure/cancellation. Rejoin never automatically
resets a failure or spends again. Use explicit retry for the same unchanged
input, or submit changed semantic inputs as a new job. The full normalized body,
including `expected_version`, binds a supplied key; reuse that original body
when retrying a lost HTTP response. New submissions still validate a supplied
`expected_version` against the latest case before accepting work.

## Run and deploy

Normal long-lived ASGI apps run a lifespan worker **by default outside Vercel**.
That includes the existing local and desktop engine entrypoints when their ASGI
lifespan runs. To manage execution separately or control tests, set
`BATATIS_JOBS_WORKER=0`. `BATATIS_JOBS_WORKER=1` explicitly enables it, but never
on Vercel. There is no response-owned BackgroundTask or fire-and-forget compute
thread. The supervised lifespan task drains its current attempt on graceful
shutdown; a killed process leaves a recoverable durable lease.

Standalone worker, from the repository with engine dependencies installed:

```sh
python -m engine.jobs worker --poll-interval 1
python -m engine.jobs worker --once
python -m engine.jobs health
```

`--once` processes at most one ready attempt and exits; delayed backoff work
remains queued. `health` prints the same health shape with whole-database counts
for an operator. These commands never start HTTP servers. The default lease is
60 seconds and heartbeat interval 10 seconds; override with `--lease-seconds`
and `--heartbeat-interval` (positive and less than half the lease). Poll interval
is 0.01–60 seconds; the CLI also accepts `BATATIS_JOBS_POLL_SECONDS`. Keep worker
host clocks synchronized. One worker executes one computation at a time; multiple
worker processes safely claim different jobs with SQL row locks and lease fences.

**Vercel does not execute queued jobs.** Deploy a continuously supervised worker
process on a long-lived host/container using `BATATIS_STORE=postgres` and the
**same `DATABASE_URL`** as the API. Set `BATATIS_JOBS_WORKER=0` on any long-lived
API replicas when using only external workers. The worker needs the same code
database (`BATATIS_CODEDB` when configured), algorithm configuration, AI access
codes/policy, provider routing, live switches and spend database configuration as
the accepting API. Credentials stay in environment/secret management; no token,
session cookie or provider credential is serialized into jobs. SQLite is suitable
only when the API and worker share the same persistent `BATATIS_CASES` file.

The queue survives browser refresh/navigation, API process replacement and worker
crashes because it lives in the case database. Hosting a worker and preserving
that database are operational prerequisites, not features supplied by a Vercel
function response. Heartbeats identify anonymous worker instances; registry rows
older than a day are removed. Queuing/progress do not update case `updated_at` or
extend case retention; a successful applied result is a case content write.

Attempts default to three for the job's lifetime (runtime configurable from one
to five). A claim consumes one attempt. Transient exceptions and abandoned leases
requeue with exponential backoff, starting at five seconds and capped at five
minutes. Validation/handler-contract failures are terminal. Explicit retry keeps
the attempt count and fencing history; it never buys another unlimited retry
budget. An unavailable handler/revision fails safely. A worker stopped during an
outbound call may have already incurred provider cost; the runtime guarantees
at-most-once result application, not exactly-once provider billing.

## Add another kind

`engine.jobs.JobHandler`, `JobRegistry` and `JobRuntime` are the extension seam.
Register the same handler on API and worker instances. `default_registry(code)`
is the central built-in registry used by `create_app` and the standalone command;
add another registration there for additional kinds. No public enum extension,
schema migration or job-store switch statement is needed for a new kind.

Supply:

1. A bounded `kind`, stable `revision`, Pydantic `request_model` with bounded
   input, and a Pydantic `TypeAdapter` for the computation result. Change revision
   when input interpretation or compute/apply semantics change incompatibly.
2. `read_fields`, `write_fields`, and optionally `input_values(case, body)` for a
   narrower JSON-serializable fingerprint. The default fingerprints declared
   case read fields plus normalized request values excluding `expected_version`.
   The runtime always adds current owner/status/authority, declared write values,
   handler revision and referenced-file identity. Include every semantic field
   used by compute **or apply**, including answers that must not be overwritten.
3. `validate_input(case, body)` for cheap deterministic acceptance/execution
   checks, and `file_ids(body)` for referenced immutable case uploads. Do not
   parse PDFs, call providers or open a second database transaction from these
   callbacks. Files are checked against their owning case at acceptance/commit.
4. `compute(case, body, context)` for slow work. It runs outside the transaction
   with a fresh access context. `ExecutionContext` supplies `store`, current
   `user`, a hashed client rate key and `progress(stage)`. Call the existing
   redaction and provider/spend gates; never pass raw case JSON or private editor
   text to a model. `uses_ai(body)` defaults to false; AI handlers must declare
   it true for requests that may call AI, so durable capability revocation is
   enforced without restricting deterministic kinds.
5. `apply(latest_case, body, validated_result)` for short deterministic mutation
   under the case/lease lock. No network, database calls, sleeps or file parsing.
   Mutating outside declared `write_fields` rolls back and fails the attempt.
   The runtime forbids generic jobs from mutating private editors, messages,
   ownership, review/workflow authority and professional determinations.
6. A bounded `stages` tuple and an existing relative `result_path` such as
   `/intake`. Emit only registered stage tokens. Progress persists no payload
   and must not imply success or completion of a skipped algorithm stage.

Then call `runtime.enqueue(case_id, kind, parsed_body, user,
idempotency_key=..., client_ip=...)` from a case-scoped endpoint returning 202.
Use an optional `admit` callback for existing cheap rate admission, after duplicate
joining. Raw client IP is never serialized; the worker receives only its hashed
rate key. The built-in identification route retains its existing per-IP start
limiter; provider calls retain their existing gates and accounting.

The built-in footprints are:

| Kind | Semantic case reads | Case writes |
| --- | --- | --- |
| `intake` | facts, intake, identify, title/manual-title flag, jurisdiction, selected reading-file IDs | facts, intake, title |
| `identify` | facts, identify, title/manual-title flag, provisions, relevance | facts, identify, title, relevance |

Input/result validation, fingerprint comparison, durable actor checks, lease
ownership/expiry and write validation all precede the atomic case-success commit.
The latest case version remains the SQL compare-and-swap target even when
editor-only saves advanced it beyond `base_version`. Neither handler writes a
snapshot back over applicant answers, private editors or unrelated metadata.
