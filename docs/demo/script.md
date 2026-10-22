# Demo video script (4 to 5 minutes)

*One example from the applicant's sign-up to the officer's close-out, filmed on the calm interface. Status is as of Oct 22, 2026, on `dev` at commit 43e7c09, and the live app at <https://batatis-vert.vercel.app> as last checked on Oct 21. Steps whose screens exist are marked **Built**. Steps whose screens are still in progress are marked **Pending UI**, and each has a fallback line, so the video can be recorded after those screens land and never shows or describes a screen that does not exist. Running time: 4:40. Narration: 396 words, about 2.8 minutes of speech at 140 words a minute, which leaves the rest of the clock for typing and clicking. The card order and the wording quoted below come from `web/src/calm/` at commit 43e7c09. Rehearse once on the final build and correct anything that has changed.*

## What the video must say, and must not

**Say.** Batatis helps an applicant prepare a complete, code-referenced application and helps an officer see what is missing. It checks administrative completeness. The officer decides. The people, project and addresses are fictional.

**Never say or show.** That the design complies, is safe, is approved or is acceptable. Any accuracy figure for code identification, because the final pipeline is not measured (`docs/implementation-plan.md` §6.2). That Batatis saves an officer time, because there is no timing data. The name of any AI or scoring provider. A real person, address or email. The old `#/accuracy` page, the Settings page, the assistant (unless it is tested live), browser developer tools, or any screen showing "Checking…" or an error.

## Example data (all fictional)

An **EXAMPLE DATA** label sits bottom left on every frame that shows case data, including the first frame. It is added in the edit and is not part of the app. Its text is "EXAMPLE DATA · fictional people, project and addresses".

| Item | Value |
|---|---|
| Applicant | Priya Natarajan, Larkspur Example Homes Ltd. (the persona in `evals/demo-cases/`). Account email `priya@example.com`, an address on the reserved example domain |
| Officer | Dana Example, City of Edmonton, officer account on the example domain. The authority access code is a secret and is never on screen |
| Site | 0000 Example Crescent NW, Edmonton, AB. Legal description Lot 0, Block 0, Plan 0000000 |
| Departure | The worked example in the Council's presentation: Sentence 9.10.15.4.(1), glazed openings in an exposing building face, attribution [F03-OP3.1]. The code database returns that pair, and the sentence is on PDF p.901 |
| Professional (Section D) | "Example Engineer", registration "EXAMPLE-0000". Obviously fictional. Confirm the field names in rehearsal |

**Paste this into Describe.** The first five lines are labelled, so the app reads them as the applicant's own statements and fills Sections A and B without asking again. The last paragraph is the applicant's own description, and it states what she proposes, not whether it is acceptable.

```text
Owner: Larkspur Example Homes Ltd.
Representative: Priya Natarajan
Mailing address: 0000 Example Way NW, Edmonton, AB
Municipal address: 0000 Example Crescent NW, Edmonton, AB
Legal description: Lot 0, Block 0, Plan 0000000

We are building a two-storey house on a narrow lot. The side wall faces the neighbouring lot and is 1.2 m from the property line. The architect drew a large window wall on that side. Its glazed area is bigger than the limit for that distance in the code's table, and we want to keep it. We propose a fire-rated window assembly and an exterior wall rated for fire exposure to make up for it.
```

**What Priya writes on the alternative-path cards.** Each is a short text she types, and the narration says Batatis never writes them.

- Rationale: "The client wants daylight on this side of a narrow lot. We propose a fire-rated window assembly in place of the smaller opening area the table allows."
- Risk: "Fire could spread through the window wall to the neighbouring house if the assembly fails."
- Mitigation: "Fire-rated glazing and frames in a rated exterior wall, installed to the manufacturer's listing."
- Assumptions: "The neighbouring house stays where it is, and the assembly is maintained."
- Maintenance: "The owner inspects the window wall every year and replaces damaged seals."
- Qualifications: "Example Engineer is responsible for the assembly details."

## What must be working before it can be recorded

