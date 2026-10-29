# Batatis applicant-flow verification: Edmonton rowhouse case

Date: 2026-10-29. App: local worktree `batatis-demo` at `459ea343` (web :3000, engine :8000, AI on).
Every run is a fresh signup (access code), a new application, the description text plus the attached `/tmp/studio-case/incomplete.pdf`, then Questions → Case → Proof → Paperwork → Review → **Check my application** → Application.
Driver: `/tmp/studio-case/ui/run.mjs` (copy: `run-final.mjs`). Logs: `/tmp/studio-case/ui/<run>/log.txt`. Identify payloads: `<run>/identify-final.json`. Screens: `<run>/s/`. Key shots: `/tmp/studio-case/shots/`.

## Bottom line

- **Final description = v4** (now in `/tmp/studio-case/description.txt`). With v4, all 6 Section C rows of the complete form appear as rule cards in **3 of 3** runs (r7, r8, r9). All six rank in the top 9 of the identification list.
- With the original description (v1, run r0) and with v2 (r1–r3), **9.10.9.16.(4) never appeared** (rank 61–73). With v3 (only 9.10.9.16.(4) named), **9.10.19.5.(2) dropped** to rank ~323 in 2 of 3 runs. That instability is why v4 names both sentences.
- **Section C in the app holds only 9.10.11.2.(2)** (OS1.2, F03, OP3.1) in every run. The values match codedb exactly. The app puts only the varied (departed) sentence in Section C. The other five complete-form rows end up as "supporting" requirements, not Section C rows. This is the main difference from the complete form (see Discrepancies).
- Engineer flag: identify `engineering_required = "depends"` in every run. On screen: "The officer must determine the professional requirement / Waiting for the officer to determine whether a registered professional is required." The applicant cannot clear it.
- Office: Edmonton in every run (Paperwork "Office" field pre-filled `Edmonton`; Application header "NBC(AE) 2023, 2nd printing · Edmonton"; Section A "Reviewing office: Edmonton").

## Article sets

| Set | Articles |
|---|---|
| Complete form, Section C (6 rows) | 9.10.11.2.(2), 9.10.9.3.(2), 9.10.19.3.(1), 9.10.19.4.(1), 9.10.9.16.(4), 9.10.19.5.(2) |
| Incomplete form, Section C (4 rows) | 9.10.11.2.(2), 9.10.9.3.(2), 9.10.19.3.(1), 9.10.19.4.(1) |
| App, Section C (all runs r1–r9) | 9.10.11.2.(2) only |
| App, rules surfaced and confirmed "applies / follows" (v4) | 9.10.9.3., 9.10.19.3., 9.10.19.4., 9.10.9.16., 9.10.19.5. (+ 9.10.9.2., 9.10.11.1., 9.10.8.10., 1.2.1.1., 1.2.1.2., …), stored as role `supporting`/`conditional` |
| App, "Article you named" read from the PDF | **1.2.1.2.(1)** from incomplete.pdf page 7 (instruction text quoting Div A). The filled Section C rows on pages 2–3 were not picked up. |

## Section C values vs codedb (`codedb/build/codedb.sqlite`, table `attributions`)

| Sentence | codedb objectives / functions | Complete form | App Section C |
|---|---|---|---|
| 9.10.11.2.(2) | OS1.2, OP3.1 / F03 | OS1.2, OP3.1 / F03 | **OS1.2 · F03 · OP3.1 ✔** (with the sentence text quoted) |
| 9.10.9.3.(2) | OS1.2, OP1.2 / F03 | same | not in Section C |
| 9.10.19.3.(1) | OS1.5 / F11 | same | not in Section C |
| 9.10.19.4.(1) | OS1.5 / F11, F81 | same | not in Section C |
| 9.10.9.16.(4) | OS1.2, OP1.2 / F03 | same | not in Section C |
| 9.10.19.5.(2) | OS1.5 / F11 | same | not in Section C |

