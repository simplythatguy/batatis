# Batatis deck: screenshot slots

Drop each image into `deck/img/` with the exact file name below (PNG). `index.html` shows the image automatically when the file exists and shows the dashed placeholder when it doesn't. Re-export the PDF after adding images.

Shots 1 to 7 follow the PR #20 demo script (`docs/demo/script.md`, not merged), filmed on PR #16's screens (in review), not on `dev`. Case text comes from the PR #14 demo cases. People and projects are fictional: every frame showing case data must carry an **EXAMPLE DATA** label. The slot on slide 9 for the filled SCC form is extra and not in the PR #20 shot list.

| # | Placeholder id | Slide | What to capture | Source label | File |
|---|---|---|---|---|---|
| 1 | `shot-s08-roles` | 8: One tool, three kinds of first-time applicants | "Who are you?" role picker: Manufacturer, General contractor, Homebuilder (PR #20 shot 1, 0:00–0:18) | PR #16 screen (in review) · EXAMPLE DATA | `img/shot-s08-roles.png` |
| 2 | `shot-s02-describe` | 2: Describe your project in plain words | Case C (homebuilder) description pasted on Describe, authority set to Edmonton, **Review gaps** listing owner, mailing address and legal description as missing, no upload (PR #20 shot 2, 0:18–0:28) | PR #16 screen (in review) · EXAMPLE DATA | `img/shot-s02-describe.png` |
| 3 | `shot-s03-not-sure` | 3: It asks before it guesses, and we test that | After reset, manufacturer description pasted; two "Your words" cards on Code check, both answered **Not sure** and logged as open questions (PR #20 shot 3, 0:28–0:51) | PR #16 screen (in review) · EXAMPLE DATA | `img/shot-s03-not-sure.png` |
| 4a | `shot-s04-search` | 4: A ranked shortlist, measured against a named acceptable solution | Code search for the bedroom window, the returned row added to the check, and its Section C row looked up from the attribution tables (PR #20 shot 4, 0:51–1:36) | PR #16 screen (in review) · EXAMPLE DATA | `img/shot-s04-search.png` |
| 4b | `shot-s04-benchmark` | 4 | PR #12 identify output and benchmark card (PR #20 shot 4). The pasted homebuilder case isn't a seeded case, so without a model key the ranked-list still must be labelled as keyword search with no AI key | PR #12 still, labelled "not in this app build" · EXAMPLE DATA | `img/shot-s04-benchmark.png` |
| 4c | `shot-s05-eval` | 5: Every citation resolves, or it's dropped | Eval still with one labelled line per variant, as in pitch-outline.md Part B (PR #20 shot 4) | Eval still, labelled model-checked | `img/shot-s05-eval.png` |
| 5 | `shot-s06-section-d` | 6: It knows where to stop | Alternative path with its six fields left empty; Section D card with the line "This tool does not write the evidence or the professional opinion." (PR #20 shot 5, 1:36–2:08) | PR #16 screen (in review) · EXAMPLE DATA | `img/shot-s06-section-d.png` |
| 6 | `shot-s07-officer` | 7: Completeness review: built in the engine, officer screen in review | Officer review screen: one planted sample package, before and after fixes; **Copy request** (PR #20 shot 6, 2:08–2:44) | PR #16 screen (in review) · EXAMPLE DATA | `img/shot-s07-officer.png` |
| 7 | `shot-s09-locked` | 9: Fills the current SCC form; built to travel | Authority select on Describe; Application with **Check completeness** disabled while gaps are open (PR #20 shot 7, 2:44–3:00) | PR #16 screen (in review) · EXAMPLE DATA | `img/shot-s09-locked.png` |
| + | `shot-s09-scc-form` | 9 | The downloaded SCC variance form PDF filled in by the engine (unsigned, officer Part 2 blank) after **Check completeness**, from an AI-agent simulated session. The "not a finding that the design complies" notice is in the app's dialog, not the PDF; the PDF's appendix separately says it "does not state that the proposed design complies." | PR #16 (in review): Check completeness download, AI-agent simulated session · EXAMPLE DATA | `img/shot-s09-scc-form.png` |

Slides 1, 10, 11 and 12 have no product shot.
