# Independent UI review — accuracy95 R2

## Review pin and scope

- Branch: `work/luna-accuracy-95-20261025`.
- Base and `HEAD`: `e5e794b6ab828afdfc52858cf3ed75d39e62a73c`.
- The worker implementation is uncommitted: `QuestionDeck.tsx` is modified and the four `DocumentReview` files are untracked. The review is pinned to these content hashes:

| File | SHA-256 |
|---|---|
| `web/src/calm/DocumentReview.tsx` | `9260460c9c91ce41eddb47495301ea9d58fa928d2545bbcbed1a3ec94265997c` |
| `web/src/calm/DocumentReview.css` | `c265288179a2feef8eb142462dedc1f32853f0d59cf5a6d68b2969a197ccbcec` |
| `web/src/calm/DocumentReview.test.ts` | `deeb710dadf14753d1f6c09432a4432093d9accf6e8567f8b9d1362a11e4a1c5` |
| `web/src/calm/DocumentReview.test.tsx` | `f64365757b916fa0eea248ee25aa519289bd8947f87fc20611f5af6b9d537598` |
| `web/src/calm/QuestionDeck.tsx` | `7aa9b8e3a8527bd87e608dbd322a7ebc6277cacc084e0b41bfccebcafae13dbc` |

Reviewed only those files and the data/persistence paths needed to establish their behavior. No source files were changed; this report is the only workspace file written. No provider, inference, or other API calls were made, and no delegation, push, commit, server, or port changes were performed.

## Findings

### [P1] Reopening after a description edit can present the previous review as current

**Locations:** `web/src/calm/DocumentReview.tsx:65-80`; `web/src/store.tsx:1111-1121`; `web/src/calm/openCase.ts:152-156`; `web/src/calm/Start.tsx:102-109`; `web/src/model.ts:705-706`; `engine/intake/service.py:117-120`; `engine/store.py:297-303`.

**Trigger:** Run intake, edit and save the description without running intake again, then close and reopen the case.

The intake record stores a hash of the description it reviewed (`engine/intake/service.py:118`). Saving a changed description adds/replaces a case fact but preserves the existing intake record (`engine/store.py:297-303`). On reopen, `readSavedCase` returns that old record, then `openedCase` restores it with `text: c.description.trim()` (`openCase.ts:155`). That substitutes the new description for the original reviewed text. `DocumentReview` compares this substituted text to the current description, so it does not set `Previous input`; it can show `Model checked` with the old facts, citations, and suggestions. The Start action uses the same comparison and can also skip the needed re-read (`Start.tsx:106`).

This can attach an old source excerpt or recommendation to the applicant's current description without a freshness warning. Same-session edits are labeled `Previous input`, but that protection is lost on reopen. Keep the actual reviewed-input identity through persistence and suppress or mark results stale when it differs. This component itself does not write canonical facts or gaps.

The focused component suite passed, but its reopen fixture uses a matching current description and intake text (`DocumentReview.test.tsx:75`); its changed-description case checks only the `Previous input` label (`DocumentReview.test.ts:125-135`). The 18 passing `openCase.test.ts` cases do not cover a stored `text_sha256` mismatch.

### [P2] Unknown review statuses still display model-generated flags

**Locations:** `web/src/calm/DocumentReview.tsx:73-83`; `web/src/calm/DocumentReview.test.ts:114-120`; `web/src/calm/DocumentReview.test.tsx:56-57`.

`findings` is restricted to `live` and `fake`, but `flags` is populated for every state except pending intake or intake error. The unknown-status fixture retains the live result's `outside_alberta` and `code_edition` flags. Selecting it shows an `Unknown` heading while those flag claims remain in the Flags group. The status note does not identify those individual claims as unsupported, and flags can contain model text without an evidence excerpt. The backend distinguishes successful model flags from the deterministic unread-page flags returned on `failed` or `gate_closed` (`engine/intake/review.py:689-693,720-725`).

Keep only status-appropriate flags: for example, preserve deterministic `not_read` flags on `failed`/`gate_closed`, show all validated flags for `live`/`fake`, and suppress model flags for `off`, `not_needed`, or an unknown status. The current test checks the heading and hides source facts, but does not assert that the model flags are absent.