The forms in `/tmp/studio-case/*.pdf` match codedb on every row.

## Per-run results

Ranks are 1-based positions in `requirements` of the final `GET /api/cases/<id>/identify` payload (all divisions, 2177 items). "Shown as cards" counts how many of the 6 complete-form rows the applicant saw (9.10.11.2.(2) appears as the departure card; the other five appear as "Does this rule apply to your project?" cards). The deck was capped at 31 rule cards per run.

| run | desc | rank 9.10.11.2 | 9.10.9.3 | 9.10.19.3 | 9.10.19.4 | 9.10.9.16 | 9.10.19.5 | shown as cards (of 6) | Section C | check headline | left for you (required) |
|---|---|---|---|---|---|---|---|---|---|---|---|
| r0 | v1 | 1 | 3 | 4 | 8 | 73 | 20 | 5 (no 9.10.9.16) | 9.10.11.2.(2) + 9.10.11.1.(1)* | not run | – |
| r1 | v2 | 1 | 2 | 12 | 6 | 66 | 20 | 5 (missing 9.10.9.16.) | 9.10.11.2.(2) OS1.2 F03 OP3.1 | Let’s check your application. | 6 (6) † |
| r2 | v2 | 1 | 12 | 11 | 4 | 61 | 323 | 4 (missing 9.10.9.16., 9.10.19.5.) | 9.10.11.2.(2) OS1.2 F03 OP3.1 | Almost there. 3 things stand between you and submission. | 11 (3) |
| r3 | v2 | 1 | 2 | 12 | 5 | 65 | 20 | 5 (missing 9.10.9.16.) | 9.10.11.2.(2) OS1.2 F03 OP3.1 | Almost there. 3 things stand between you and submission. | 12 (3) |
| r4 | v3 | 1 | 13 | 12 | 5 | 4 | 323 | 5 (missing 9.10.19.5.) | 9.10.11.2.(2) OS1.2 F03 OP3.1 | The check couldn’t finish. | 1 (1) ‡ → retry: 16 (6) |
| r5 | v3 | 1 | 3 | 13 | 6 | 2 | 324 | 5 (missing 9.10.19.5.) | 9.10.11.2.(2) OS1.2 F03 OP3.1 | Almost there. 4 things stand between you and submission. | 10 (4) |
| r6 | v3 | 1 | 2 | 13 | 7 | 6 | 21 | 6 | 9.10.11.2.(2) OS1.2 F03 OP3.1 | Almost there. 12 things stand between you and submission. | 16 (12) |
| r7 | v4 | 1 | 3 | 5 | 9 | 8 | 2 | 6 | 9.10.11.2.(2) OS1.2 F03 OP3.1 | Almost there. 5 things stand between you and submission. | 13 (5) |
| r8 | v4 | 1 | 3 | 5 | 9 | 8 | 2 | 6 | 9.10.11.2.(2) OS1.2 F03 OP3.1 | Almost there. 6 things stand between you and submission. | 12 (6) |
| r9 | v4 | 1 | 2 | 4 | 8 | 5 | 3 | 6 | 9.10.11.2.(2) OS1.2 F03 OP3.1 | Almost there. 5 things stand between you and submission. | 13 (5) |

\* r0 (earlier, interrupted run): its driver answered "Yes, it differs" for 9.10.11.1., which is not a sensible answer. Later runs answer "No, it follows".
† r1: the Case stage click did not take, so no case draft was written and the check judged an empty case. This was a driver race (fixed in `stage()`), not an app failure.
‡ r4: the check failed with "The check couldn’t finish. Check unavailable." `check.mjs r4` re-ran it in the same session; the retry gave 16 items for the applicant (6 required) and 5 for the officer. Shot: `shots/r4-check-failed.png`, `shots/r4-check-retry-all.png`.