1. **The pending screens are merged and deployed.** Intake facts with pointers, the five-question planner, and the fork and scope notices. Code identification's quoted choices and benchmark record. The jurisdiction picker and process notes. The officer package review, the information request, the re-upload diff and the close-out record (`docs/implementation-plan.md` §3). If one is not ready, use that shot's fallback line, or cut the shot if it has none.
2. **Live model access is on, with the spend cap in place,** and the relevance rings are scored. Without it, code identification shows its labelled keyword fallback. Run the example description and confirm that 9.10.15.4.(1) appears among the offered articles. If it does not, change the wording of Priya's description and not the narration.
3. **The official PDF exports on the deployment.** The Council's form file must be present on the server, and its SHA-256 must match the field map (`docs/deploy.md`). Export once and open the PDF.
4. **An officer account exists** for Edmonton, in a separate browser profile, with the access code set on the server (`docs/api/accounts-review.md`). Do the officer's onboarding before recording and film only the sign-in.
5. **A clean slate.** New applicant and officer accounts on the example domain, no earlier test applications in the list, and nothing left from an old case. Cases are deleted after 7 days.
6. **The final commit is the one deployed.** Vercel's deployment allowance ran out once on Oct 20 (`docs/deploy.md`), so deploy early and film that exact commit.
7. **Rehearse the whole path once** with a stopwatch. Compare each shot with its window below. Check that the card order matches the order written here.
8. **The recording set-up.** A 1440 by 900 window at 30 frames a second, the dark interface as designed, no notifications from other apps, and captions burned in from the narration lines. Narrate at about 140 words a minute, by voice or by a text-to-speech voice. The Playwright tools and voices used for an earlier draft sit outside the repo (`demo-video-tools`), and the open PR #28 is a one-command recorder: check either against the final screens before relying on it.

## Shot list

| Shot | Clock | Who | Screen | Status |
|---|---|---|---|---|
| A1 | 0:00 to 0:18 | Applicant | Sign-up and onboarding | Built |
| A2 | 0:18 to 0:40 | Applicant | Describe | Built |
| A3 | 0:40 to 1:13 | Applicant | The first questions | Built, with a pending part: pointers and the five questions |
| A4 | 1:13 to 1:51 | Applicant | Code check and the code drawer | Built, with a pending part: three quoted choices and the benchmark record |
| A5 | 1:51 to 2:13 | Applicant | The alternative-path cards | Built |
| A6 | 2:13 to 2:33 | Applicant | Section D and the engineer callout | Built |
| A7 | 2:33 to 3:11 | Applicant | Review, Application, the PDF, submit | Built |
| O1 | 3:11 to 3:33 | Officer | Sign-in, queue, claim, paper sheet | Built |
| O2 | 3:33 to 3:58 | Officer | Package review and information request | Pending UI |
| O3 | 3:58 to 4:18 | Both | Return, resubmit, accept | Built (the re-upload diff is Pending UI) |
| O4 | 4:18 to 4:32 | Officer | Close-out record | Pending UI |
| C1 | 4:32 to 4:40 | | Closing card | |

The deck asks its cards in the order of the form: Section A, Section B, Section C, then Priya's own alternative-path cards and Section D. That is why the reviewing authority comes before the code check.

### A1. Sign-up and onboarding (0:00 to 0:18, Built)

**Screens.** `#/signup`, then `#/onboarding`.

**Actions.**

1. Open with the title card for 3 seconds: "Batatis" and the EXAMPLE DATA label.
2. On "Create your account" type the name, the example email and a password. The password is masked. Press **Continue**.
3. On "How will you use Batatis?" choose **I'm applying for a variance** (sub-line "Manufacturer, general contractor or homebuilder").
4. On "Which describes you best?" choose **Homebuilder**. The app lands on Describe.

**Narration.**

> Priya builds houses in Edmonton. She wants a variance, so she makes an account and says she is a homebuilder. The people, projects and addresses in this video are fictional.

*30 words, 12.9 s at 140 wpm in a 18 s window.*

### A2. Describe (0:18 to 0:40, Built)

