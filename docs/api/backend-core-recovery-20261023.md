# Verified backend core restoration — 23 October 2026

Base: `c3d7966746ca8ce14de57c8e738d55127875cfe4`. This local commit restores only the
compatible U2/U3/U4/U7 core. Reader/export and journey changes are preserved separately
as a **held candidate**, not part of this core or a release approval.

| Included source | Scope |
| --- | --- |
| U3 `9f01f617` | Selected-article models/routes, PostgreSQL projection, schema exporter and tests. |
| U4 `a0b73ef6` | Explicit comments navigation, role/status eligibility and tests. |
| U2 `567d0ead` | Typed PDF grounding, verified excerpts, context/file revalidation and tests; U4 overlap deduplicated. |
| U7 frozen R4 | `providers.py`, `screen.py`, `jev_runtime.py`, `test_jev_runtime.py`; all four byte-identical to the saved U7 edits and frozen R4. |

The exact core index tree was exported into an owned clean snapshot with the existing code
database copied to its ignored build directory. The canonical `.venv` ran:

```text
python -m pytest -q engine/tests/test_selected_articles.py \
  engine/tests/test_assist_comments_navigation.py engine/tests/test_assist_documents.py \
  engine/tests/test_jev_runtime.py --tb=short
252 passed, 51 skipped, 3 warnings in 40.08s
```

The 51 skips require an owned PostgreSQL database. The three warnings concern pytest's
`record_property`/xunit2 reporting compatibility. The core schema was exported to the
external backup and checked against that same output successfully. Generated web contracts
were deliberately not edited; the parent serializes generation after integration.

The original selected-article regression returned 404 on the starting backend. In the
verified core, persistence/reopen, owner authorization, current-version conflicts, deletion,
revocation and concurrent-write tests pass for SQLite. This is offline/local evidence only.

## Current-client compatibility

No required decision, submission or receipt fields are added by this core. Existing assistant
requests remain valid; document binding fields are required only when selecting that optional
new document capability. Assistant/selection response additions are additive. The parent's
composed U2/U3/U4 client already implements those capabilities; no UI file was authored here.

The separate journey candidate requires a displayed `expected_version` for refusals and rejects
a refusal correction checklist. Its P14 guard and newer concurrency tests are retained, not
weakened. Current UI `cc7e37c5` does not send that revision, so **hold the candidate until the
matching client patch is restored**. Optional submission versions and legacy empty receipt
bodies are compatible, but their improved client behavior remains pending. Professional
handoff controls, evidence file binding/opening, decision/history projections, displayed-message
receipts, resubmission/expiry UI and account/application cancellation also remain client work.

The held reader/journey broad diagnostic had 113 failures, 15 errors, 3035 passes and 770 skips.
It is not the verification result of this core. Its detailed manifest and bounded later repairs
remain in the separate held commit and backup, without a full-green claim.

## Preservation and exclusions

- No original worktree, branch, untracked file, environment, secret, runtime or counter was changed.
- U1/U7's eight original unfinished file hashes still match the recovery backup.
- The parent's original untracked visibility test and journey audit remain untouched.
- No server, live provider call, runtime freeze/resume, push, PR or remote write was performed.
- Jev source restoration enables no live mode or uncapped configuration. Separate exact-source
  review, spend reconciliation, runtime transition/rollback and authorized live verification remain held.
- Parent-owned reader companion changes are preserved in `batatis-backend-parent-companion.patch`:
  tracked template bundling in `vercel.json` and avoiding implicit legacy-form fetch under
  `--codes-only` in `scripts/fetch_sources.py`.

Durable files, full candidate tar/patch, clean core snapshot metadata, schema and raw test logs/XML:
`/Users/aamia/.t3/backups/batatis-recovery-20261023T143349Z/backend-integration-ad54298b/`.

Methods actually read/applied: T3 workflow `SKILL.md`, `references/routes.md` and
`references/visual-evidence.md`; Matt Pocock `engineering/diagnosing-bugs/SKILL.md` and
`engineering/code-review/SKILL.md`; pstack `poteto-mode/playbooks/bug-fix.md`; repository
`batatis-hackathon/SKILL.md` and `batatis-variance-workflow/SKILL.md`. No further delegation.
This core has no separately authored UI surface; parent owns server/browser evidence.
