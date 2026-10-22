# Voice backend

Backend slice only. Browser microphone capture, orb, playback, attachment controls,
navigation application and visual evidence belong to frontend/integration work.
The tests use synthetic providers/audio, plus an isolated local WebSocket and
PostgreSQL. They do not establish live app audio, transcription quality, production
availability or provider invoice reconciliation.

## Transport and configuration

The server owns the upstream WebSocket and pins **`grok-voice-3.0`** in both its
URL and session configuration. There is one adapter and no fallback model.
`BATATIS_LIVE=1` and an explicit server `XAI_API_KEY` are required. An OpenAI key
does not enable voice. Unknown providers fail closed. The token-priced LLM gate
cannot authorize xAI voice.

The browser receives **no provider credential**, including no ephemeral secret.
Irsal's direct ephemeral transport informed the protocol, PCM format and identity
guards. Its event persona and managed-agent instructions are not used. Direct
client tokens were unsuitable for retaining Batatis's server-controlled allowance:
authentication TTL does not establish a maximum active call duration.

Set `BATATIS_WEB_ORIGIN` to the exact browser origin. Local default:
`http://localhost:5480`. On Vercel the origin must be explicitly configured and
`BATATIS_STORE=postgres` must back the existing spend ledger. The existing
`BATATIS_DAILY_SPEND_CAP_USD`, assistant rate window and shared LLM rate window
are retained. No cap is raised. Rate windows remain per process/IP, as before.