Stability on v4 (r7–r9): the same six rows were surfaced, Section C was the same, the engineer flag was the same and the office was the same. The rule-card order varies slightly (9.10.19.5 first in r7 and r8, 9.10.9.3 first in r9). 9.10.11.1. was rank 20 in r7 and r8 but rank 850 in r9 (it was not shown in r9). The check finding count varies between 12 and 13 items (5–6 required) across the three runs.

### Exact on-screen rule cards, v4 (order shown; applicant answer)

- **r7**: 9.10.19.5. Interconnection of Smoke Alarms [Yes]; 9.10.9.3. Openings to be Protected with Closures [Yes]; 9.10.9.2. Continuous Barrier [Yes]; 9.10.19.3. Location of Smoke Alarms [Yes]; 9.10.9.16. Separation of Residential Suites [Yes]; 9.10.19.4. Power Supply [Yes]; 1.2.1.1. Non-defined Terms [Yes]; 1.2.1.2. Defined Terms [Yes]; 9.10.11.1. Required Firewalls [Yes]; 9.10.8.10. Application to Houses [Yes]; 4.1.8.18. Elements of Structures, Non-structural Components and Equipment [No]; 3.2.5.12. Automatic Sprinkler Systems [No]; 9.10.2.2. Home-Type Care Occupancies [Yes]; 9.10.14.5. Construction of Exposing Building Face and Walls above Exposing Building Face [Yes]; 9.10.15.5. Construction of Exposing Building Face of Houses [Yes]; 4.1.8.19. Seismic Isolation [No]; 3.2.4.20. Smoke Alarms [No]; 7.2.7.3. Flume and Receiving Pool Design and Construction [No]; 3.2.5.7. Water Supply [No]; 4.1.8.1. Analysis [No]; 4.1.8.11. Equivalent Static Force Procedure… [No]; 3.2.3.1. Limiting Distance and Area of Unprotected Openings [No]; 3.2.4.18. Audibility of Alarm Systems [No]; 4.1.8.10. Additional System Restrictions [No]; 4.2.4.1. Design Basis [No]; 9.36.5.10. Modeling Building Envelope of Proposed House [Yes]; 9.36.5.4. Calculation Methods [Yes]; 3.7.2.2. Water Closets [No]; 9.36.2.10. Construction of Air Barrier Details [Yes]; 3.3.3.5. Compartments and Fire Separations [No]; 3.8.3.6. Doorways and Doors [No]
- **r8**: identical list and order to r7.
- **r9**: 9.10.9.3.; 9.10.19.5.; 9.10.19.3.; 9.10.9.16.; 9.10.19.4.; 9.10.9.2.; 1.2.1.1.; 1.2.1.2.; 9.10.8.10.; then the same Part 3/4/7/9.36 tail as r7, plus 4.1.6.2. Specified Snow Load [No]. (No 9.10.11.1.)
- Before these cards, every run shows the departure card "More than two neighbouring houses with a secondary suite share one section without a firewall between them." → **Add this rule to my application** → "How does your design differ?" citing **9.10.11.2.(2)** → Confirm.
- After each pair of "applies" cards comes "Does your design do something different from the rule on …?". Every run answered **No, it follows** for every one of these.

## Section D (case and proof), from r7 (v4); r8 and r9 are the same in substance

- Case draft (Draft my case → Accept all): Rationale (benchmark 9.10.11.2.(2); Division C code analysis needed), Risk assessment (fire department response 10–30 min flagged as an unverified assumption; benchmark intent), Mitigating measures (1 h party wall, solid-core self-closing doors, interconnected hardwired alarms), Assumptions and limits (2 storeys, 4 houses, 260 m²), Qualifications (Dana Okafor, Northline, designer of record, read from the PDF). **Maintenance and operation: "Not written"** in r4, r5, r7 and r9 (r2, r3 and r8 wrote only a "Plan:" line).
- Evidence tasks (Proof → Evidence): `9.10.11.2.(2) · People: fire spread` and `9.10.11.2.(2) · Nearby buildings: fire spread`, one task per objective of the varied sentence only.
- Professional questions answered: principal homes 4; fire suppression No; reserved professional judgement No; registered professional "Not engaged yet". Result: "Routed to the officer: whether a registered professional is required."
- Check findings, r7 ("Show all"): missing supporting document (field blank); signature at preparation stage; why the project needs the departure and which analysis method; what happens if each measure fails; source of the 10–30 min response time and reassessment triggers; qualifications and a single coordinator; scope of any engaged professional; routed to the officer: professional requirement. **For the officer:** missing evidence for 9.10.11.2.(2) (F03–OS1.2, F03–OP3.1); no testing or engineering studies named; no maintenance or commissioning info; no statement on component failure; no statement on lapsed maintenance; upkeep not written.

