# Accounts and administrative review API

Implemented on `api/accounts-review`, based on `f48c797`. No deployment, push, or PR.
All results described here are local or offline test evidence. This API checks
administrative completeness; acceptance does not establish technical correctness,
equivalent performance, professional authentication, or permission to build.

## Routes

| Route | Behavior |
| --- | --- |
| `GET /auth/providers` | Password, plus configured Google/Microsoft providers only. |
| `POST /auth/signup` | Email/name/password; 201 `{user}`, duplicate email 409. |
| `POST /auth/login` | `{user}` and rotated cookie, generic incorrect-credentials 401. |
| `POST /auth/logout` | Delete server session and cookie; 204. |
| `GET /auth/me` | `{user}`, or 401. |
| `POST /auth/onboarding` | Applicant type, or authority plus reviewer access code. |
| `GET /auth/oauth/{provider}/start?redirect=/path` | Browser-bound state, nonce and S256 PKCE; 302. |
| `GET /auth/oauth/{provider}/callback` | Verified OIDC/token/userinfo exchange, session and web redirect; 302. |
| `POST /cases` | Sets owner from the cookie; anonymous creation remains available. Optional `authority`; otherwise the jurisdiction id is used for owned cases. |
| `GET /me/applications` | Owner's applications newest first, reviewer name and unread count. `completeness` is null: list requests do not run the expensive full checker. |
| `POST /cases/{case_id}/submit` | Owner only; same `check_completeness` as GET gaps. Blocking findings return 409 `detail: {message, gaps}`; otherwise submitted with timestamp. |
| `GET /review/queue?status=&mine=` | Reviewers only, authority-scoped; claim, decision, applicant summary and unread count. Completeness is null. |
| `POST /review/{case_id}/claim` | Claim/idempotent self-claim; conflict is 409 with top-level `detail` and `claim`. `take_over: true` records both names in history. |
| `DELETE /review/{case_id}/claim` | Current claimer only, before a decision; 204 and status submitted. |
| `POST /review/{case_id}/decision` | Current claimer, in review. `accept` or `return`; return needs a message of at least 10 characters. Returns the case. |
| `GET /cases/{case_id}/messages` | `{messages}` with caller-relative `read_by_me`. |
| `POST /cases/{case_id}/messages` | Signed-in owner or authorized reviewer; plain text, 1–4000 characters, nonblank; 201 message. |
| `POST /cases/{case_id}/messages/read` | Mark existing messages read for this caller; 204. |
| `POST /assist` | Authorized optional case context, screen/focus/question and up to eight history entries. Answer, verified cited ids, removed ids and provider notice. |

The status machine is `draft → submitted → in_review → returned | accepted`,
with `returned → submitted` resubmission. Resubmission clears the current claim
and decision; previous decisions/messages/history remain in the case. Withdrawal
is optional in the contract and no withdrawal endpoint is implemented.

Owned applications allow content edits only while draft or returned. A blocked
edit returns 409 `Submitted applications are read-only until returned`. Owners
may delete their application in any status. Updating an owned case's jurisdiction
also updates its reviewing authority. A role change in either direction requires
an authority code: applicants use the target authority's code; reviewers leaving
the role use their current authority's code. This prevents switching role through
a less restrictive onboarding payload. Privilege changes invalidate all existing
sessions and issue a fresh session.

## Central access policy

`engine/access.py:authorize_case` and the application-wide dependency protect all
case path routes, including routers subsequently included by the code-library
branch. Metadata reads preserve existing endpoint snapshot/CAS timing. Stores
recheck access on snapshots and content writes under their existing transaction
locks. Unowned legacy cases retain anonymous read/write behavior. New message
posting/read receipts require a signed-in author.

For owned cases, the owner may read. A reviewer may read only when their authority
matches and status is submitted, in_review, returned or accepted. Reviewers cannot
write applicant facts, selections, jurisdiction, evidence or files. Unauthorized
case access returns 404. Review operations additionally require a reviewer role
and current claim as appropriate. Messages remain available while content is locked.

Guarded existing routes:

- `GET /cases/{case_id}`
- `POST /cases/{case_id}/facts`
- `POST /cases/{case_id}/files`
- `DELETE /cases/{case_id}`
- `POST /cases/{case_id}/export` (read permission)
- `PUT /cases/{case_id}/jurisdiction`
- `POST /cases/{case_id}/section-d` (write permission, including rebuilds)
- `GET /cases/{case_id}/section-d/issues`
- `GET /cases/{case_id}/professional`
- `GET /cases/{case_id}/process-fields`
- `GET /cases/{case_id}/gaps`
- `POST /cases/{case_id}/evidence`
- `DELETE /cases/{case_id}/evidence/{evidence_id}`

