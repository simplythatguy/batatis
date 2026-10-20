# Demo video script (3:00)

Edit clocks below. Spoken lines are sized for that slot. If a click runs long, drop a sentence from the end of the narration. Keep the empty fields, the on-screen limit (“does not write the evidence”), and the officer line “This does not certify the design.”

This cut is recordable on PR #16’s screens today, plus two stills you add in the edit. The app does not show a ranked identify list, a benchmark card, or the eval numbers.

| Criterion | Time | Where it is |
| --- | --- | --- |
| General applicability | 0:18 | Shot 1 |
| Intake | 0:33 | Shots 2 and 3 |
| Code identification | 0:45 | Shot 4, including the 0:07 eval still |
| Recommendations | 0:24 | Shot 5 |
| X factor | 0:08 | Shot 5, second beat |
| Review | 0:36 | Shot 6 |
| Usability and portability | 0:16 | Shot 7 |

Dropped from the previous draft: the refusal shot (she asks, Batatis refuses) and the homebuilder STANDATA split. The homebuilder paste is 0:10. There is no contractor walkthrough and no upload.

## What this recording uses

| Source | Branch | What you take from it |
| --- | --- | --- |
| [PR #14](https://github.com/simplythatguy/batatis/pull/14) | `cursor/evals-demo-cases-7ecf` | Paste text below. Cue sheets live under `evals/demo-cases/keys/<case>/` (`expected/` and `presenter/` moved there). Nothing in the app loads them. |
| [PR #16](https://github.com/simplythatguy/batatis/pull/16) | `cursor/e2e-product-flow-4362` | The screens you film: `#/`, `#/describe`, `#/code-check`, `#/section-c`, `#/application`, `#/officer`. |
| [PR #12](https://github.com/simplythatguy/batatis/pull/12) | `backend/identify-api` | The ranked-list still and the `benchmark_acceptable_solution` still, from an identify payload for the pasted text. The published top-1 line on the eval still. |
| [PR #8](https://github.com/simplythatguy/batatis/pull/8) | `backend/section-d-issues` | The variant headline on the eval still. The issues payload (`at_stake`, `practice_of_engineering`) is not on the #16 card. |

Do not merge those branches to record. Run `web/` from PR #16. Do not film `dev` and call it this demo. On `dev` the app opens a preloaded NorthCore fixture, there is no Who screen, no Search, and no “Add to this check”. Officer review is the “Not built yet” card. The application button on `dev` already reads **Check completeness**.

## Cases (example data)

People, companies, addresses, and products in the paste are fictional. Citations on a code row come from the NBC(AE) 2023 **2nd-printing** code database. The Code check header reads “NBC(AE) 2023 · 2nd printing”. A citation on a row looks like `NBC(AE) 2023 p2, Div B, … [PDF p.952]`. Read the string on the row. Do not quote a page from memory.

Narrate a fact only when it is on screen after the paste: in the description box, on a chip, in the ledger, or on a code row. Do not narrate the PDFs. Permeance, an unsigned letter, a sales email, a supplier quote, bracing, and an OSB or furring thickness are not in the paste. Leave them out.

| Label (edit overlay) | Who | Paste this into Describe |
| --- | --- | --- |
| `EXAMPLE DATA · Case C · Homebuilder` | Priya Natarajan, Larkspur Example Homes. | Two-storey infill at 0000 Example Crescent NW, Edmonton, about 210 m², no sprinklers. Heated slab with R-7.5 under it. Unvented low-slope roof, spray foam thickness still TBD. Bedroom 3 window clear opening 400 mm by 780 mm. What needs a variance? |
| `EXAMPLE DATA · Case A · Manufacturer` | Mira Okafor, Example Panel Works Ltd. Product: EPW NailBase CI-50. | We make EPW NailBase CI-50, a 50 mm insulating sheathing panel, and we want it approved across Alberta so builders can nail vinyl siding straight into the facer. One pilot house: 0000 Example Way NW, Edmonton. Owner not decided. No legal description. No permit yet. |

Do not upload `project-brief.pdf`. On this build the file row says **Not read** and “The engine has no file upload route, so this PDF was not read.” Upload stays off camera (PENDING a `/files` route). Cue sheets under `evals/demo-cases/keys/<case>/` stay off the machine and off camera. Their headers say agent-authored, model-checked, not human-verified. Do not read `sco-review.md` as the officer script.

## Lower third (edit overlay, not app UI)

“EXAMPLE DATA” is not in the app. You add it in the edit, bottom left, including the first frame. If the app later has its own EXAMPLE banner, keep this overlay off that banner.

Shot 1 shows all three lines (the contractor line is named there and not walked through):

`EXAMPLE DATA · Case A · Manufacturer`
`EXAMPLE DATA · Case B · General contractor`
`EXAMPLE DATA · Case C · Homebuilder`

Shots 2 and 4 show the Case C line. Shot 3 shows the Case A line. Shot 6 shows only `EXAMPLE DATA · Sample officer package`. Shot 7 shows the case that is actually on screen.

## Do not record

- **Try an example.** On Who those three buttons are always visible: “Manufacturer · NorthCore sheathing”, “General contractor · corridor ducts”, “Homebuilder · infill soffit”. Do not click them. Frame or crop above them. They are not Cases A–C.
- **An upload.** Do not drop a PDF on Describe.
- **The code-check intro.** Crop out “Identify is command-line only. Search calls GET /code/search”. Do not read it. Do not read a `POST /cases/…` line on Section D.
- **`#/accuracy`.** The nav label is Model-checked. Do not open it. The eval still in shot 4 is the only place those counts appear, and it is labelled model-checked, not human-verified.
- **A compliance, safety, or certification finding.** The tool does not decide those. You may read the officer request’s own sentence, which says it does not.

## Setup

1. App from PR #16: `cd web && npm run dev`. Engine on `http://127.0.0.1:8000` so `/api` proxies. Width about 1440. Frame the sidebar.
2. Start at Who with **Reset case**. Typing `#/` while a case is open opens Describe, not Who. On Who the sidebar highlight sits on Describe. The title in the header is still **Who are you?**
3. Set **Which authority will review this?** before Save, Upload, or Continue. The note under the select says it is sent when the case is first saved and the engine has no route to change it later. The select exists only on Describe.
4. `#/officer` redirects to Who unless a case is open. Leave Case C open for shot 6.

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

The application tabs are **Section A**, **Section B**, **Alternative path**, and **Section D**. Section C is its own nav item.

The gap strip is collapsed to “N blocking · N warning” until you open **Review gaps**.

## Shot list

| Shot | Clock | Case label | What | Criterion |
| --- | --- | --- | --- | --- |
| 1 | 0:00–0:18 | All three | Who | General applicability |
| 2 | 0:18–0:28 | Case C | Paste. No upload. | Intake |
| 3 | 0:28–0:51 | Case A | Paste, then both Not sure cards | Intake |
| 4 | 0:51–1:36 | Case C | Search, Section C, ranked list, benchmark card, eval still | Code identification |
| 5 | 1:36–2:08 | Case C | Section D, then the on-screen limit | Recommendations, then X factor |
| 6 | 2:08–2:44 | Sample officer package | One planted package | Review |
| 7 | 2:44–3:00 | Case on screen | Authority select and locked export | Usability and portability |

Three example packages on `#/officer` are not built. No open PR loads Cases A–C there. Shot 6 films the one planted package that #16 already renders.

---

### Shot 1 — Three applicants (0:18)

- **Clock:** 0:00–0:18
- **Case label:** all three lines
- **Route:** `#/` Who are you?
- **On `dev`:** no Who screen. It opens Describe on the NorthCore fixture.

**On-screen action.** Hold on Who. The role buttons read Manufacturer, General contractor, Homebuilder. Do not click the three buttons under **Try an example**. Crop above them. Do not click a role yet.

**Narration.** “Three example cases. A manufacturer, a general contractor, and a homebuilder. Same variance template. The people and the projects are fictional.”

---

### Shot 2 — Homebuilder paste (0:10)

- **Clock:** 0:18–0:28
- **Case label:** `EXAMPLE DATA · Case C · Homebuilder`
- **Route:** `#/describe`

**On-screen action.** Click **Homebuilder**. The header is “What are you building?” Paste the Case C paragraph. Set **Which authority will review this?** to Edmonton before Continue. Do not upload. Open **Review gaps** and point at **Owner missing**, **Mailing address missing**, and **Legal description missing**. Permit stays empty. It is optional and has no chip. Open the fact ledger. It shows **What you described** and **Proposed alternative**, both from Your description, plus a **Storeys** fact. Do not narrate a slab STANDATA, a roof STANDATA, or a supplier quote. That classification is not on this build.

**Narration.** “Priya’s description is a two-storey Edmonton infill. The window opening on screen is 400 by 780 millimetres. Owner, mailing address, and legal description are missing.”

---

### Shot 3 — Not sure (0:23)

- **Clock:** 0:28–0:51
- **Case label:** `EXAMPLE DATA · Case A · Manufacturer`
- **Route:** `#/` then `#/describe` then `#/code-check`

**On-screen action.** **Reset case.** The note reads “Cleared. Nothing from the previous case is kept.” Click **Manufacturer**. Paste the Case A paragraph. Set the authority to Edmonton before Continue. Do not upload. Open **Review gaps**: **Owner missing**, **Mailing address missing**, **Legal description missing**. The ledger is **What you described** and **Proposed alternative** only. Case A states no storeys, so there is no Storeys fact.

Click **Continue to code check**. Two **Your words** cards are on screen: **Sheathing membrane** and **Storey count**. Each says “From what you wrote. Not a ranked article.” Answer **Not sure** on both. Do not answer Yes. Unanswered cards block **Continue to Section C**. Crop the intro that names `GET /code/search`.

**Narration.** “Mira’s description names a 50 millimetre panel, vinyl nailed into the facer, and one Edmonton house. Those two cards are her words. Not sure on both. They are not ranked articles.”

---

### Shot 4 — Code identification (0:45)

- **Clock:** 0:51–1:36
- **Case label:** `EXAMPLE DATA · Case C · Homebuilder`
- **Route:** back to the Case C code check, then `#/section-c`, then two stills

Return to the Case C case you pasted in shot 2 (the edit can cut back; do not Reset if you still need that case). One **Your words** card, from the description. Answer **Not sure** on it. Crop the search intro.

**0:51–1:03, search.** In **Search Division B**, type `bedroom window unobstructed` and search. At most 8 rows. Each row is the id the database returned and a **Code text** pill. If a row’s id is `9.9.10.1.(2)`, click **Add to this check** and answer **Yes**. Open **Code reference** and read the citation that is printed. The header says 2nd printing. If that id is not in the list, do not type it in, do not say it, and do not add a card.

While that row is up, and only if its code text shows a 0.35 m² opening and the description still shows 400 mm by 780 mm: “0.31 square metres where the code asks 0.35.” Do not say close enough. Do not search `heated floor insulation`. Do not voice `9.27.5.1` on this search. That id is a different query (`cladding fastened furring`), and only if a returned row shows it. Search on that query has returned sentences (1) and (5). Do not say sentence (2) unless that id is the row.

**1:03–1:11, Section C.** Click **Continue to Section C**. The table has a row only for the article you marked Yes. The source pill reads **Live lookup** when the engine answers. Objective and function are the attribution-table pair. If the intent cell reads **None for this provision**, say so and do not fill it. The detail line is “No NBC 2020 intent statement for this provision.” If the intent text looks like a different provision, say so and do not read it as this article’s intent. Below the table the blocks are **Code text** and **NBC 2020 Intent Statements**. A live row has no **AI-written** block. That pill is on the Code check question. If the pill says **Cached demo run** or **Lookup failed**, say that and do not recite objective codes from memory.

**Narration for the app frames.** “Search returns database rows only. The row on screen is 9.9.10.1.(2). Section C is a lookup. Intent stays on none for this provision when that is what it says. Batatis checks completeness. The officer decides compliance.”

**1:11–1:22, ranked list still.** This list is not the search box. It is the identify order from PR #12 for this same paste: provision, title, probability, committed. If the payload has no model key, the still is labelled **Cached demo run**, the order is BM25, and nothing is committed. Read only ids printed on the still. If you have no payload, omit the still and do not say ranked.

**1:22–1:29, benchmark card.** Same payload. The card’s role line is `benchmark_acceptable_solution`. Read the provision, the explanation, and the citation if they are on the card. `9.9.10.1.(2)` is an example of that field only when the card prints it. If the card says no article was identified, read that sentence and stop. If you have no card, do not say benchmark. Do not say OSB, furring, or a millimetre thickness.

**1:29–1:36, eval still.** A full-frame still, not `#/accuracy`. Title it model-checked, not human-verified. Copy these lines and no others:

- `rules_plus_unknown` (shipped): 50/60 in-sample, 0 under-flags
- `rules_only`: 55/60 in-sample, 1 under-flag
- `c_openai_rerank_verify`: top-1 9/11 on the 11 evals_dev cases with must_cite gold, 3 repeats

The 9/11 line is three repeats, not a single run. Do not relabel it. These figures are not a finding that a design complies, is safe, or is certified.

**Narration.** “Model-checked, on the dev cases. Not a compliance finding.”

---

### Shot 5 — Section D, then the limit (0:24 + 0:08)

- **Clock:** 1:36–2:08
- **Case label:** `EXAMPLE DATA · Case C · Homebuilder`
- **Route:** `#/application?tab=alt`, then `#/application?tab=D`

**On-screen action.** Open **Alternative path**. The six fields are empty: Rationale, Risk assessment, Mitigating measures, Assumptions and limits, Maintenance and operation, Qualifications. Do not type into them. Open **Review gaps** so **Owner missing** and the six “… empty” rows are visible. Open **Section D**. The panel title is “Section D and professional screening”.

On this build the card shows a provision id, a status, the performance issue, and “Evidence types to consider: … Not results”, and only when those routes return. The line you read is “This tool does not write the evidence or the professional opinion.” It is on screen only after the routes return, and a route path is printed just before it. Do not read the route. If the panel says the routes did not return, say that and do not invent a card. `at_stake` and a per-issue `practice_of_engineering` value (`true`, `false`, or `"unknown"`) are the PR #8 payload. Speak them only when those words are on screen.

Read the practice line that is actually rendered: “a registered professional is indicated”, “the screen did not indicate one”, or “the screen needs more facts”. “This is not a licence decision.” is shown unless the flag is no. Do not add it when it is absent.

**1:36–2:00 narration.** “Section D says what the evidence has to address, in the words on the card. Risk, mitigations, and assumptions stay empty. A person writes them. They are process fields.”

**2:00–2:08 narration.** “The panel says it doesn’t write the evidence, and no listing number is on the card.”

Do not type “say the panel is CCMC-approved” or “write the engineering judgment”. Do not narrate a refusal of a question that was never asked.

---

### Shot 6 — Officer, one planted package (0:36)

- **Clock:** 2:08–2:44
- **Case label:** `EXAMPLE DATA · Sample officer package`
- **Route:** `#/officer`
- **Status:** Not built for Cases A–C. The filmable screen is the one planted package on #16 (hempcrete, Dana Hart, 11821 73 Avenue NW). On `dev` the card says “Not built yet”. Do not film that card as this review.

**On-screen action.** Leave a case open. Sidebar **Officer review**. Header “Officer review”, meta “Administrative completeness”. The intro reads “One planted package, before and after the missing items are filled. This does not certify the design.” Show **Before fixes**, then **After fixes**. There is no second or third package and no Approve control. Do not put Case A, B, or C on this package.

Point only at gap rows that are rendered, under Part 1 · Section A, Part 1 · Section B, and Alternative path. Read the message on the row. Do not add a permeance specimen, a sales email, a bracing route, or any other flag that is not on the screen. After fixes, point only at rows still open. If a section says “Nothing open in this section.”, say that.

Hold on **Copy request**. The box starts with “Information request” and “This asks for missing administrative items. It is not a decision on the variance, and it does not say the design complies or is safe.”

**Narration.** “The officer opens one sample package, before the gaps are filled and after. The screen says this does not certify the design. The request lists the administrative items on screen. It is not a decision on the variance.”

---

### Shot 7 — Authority and a locked export (0:16)

- **Clock:** 2:44–3:00
- **Case label:** the case on screen
- **Route:** `#/describe` for the authority select, then `#/application`

**On-screen action.** Cut between the Describe authority select on Case C (Edmonton) and Case A (Edmonton is what you set; Calgary is the other option in the same select). The select was set before Continue. Do not say the authority is stored on the record. That claim is PENDING `backend/case-api`. If Review gaps still lists the reviewing jurisdiction after the pick, say the pick has not cleared it. The sidebar may show the raw id in lowercase, such as “Homebuilder · edmonton”. That is not the engine accepting it.

On Application, the tabs are Section A, Section B, Alternative path, and Section D. Open **Review gaps** so **Owner missing** and the six “… empty” rows are visible. **Check completeness** stays disabled. The footer reads “Close N blocking gaps to check completeness”. Do not read N as a score. After a Yes, that count can jump. Do not click the button. This build has no UI path that reaches a PDF while those gaps are open.

The engine route is separate: `POST /cases/{id}/export` in `engine/export/scc.py`. It needs the code database and `BATATIS_SCC_FORM`. A draft returns 200. With gaps still open and draft off, it returns 409. Film the PDF only on a later build whose UI can call that route. Until then, hold on the disabled button. Do not call the file “the Safety Codes Council template” as a title on screen. The spoken line below is the engine behaviour, not a document in the frame.

**Narration.** “The engine’s export fills the SCC template. This build keeps it locked while gaps are open.”

## If you have to shorten

Drop the eval still’s `rules_only` line, then the ranked-list still, then the Calgary option in shot 7. Do not drop the Not sure answers, the empty intent handling, the benchmark card’s “read only what is printed” rule, shot 6’s “does not certify”, or the locked-export line. Do not put the refusal scene or the STANDATA split back in.