## Discrepancies and app weaknesses (with evidence)

1. **Section C model differs from the complete form.** The app lists only the departed sentence (9.10.11.2.(2)). The five compensating rows the City's solution relies on (9.10.9.3.(2), 9.10.19.3.(1), 9.10.19.4.(1), 9.10.9.16.(4), 9.10.19.5.(2)) are confirmed as "supporting" but never written to Section C, so their objectives and functions never appear on the form. A demo that compares against the complete form will show 1 row against 6. `shots/r7-v4-section-c.png`.
2. **Attached-PDF article reading picks boilerplate.** "Article you named: 1.2.1.2.(1), incomplete.pdf, page 7" comes from the form's instruction text. The four filled Section C rows of the attached form (9.10.11.2.(2), 9.10.9.3.(2), 9.10.19.3.(1), 9.10.19.4.(1)) are not taken as named articles. `shots/r3-understood-named-1.2.1.2.png`, `shots/v4-r7-02-understood.png`.
3. **Ranking is unstable for identical input.** With v2, 9.10.19.5. was rank 20 in r1 and r3 but rank 323 in r2. With v3 it was rank 323–324 in r4 and r5 but rank 21 in r6. 9.10.11.1. swings between rank ~19 and 850–1011. Only naming the sentences (v4) made the result stable.
4. **Without the sentence numbers, 9.10.9.16.(4) is never surfaced**, even when the description uses the code's own words (v2 rank 61–66). An applicant who doesn't know the number would not see it in the first 31 cards.
5. **Identify rate limit (6 per 10 min per IP)**: "The code check didn’t finish. Identification limit reached; try again in N seconds." Parallel or repeated applicants from one IP hit it. A demo should run only one application at a time. `shots/app-identify-rate-limit.png`.
6. **"The saved case changed somewhere else. Your answers are still here."** appeared after the footprint answer while a background identify was running; the question stayed stuck until reload. `shots/app-conflict-saved-case-changed.png`.
7. **Transient "Loading applications… / Your questions start once you describe your project."** mid-deck right after an answer. It looks like the case was lost. `shots/app-loading-lost-questions.png`.
8. **Check can fail** ("The check couldn’t finish. Check unavailable."); the retry worked. `shots/r4-check-failed.png`.
9. **Second "Confirm" on "How does your design differ?"** is sometimes disabled for more than 30 s while it re-identifies (r2, r4). Clicking it later works.
10. Minor: "Use of the building: apartments or other multi-unit housing" for a row house; the case draft says "building area of 260" without a unit in some runs (r4); Maintenance and operation was left unwritten in most runs; the registry note says "Using offline snapshot dated 2026-10-18; live registry unavailable (JSONDecodeError/URLError)".

## Final description (v4, `/tmp/studio-case/description.txt`)