All new submission, review and message routes use the same policy. `/assist`
explicitly authorizes its JSON `case_id` before constructing context. The branch
has no case-specific identify, file-download, or relevance route; new path-based
case routes inherit the dependency. A regression test includes an unmodified
router after app creation and checks this protection. Merge verification should
still exercise the concurrent branch's actual relevance route.

The evidence DELETE route retains its base-commit version-body contract. The base
suite has conflicting expectations about no-body evidence withdrawal; this change
does not alter that contract.

## Persistence and retention

Both `CaseStore` (SQLite/file default) and `PostgresCaseStore` use the new account
store adapters. Additive `CREATE TABLE/INDEX IF NOT EXISTS` migrations create
`account_users`, `account_sessions`, `account_identities`, `account_oauth`, and
`account_rates`, plus session expiry/user indexes. PostgreSQL appends these to its
existing `MIGRATIONS`; no existing tables are dropped or rewritten.

Ownership, authority, status, submission timestamp, claim, decision, status history,
and messages/read receipts live in the case JSON. All workflow/thread mutations
use the existing case version CAS, retrying against fresh state. Thus deletion
and the existing seven-day **creation-based** case retention remove messages,
history, decisions and files with the case, on both backends. Submitting or
messaging does not extend that seven-day window. User accounts remain durable.
Sessions expire after 30 days of inactivity, refreshed on successful authenticated
requests; OAuth exchanges expire after ten minutes. Account expiry cleanup runs
with normal case purge transactions and when creating sessions/OAuth exchanges.
The existing retention CLI and cron therefore also clean expired account records.

## Configuration and security receipt

| Check | Implementation / evidence |
| --- | --- |
| Password storage | `hashlib.scrypt`: N=131072, r=8, p=1, dklen=64, random 32-byte per-user salt, 256 MiB maxmem. Passwords need 10–1024 characters. Password hashes/salts are internal account data only. |
| Timing comparisons | `secrets.compare_digest` for password hashes, reviewer codes, OAuth state/nonce and userinfo subject. Missing/OAuth-only accounts pay the same scrypt cost. |
| Sessions / fixation | Random 32-byte tokens; only SHA-256 digests stored. Login and OAuth completion rotate/invalidate the presented old session. Logout deletes the server record. Tested rotation, expiry, refresh and logout. |
| Cookies | `batatis_session`, HttpOnly, SameSite=Lax, path `/`, 30 days; Secure unless request hostname is localhost/127.0.0.1/::1. Use HTTPS and trusted proxy/Host configuration in hosting. |
| CSRF / CORS | Every changing `/auth/*` route requires `Content-Type: application/json` (415 otherwise). SameSite=Lax cookies. CORS allows credentials for the existing localhost regex and `BATATIS_WEB_ORIGIN`; arbitrary remote origins are denied. |
| Rate limits | Durable hashed IP signup/OAuth/onboarding buckets, login IP+email and aggregate IP buckets. `BATATIS_AUTH_RATE_LIMIT` default 10; `_WINDOW_SECONDS` default 600. Assistant adds the existing process-local LLM/IP limit and `BATATIS_ASSIST_RATE` (or `_LIMIT`), default 12/600s. |
| IDOR | Owner/other applicant/same-authority reviewer/other-authority reviewer/anonymous matrix, every current case route, messages, claims and decisions. Concurrent claim test has one winner. Store write guards close edit/submit races. |
| Logs / caches | Engine logs method/path/status, never bodies, emails, passwords or provider error text. Sensitive routes carry no-store. Run Uvicorn with `--no-access-log` so its separate access logger does not record OAuth callback query parameters. |
| OIDC | Signed RS256 JWT verification through PyJWT/cryptography; audience, expiry, issued-at, issuer, nonce and subject checks; verified Google email; browser state cookie, one-use server state and S256 PKCE. Tests use signed fake tokens and `httpx.MockTransport`; no network. |
| Identity linking | Provider issuer+subject owns identity. Matching email never silently attaches an existing password account; conflict returns 409. Microsoft email is display metadata. |
| Redirects | Relative absolute-path redirects only; scheme, network paths, decoded backslashes/control characters rejected. Final origin is server configuration. |

