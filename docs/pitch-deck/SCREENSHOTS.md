# Batatis deck: refresh steps and screenshot slots

**Status: `batatis-pitch-deck.pdf` is stale, and `index.html` has current text with no screenshots.** The PDF was built from the earlier slides (PR #32), before the calm interface, the merged backends and the rewritten plans, so do not submit it. `index.html` was regenerated on Oct 22 from the current `pitch-slides.md` and `pitch-narration.md`, and it shows "Screenshot pending" in every slot. The PDF is exported from `index.html` after the screens in the Implementation Plan §3 ("backend only" rows) land and the screenshots below are added.

## Refresh steps

1. Record or capture the screenshots below on the final build. Every frame that shows case data carries the EXAMPLE DATA badge, and people and addresses are fictional.
2. Save each image into `docs/pitch-deck/img/` as a PNG with the exact file name below. `index.html` shows the image when the file exists and a dashed "Screenshot pending" placeholder when it does not.
3. Run `python3 docs/pitch-deck/.build/build.py`. It reads `docs/pitch-slides.md` and `docs/pitch-narration.md` and rewrites `index.html`. Captions (6 words or fewer) live in the `SHOTS` table in `.build/build.py`, which already matches this file.
4. Export the PDF from `index.html` and replace `batatis-pitch-deck.pdf`.

## Shot list

Only built screens appear in the deck. A slide whose screen is still pending shows no shot, so the deck never pictures a screen that does not exist yet.

| Slide | Placeholder id | Caption | What to capture | File |
|---|---|---|---|---|
| 2 | `shot-s02-describe` | Describe: one box, one question | The Start screen: the headline "What are you building differently?" and the description box | `img/shot-s02-describe.png` |
| 2 | `shot-s02-question` | One question at a time | A question card in the deck with "Why we ask" open | `img/shot-s02-question.png` |
| 4 | `shot-s04-code-check` | Code check card and code drawer | A code check card for the example article with the verbatim text in the drawer | `img/shot-s04-code-check.png` |
| 5 | `shot-s05-library` | Code library with relevance rings | The code library reader with the relevance ring on an article | `img/shot-s05-library.png` |
| 6 | `shot-s06-engineer` | Engineer callout on the review | The review screen showing the engineer callout and Sections A to D | `img/shot-s06-engineer.png` |
| 7 | `shot-s07-queue` | Officer queue with claim | The reviewer queue with "Start reviewing" | `img/shot-s07-queue.png` |
| 7 | `shot-s07-sheet` | Paper sheet with completeness list | An application as a paper sheet beside its completeness list | `img/shot-s07-sheet.png` |
| 8 | `shot-s08-onboarding` | Onboarding sets the applicant type | The onboarding question: manufacturer, general contractor or homebuilder | `img/shot-s08-onboarding.png` |
| 9 | `shot-s09-application` | Draft or official PDF, gated | The application screen with the download panel | `img/shot-s09-application.png` |
| 9 | `shot-s09-scc-form` | Council form, officer part blank | The downloaded SCC variance form: unsigned, officer Part 2 blank | `img/shot-s09-scc-form.png` |

Slides 1, 3, 10, 11 and 12 have no product shot.

## Pending screens (not in the deck until they exist)

These need their own capture after the screens land. Add a shot and a `SHOTS` entry for each.

- The intake reader's facts with a pointer to the source words, and the five-question planner (slide 2).
- Code identification's quoted choices and the benchmark acceptable-solution record (slide 4).
- The jurisdiction picker and process notes (slide 9).
- The officer package review: findings, the drafted information request, the "x of y gaps resolved" diff, and the close-out record (slide 7).
