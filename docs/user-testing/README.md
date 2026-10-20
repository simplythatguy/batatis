# User-testing protocol (appendix to the Implementation Plan)

This folder describes the user testing **we would run** on Batatis with real applicants and Safety Codes Officers (SCOs). No real-user or officer sessions have been run yet. Simulated AI-agent sessions (Round S) are reported separately and labelled SIMULATED. Every number in a results table is blank until a session takes place.

Batatis checks alternative-solution (variance) applications under NBC(AE) 2023 for **administrative completeness, not technical correctness**. The tests measure that claim.

| File | What it is |
|---|---|
| `session-script.md` | 20-minute moderated think-aloud for applicants (Round 1, and an optional retest of Round 1 after fixes (same tasks)), with SUS and a compact findings table |
| `consent-form.md` | One-page plain-language consent with recording opt-ins |
| `officer-timing-protocol.md` | Round 1b. Within-subjects timing comparison for SCOs: manual checklist vs Batatis on a planted-gap package |

## Rounds
- **Round S (simulated):** AI-agent first-timer sessions. Reported separately and labelled SIMULATED. This folder does not record those results.
- **Round 1 (real applicants):** 3 applicants (homebuilder, general contractor, manufacturer or designer) on the think-aloud script. We fix S1/S2 findings afterwards.
- **Optional retest of Round 1 after fixes (same tasks):** after the fixes, with new participants where possible. Same tasks as Round 1. We compare task success, time on task, first stuck point and SUS with Round 1.
- **Round 1b (real officers):** 1–2 SCOs or permit staff on the timing protocol (manual checklist vs Batatis).

## How to run a session
1. Use a build that has the full workflow (Describe your idea → Code check → Section C → Application). Record the commit.
2. Round 1 applicants receive only a project brief and drawing notes. The planted-gap SCO package and its answer key are for Round 1b only. They are not in this repo; they will be added under evals/demo-cases/ in a separate PR. Example documents are labelled EXAMPLE DATA. Never show the answer key to a participant.
3. Get a signed consent form, then follow the script or protocol word for word. Fill in the tables during or right after the session.

## What the evidence supports
- **Usability and Portability (10%):** task success, time to a finished application, first stuck point, SUS, and the officer side (would an SCO open it twice?).
- **General Applicability (5%):** results by role (homebuilder, GC, manufacturer, designer, SCO).
- **Review (10%):** officer time saved vs the manual checklist, gap recall, false positives.
- **Implementation Plan (10%):** Round 1 findings, then fixes, then the optional retest ("How will the product testing with users inform final design?").
- **Business Plan (10%), optional:** time saved, only once there's real data.

With small samples (n < 10), results are **indicative only**. We will report raw numbers per participant and will not claim statistical significance.

The project owner decides who runs the sessions and whom to invite. This is not a university REB-approved study (see `consent-form.md`).