> We're building a row house in Edmonton: four attached houses side by side, each on its own freehold lot, and every house has a basement secondary suite, so the building contains more than 2 adjacent houses with a secondary suite. The code would normally need the party walls between them to be firewalls. Instead, following the City of Edmonton's published alternative solution for secondary suites in rowhouses and its Policy B23-01, each party wall between the houses will be a fire separation with a 1-hour fire-resistance rating. Inside each house with a secondary suite, the walls and floor-ceiling framing that separate the suite from the main dwelling unit are protected, as Sentence 9.10.9.16.(4) allows, by a continuous smoke-tight barrier of 12.7 mm gypsum board on both sides of the walls and on the underside of the floor-ceiling framing. Doors in those separations are solid-core and self-closing. Smoke alarms are hardwired with battery backup, on every storey and in every bedroom, and, as Sentence 9.10.19.5.(2) requires, interconnected by hard-wiring so that any one smoke alarm sounding makes all smoke alarms in the house with a secondary suite sound. Fire department response is expected within 10 to 30 minutes.

Earlier versions: `description-v1.txt` (original), `description-v2.txt` (code wording, no numbers), `description-v3.txt` (names 9.10.9.16.(4) only). All the added facts are true of the case: the complete form cites both sentences, and the design is exactly the 9.10.9.16.(4) barrier option and the 9.10.19.5.(2) interconnection.

## UI steps that work (selectors, Playwright)

Viewport 1440×900. `BASE = http://localhost:3000`. Run **one application at a time** (identify rate limit). Expect about 9–16 minutes end to end.

1. **Sign up**: `goto(BASE + "/#/signup")` → `getByLabel("Access code").fill(BATATIS_ADMIN_CODE)` → `getByLabel("Your name").fill("Dana Okafor")` → `getByRole("button",{name:"Continue"})`. If the URL contains `onboarding`, click `getByRole("button",{name:/I have a building project/})` and then `/^(Finish|OK)$/` (see `ui/lib.mjs signup()`).
2. **Describe**: `goto(BASE + "/#/")` → `locator("#cf-describe").fill(description)` → `Promise.all([page.waitForEvent("filechooser"), getByRole("button",{name:/Attach files/}).click()])` → `chooser.setFiles("/tmp/studio-case/incomplete.pdf")` → wait for text `1 file attached` → `getByRole("button",{name:/^(Start|Continue)/})`.
3. **Understood**: wait for text `Here’s what I understood` (≤5 min; cached re-reads take about 8 s) → `getByRole("button",{name:/^Looks right/})`.
4. **Deck loop.** Read the heading above "Your answer" in `main`. Skip the leading lines `Document review`, `Model checked`, `Unread content` and digits. Each loop: act, then wait 4 s.
   - `Checking the code…` / `Reading` / `Preparing` → wait.
   - `The code check didn’t finish.` → parse `try again in (\d+) seconds`, wait, then `getByRole("button",{name:/^Try again/})`.
   - Text `The saved case changed somewhere else` → `page.reload()`.
   - Text `Loading applications` / `Your questions start once you describe` → wait (reload after about 60 s).
   - `You likely need a variance` → `getByRole("button",{name:/^Continue/})`.
   - Text questions (`main input[type=text]:visible` + `/^Continue/`): `How many storeys` → `2`; `building area|footprint` → `260`; `How many houses` → `4`; `have a secondary suite?` → `4`; `Between firewalls` → `4`.
   - Departure card (text `Add this rule to my application`) → `getByRole("button",{name:/Add this rule/})`.
   - `How does your design differ?` (shows 9.10.11.2.(2)) → `getByRole("button",{name:/^Confirm/})`. It can appear twice, and the second Confirm can stay disabled for up to about 30 s.
   - `Your city has a pre-reviewed path…` (standing package B23-01) → `getByRole("button",{name:/build my own case/})`. This builds the full SCC Sections A–D form; "Yes, follow its conditions" leads to the Letter of Construction Intention path, which was not tested.
   - `Rules that may apply` → `/^Continue/`.
   - `Does this rule apply to your project?`: the provision is the line after `Your answer`. Part 1/2/9 → `getByRole("button",{name:/Yes, it applies/})`. Parts 3–8 → `/No, it doesn.t apply/`, then `getByLabel("Why it doesn’t apply").fill("This is a Part 9 row house; this Part N requirement is outside its scope.")` and `/^Continue/`.
   - `Does your design do something different from the rule on …?` → `getByRole("button",{name:/No, it follows/})` (only "firewalls not required" would be Yes, and it never re-appears).
   - The deck does not end on its own (2080 candidates). After about 31 rule cards, leave through the stage bar.
