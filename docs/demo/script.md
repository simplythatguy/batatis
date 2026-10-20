# Demo video script (3:00)

Shot list for one continuous recording of the Vite app in `web/`. One applicant prepares a variance application. One Safety Codes Officer reviews the packages for administrative completeness.

Clock below is the edit. Spoken lines are sized for that slot. If a click runs long, drop a sentence from the end of the narration. Keep the refusal, the empty fields, and the word incomplete.

## What this recording uses

| Source | Branch | What you take from it |
| --- | --- | --- |
| [PR #14](https://github.com/simplythatguy/batatis/pull/14) | `cursor/evals-demo-cases-7ecf` | The three example cases under `evals/demo-cases/`. Files only. Nothing in the app loads them. |
| [PR #16](https://github.com/simplythatguy/batatis/pull/16) | `cursor/e2e-product-flow-4362` | The Vite flow: `#/`, `#/describe`, `#/code-check`, `#/section-c`, `#/application`, `#/officer`. |
| [PR #8](https://github.com/simplythatguy/batatis/pull/8) | `backend/section-d-issues` | `GET /cases/{id}/section-d/issues` and the practice-of-engineering screen on each issue. |

Do not merge those branches to record. Copy the three PDFs out of PR #14 and run the `web/` app from PR #16 when you are ready to shoot the pending shots.

`PENDING #<pr>` means that shot is not on `dev` yet. On `dev` today the app opens a preloaded NorthCore fixture. Officer review is the “Not built yet” card. There is no Section D tab and no practice-of-engineering screen. Do not film `dev` and call it this demo.

## Cases (example data)

People, companies, addresses, products, listings, tests, and letters are fictional. Code, STANDATA, and process citations in the case files were checked against the NBC(AE) 2023 **1st printing**. The 2nd printing is the edition in force. Its wording was not re-verified for this video. Say that once (shot 3). Do not quote a 2nd-printing page.

| Label (keep this on screen) | Who | Paste this into Describe |
| --- | --- | --- |
| `EXAMPLE DATA · Case A · Manufacturer` | Mira Okafor, Example Panel Works Ltd. Product: EPW NailBase CI-50. | We make EPW NailBase CI-50, a 50 mm insulating sheathing panel, and we want it approved across Alberta so builders can nail vinyl siding straight into the facer. One pilot house: 0000 Example Way NW, Edmonton. Owner not decided. No legal description. No permit yet. |
| `EXAMPLE DATA · Case B · General contractor` | Carlos Mendes, Northgate Example Builders Ltd. Example Commons, Calgary. | Firestop inspection failed 46 plastic pipe penetrations on levels 3 and 4 at Example Commons, 0000 Example Avenue SW, Calgary. Five-storey sprinklered building, permit already issued. Drywall close-in is in 9 days. Can we get a variance and keep going? |
| `EXAMPLE DATA · Case C · Homebuilder` | Priya Natarajan, Larkspur Example Homes. | Two-storey infill at 0000 Example Crescent NW, Edmonton, about 210 m², no sprinklers. Heated slab with R-7.5 under it. Unvented low-slope roof, spray foam thickness still TBD. Bedroom 3 window clear opening 400 mm by 780 mm. What needs a variance? |

Upload only `input/project-brief.pdf` from that case. Each PDF is stamped EXAMPLE DATA. Leave `README.md`, `expected/`, and `presenter/` off the machine you upload from. Those files are cue sheets. Their headers say agent-authored, model-checked, not human-verified. Do not put a score from them on screen, and do not call them human-verified.

## Lower third (every shot)

Bottom left, for the whole shot, including the first frame:

`EXAMPLE DATA · Case A · Manufacturer`
`EXAMPLE DATA · Case B · General contractor`
`EXAMPLE DATA · Case C · Homebuilder`

Shots 1, 10, and 11 show all three lines. Every other shot shows the one line for the case in that shot. The sidebar role name is extra. It does not replace this lower third.

## Do not record

- **Try an example.** Those three buttons are different projects: “Manufacturer · NorthCore sheathing”, “General contractor · corridor ducts”, “Homebuilder · infill soffit”. They are not Cases A–C.
- **The officer’s planted package.** On PR #16, `#/officer` reviews one garden-suite package (hempcrete, Dana Hart, 11821 73 Avenue NW). Do not put Case A, B, or C labels on that package.
- **Model-checked numbers.** Do not open `#/accuracy`. Do not read “55 of 60”, any “x of y”, or a confidence interval. A proposal with a confidence is still a proposal. Confirmation is the applicant’s. Nothing on that screen is a human-verified score, and nothing on it is a compliance finding.
- **A finished professional opinion.** The practice-of-engineering screen flags, asks, or recommends that a registered professional be named. It does not write the letter, the engineering judgment, the listing, or the rating. It does not decide that a design complies, is safe, or is approved.

Narration never says: complies, safe, approved, equivalent performance, “close enough”, or “the panel is CCMC-approved” as the tool’s conclusion.

## Setup

1. App from PR #16: `cd web && npm run dev`. Engine on `http://127.0.0.1:8000` so `/api` proxies. Frame the sidebar. Width about 1440.
2. Start at `#/`. The screen title is **Who are you?**
3. Reset between cases with **Reset case**, which returns to Who. Then pick the next role. Do not use Try an example.

Routes are hash routes.

| Route | Screen |
| --- | --- |
| `#/` | Who are you? |
| `#/describe` | What are you building? |
| `#/code-check` | Code check |
| `#/section-c` | Section C · Objectives, functions and intent |
| `#/application?tab=alt` | Application · Alternative path |
| `#/application?tab=D` | Application · Section D and professional screening |
| `#/officer` | Officer review · Administrative completeness |

## Shot list

| Shot | Clock | Case label | Route | Criterion | Pending |
| --- | --- | --- | --- | --- | --- |
| 1 | 0:00–0:12 | All three | `#/` | General Applicability 5 | PENDING #16 |
| 2 | 0:12–0:30 | Case A | `#/describe` | Intake 20 | PENDING #16, PENDING #14 |
| 3 | 0:30–0:48 | Case A | `#/code-check` | Code Identification 20 | PENDING #16 |
| 4 | 0:48–1:03 | Case A | `#/section-c` | Code Identification 20 | PENDING #16 |
| 5 | 1:03–1:22 | Case A | `#/application?tab=D` | Recommendations 10 | PENDING #16, PENDING #8 |
| 6 | 1:22–1:34 | Case A | `#/application?tab=D` | X Factor 5 | PENDING #16, PENDING #8 |
| 7 | 1:34–1:52 | Case B | `#/describe` → `#/code-check` | Code Identification 20 | PENDING #16, PENDING #14 |
| 8 | 1:52–2:04 | Case B | `#/application?tab=D` | Recommendations 10 | PENDING #16, PENDING #8 |
| 9 | 2:04–2:22 | Case C | `#/describe` → `#/code-check` | General Applicability 5 | PENDING #16, PENDING #14 |
| 10 | 2:22–2:44 | All three | `#/officer` | Review 10 | PENDING #16 |
| 11 | 2:44–3:00 | All three | `#/application` | Usability and Portability 10 | PENDING #16 |

---

### Shot 1 — Three applicants, one template

- **Clock:** 0:00–0:12
- **Case label:** all three lines
- **Route:** `#/` Who are you?
- **Status:** PENDING #16. `dev` has no Who screen. It opens Describe on the NorthCore fixture.
- **Criterion:** General Applicability 5

**On-screen action.** Hold on Who. The three buttons read Manufacturer, General contractor, Homebuilder. Leave **Try an example** closed and unclicked. The lower third carries all three example-case labels.

**Narration.** “Three example cases. A manufacturer, a general contractor, and a homebuilder. Same variance template for each. The people and the projects are fictional.”

---

### Shot 2 — Manufacturer intake

- **Clock:** 0:12–0:30
- **Case label:** `EXAMPLE DATA · Case A · Manufacturer`
- **Route:** `#/describe`
- **Status:** PENDING #16 for the empty case and the authority field. PENDING #14 for `evals/demo-cases/a-manufacturer-nailbase-sheathing/input/project-brief.pdf`.
- **Criterion:** Intake 20

**On-screen action.** Click **Manufacturer**. The header is “What are you building?” and the sidebar reads Manufacturer. Paste the Case A paragraph. Set **Which authority will review this?** to Edmonton. Upload the Case A `project-brief.pdf` (EXAMPLE DATA stamp visible in the file name row, or flash page 1 of the PDF). Open **Applicant and site details**. Leave Owner, mailing address, legal description, and permit empty. Point at the gap chips for those fields. In the fact ledger, the pasted description is a fact from “Your description”. Nothing else is filled in.

The description contains the word “sheathing”. Code check will grow a “Your words” card from that. Do not treat it as the article. That happens in shot 3.

**Narration.** “Mira wants the panel approved across Alberta, and she has one Edmonton pilot house. Owner, legal description, and permit stay empty. The manufacturer is not written in as the owner.”

---

### Shot 3 — The fastening article

- **Clock:** 0:30–0:48
- **Case label:** `EXAMPLE DATA · Case A · Manufacturer`
- **Route:** `#/code-check`
- **Status:** PENDING #16. Search and “Add to this check” are not on `dev`. Identify stays command-line only. This shot does not cut to a terminal.
- **Criterion:** Code Identification 20

**On-screen action.** Click **Continue to code check**. The card built from the paragraph wears **Your words** and “Not a ranked article.” Answer **Not sure** on that card. Do not answer Yes on it.

In **Search Division B**, type `cladding fastened furring` and search. The list is at most 8 rows, and each row is **Code text** plus the id the database returned. If a row’s id is `9.27.5.1`, click **Add to this check** and answer **Yes**. Open **Code reference** so the provision id and the citation string are readable. If `9.27.5.1` is not in the list, do not type it in. Say the database did not return it, and skip shot 4.

**Narration.** “That card is her words. Search returns database rows only. This example’s departure is 9.27.5.1, vinyl nailed into the facer. The benchmark is 11 mm OSB, or furring. First printing only. Second-printing wording is unverified.”

---

### Shot 4 — Section C lookup

- **Clock:** 0:48–1:03
- **Case label:** `EXAMPLE DATA · Case A · Manufacturer`
- **Route:** `#/section-c`
- **Status:** PENDING #16 for the live lookup on a case that started empty. `dev` can look up the fixture’s own rows. Those rows are NorthCore, not NailBase.
- **Criterion:** Code Identification 20

**On-screen action.** Click **Continue to Section C**. The table has a row only for the article you marked Yes. The source pill reads **Live lookup** when the engine answers. Objective and function codes are the attribution-table pair. Intent is captioned “NBC 2020 Intent Statements, explanatory only”. If the intent cell is empty, leave it empty. Below the table, **Code text** and **AI-written** sit in separate blocks. Do not read the AI block as the code sentence.

If the lookup pill says **Cached demo run** or **Lookup failed**, say that on camera and do not recite objective codes from memory.

**Narration.** “Section C is a lookup. Objective and function come from the attribution table after the article is confirmed. Intent is the national explainer, labeled as an explainer. An empty intent cell stays empty.”

---

### Shot 5 — What the evidence must address

- **Clock:** 1:03–1:22
- **Case label:** `EXAMPLE DATA · Case A · Manufacturer`
- **Route:** `#/application?tab=alt`, then `#/application?tab=D`
- **Status:** PENDING #16 for the Section D tab and the panel “Section D and professional screening”. PENDING #8 for the issues list (`at_stake`, evidence types, `practice_of_engineering`, empty process fields, status). PR #16’s panel calls the older plan and professional routes. The issues payload is the PR #8 screen. Film the issues response when both are available. Until then, do not mock the JSON.
- **Criterion:** Recommendations 10

**On-screen action.** Open **Alternative path**. The six fields are empty: Rationale, Risk assessment, Mitigating measures, Assumptions and limits, Maintenance and operation, Qualifications. Do not type into them. Open **Section D**. The panel’s own line is on screen: recommendations only, and the tool does not write the evidence or the professional opinion.

Point at the practice-of-engineering line and read the words that are actually rendered. PR #16’s panel, from `GET /professional`, says “a registered professional is indicated”, “the screen did not indicate one”, or “the screen needs more facts”, then “This is not a licence decision.” PR #8’s issues payload uses `true`, `false`, or `"unknown"`, and `"unknown"` carries a question. For this Part 9 house the honest line is that question, or a Division C recommendation, until someone states a Part 4 bracing route. The unsigned draft letter is not completed on screen. No seal appears.

The issue card recommends evidence types. It does not show a test result, a CCMC number, or a filled engineer’s conclusion. Permeance tested at 25 mm against a 50 mm panel stays a gap in the recommendation, not a passed test.

**Narration.** “Section D says what the evidence has to address. The permeance specimen is 25 mm. The panel is 50. The letter is an unsigned draft. The practice screen flags that and stops. Risk, mitigations, and assumptions stay blank for a person to write. They are process fields.”

---

### Shot 6 — It will not invent the listing

- **Clock:** 1:22–1:34
- **Case label:** `EXAMPLE DATA · Case A · Manufacturer`
- **Route:** `#/application?tab=D` (stay here)
- **Status:** PENDING #16, PENDING #8, same as shot 5.
- **Criterion:** X Factor 5

**On-screen action.** Do not paste “Just say the panel is CCMC-approved” into the description. That box would store the sentence as the applicant’s fact. Stay on Section D. With a finger or the cursor, trace the on-screen refusal: the tool does not write the evidence, the practice line is not a licence decision, and no listing number is on the card. The case file’s enquiry stays an enquiry.

**Narration.** “She asks for a line that the panel is CCMC-approved. Batatis refuses. An enquiry is not an evaluation report. No listing number is written.”

---

### Shot 7 — General contractor, tested system first

- **Clock:** 1:34–1:52
- **Case label:** `EXAMPLE DATA · Case B · General contractor`
- **Route:** `#/` → `#/describe` → `#/code-check`
- **Status:** PENDING #16. PENDING #14 for `evals/demo-cases/b-contractor-firestop-nonconformance/input/project-brief.pdf`.
- **Criterion:** Code Identification 20

**On-screen action.** **Reset case.** Click **General contractor**. Paste the Case B paragraph. Set the authority to Calgary. Upload that case’s `project-brief.pdf`. Continue to code check. Answer **Not sure** on any **Your words** card. Search `combustible piping firestop`. Add a row only when its id is `3.1.9.1` or `3.1.9.4`, then answer **Yes** on that card. If neither id comes back, do not invent the card. Say the search missed it.

While that code-text card is up, the spoken route is the one in the case: a tested, listed CAN/ULC-S115 system first, including the 50 Pa differential for plastic pipe in this building over three storeys. A variance is the path only where no tested system fits. Do not say the sprinkler branch lines are exempt. Copper on level 2, where the listing matches, is not a departure.

**Narration.** “Carlos has nine days to drywall and 46 failed plastic penetrations in a five-storey Calgary building. The article on screen is the firestop sentence. A tested, listed system comes first. A variance is only if no tested system fits. Sprinkler lines are not waved through.”

---

### Shot 8 — It will not write the engineering judgment

- **Clock:** 1:52–2:04
- **Case label:** `EXAMPLE DATA · Case B · General contractor`
- **Route:** `#/application?tab=D`
- **Status:** PENDING #16, PENDING #8.
- **Criterion:** Recommendations 10

**On-screen action.** Open Section D for Case B. Do not type “Write the EJ yourself” into a field. The sales email is not on the card as an engineering judgment. The practice line recommends a registered professional for this Part 3 building, or it asks for the missing fact. Either way the next sentence on screen is that this is not a licence decision. No rating, no listing number, and no test result is filled in by the tool. The coordinating registered professional is not replaced by the contractor.

**Narration.** “He asks Batatis to write the engineering judgment. It will not. The rep’s email is not that judgment. The screen flags practice of engineering and does not decide the rating.”

---

### Shot 9 — Homebuilder, one house, one variance

- **Clock:** 2:04–2:22
- **Case label:** `EXAMPLE DATA · Case C · Homebuilder`
- **Route:** `#/` → `#/describe` → `#/code-check`
- **Status:** PENDING #16. PENDING #14 for `evals/demo-cases/c-homebuilder-infill-house/input/project-brief.pdf`. The three-way split below is the case’s expected classification. Speak it only while the matching code-text card, or a gap that names the STANDATA, is actually on screen. If the screen only shows the pasted paragraph, say that the classification is not on this build yet and cut the STANDATA sentences.
- **Criterion:** General Applicability 5

**On-screen action.** **Reset case.** Click **Homebuilder**. Paste the Case C paragraph. Authority: Edmonton. Upload that case’s PDF. On code check, answer **Not sure** on **Your words**. Search `bedroom window unobstructed`. Add `9.9.10.1` only if that id is returned, and answer **Yes**. A second search, `heated floor insulation`, is optional and only if you still have the seconds. Add nothing whose id you did not read off a returned row.

The classification this example is built to show, when the screen actually shows it:

- Heated slab at R-7.5: covered by STANDATA 23-BCV-003, no new variance request, the officer confirms. Slab edges are still 9.36.2.8. The drawing note leaves the edges off.
- Unvented roof as drawn (2% slope, spray foam plus batt, thickness TBD): probably outside STANDATA 23-BCV-017.
- Bedroom 3 window, 400 mm by 780 mm: the departure from 9.9.10.1.(2). Fall protection is a separate check. A rotary operator is not the limiter.

Do not say the opening is close enough. Do not say the owner accepts the risk.

**Narration.** “Priya has three ideas on one Edmonton house. The heated slab is already a province-wide STANDATA, and the edges are still open. The roof, as drawn, sits outside that roof STANDATA. The bedroom window is the variance. One product, three different routes.”

---

### Shot 10 — Officer, administrative completeness

- **Clock:** 2:22–2:44
- **Case label:** all three lines, each on its own package
- **Route:** `#/officer`
- **Status:** PENDING #16. The officer screen on that branch does not read Cases A–C. It reviews the planted garden-suite package. Do not relabel that package. `dev` shows “Not built yet”. Do not film that card as a finished review. Record this shot when Officer review lists the open example package.
- **Criterion:** Review 10

**On-screen action.** Sidebar **Officer review**. Header: “Officer review”, meta “Administrative completeness”. Show three packages, in order, each with its lower-third label. Every package’s status line is incomplete, return to the applicant. There is no Approve control.

Hold on Case A and **Copy request**. The request text starts with an information request and says it asks for missing administrative items. It is not a decision on the variance.

Case A flags to point at, in order: Section A owner missing, legal description and permit missing, no code analysis and no assumptions and limits, permeance specimen 25 mm against a 50 mm panel, engineer letter still an unsigned draft, bracing route not stated, product-approval wording. Case B: no listed-system remediation, the engineering judgment is a sales email, scope of penetrations unclear, intent cell still empty. Case C: mailing address and owner authorization, no code analysis, window opening taken from a supplier quote, fall protection not addressed.

The may-say line on screen is about missing information. The must-not line is absent: no “equivalent performance”, no “approved”, no “FireSeal will hold the rating”, no “0.31 m² is close enough”.

The cue sheet for those flags is `expected/sco-review.md` in each case. That file is model-checked, not human-verified. Use it to recognize the right gaps. Do not put its header, or any count, in the frame.

**Narration.** “The officer opens the same three example packages. Each one is administratively incomplete. The manufacturer is missing the owner, the legal description, and a signed letter, and the ask still says product approval. The request lists those items. It never says complies, safe, or approved. The other two packages come back the same way.”

---

### Shot 11 — Same record, two authorities

- **Clock:** 2:44–3:00
- **Case label:** all three lines stay in the lower third
- **Route:** `#/application` (Case A still loaded is fine; cut in the Case B authority field if you have the frame)
- **Status:** PENDING #16 for the authority select and for **Check completeness**. On `dev` the button is **Run pre-flight** and there is no authority field.
- **Criterion:** Usability and Portability 10

**On-screen action.** Cut from Edmonton selected on Case A to Calgary selected on Case B. Same sidebar, same Sections A–D. The gap strip still lists empty owner and empty process fields. **Check completeness** is disabled, and the footer counts the blocking gaps. Do not fill the gaps in order to unlock the button. Do not download a PDF in this minute. The picker itself lists Calgary and Edmonton. Say that. The portable part is the case record and the Safety Codes Council template, which is the export the engine is built to return, not a second app for each authority.

Applicant surface in this shot: empty fields stayed empty, and proposed items would sit under Model-checked until the applicant confirms them. You do not open that page. Officer surface was shot 10: code text and the AI explanation were separate blocks in shot 4, and the officer list was administrative gaps.

**Narration.** “Edmonton on the houses, Calgary on the tower. The authority is a field on the same record. The export is the Safety Codes Council template, so it is not locked to one city. The PDF stays shut while the gaps are open. Completeness is not a safety finding.”

## If you have to shorten

Drop shot 6’s second sentence, then shot 9’s edge-insulation clause, then the copper-pipe clause in shot 7. Do not drop shot 8, shot 10’s “incomplete”, or the empty practice-of-engineering refusal.
