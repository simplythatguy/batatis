# Demo video script (3:00)

Edit clocks below. Spoken lines are sized for that slot. If a click runs long, drop a sentence from the end of the narration. Keep the empty fields, the on-screen line “Recommendations only. You write the evidence and the answers. This does not decide that the design complies or is safe.”, and the officer line “This does not decide whether the design complies or is safe.”

This cut is recordable on PR #16’s screens at `f66a461` (re-check against #16's merge sha before recording), plus three stills you add in the edit: the ranked list, the benchmark card, and the eval card. The app does not show a ranked identify list, a benchmark card, or the eval numbers. After #16 merges, re-check the Code check note (“Article ranking isn't available on this engine yet…”) and the gap labels once more.

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
| [PR #16](https://github.com/simplythatguy/batatis/pull/16) | `cursor/e2e-product-flow-4362` @ `f66a461` (re-check against #16's merge sha before recording) | The screens you film: `#/`, `#/describe`, `#/code-check`, `#/section-c`, `#/application`, `#/officer`. Run the engine from this branch. |
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

Shots 2 and 4 show the Case C line. Shot 3 shows the Case A line. Shot 6 shows the Case A line, because that is the open application. Shot 7 shows the case that is actually on screen.

## Do not record

- **Try an example.** On Who those three buttons are always visible: “Manufacturer · NorthCore sheathing”, “General contractor · corridor ducts”, “Homebuilder · infill soffit”. Do not click them. Frame or crop above them. They are not Cases A–C.
- **Paste text from your plans.** Leave the box empty. There is no upload control to drop a PDF on.
- **Use this provision.** On Section C, do not click it. Scroll past or crop those cards.
- **Footer and gap-note jargon.** Crop the footer status text (“Draft saved on the engine…”, “Checking GET /cases/{id}/gaps…”) and the note under **What is missing** when it names a GET path.
- **`#/accuracy`.** The nav label is **Accuracy report**. Do not open it. The eval still in shot 4 is the only place those counts appear, and it is labelled model-checked, not human-verified.
- **A compliance, safety, or certification finding.** The tool does not decide those. You may read the officer request’s own sentence, which says it does not.

## Setup

1. App from PR #16 at `f66a461` (re-check against #16's merge sha before recording): `cd web && npm run dev`. Run the engine from PR #16’s branch, not #12. Engine on `http://127.0.0.1:8000` so `/api` proxies. Width about 1440.
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
| 6 | 2:08–2:44 | Case A | Officer review of the open application | Review |
| 7 | 2:44–3:00 | Case on screen | Authority, gaps open, then the draft variance-form PDF | Usability and portability |

`#/officer` reviews the application that is already open. It does not open a sample package. Shot 6 films Case A.

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

- `rules_plus_unknown 50/60 in-sample, 0 under-flags (on text-only cases it answers only yes or ask, never no, so 0 under-flags holds by construction), 27 unknowns sent to the applicant; held-out 7/8 blind (pre-fix), post-fix 4/8 (no longer blind); model-checked, not human-verified`
- `rules_only`, dev set: 55/60 in-sample, 1 under-flag
- `[if merged: PR #12] c_openai_rerank_verify: top-1 9/11 and recall@5 9/11 on the 11 dev cases with a gold article (in-sample, single run, 9 cases without gold excluded); BM25 baseline 5/11; asks the applicant on 40% of cases, model-checked, not human-verified`

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

Read “Practice of engineering: {flag}. {sentence}” as shown. On this build a depends flag reads "Practice of engineering: depends. The screen needs more facts. This is not a licence decision." A no flag reads "Practice of engineering: no. The screen did not indicate one." Read it as shown. `at_stake` and a per-issue `practice_of_engineering` value are on a card only when that issues list is rendered. Speak them only when those words are on screen. Do not attach a file, a letter, or a drawing. An attachment is not what clears the flag. Nothing is uploaded in this recording.

**1:36–2:00 narration.** “Section D says what the evidence has to address, in the words on the card. Risk, mitigations, and assumptions stay empty. A person writes them. They are process fields.”

**2:00–2:08 narration.** “You write the evidence, and it does not decide compliance.”

Do not type “say the panel is CCMC-approved” or “write the engineering judgment”. Do not narrate a refusal of a question that was never asked.

---

### Shot 6 — Officer review of the open application (0:36)

- **Clock:** 2:08–2:44
- **Case label:** `EXAMPLE DATA · Case A · Manufacturer`
- **Route:** `#/officer`

**On-screen action.** Case A is still open from shot 3. Sidebar **Officer review**. Header “Officer review”, meta “Administrative completeness”. This screen reviews that application. It does not open a sample package. A blank application says “Your application is blank. This screen does not open the sample package.” With Case A open, the intro reads “This review is of the application in front of you. It checks whether information is present. It does not decide whether the design complies or is safe.”

Walk the sections in this order. Read only what is printed.

1. **Documents.** With nothing uploaded, the line is “No documents uploaded on this application.”
2. **Open Not sure.** Case A has two Not sure answers from shot 3. If those rows render, point at them and say “Mira's two Not sure answers are open questions for the officer.” If the section says “No open Not sure answers.”, say that.
3. **Open questions from article ranking.** This heading is on screen only when ranking returned questions. If it is absent, do not invent it.
4. **Professional.** Read the flag lines that are printed.
5. **Grouped completeness report.** Read the note that is printed. If it says the report is not available on this engine yet, say that.
6. **Information request**, with **Copy request**. Above the request, the screen says “Administrative completeness does not decide these.”

There is no Before fixes control, no After fixes control, and no planted package. Do not say “This does not certify the design.”

**Narration.** “The officer opens the application that is already on screen. The screen says this does not decide whether the design complies or is safe. The request lists the administrative items on screen.”

---

### Shot 7 — Authority, gaps open, then the draft variance-form PDF (0:16)

- **Clock:** 2:44–3:00
- **Case label:** the case on screen
- **Route:** `#/describe` for the authority select, then `#/application`

Record the Case C frame in step 2 of the recording order, before Reset. Record the Case A frame after shot 3.

**On-screen action.** Cut between the Describe authority select on Case C (Edmonton) and Case A (Edmonton is what you set; Calgary is the other option in the same select). The note under the select is “Nothing is sent until you pick. You can change it later.” Picking Edmonton clears **Reviewing authority missing**. The sidebar may show the raw id in lowercase, such as “Homebuilder · edmonton”.

On Application, the tabs are Section A, Section B, Alternative path, and Section D. Open **Review gaps** so **Owner missing**, **Confirm storeys** on Case C, and the six “… empty” rows are visible. While those gaps are open the footer reads "N required items need attention." Do not read N as a score.

Then click **Check completeness**. It opens a review dialog. While blocking gaps are open, **Download application PDF** stays disabled; it is enabled only when the engine reports 0 blocking items. Click **Download draft PDF**. That is the engine-filled Safety Codes Council variance form: the 5-page Oct 6, 2026 form plus engine-generated attachment pages (7 for Unc's 3b case; not the brief's Appendix 1). The saved name is the filename the engine returns. The dialog shows it as “Download started:” plus that name. Do not call the attachment pages the brief's Appendix 1. **Download text record** is a separate .txt file. It is not this PDF, and it is not the Safety Codes Council form. The dialog prints “This is an administrative completeness check. It does not decide whether the design complies or is safe.” After the draft is ready, read the sentence that is printed. “This PDF is for administrative review. It does not confirm that the design complies or is safe.” is the line printed when the application PDF is ready, not after the draft.

**Narration.** “Edmonton is selected, and that clears Reviewing authority missing. Check completeness lists what is still missing. The dialog says: This is an administrative completeness check. It does not decide whether the design complies or is safe. When the application PDF is ready, the screen says: This PDF is for administrative review. It does not confirm that the design complies or is safe.”

## If you have to shorten

Drop the eval still’s `rules_only` line, then the ranked-list still, then the Calgary option in shot 7. If `rules_only` is cut, the shipped line stays `rules_plus_unknown 50/60 in-sample, 0 under-flags (on text-only cases it answers only yes or ask, never no, so 0 under-flags holds by construction), 27 unknowns sent to the applicant; held-out 7/8 blind (pre-fix), post-fix 4/8 (no longer blind); model-checked, not human-verified`. Do not drop the Not sure answers, the function and objective printed there, the benchmark card’s “read only what is printed” rule, shot 6’s “does not decide whether the design complies or is safe”, or shot 7’s draft variance-form PDF (the 5-page Oct 6, 2026 form plus engine-generated attachment pages). Do not put the refusal scene or the STANDATA split back in.
