# Application retention

Batatis uses inactivity and workflow status, rather than deleting every application seven days after creation.

| Record | Automatic deletion |
| --- | --- |
| Unsigned draft | After 7 inactive days |
| Account-owned draft | After 180 inactive days |
| Submitted, under review, or returned for changes | No automatic expiry while that process remains open |
| Accepted, refused, or withdrawn | After 730 inactive days |

This is a product policy, not a statement of a municipality's legal records obligations. Six months gives applicants time to gather material without keeping abandoned drafts indefinitely. Active administrative proceedings must remain available. Two years after final activity gives an applicant time to retain their own completed record while limiting stored personal data.

Activity means a saved content change, a successful file upload, or application correspondence, using the stored `updated_at` timestamp. Opening, polling, reading, or heartbeating a job does not extend retention. The API reports `expires_at`; it is null while review or requested changes remain open. Every write checks expiry after acquiring its lock. Failed or stale saves cannot revive an expired record.

The owner can delete sooner. Application deletion and expiry remove its files, preferences and durable background work; existing review-session cleanup removes associated package reviews. Account access revocation prevents workers from committing for that account. Workers recheck ownership/status and lease fences before committing, so deleted data cannot be recreated by a late AI result.

The engine and web display the same privacy notice. Recognized personal information is still removed before provider calls. This policy does not change third-party providers' API data-use terms or move provider processing out of the United States.

The daily authenticated retention cron and request-time sweep remain enabled. Run `python -m engine.retention` for an immediate purge. Reads and writes also enforce targeted expiry between sweeps. Backups and organization-specific retention obligations require separate operational arrangements; this policy describes Batatis's application store.