**Screen.** `#/`. Headline "What are you building differently?".

**Actions.**

1. Paste the example text into the box. Pause so the labelled lines are readable.
2. Press **Start** (the button shows the ⌘↵ hint). The app goes to `#/questions`.

**Narration.**

> She describes the project in her own words, and labels the owner and the address so Batatis can read them. Anything it only infers from her sentences, it asks her to confirm.

*32 words, 13.7 s at 140 wpm in a 22 s window.*

### A3. The first questions (0:40 to 1:13, Built with a pending part)

**Screen.** `#/questions`. One card at a time, in form order.

**Actions.** Use the A, B and C keys to speed up the choices.

1. "What date is this request?" Pick today's date.
2. "Who will review your application?" (eyebrow "Section B · Reviewer"). Choose **Edmonton**. The choices are Calgary, Edmonton and "Not sure yet".
3. "Check what we read": "How many storeys is the building?", with the line "Your description says “two-storey”." Choose **Yes, 2 storeys**. Pause on the quoted phrase.
4. "Is this for one site, or the whole jurisdiction?" Choose **No, one site**.
5. "Do you already have a permit number?" is optional and is offered once. Press **Skip**.
6. "Is this the alternative you're proposing?" quotes her description. Choose **Yes, use my description**.
7. The owner, representative, mailing address, municipal address and legal description were labelled lines, so they are already filled and are not asked again.
8. **Pending UI.** When the intake reader's screen lands, show the highlighted source phrase on each fact it read, a conflict turned into a question, and the planner's questions with their "Why we ask" lines (at most five). When the jurisdiction picker lands, show Edmonton's process note with the authority card.

**Narration.**

> The questions come one at a time, in the order of the form. She picks the reviewing authority. Batatis shows what it read from her words, each fact beside the phrase it came from, and she confirms it. It asks at most five questions, and it says why it asks.

*50 words, 21.4 s at 140 wpm in a 33 s window.*

**If the screen is not built when you record, say instead:** The questions come one at a time, in the order of the form. She picks the reviewing authority, and she confirms the storey count that Batatis read from her words. The count is not added until she says yes. *(37 words.)*

### A4. Code check and the code drawer (1:13 to 1:51, Built with a pending part)

**Screen.** `#/questions`. Cards with the eyebrow "Code check".

**Actions.**

1. The card reads "Is your design different from what this rule asks for?" with a citation chip such as `9.10.15.4.(1) Show the code`. Click the chip.
2. In the drawer, scroll the verbatim code text (label "Code text · verbatim", its PDF page and the NRC credit). Open "Why this rule exists" and point at the label that says the national intent statements are explanatory. Show the objective and function chips for the pair (OP3.1 and F03). Close with **Esc**.
3. Choose **Yes, it differs**.
4. **Pending UI.** When the quoted-choices screen lands, show the offer of up to three articles, each with a quote and a question, and the benchmark acceptable-solution record. Today the cards come from the whole ranked list and can be many, so do not film this shot until the screen limits them.

**Narration.**

> Now the code. Batatis scores every Division B article against her description and offers up to three, each with the code's own words. It commits nothing by itself. She opens the code. The text is verbatim, with its page. She says her design differs from this rule.

*47 words, 20.1 s at 140 wpm in a 38 s window.*

**If the screen is not built when you record, say instead:** Now the code. Batatis ranks articles for her description. She opens one. The text is verbatim, with its page, and the national intent statement is labelled explanatory. Nothing joins Section C until she says her design differs. *(37 words.)*

### A5. The alternative-path cards (1:51 to 2:13, Built)

**Screen.** `#/questions`. Cards with the eyebrow "Your case".

**Actions.**

1. Type the short text above on each card: rationale, risk, mitigating measures, assumptions and limits, maintenance, and qualifications.
2. Keep the card line "You write this in your own words. Batatis never writes it for you." on screen for one card.

**Narration.**

> Then the alternative path. She writes her own rationale, risk and mitigation. Batatis asks the questions and shows what to include. It never writes these for her.

