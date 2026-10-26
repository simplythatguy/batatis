# Dependable applicant saves

`PATCH /cases/{case_id}/draft` saves changed answers and unfinished editors together. It never calls a provider, identifies a code, changes professional evidence, or waits for a background job. Use the saved case as the acknowledgement; do not reload intake, identification, and the case after each save.

```json
{
  "expected_version": 12,
  "facts": [{"id":"answer-owner-2","field":"owner_name","value":"Applicant name","kind":"pointed","status":"confirmed","source":{"type":"user_text","ref":"Applicant","quote":"Applicant name"}}],
  "applicant_draft": {
    "role": "owner",
    "question_text": {"permit": {"base":"","value":"Unfinished permit answer"}},
    "skipped": ["risk"],
    "packages": {"offered-package":"no"}
  }
}
```

The response is the full current `Case`, including its committed `version`, `updated_at`, and `applicant_draft`. `facts` contains only changed revisions, including explicit withdrawals. Existing revisions not named by id stay in their original order; changed ids move to the end. An unchanged revision is a no-op. The store writes only changed JSON paths and fact deltas in one transaction, preserving messages, workflow history and AI output. PostgreSQL still uses its normal JSONB/MVCC physical storage; this is not a claim of in-place disk updates.

`jurisdiction` and `selected_articles` can be included in the same patch. Omission retains the saved value; `jurisdiction: null` clears it; `selected_articles: []` clears the card selection. Card selections never confirm code references. `applicant_draft: null` clears unfinished editors. Otherwise that property replaces the whole bounded applicant draft. It contains unconfirmed question text, choices, skips, standing-package choices, uncertainty choices, applicant role and unfinished document editors. Those values never satisfy completeness or establish evidence, credentials or technical acceptance.

Only public fact source types accepted by the existing answer route are accepted. A confirmed attachment must refer to bytes owned by this application. Unknown properties and authority/workflow fields are rejected. Existing ownership, submitted-record read-only access, provider redaction and deletion rules apply.

A stale `expected_version` returns `409` and commits nothing. Keep the applicant's local text visible and unsaved; reconcile explicitly. Do not silently fetch the newest version and overwrite another device's changes. Missing, deleted, expired and inaccessible records return `404`; never recreate them automatically.

The browser must mark every typed change dirty synchronously, debounce/coalesce writes, and show Saved only when the latest displayed revision and all unfinished editors were acknowledged. Flush before switching applications, New application, submission and exports. Keep the current draft open after a failed flush. Protect unacknowledged text and held files on browser unload. Application content must not be copied to browser storage; account-scoped case identifiers may be stored to reopen through the authorized API.

Slow computation belongs in the [durable job runtime](jobs.md). Save the input first, enqueue quickly, then observe progress outside the save queue. A successful job is not an acknowledgement of newer typed edits.

`applicant_draft.intake_file_ids` preserves the selected reading uploads before
and after intake. `[]` explicitly removes all reading inputs; null identifies a
legacy snapshot whose last intake file IDs can be restored. Only uploads owned
by this application are accepted. Names and other upload metadata come from the
existing file inventory on reopen, rather than a second browser copy. Failed
uploads remain unsaved and require the open browser to retry their held bytes.