5. **Case**: `getByRole("button",{name:/^Case:/})`, then check that the heading starts with `Your case` (retry if not) → `getByRole("button",{name:/Draft my case/})` → poll until `Drafting your case` disappears (about 1–3 min) → `getByRole("button",{name:/Accept all/})`.
6. **Proof**: `getByRole("button",{name:/^Proof:/})` (heading `Who is responsible…`). The question is the line after `Evidence`. `principal homes` → fill `4` + `/Save and continue/`; `fire suppression` → `getByRole("button",{name:"No",exact:true})`; `reserved professional judgement` → `No`; `registered professional for this scope` → `getByRole("button",{name:"Not engaged yet",exact:true})`. Then `getByRole("button",{name:/Continue to evidence/})` shows the evidence tasks.
7. **Paperwork**: `getByRole("button",{name:/^Paperwork:/})` (heading `Last details for the form`). Use `getByRole("textbox",{name:X,exact:true}).fill(v)` + Tab for each of `Owner` "Prairie Lane Homes Ltd.", `Representative` "Dana Okafor, Northline Home Design Ltd.", `Mailing address` "4410 Example Trail NW, Edmonton AB T6X 0Z0", `Site address` "1204 to 1210 Riverbend Mews NW, Edmonton AB", `Legal description` "Lots 11 to 14, Block 7, Plan 2499999", `Permit number` "Not yet issued (applied with this request)". Then `getByRole("button",{name:"Today",exact:true})`, `getByRole("button",{name:"One building site"})` (role query; `getByText` matches a hidden twin) and `getByRole("button",{name:/^Done/})`. `Office` is pre-filled `Edmonton`.
8. **Review**: top tabs are links: `getByRole("link",{name:/^\d Review/})` → `getByRole("button",{name:/Check my application/})` → wait about 20 s → `getByRole("button",{name:/^Show all \d+/})` expands the findings. If the heading is `The check couldn’t finish.`, use `getByRole("button",{name:/Try the check again/})`.
9. **Application**: `getByRole("link",{name:/^\d Application/})`. For Section C, `getByText("Section C",{exact:true}).scrollIntoViewIfNeeded()` (the page scrolls inside a container, so `fullPage` screenshots do not reach it; see `ui/shots.mjs`).

Reusable scripts: `ui/run.mjs <run> <descFile>` (whole flow; saves `state.json`), `ui/check.mjs <run>` (re-run the check in a saved session), `ui/shots.mjs <run> <prefix>` (Section C and D screenshots), `ui/rank.py`, `ui/summ.py`.

## Key screenshots (`/tmp/studio-case/shots/`)

- Flow, v4 run r7: `v4-r7-01-attached.png`, `-02-understood.png`, `-03-route.png`, `-04-standing.png`, `-05-rule-card.png` (9.10.11.2 departure), `-06-how-differ.png`, `-07-rules-intro.png`, `-08-first-rule-card.png`, `-10-case-drafted.png`, `-11-proof.png`, `-12-evidence.png`, `-13-paperwork.png`, `-14-review.png`, `-15-checked.png`, `-16-checked-all.png`, `-17-application.png`, `r7-v4-section-c.png`, `r7-v4-section-d.png`.
- `r4-10-first-rule-card.png` (9.10.9.16 card), `r4-section-c.png`, `r4-check-retry-all.png`.
- Weaknesses: `r3-understood-named-1.2.1.2.png`, `app-identify-rate-limit.png`, `app-conflict-saved-case-changed.png`, `app-loading-lost-questions.png`, `r4-check-failed.png`.
