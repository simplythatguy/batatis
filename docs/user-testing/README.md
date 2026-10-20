# User-testing protocol (appendix to the Implementation Plan)

This folder describes the user testing **we would run** on Batatis with real applicants and Safety Codes Officers (SCOs). No sessions have been run yet, and these files contain no results. Every number in a results table is blank until a session takes place.

Batatis checks alternative-solution (variance) applications under NBC(AE) 2023 for **administrative completeness, not technical correctness**. The tests measure that claim.

| File | What it is |
|---|---|
| `session-script.md` | 20-minute moderated think-aloud for applicants (Rounds 1 and 1b), with SUS and a compact findings table |
| `consent-form.md` | One-page plain-language consent with recording opt-ins |
| `officer-timing-protocol.md` | Within-subjects timing comparison for SCOs: manual checklist vs Batatis on a planted-gap package |

## Rounds
- **Round 1 (baseline):** 3–5 applicants (homebuilder, general contractor, manufacturer or designer), plus 1–3 SCOs or permit staff on the timing protocol. We fix S1/S2 findings afterwards.
- **Round 1b (retest):** after the fixes, with new participants where possible, same tasks plus 1–2 trap tasks. We compare task success, time on task, first stuck point and SUS with Round 1.

## How to run a session
1. Use a build that has the full workflow (Describe → CodeCheck → SectionC → Application/export). Record the commit.
2. Have the sample files ready (`unc-samples/01`, `02`, `03`). All of them are labelled EXAMPLE DATA. Never show `03-sco-bundle-TESTER-KEY.md` to a participant.
3. Get a signed consent form, then follow the script or protocol word for word. Fill in the tables during or right after the session.

## What the evidence supports
- **Usability and Portability (10%):** task success, time to a finished application, first stuck point, SUS.
- **General Applicability (5%):** results by role (homebuilder, GC, manufacturer, designer, SCO).
- **Implementation and Business Plan:** officer review speed-up and gap recall.

With small samples (n < 10), results are **indicative only**. We will report raw numbers per participant and will not claim statistical significance.

The project owner decides who runs the sessions and whom to invite. This is not a university REB-approved study (see `consent-form.md`).
