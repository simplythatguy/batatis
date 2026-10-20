# Demo video script (3:00)

Edit clocks below. Spoken lines are sized for that slot. If a click runs long, drop a sentence from the end of the narration. Keep the empty fields, the on-screen line “Recommendations only. You write the evidence and the answers. This does not decide that the design complies or is safe.”, and the officer line “This does not certify the design.”

This cut is recordable on PR #16’s screens at `579cd2c`, plus three stills you add in the edit: the ranked list, the benchmark card, and the eval card. The app does not show a ranked identify list, a benchmark card, or the eval numbers. Re-check this script against #16’s merge sha before the final push to PR #20.

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
| [PR #16](https://github.com/simplythatguy/batatis/pull/16) | `cursor/e2e-product-flow-4362` @ `579cd2c` | The screens you film: `#/`, `#/describe`, `#/code-check`, `#/section-c`, `#/application`, `#/officer`. Run the engine from this branch. |
| [PR #12](https://github.com/simplythatguy/batatis/pull/12) | `backend/identify-api` | The ranked-list still and the `benchmark_acceptable_solution` still, from an identify payload for the pasted text. The published top-1 line on the eval still. Do not run this engine while filming. |

Run `web/` from PR #16. Run the engine from PR #16’s branch, not #12. #12’s `/cases/{id}/identify` adds unanswered ranked cards, which changes the Your-words card counts and blocks **Continue to Section C**. Do not film `dev` and call it this demo. On `dev` the app opens a preloaded NorthCore fixture, there is no Who screen, no Search, and no “Add to this check”. Officer review is the “Not built yet” card. The application button on `dev` already reads **Check completeness**.

## Cases (example data)

People, companies, addresses, and products in the paste are fictional. Citations on a code row come from the NBC(AE) 2023 **2nd-printing** code database. The Code check header reads `NBC(AE) 2023, 2nd printing`. A citation on a row looks like `NBC(AE) 2023 p2, Div B, … [PDF p.952]`. Read the string on the row. Do not quote a page from memory.

Narrate a fact only when it is on screen after the paste: in the description box, on a chip, in the ledger, or on a code row. Do not narrate the PDFs. Permeance, an unsigned letter, a sales email, a supplier quote, bracing, and an OSB or furring thickness are not in the paste. Leave them out.

| Label (edit overlay) | Who | Paste this into Describe |
| --- | --- | --- |
| `EXAMPLE DATA · Case C · Homebuilder` | Priya Natarajan, Larkspur Example Homes. | Two-storey infill at 0000 Example Crescent NW, Edmonton, about 210 m², no sprinklers. Heated slab with R-7.5 under it. Unvented low-slope roof, spray foam thickness still TBD. Bedroom 3 window clear opening 400 mm by 780 mm. What needs a variance? |
| `EXAMPLE DATA · Case A · Manufacturer` | Mira Okafor, Example Panel Works Ltd. Product: EPW NailBase CI-50. | We make EPW NailBase CI-50, a 50 mm insulating sheathing panel, and we want it approved across Alberta so builders can nail vinyl siding straight into the facer. One pilot house: 0000 Example Way NW, Edmonton. Owner not decided. No legal description. No permit yet. |

Describe has no upload control. Above an empty box it reads “Upload isn't available yet. Paste the text instead.” The box label is **Paste text from your plans**. Leave that box empty. Cue sheets under `evals/demo-cases/keys/<case>/` stay off the machine and off camera. Their headers say agent-authored, model-checked, not human-verified. Do not read `sco-review.md` as the officer script.

## Lower third (edit overlay, not app UI)

“EXAMPLE DATA” is not in the app. You add it in the edit, bottom left, including the first frame. If the app later has its own EXAMPLE banner, keep this overlay off that banner.

Shot 1 shows all three lines (the contractor line is named there and not walked through):

`EXAMPLE DATA · Case A · Manufacturer`
`EXAMPLE DATA · Case B · General contractor`
`EXAMPLE DATA · Case C · Homebuilder`

Shots 2 and 4 show the Case C line. Shot 3 shows the Case A line. Shot 6 shows only `EXAMPLE DATA · Sample officer package`. Shot 7 shows the case that is actually on screen.

## Do not record

- **Try an example.** On Who those three buttons are always visible: “Manufacturer · NorthCore sheathing”, “General contractor · corridor ducts”, “Homebuilder · infill soffit”. Do not click them. Frame or crop above them. They are not Cases A–C.
- **Paste text from your plans.** Leave the box empty. There is no upload control to drop a PDF on.
- **Use this provision.** On Section C, do not click it. Scroll past or crop those cards.
- **Footer and gap-note jargon.** Crop the footer status text (“Draft saved on the engine…”, “Checking GET /cases/{id}/gaps…”) and the note under **What is missing** when it names a GET path.
- **`#/accuracy`.** The nav label is **Accuracy report**. Do not open it. The eval still in shot 4 is the only place those counts appear, and it is labelled model-checked, not human-verified.
- **A compliance, safety, or certification finding.** The tool does not decide those. You may read the officer request’s own sentence, which says it does not.

## Setup

1. App from PR #16 at `579cd2c`: `cd web && npm run dev`. Run the engine from PR #16’s branch, not #12. Engine on `http://127.0.0.1:8000` so `/api` proxies. Width about 1440.
2. Start at Who with **Reset case**. Typing `#/` while a case is open opens Describe, not Who. On Who there is no sidebar nav, only the case card and **Reset case**. The title in the header is still **Who are you?**
3. Set **Which authority will review this?** before Continue. The note under the select is “Nothing is sent until you pick. You can change it later.” Picking Edmonton clears **Reviewing authority missing**. The select exists only on Describe.
4. `#/officer` shows Who unless a case is open. Any open case is enough for shot 6.

## Recording order

The app holds one case. **Reset case** wipes it, including the note “Cleared. Nothing from the previous case is kept.” Do not record the shots from top to bottom.

1. Shot 1.
2. Shot 2, then shot 4, then shot 5, then shot 7’s Case C frame. Case C stays open through these. Do not Reset.
3. Reset, then shot 3 (Case A).
4. Shot 7’s Case A frame.
5. Shot 6, with Case A still open.

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
| 2 | 0:18–0:28 | Case C | Paste. Leave the plans box empty. | Intake |
| 3 | 0:28–0:51 | Case A | Paste, then both Not sure cards | Intake |
| 4 | 0:51–1:36 | Case C | Search, Section C, ranked list, benchmark card, eval still | Code identification |
| 5 | 1:36–2:08 | Case C | Section D, then the on-screen limit | Recommendations, then X factor |
| 6 | 2:08–2:44 | Sample officer package | One planted package | Review |
| 7 | 2:44–3:00 | Case on screen | Authority select, then the SCC variance-form PDF | Usability and portability |

Three example packages on `#/officer` are not built. No open PR loads Cases A–C there. Shot 6 films the one planted package that #16 already renders.

---

### Shot 1 — Three applicants (0:18)

- **Clock:** 0:00–0:18
- **Case label:** all three lines
- **Route:** `#/` Who are you?
- **On `dev`:** no Who screen. It opens Describe on the NorthCore fixture.

**On-screen action.** Hold on Who. The role buttons read Manufacturer, General contractor, Homebuilder. Do not click the three buttons under **Try an example**. Crop above them. Do not click a role yet. The sidebar on this screen is the case card and **Reset case**.

**Narration.** “Three example cases. A manufacturer, a general contractor, and a homebuilder. Same variance template. The people and the projects are fictional.”

---

### Shot 2 — Homebuilder paste (0:10)

- **Clock:** 0:18–0:28
- **Case label:** `EXAMPLE DATA · Case C · Homebuilder`
- **Route:** `#/describe`

**On-screen action.** Click **Homebuilder**. The header is “What are you building?” Paste the Case C paragraph. Set **Which authority will review this?** to Edmonton before Continue. Leave **Paste text from your plans** empty. Open **Review gaps** and point at **Owner missing**, **Mailing address missing**, and **Legal description missing**. Permit stays empty. It is optional and has no chip. Open the fact ledger. It shows **What you described** and **Proposed alternative**, both from Your description, plus a **Storeys** fact. Storeys is a proposed fact, with **Confirm** and **Not right**. Leave it unconfirmed. That adds a blocking gap labelled **Confirm storeys**. Do not narrate a slab STANDATA, a roof STANDATA, or a supplier quote. That classification is not on this build.

**Narration.** “Priya’s description is a two-storey Edmonton infill. The window opening on screen is 400 by 780 millimetres. Owner, mailing address, and legal description are missing. Storeys is still unconfirmed.”

---

### Shot 3 — Not sure (0:23)

- **Clock:** 0:28–0:51
- **Case label:** `EXAMPLE DATA · Case A · Manufacturer`
- **Route:** `#/` then `#/describe` then `#/code-check`

Film this after shot 7’s Case C frame. **Reset case** here wipes Case C. That is the point of the recording order.

**On-screen action.** **Reset case.** The note reads “Cleared. Nothing from the previous case is kept.” Click **Manufacturer**. Paste the Case A paragraph. Set the authority to Edmonton before Continue. Leave **Paste text from your plans** empty. Open **Review gaps**: **Owner missing**, **Mailing address missing**, **Legal description missing**. The ledger is **What you described** and **Proposed alternative** only. Case A states no storeys, so there is no Storeys fact.

Click **Continue to code check**. The note on this engine is “Article ranking isn't available on this engine yet. These cards are questions from your description.” Two **Your words** cards are on screen: **Sheathing membrane** and **Storey count**. Each says “From what you wrote. Not a ranked article.” Answer **Not sure** on both. Do not answer Yes. Unanswered cards block **Continue to Section C**.

**0:47–0:51.** Hold 3–4 seconds on the question saved under a Not sure answer. The label is **Open question**, then the card’s question, then “Logged as an open question.” That is the Not sure answer. Do not answer Yes or No.

**Narration.** “Mira’s description names a 50 millimetre panel, vinyl nailed into the facer, and one Edmonton house. Those two cards are her words. Not sure on both. They are not ranked articles.”

---

### Shot 4 — Code identification (0:45)

- **Clock:** 0:51–1:36
- **Case label:** `EXAMPLE DATA · Case C · Homebuilder`
- **Route:** Case C code check, still open from shot 2, then `#/section-c`, then three stills

Film this immediately after shot 2. Case C is still the open case. Do not Reset. One **Your words** card, from the description. Answer **Not sure** on it. The ranking note reads “Article ranking isn't available on this engine yet. These cards are questions from your description.”

**0:51–1:03, search.** In **Search Division B**, type `bedroom window unobstructed` and search. At most 8 rows. Each row is the id the database returned and a **Code text** pill. If a row’s id is `9.9.10.1.(2)`, click **Add to this check** and answer **Yes**. Open **Code reference** and read the citation that is printed. The header says `NBC(AE) 2023, 2nd printing`. If that id is not in the list, do not type it in, do not say it, and do not add a card.

Read 0.35 m² and the 400 by 780 millimetre opening when the row prints them. That pair is the point of the search. Do not say 0.31 unless that figure is printed on the row. Do not search `heated floor insulation`. Do not voice `9.27.5.1` on this search. That id is a different query (`cladding fastened furring`), and only if a returned row shows it. Search on that query has returned sentences (1) and (5). Do not say sentence (2) unless that id is the row.

**1:03–1:11, Section C.** Click **Continue to Section C**. Section C auto-searches the description and shows up to 8 cards, each with **Use this provision**. Don't click **Use this provision**; scroll past or crop the results. Those buttons add unconfirmed rows. The table has a row only for the article you marked Yes. The source pill reads **Live lookup** when the engine answers. Read the function and objective printed on the row. If the intent cell reads **None for this provision**, say so and do not fill it. If the intent text looks like a different provision, say so and do not read it as this article’s intent. Below the table the blocks are **Code text** and **NBC 2020 Intent Statements**. A live row has no **AI-written** block. That pill is on the Code check question. If the pill says **Lookup failed**, say that and do not recite objective codes from memory.

Say `9.9.10.1.(2)` only if that id is the row on screen.

**Narration for the app frames.** “Search returns database rows only. Section C is a lookup. Read the function and objective printed there, and the intent text on screen. Batatis checks completeness. The officer decides compliance.”

**1:11–1:22, ranked list still.** This list is not the search box, and it is not in this app build. Caption the still `[if merged: PR #12]`, and also `baseline order, not the 9/11 model`. This paste is not a seeded model run, so do not caption it Cached demo run or Keyword search, no AI key. The payload fields are provision, title, probability, and `committed`. On this BM25 fallback still `committed` is false, and identify does not auto-commit. Read only values printed on the still. If you have no payload, omit the still and do not say ranked.

**1:22–1:29, benchmark card.** Caption the still `[if merged: PR #12]`. The card’s role line is `benchmark_acceptable_solution`. Read the provision, the explanation, and the citation if they are on the card. `9.9.10.1.(2)` is an example of that field only when the card prints it. If the card says no article was identified, read that sentence and stop. If you have no card, do not say benchmark. Do not say OSB, furring, or a millimetre thickness.

**1:29–1:36, eval still.** A full-frame still, not `#/accuracy`. The identify line depends on PR #12: caption it `[if merged: PR #12]`. Copy these lines and no others:

- `rules_plus_unknown 50/60 in-sample, 0 under-flags, 27 unknowns sent to the applicant; held-out 7/8 blind (pre-fix), post-fix 4/8 (no longer blind); model-checked, not human-verified`
- `rules_only`, dev set: 55/60 in-sample, 1 under-flag
- `c_openai_rerank_verify: top-1 9/11 and recall@5 9/11 on the 11 dev cases with a gold article (in-sample, single run, 9 cases without gold excluded); BM25 baseline 5/11; asks the applicant on 40% of cases, model-checked, not human-verified`

These figures are not a finding that a design complies, is safe, or is certified.

**Narration.** “Model-checked, on the dev cases. Not a compliance finding.”

---

### Shot 5 — Section D, then the limit (0:24 + 0:08)

- **Clock:** 1:36–2:08
- **Case label:** `EXAMPLE DATA · Case C · Homebuilder`
- **Route:** `#/application?tab=alt`, then `#/application?tab=D`

**On-screen action.** Open **Alternative path**. The six fields are empty: Rationale, Risk assessment, Mitigating measures, Assumptions and limits, Maintenance and operation, Qualifications. Do not type into them. Open **Review gaps** so **Owner missing**, **Confirm storeys**, and the six “… empty” rows are visible. Open **Section D**. The panel title is “Section D and professional screening”.

If there is no engine case, the note is “Save the draft first. Then this page lists the evidence still missing.” Read that and do not invent a card. When the routes return, the line you read is “Recommendations only. You write the evidence and the answers. This does not decide that the design complies or is safe.”

Section D has evidence fields and professional-question dropdowns. Leave them untouched, and don't Save. Do not type into an evidence box. Do not click **Save this evidence**.

Read “Practice of engineering: {flag}. {sentence}” as shown. On this build a depends flag is doubled on screen: “Practice of engineering: depends. depends. The screen needs more facts.” Read the doubled line if that is what is printed. “This is not a licence decision.” is shown unless the flag is no. Do not add it when it is absent. `at_stake` and a per-issue `practice_of_engineering` value are on a card only when that issues list is rendered. Speak them only when those words are on screen. Do not attach a file, a letter, or a drawing. An attachment is not what clears the flag. Nothing is uploaded in this recording.

**1:36–2:00 narration.** “Section D says what the evidence has to address, in the words on the card. Risk, mitigations, and assumptions stay empty. A person writes them. They are process fields.”

**2:00–2:08 narration.** “You write the evidence, and it does not decide compliance.”

Do not type “say the panel is CCMC-approved” or “write the engineering judgment”. Do not narrate a refusal of a question that was never asked.

---

### Shot 6 — Officer, one planted package (0:36)

- **Clock:** 2:08–2:44
- **Case label:** `EXAMPLE DATA · Sample officer package`
- **Route:** `#/officer`
- **Status:** Not built for Cases A–C. The filmable screen is the one planted package on #16: hempcrete walls for a garden suite. The civic address on that package is `100 Example Street NW, Edmonton`. It is a fictional demo value. Read the address that is printed. Do not read `11821 73 Avenue NW`. On `dev` the card says “Not built yet”. Do not film that card as this review.

**On-screen action.** Case A is still open from shot 3. Any open case is enough. Sidebar **Officer review**. Header “Officer review”, meta “Administrative completeness”. The intro reads “One planted package, before and after the missing items are filled. This does not certify the design.” Show **Before fixes**, then **After fixes**. Keep the status line on camera. It reads “Administrative completeness for this planted example. This does not certify the design.” If the engine fails, the line is “The engine's check did not return (…). This list is the browser check for the planted example, not a code review.” Say that if it appears. There is no second or third package and no Approve control. Do not put Case A, B, or C on this package.

Point only at gap rows that are rendered, under Part 1 · Section A, Part 1 · Section B, and Alternative path. Read the message on the row. Do not add a permeance specimen, a sales email, a bracing route, or any other flag that is not on the screen. After fixes, point only at rows still open. If a section says “Nothing open in this section.”, say that.

Hold on **Copy request**. The box starts with “Information request”, “Planted example. Not a real application.”, and “This asks for missing administrative items. It is not a decision on the variance, and it does not say the design complies or is safe.”

**Narration.** “The officer opens one sample package, before the gaps are filled and after. The screen says this does not certify the design. The request lists the administrative items on screen. It is not a decision on the variance.”

---

### Shot 7 — Authority, then the variance-form PDF (0:16)

- **Clock:** 2:44–3:00
- **Case label:** the case on screen
- **Route:** `#/describe` for the authority select, then `#/application`

Record the Case C frame in step 2 of the recording order, before Reset. Record the Case A frame after shot 3.

**On-screen action.** Cut between the Describe authority select on Case C (Edmonton) and Case A (Edmonton is what you set; Calgary is the other option in the same select). The note under the select is “Nothing is sent until you pick. You can change it later.” Picking Edmonton clears **Reviewing authority missing**. The sidebar may show the raw id in lowercase, such as “Homebuilder · edmonton”.

On Application, the tabs are Section A, Section B, Alternative path, and Section D. Open **Review gaps** so **Owner missing**, **Confirm storeys** on Case C, and the six “… empty” rows are visible. While those gaps are open the footer reads “Close N blocking gaps to check completeness”. Do not read N as a score.

Then show the **Check completeness** download. It is the engine-filled Safety Codes Council variance form PDF: the 5-page Oct 6, 2026 form plus engine-generated attachment pages (7 for Unc's 3b case; not the brief's Appendix 1). The dialog says this is not a finding that the design complies. Do not call the attachment pages the brief's Appendix 1. **Download draft record** is a separate `.txt` file, `{id}-draft-record.txt`, and only once every gap is closed. It is not this PDF, and it is not the Safety Codes Council form.

**Narration.** “Edmonton is selected, and that clears Reviewing authority missing. Check completeness downloads the Safety Codes Council variance form: the five-page October 6, 2026 form, plus the engine’s attachment pages. On Unc’s 3b case those attachment pages are seven. They are not Appendix 1. The dialog says this is not a finding that the design complies.”

## If you have to shorten

Drop the eval still’s `rules_only` line, then the ranked-list still, then the Calgary option in shot 7. If `rules_only` is cut, the shipped line stays `rules_plus_unknown 50/60 in-sample, 0 under-flags, 27 unknowns sent to the applicant; held-out 7/8 blind (pre-fix), post-fix 4/8 (no longer blind); model-checked, not human-verified`. Do not drop the Not sure answers, the function and objective printed there, the benchmark card’s “read only what is printed” rule, shot 6’s “does not certify”, or shot 7’s variance-form PDF (the 5-page Oct 6, 2026 form plus engine-generated attachment pages). Do not put the refusal scene or the STANDATA split back in.