Provider variables: `BATATIS_GOOGLE_CLIENT_ID`, `BATATIS_GOOGLE_CLIENT_SECRET`;
`BATATIS_MICROSOFT_CLIENT_ID`, `BATATIS_MICROSOFT_CLIENT_SECRET`,
`BATATIS_MICROSOFT_TENANT`. Microsoft uses a tenant GUID, `common`,
`organizations`, or `consumers`; tenant-domain aliases are rejected during token
validation. Set `BATATIS_WEB_ORIGIN` (default `http://localhost:5480`) and optionally
`BATATIS_API_ORIGIN` to a trusted public API origin. The `/api` deployment prefix
is preserved in callback URLs. `BATATIS_REVIEWER_CODES` is a JSON authority→code
object; missing codes close reviewer signup with the specified 403 detail.

Seed a reviewer with `python -m engine.accounts create-reviewer --email ...
--name ... --authority edmonton`. It prints a random bootstrap password once to
stdout and stores only its scrypt hash. **The bootstrap password is not currently
enforced as single-use and there is no password-change/recovery endpoint.**

The OIDC implementation follows the primary provider descriptions:
[Google OpenID Connect](https://developers.google.com/identity/openid-connect/openid-connect)
and [Microsoft authorization-code flow](https://learn.microsoft.com/en-us/entra/identity-platform/v2-oauth2-auth-code-flow).

## Assistant boundaries

Anthropic `claude-sonnet-5-5` is preferred when its key is configured; otherwise
OpenAI uses `llm_gate.DEFAULT_MODEL`. No Haiku model. `BATATIS_LIVE=1` and the selected
provider's key are required; otherwise 503 `Assistant unavailable`. Full maximum
output and a conservative UTF-8-byte input bound are reserved through `llm_gate`.
Usage reconciles successful calls; uncertain failed calls retain the reservation.

Context uses the authorized application's facts, gaps, process fields, focused
card/message, and focused provision's verbatim database text plus deterministic
Section C rows. Questions are capped at 1500 characters and history at eight
user/assistant entries. History is untrusted user-message data. Assistant history
is not persisted. The provider-specific notice describes this disclosure.

The system prompt forbids invented articles, compliance/safety determinations,
professional evidence drafting, and authoring the applicant's risk, mitigation or
assumptions passages. Explanations and questions are permitted. A post-check
replaces nonexistent article/sentence ids with `[unknown reference removed]` and
lists them. Generated categorical words `approved`, `compliant`, `complies`, and
`safe` trigger conservative help text. Model instructions remain a probabilistic
control, not a guarantee against every misleading paraphrase. Existing global
privacy meta text still describes OpenAI; the assistant's `notice` and header
identify its actual selected provider. Frontend/privacy-copy reconciliation is
outside this backend-only change.

Server decision text uses **“Accepted as administratively complete”** or
**“Returned for administrative information”**. It never generates “approved”,
“compliant”, “complies”, or “safe”. User-authored messages and reviewer notes are
stored verbatim as text; clients must render them as text, never HTML.

## Verification and limits

Baseline: 613 passed, 15 failed, 216 skipped at `f48c797`. The isolated Python
invocation initially needed pytest `-o pythonpath=.`; the final requested command
without `-I` runs directly from this checkout. Final result: **680 passed, 15
failed, 216 skipped** in 27.05 seconds. All 15 failure ids match the baseline;
there are zero new failures and 67 additional passing tests. Schema checks and
`git diff --check` pass. Full receipt: `/tmp/accounts-review-final-suite.txt`.

The HTTP script `python -m engine.tests.e2e_accounts_review` completed on port 8040:
signup/onboarding → owned application → blocked submission → public facts,
deterministic benchmark selection and synthetic PDF upload → submit → queue →
claim → second-reviewer 409 → return/message → unread/read/reply → resubmit →
accept → edit rejected. No identify/model call was needed to pass the real gap
checker. The fixture retained the officer-routed professional-engagement warning;
it asserts no real professional evidence. `/assist` returned 503 without keys.
Transcript: `/tmp/accounts-review-e2e.txt`. The server was stopped.

File-store/API, signed-token OIDC and fake-model assistant tests ran locally.
No PostgreSQL server/TEST_DATABASE_URL or provider credentials were available;
real PostgreSQL, real-provider OAuth/assistant and production behavior remain
unverified. No new UI was implemented, so there is no visual capture.

Regenerated only `web/src/api/engine.schema.json` and `types.gen.ts` with
`python -m engine.schema_export` and `node web/scripts/gen-types.mjs`. The schema
exporter explicitly includes the new auth/review/message/assistant wire models.

Methods used: T3 workflow feature route; pstack `poteto-mode/playbooks/feature.md`;
Matt Pocock `engineering/tdd`, `codebase-design`, and `code-review`. Review applied
the standards/spec axes locally because delegation was explicitly prohibited.
The route map supplied no dedicated security-review method; the contract's
security checklist above governed the security pass. Workflow maintenance was
read-only and reported model-preferences drift; intentional configuration was kept.