*27 words, 11.6 s at 140 wpm in a 22 s window.*

### A6. Section D and the engineer callout (2:13 to 2:33, Built)

**Screen.** `#/questions` (the card "Who is responsible, and which documents back this up?"), then `#/review`.

**Actions.**

1. Answer the professional questions and show the list of evidence documents and who is responsible for each. Enter the fictional professional ("Example Engineer", "EXAMPLE-0000") so that the official PDF can unlock later.
2. Open `#/review` and show the amber callout "An engineer or architect is required for Section D" with the line "Batatis can list what that evidence must address, but it can't write it." If the callout disappears once the professional is entered, film it first and enter the professional afterwards.

**Narration.**

> Section D is evidence, and that needs a professional. Batatis says when an engineer or architect is required, lists what the evidence must address, and stops there.

*27 words, 11.6 s at 140 wpm in a 20 s window.*

### A7. Review, Application, the PDF and submit (2:33 to 3:11, Built)

**Screens.** `#/review`, then `#/application`.

**Actions.**

1. On Review press **Check my application**. Read the headline ("Almost there. N things stand between you and the official PDF." or "Nothing required is missing."), the tiles and the "Still needed" list. Press **Answer** on one row to fix it, then return.
2. Show the Sections A to D panel, with Section C's line "looked up, not AI-written".
3. Press **Preview application** to show the paper sheet. Point at the Section C row, "Objectives OP3.1 · Functions F03".
4. In the download panel, first show the gate while anything is missing ("The official PDF unlocks after a current check finds no required items."). When it reads "Ready for the official PDF.", press **Official PDF**.
5. Open the downloaded PDF. Page 1 shows Part 1 filled in. Show that the officer's Part 2 and the signatures are blank. Fields that Priya left empty, such as the permit number, stay blank. A field shows N/A only if the applicant has said it does not apply and given a reason, and there is no screen for that yet (PR #60 is backend only), so do not film or mention N/A.
6. Press **Submit to Edmonton**. The panel reads "Sent to Edmonton" and "Waiting for an officer to pick it up."

**Narration.**

> The review lists what is missing, by section. When nothing required is missing, the Council's October 2026 form unlocks. Part 1 is filled in from her answers, and the officer's part and the signatures are blank. Batatis checks completeness, not whether the design complies. She submits it to Edmonton.

*49 words, 21.0 s at 140 wpm in a 38 s window.*

### O1. Officer sign-in, queue, claim and the paper sheet (3:11 to 3:33, Built)

**Screens.** `#/signin`, `#/review` (the queue), `#/review/<case id>`.

**Actions.**

1. In the officer's browser profile sign in with the example email and password. The app opens the queue, titled "Review queue" with the authority's name.
2. Show the row: the application title, the applicant, when it was sent, the completeness count, the status and the reviewer column. Press **Start reviewing**.
3. On the application page read the paper sheet beside the "Completeness" list. Point at an item marked "— missing" and, if one exists, a value marked "not confirmed by the applicant".

**Narration.**

> On the other side, an officer signs in. The queue shows what has been sent. She starts reviewing, so nobody duplicates the work, and reads the application as a paper sheet beside its completeness list.

*35 words, 15.0 s at 140 wpm in a 22 s window.*

### O2. Package review and the information request (3:33 to 3:58, Pending UI)

**Screen.** The application page for the claimed case. The exact panel is not built yet.

**Actions (when the screen lands).**

1. Open the package review for this case. Show the findings grouped by section A to D and the process items, each field marked present, blank or not found, and the supporting-documents panel.
2. Open the drafted information request. Edit one item, then send it. The applicant is notified.
3. Show that nothing in the panel says the design is acceptable.

**Narration.**

> The package review reads the form and its attachments, and reports each field as present, blank or not found. It drafts a request where every item is a question to the applicant. The officer edits it and sends it.

*39 words, 16.7 s at 140 wpm in a 25 s window.*

**If the screen is not built when you record, say instead:** The officer returns the application with a message and ticks the items the applicant should fix. *(16 words.)*