## Findings that checked out

- The new surface is reachable above the Questions deck and reads the persisted `IntakeRecord.review`. Source facts show their status; evidence disclosures expose the exact excerpt, source name, and page. Conflicts show both excerpts. Cited provisions separate the document's edition from the current Alberta number lookup and state that applicability still needs Section C confirmation.
- Evidence-to-request and next-question rows are identified as model suggestions and explicitly do not add blocking gaps. The component accepts only `intake`, `files`, `description`, and read status props; it has no store dispatch or mutation path. `QuestionDeck` also excludes the component from deck keyboard shortcuts. I found no component path that changes canonical facts, shared gaps, or their blocking status.
- `off`, `failed`, `gate_closed`, `not_needed`, `fake`, pending intake, and intake error have distinct visible labels/copy. The focused tests verify the source/edition display, unknown source fallback, keyboard disclosure, unread page reporting, and that the unit fixture makes no HTTP requests.

## Verification and limits

- `DocumentReview.test.ts`: **10 passed, 0 failed** using the repository's real Chromium component fixture. It covers keyboard Enter/Tab behavior and 390px/320px layout and checks for page overflow/clipping.
- `openCase.test.ts`: **18 passed, 0 failed**. It exercises saved-case restoration but not document-review freshness against the persisted input hash.
- I did not run typecheck, build, or the full suite because the parent verification was already running. I found no project Lint Apple package/configuration or suitable integration, so that coverage is absent.
- I inspected the supplied component-only images at 1440×900 and 390×844: `/var/folders/kb/p8qx9n8s4x19f367fybbdk1w0000gn/T/batatis-document-review-unit-ngUDmw/component-desktop.png` and `/var/folders/kb/p8qx9n8s4x19f367fybbdk1w0000gn/T/batatis-document-review-unit-ngUDmw/component-mobile.png`. The excerpt and metadata remain legible and the phone capture has no horizontal clipping. These are unit-fixture visuals, not whole-app acceptance. Whole-app preview/capture remains parent-owned; the supplied T3 snapshot attempts timed out with `Preview automation snapshot timed out after 15000ms.` The user-owned port 3000 and active Arc session were left untouched.

## Methods used

- T3 route and UI evidence guidance: `/Users/aamia/.codex/skills/t3-workflow/SKILL.md`; `/Users/aamia/.codex/skills/t3-workflow/references/routes.md`; `/Users/aamia/.codex/skills/t3-workflow/references/ui-quality.md`; `/Users/aamia/.codex/skills/t3-workflow/references/visual-evidence.md`.
- Matt Pocock code review: `/Users/aamia/.agents/skill-libraries/mattpocock/skills/engineering/code-review/SKILL.md` (adapted to the explicit no-delegation boundary).
- Open Pstack TypeScript methods: `/Users/aamia/.agents/skill-libraries/pstack/skills/typescript-best-practices/SKILL.md`; `/Users/aamia/.agents/skill-libraries/pstack/skills/principle-type-system-discipline/SKILL.md`.
- UI quality method: `/Users/aamia/.agents/skills/better-ui/SKILL.md`.
- Batatis contracts: `/Users/aamia/.t3/worktrees/batatis/work-luna-accuracy-95-20261025/AGENTS.md`; `/Users/aamia/.t3/worktrees/batatis/work-luna-accuracy-95-20261025/.cursor/skills/batatis-hackathon/SKILL.md`; `/Users/aamia/.t3/worktrees/batatis/work-luna-accuracy-95-20261025/.cursor/skills/batatis-variance-workflow/SKILL.md`; `/Users/aamia/.t3/worktrees/batatis/work-luna-accuracy-95-20261025/.cursor/skills/batatis-ui-linear/SKILL.md`; `/Users/aamia/.t3/worktrees/batatis/work-luna-accuracy-95-20261025/.cursor/skills/batatis-ui-opus/SKILL.md`; `/Users/aamia/.t3/worktrees/batatis/work-luna-accuracy-95-20261025/.cursor/skills/batatis-ui-minimalist/SKILL.md`; `/Users/aamia/.t3/worktrees/batatis/work-luna-accuracy-95-20261025/docs/design-system-calm.md`.