The current FastAPI service registration remains in `vercel.json`. Current
[Vercel WebSocket documentation](https://vercel.com/docs/functions/websockets)
supports Functions WebSockets with FastAPI/ASGI. This is a hosting capability,
not proof that this project's deployed rewrites, Fluid Compute or browser proxy
have been exercised. A local Vite `/api` proxy must forward WebSocket upgrades.
Both `/voice/relay/session` and `/api/voice/relay/session` are registered so the
HTTP-only `/api` stripping middleware need not be broadened.

Official transport references checked 2026-10-22:
[voice REST/realtime protocol](https://docs.x.ai/developers/rest-api-reference/inference/voice),
[speech-to-speech guide](https://docs.x.ai/developers/model-capabilities/audio/speech-to-speech),
[exact model/modalities](https://docs.x.ai/developers/models/grok-voice-3.0).
The adapter uses server-only Bearer authentication, JSON audio events, PCM16 LE
24 kHz mono, server VAD, no tools and no resumption. Redirects/proxies and wire
debug logging are disabled. Raw audio reaches the provider before redaction;
do not describe live transcription as pre-redacted.

## Browser contract

Generated `VoiceCapability`, `VoiceStart`, `VoiceCommand` and `VoiceScope` types
come from `engine/schema_export.py` and the existing web generator. The conditional
case/version and command invariants below also apply.

`GET /api/voice/session`, with the real login cookie, returns:

```json
{
  "available": true,
  "reason": null,
  "protocol": "batatis.voice.v1",
  "relay_path": "/api/voice/relay/session",
  "max_seconds": 55,
  "notice": "Voice sends your microphone audio directly to a third-party AI service ..."
}
```

The actual notice is the complete `NOTICE` constant in `engine/voice.py`, also in
`X-Batatis-Notice`. Display that notice before explicit microphone/start action.
The standard HTTP privacy metadata describes text handling; the voice notice
explicitly states that microphone audio and its live transcription are not
pre-redacted. GET is `no-store`, creates no provider, opens no audio, consumes no
rate slot and reserves no money. `available` describes configuration; start can
still be refused by fresh auth, context, rate, budget or upstream checks.
Optional `?case_id=...` authorizes metadata only. Anonymous reads return HTTP 401;
inaccessible cases return 404. Capability reads do not include private context.

Open a same-origin WebSocket at the returned path with subprotocol
`batatis.voice.v1` and the browser's existing cookie. Credentials/query parameters
are not accepted. Origin must match the configured origin exactly. Rejected
handshakes close with 4401 (missing/expired/revoked real login), 4403 (origin,
protocol or query rejected), or 1013 (auth store unavailable).

The authenticated socket first emits `session.ready` with an opaque `session_id`.
That alone does not start a provider. Within five seconds, send:

```json
{
  "type": "session.start",
  "scope": {
    "context_id": "random-local-context-identity",
    "revision": 0,
    "case_id": null,
    "case_version": null,
    "screen": "settings",
    "focus": null,
    "destinations": ["settings", "notifications"],
    "attachment_ids": []
  }
}
```

Mint a new `context_id` per account/selected-case lifetime, including separate
unsaved contexts. It is an identity guard, not authorization. Non-null `case_id`
requires the actual current `case_version`, and vice versa. Unknown properties,
destinations or invalid identities are rejected. `session.started` is emitted
only after authorization, allowance reservation, upstream exact-model confirmation
and session configuration acknowledgement. It includes `expires_at`,
`max_seconds`, the full voice notice and audio format. `expires_at` includes time
already spent connecting/configuring; it is not a new 55-second lease.

Subsequent commands use the ready/started `session_id`, original `context_id`,
and current `revision`:

| Type | Additional fields | Meaning |
| --- | --- | --- |
| `audio.append` | `audio`: base64 PCM16 LE | At most 32,000 decoded bytes per frame; valid, even byte count. |
| `audio.clear` | none | Discard pending input and invalidate pending output; emits `audio.clear`. |
| `response.cancel` | none | Cancel generating speech if present and clear browser playback; no native case work exists to cancel. |
| `context.update` | `scope`: complete replacement scope | Same context/case/version; revision must increase by exactly one. |
| `session.end` | none; revision optional | End this socket's session; repeated close/end cleanup is harmless. |

The socket also accepts exactly `{"type":"session.end"}` before start, with no
provider or allowance. During preparation/connection, the bound `session.end`
command remains observable and interrupts work. Audio must wait for
`session.started`. During context updates, wait for `context.updated` before
resuming input. Do not send browser `session.update`, model names, tools,
arbitrary URLs, confirmation flags or provider-protocol events.

Every server event includes `session_id`, `context_id`, `revision`, `case_id` and
`case_version` (scope fields are null before start). Discard events that no longer
match the browser's current account/case/context/revision. Close the socket and
stop microphone/playback on account or case changes and unmount; never reconnect
automatically. A fresh explicit start re-authorizes and reserves a fresh allowance.

| Server event | Payload/required browser behavior |
| --- | --- |
| `session.ready` | No provider yet; retains identity for ending while startup is pending. |
| `session.started` | Provider acknowledged; microphone frames may begin. |
| `audio.clear` | Stop queued/playing audio immediately. Also occurs on new speech and context updates. |
| `context.updated` | The authorized reference update was sent; this does not prove semantic understanding. |
| `transcript.completed` | `turn_id`, scrubbed display `text`, optional `navigation: {destination}`. Only final full speech can plan navigation. |
| `response.text` | `response_id`, `text`, `withheld_audio`. Render as generated help, never as confirmed application evidence. |
| `response.audio` | `response_id`, base64 `audio`; queue PCM playback only for the current identity/revision. |
| `response.done` | Completed checked response; no application write or navigation confirmation. |
| `session.error` | Neutral `message`, `status` 429/503, optional `retry_after`; currently used for allowance/rate refusal. |
| `session.ended` | `reason` below; stop capture/playback and release browser resources. |

Terminal reasons: `ended`, `expired`, `disconnected`, `authorization_changed`,
`context_changed`, `invalid_request`, `limit`, `unavailable`. Upstream failures,
model mismatch and unsupported tool calls produce fixed neutral state, never
upstream payloads or credentials. A terminal event is followed by close 1000;
transport loss may prevent delivery of that event. No HTTP session-ticket,
session-resume, credential or cross-socket end endpoint exists.

## Authorization, references and navigation

The mounted subapp does not inherit the HTTP-only `Request` dependency. It
explicitly validates origin/protocol, authenticates the actual cookie against
the account store, and revalidates throughout preparation/connection/active work.
The existing HTTP dependency remains intact. Real auth is refreshed at least
once a second and before client actions, source updates, completed transcripts
and checked output. Role/authority changes, logout, case version changes or loss
of access end the old lifetime.

Case access metadata is authorized **before** reading its full record, account
names or files. Reviewer authority, submitted-file visibility and self-owner
navigation rules use the existing policy. Shared assistant context,
completeness gaps, process fields, deterministic Section C rows and exact code
lookup are reused; at most four selected benchmarks and 64,000 UTF-8 context
bytes are included. Source article authority comes from actual lookup records,
not article numbers in user text/documents or model memory.

Upload through existing `POST /api/cases/{case_id}/files`; preserve its
draft/returned mutation gates. Use the returned file `id` in `attachment_ids` on
start/update. Voice reads only actual files scoped to the authorized current
case: at most three PDFs, three text pages and 6,000 characters per PDF. Excerpts
retain case/file/page pointers, truncation and redaction labels. Unreadable files,
scans and image-only pages remain `not_read`; filenames do not establish content.
No image payload or full PDF bytes go to Grok. No extraction becomes confirmed
facts, a Section D attachment confirmation or professional evidence automatically.

Context updates invalidate pending turns, speech and plans. Additions can be
selected while the session exists, but an in-flight utterance is discarded across
that revision; frontend behavior must make this recovery usable. Case/account
changes require end/start, not a context update.

Navigation is `engine/assist_navigation.py`'s closed destination registry, with
client offers intersected with current server authorization. Partial speech,
quoted/negated/hypothetical/mixed requests and URLs never become model tools.
The parent quotation repair `c56ed48` is a dependency. The browser must independently
check the matching identity/revision and apply the returned destination using
its native destination adapter; a plan does not prove that anything opened.
Model prose can never submit, edit, delete, archive or navigate.

Generated audio is buffered until the complete response and final user transcript
are present. Categorical safety/compliance claims, unsupported citations, known
personal text, and explicit professional/process-evidence authoring requests
withhold audio and return conservative help. This introduces response latency
and is a bounded filter, not proof of technical correctness or complete semantic
safety. Administrative completeness stays distinct from professional assessment.

## Allowance and evidence limits

One authorized start reserves **USD 0.160000 total** in the same money ledger as
text AI: one whole minute at USD 0.08 plus at most 20 non-audio upstream messages
at USD 0.004 each. This conservative policy uses the current official
[xAI voice prices](https://docs.x.ai/developers/pricing). Configuration, context,
clear and cancellation messages all count, including failed sends; a 21st
non-audio send is refused. Only audio append frames use the separate audio bound.
Accepted input and output each cap at 55 seconds of PCM bytes. The server aborts
the upstream transport after a 55-second lifetime including connect/configure,
before bounded shielded cleanup; no client timer or token TTL is the enforcement.

The entire allowance stays held after a provider attempt, including timeout,
refusal, malformed data, interruption, early end and missing usage. It is never
settled as text tokens or reported as zero provider use. A cancellation racing an
in-flight ledger operation may conservatively retain that reservation even if
connection has not begun. Auth/context failures or end during context preparation
do not reserve. Real provider billing/usage reconciliation remains an integration
limit; synthetic tests prove the app's local bounds and ledger behavior.

Tests: `engine/tests/test_voice*.py`; the PostgreSQL tests require an explicitly
owned `BATATIS_VOICE_TEST_DATABASE_URL` containing `batatis-voice-pg-`. Normal
runs skip that opt-in integration when absent. The implementation run used its
own PostgreSQL 17.11 UTF8 Unix-socket cluster and temporary case/source databases.
No paid provider calls, production/user stores or microphone were used. A local
synthetic WebSocket test exercises the real client library's abort/close behavior.