### O3. Return, resubmit and accept (3:58 to 4:18, Built)

**Screens.** The officer's page, the applicant's page, then the officer's page again. Keep this to a short cut.

**Actions.**

1. If the information request is not built, press **Return with message** on the officer's page, tick the items to address and press **Send and return** (the dialog is titled "Return with a message").
2. In the applicant's profile show the notification bell and the returned banner with the officer's message. Fix one item and press **Resubmit to Edmonton**.
3. Back in the officer's profile press **Accept as complete**. Read the dialog: "Accept as administratively complete?" and "It isn't an approval of the design; technical review stays with the authority." Confirm. The page shows "Accepted as administratively complete."
4. **Pending UI.** After a package re-upload, show the line "x of y gaps resolved".

**Narration.**

> Priya fixes the items and resubmits. The officer accepts the application as administratively complete. The screen says this is not an approval of the design.

*25 words, 10.7 s at 140 wpm in a 20 s window.*

### O4. Close-out record (4:18 to 4:32, Pending UI)

**Screen.** The accepted case. The panel is not built yet.

**Actions (when the screen lands).** Show the close-out record: the due date 10 days after the decision (the rule before Dec 1, 2026), what to send to the Council (the variance as decided, for the single location) and what to keep. Press the control that records that the officer sent the copy. State on screen that Batatis sends nothing. Do not say that the 10-day date still holds after Dec 1: from then the Council's portal rule applies (register at issuance or as soon as reasonably practicable after), and the record does not follow it yet.

**Narration.**

> After the decision, a close-out record lists what to send the Council and what to keep, with a due date. The officer sends or registers it. Batatis never does.

*29 words, 12.4 s at 140 wpm in a 14 s window.*

### C1. Closing card (4:32 to 4:40)

**Screen.** A plain card for 8 seconds, with the EXAMPLE DATA label. Three lines. **Built**: sign-up, the question flow, Section C by lookup, the Council's form, the officer queue and decision. **Backend, screens in progress**: intake reader, code identification, jurisdiction packs, package review. **Roadmap**: coded rules, standing-package checklists, accuracy report, Calgary form, other provinces. If a pending screen did land, move its line to **Built**.

**Narration.**

> Batatis checks completeness. The officer decides.

*6 words, 2.6 s at 140 wpm in a 8 s window.*

## After recording

1. Play the video with the sound off and read the captions. Confirm that nothing says or implies that the design complies, is safe, is approved or is acceptable.
2. Play it with the captions off and listen for a provider's name. There must be none.
3. Check the EXAMPLE DATA label on every frame with case data, including the first.
4. Check the running time (4:40 as written, 5:00 at most). If it runs long, shorten the pauses before cutting a narration line.
5. If any shot used a fallback line or was cut, say so in the submission notes.
6. Save the final file outside the repo, and record its name and the commit that was filmed in `docs/submission/README.md`.

## Where each claim comes from

| In the video | Source |
|---|---|
| The Council's form dated Oct 6, 2026, Part 2 and signatures blank | `engine/export/field_maps/scc_2026-10.json`, `docs/research/2026-10-21-source-checks.md` §1 |
| Section C looked up from the attribution tables | `codedb/README.md`, `docs/api/identify.md` |
| 9.10.15.4.(1) with [F03-OP3.1], PDF p.901 | `docs/research/2026-10-21-source-checks.md` §7 |
| The close-out record lists what to send and keep, with a due date 10 days after the decision (the rule before Dec 1, 2026; the Council's portal rule applies from Dec 1) | `docs/research/2026-10-21-source-checks.md` §1 (IB-2025-11-18 for the 10 days, IB-2026-10-01 for the portal from Dec 1), `docs/api/package-review.md` |
| "Accepted as administratively complete" | `docs/api/accounts-review.md`, `web/src/calm/reviewer/ReviewDetail.tsx` |
| Package review and information request | `docs/api/package-review.md` |
| Screen text quoted above | `web/src/calm/` at commit 43e7c09 |
