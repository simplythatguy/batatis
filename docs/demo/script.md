# Demo video script (4 to 5 minutes)

*One example from the applicant's sign-up to the officer's close-out, filmed on the calm interface. Status is as of Oct 22, 2026, on `dev` at commit 309ff03, and the live app at <https://batatis-vert.vercel.app>, whose script bundle contains the intake and code-check screens (checked on Oct 22). Steps whose screens exist are marked **Built**. Steps whose screens are still in progress are marked **Pending UI**, and each has a fallback line, so the video can be recorded after those screens land and never shows or describes a screen that does not exist. Running time: 4:40. Narration: 388 words, about 2.8 minutes of speech at 140 words a minute, which leaves the rest of the clock for typing and clicking. The card order and the wording quoted below come from `web/src/calm/` at commit 309ff03, and the cards it reads from the example text were checked by running the intake rules on it without a model. Rehearse once on the final build and correct anything that has changed.*

## What the video must say, and must not

**Say.** Batatis helps an applicant prepare a complete, code-referenced application and helps an officer see what is missing. It checks administrative completeness. The officer decides. The people, project and addresses are fictional.

**Never say or show.** That the design complies, is safe, is approved or is acceptable. Any accuracy figure for code identification, because the final pipeline is not measured (`docs/implementation-plan.md` §6.2). That Batatis saves an officer time, because there is no timing data. The name of any AI or scoring provider. A real person, address or email. The old `#/accuracy` page, the Settings page, the assistant (unless it is tested live), browser developer tools, or any screen showing "Checking…" or an error.

## Example data (all fictional)

An **EXAMPLE DATA** label sits bottom left on every frame that shows case data, including the first frame. It is added in the edit and is not part of the app. Its text is "EXAMPLE DATA · fictional people, project and addresses".

| Item | Value |
|---|---|
| Applicant | Priya Natarajan, Larkspur Example Ltd. (the persona in `evals/demo-cases/` is Larkspur Example Homes Ltd.; the word "Homes" is left out here because the reader takes it for the building's use). Account email `priya@example.com`, an address on the reserved example domain |
| Officer | Dana Example, City of Edmonton, officer account on the example domain. The authority access code is a secret and is never on screen |
| Site | 0000 Example Crescent NW, Edmonton, AB. Legal description Lot 0, Block 0, Plan 0000000 |
| Departure | The worked example in the Council's presentation: Sentence 9.10.15.4.(1), glazed openings in an exposing building face, attribution [F03-OP3.1]. The code database returns that pair, and the sentence is on PDF p.901 |
| Professional (Section D) | "Example Engineer", registration "EXAMPLE-0000". Obviously fictional. Confirm the field names in rehearsal |

**Paste this into Describe.** The first five lines are labelled, which the intake reader recognizes. It proposes each one as a card, and Priya confirms it. The last paragraph is the applicant's own description, and it states what she proposes, not whether it is acceptable. Its last sentence is the only one that says what she wants to do instead, so the reader offers it as one card.

```text
Owner: Larkspur Example Ltd.
Representative: Priya Natarajan
Mailing address: 0000 Example Way NW, Edmonton, AB
Municipal address: 0000 Example Crescent NW, Edmonton, AB
Legal description: Lot 0, Block 0, Plan 0000000

We are building a two-storey house on a narrow lot. The side wall faces the neighbouring lot and is 1.2 m from the property line. The architect drew a large window wall on that side. Its glazed area is bigger than the limit for that distance in the code's table. We propose a fire-rated window assembly and an exterior wall rated for fire exposure instead.
```

**What Priya writes on the alternative-path cards.** Each is a short text she types, and the narration says Batatis never writes them.

- Rationale: "The client wants daylight on this side of a narrow lot. We propose a fire-rated window assembly in place of the smaller opening area the table allows."
- Risk: "Fire could spread through the window wall to the neighbouring house if the assembly fails."
- Mitigation: "Fire-rated glazing and frames in a rated exterior wall, installed to the manufacturer's listing."
- Assumptions: "The neighbouring house stays where it is, and the assembly is maintained."
- Maintenance: "The owner inspects the window wall every year and replaces damaged seals."
- Qualifications: "Example Engineer is responsible for the assembly details."

## What must be working before it can be recorded

1. **The officer screens are merged and deployed (open PR #62).** The package review, the information request, the re-upload diff and the close-out record (`docs/implementation-plan.md` §3). If one is not ready, use that shot's fallback line, or cut the shot if it has none. The intake and code-check screens are merged (PR #61). The benchmark record and the jurisdiction picker have no screen, so the video does not mention them.
2. **Live model access is on, with the spend cap in place,** and the relevance rings are scored. PR #61 walked the new screens only with the offline fake provider, so run the whole example once with live access and compare the cards with A3 and A4. The reader's model pass can add or change cards. Without live access the code check shows its labelled keyword fallback (use the A4 fallback line). Confirm that 9.10.15.4.(1) is among the quoted choices. If it is not, change the wording of Priya's description and not the narration, or add the article from the code library with **Add to my application**, which opens a card for it.
3. **The official PDF exports on the deployment.** The Council's form file must be present on the server, and its SHA-256 must match the field map (`docs/deploy.md`). Export once and open the PDF.
4. **An officer account exists** for Edmonton, in a separate browser profile, with the access code set on the server (`docs/api/accounts-review.md`). Do the officer's onboarding before recording and film only the sign-in.
5. **A clean slate.** New applicant and officer accounts on the example domain, no earlier test applications in the list, and nothing left from an old case. Applications follow the inactivity and workflow retention policy.
6. **The final commit is the one deployed.** Vercel's deployment allowance ran out once on Oct 20 (`docs/deploy.md`), so deploy early and film that exact commit.
7. **Rehearse the whole path once** with a stopwatch. Compare each shot with its window below. Check that the card order matches the order written here.
8. **The recording set-up.** A 1440 by 900 window at 30 frames a second, the dark interface as designed, no notifications from other apps, and captions burned in from the narration lines. Narrate at about 140 words a minute, by voice or by a text-to-speech voice. The Playwright tools and voices used for an earlier draft sit outside the repo (`demo-video-tools`), and the open PR #28 is a one-command recorder: check either against the final screens before relying on it.

## Shot list

| Shot | Clock | Who | Screen | Status |
|---|---|---|---|---|
| A1 | 0:00 to 0:18 | Applicant | Sign-up and onboarding | Built |
| A2 | 0:18 to 0:40 | Applicant | Describe | Built |
| A3 | 0:40 to 1:13 | Applicant | What it read, and the first questions | Built |
| A4 | 1:13 to 1:51 | Applicant | Code check and the code drawer | Built (the benchmark record has no screen) |
| A5 | 1:51 to 2:13 | Applicant | The alternative-path cards | Built |
| A6 | 2:13 to 2:33 | Applicant | Section D and the engineer callout | Built |
| A7 | 2:33 to 3:11 | Applicant | Review, Application, the PDF, submit | Built |
| O1 | 3:11 to 3:33 | Officer | Sign-in, queue, claim, paper sheet | Built |
| O2 | 3:33 to 3:58 | Officer | Package review and information request | Pending UI |
| O3 | 3:58 to 4:18 | Both | Return, resubmit, accept | Built (the re-upload diff is Pending UI) |
| O4 | 4:18 to 4:32 | Officer | Close-out record | Pending UI |
| C1 | 4:32 to 4:40 | | Closing card | |

The deck asks its cards in this order: the facts Batatis read (each one to confirm), up to five planner questions, the reviewing authority (not asked once she confirms Edmonton as the site), the Section A and B details that remain, the code check (Section C), Priya's own alternative-path cards and Section D.

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
2. Press **Start** (the button shows the ⌘↵ hint). The app goes to `#/questions`. The first card reads "Reading what you wrote…" while the intake reader works: "Batatis reads your description and the text of your PDFs, and marks the words each value came from. Nothing is used until you confirm it." It takes a few seconds. The code check starts by itself when the reading ends.

**Narration.**

> She describes the project in her own words and presses Start. Batatis reads what she wrote and marks the words each fact came from. Nothing is used until she confirms it.

*31 words, 13.3 s at 140 wpm in a 22 s window.*

### A3. What it read, and the first questions (0:40 to 1:13, Built)

**Screen.** `#/questions`. One card at a time. Use the A and B keys for the choices and Enter to continue. Keep three cards on screen at normal speed and jump-cut the rest at about a second a card.

**Actions.**

1. The first card has the eyebrow "Check what we read" and the question "Who is the owner?". Her own sentence is shown under it with "Larkspur Example Ltd" marked, then the source line "Your description" and the line "Read from your words." Pause on the marked words. Choose **Yes, Larkspur Example Ltd** (A).
2. Jump-cut through the cards for the representative, the mailing address, "Where is the site?", the municipal address, the legal description, and the lot, block and plan, confirming each with A and Enter. Confirming "Edmonton" as the site also sets the reviewing authority, so "Who will review your application?" is not asked.
3. Slow down on "How many storeys is the building?". Her words "two-storey" are marked. Choose **Yes, 2 storeys**. Then jump-cut through "What is the building used for?" (a single-family house), "How far is the wall from the property line?" (1.2 m) and "Is this what you want to do differently?" (her last sentence; the choice reads "Yes, that's what I want to do").
4. The first planner card has the eyebrow "A quick question". With the rules-only reading of the example text it asks "What is the building area (the footprint) in square metres?", and the planner can re-rank its questions after the code check. Above its input the fork note says "Your design seems to differ from the code's standard way, so this is a variance request." Open "What a variance needs" and point at the two halves, "Permission to build it differently" and "Proof that it works at least as well". Press **Not sure**. The line "Saved as Not sure. It never blocks you, and it is not asked again." appears.
5. Open "Why we ask" on the next planner card (for example "Is the building sprinklered?"), then answer it. Jump-cut through the other planner cards (with the rules-only reading, the Part 4 engineer question and the wall assembly).
6. Jump-cut through the Section A and B cards that remain: "What date is this request?" (today's date), "Is this for one building site, or for every site in the municipality?" (**One building site**), and the optional "Do you already have a permit number?" (**Skip**).

**Narration.**

> Batatis shows each fact it read next to the words it came from, and she confirms each one. It then asks at most five questions and says why. A note says this looks like a variance request, and it never judges the design.

*43 words, 18.4 s at 140 wpm in a 33 s window.*

### A4. Code check and the code drawer (1:13 to 1:51, Built)

**Screen.** `#/questions`. Cards with the eyebrow "Which rules apply · Section C".

**Actions.**

1. The card "Checking the code for your project…" shows four stages: "Reading every rule in the building code" (with the count of articles), "Re-checking the closest ones", "Reading the top matches in full" and "Choosing what to ask you". If the check has not started, the card reads "Check the code for your project." and has a **Check the code now** button. Wait for the four stages to finish, or cut the wait. Press **Continue**.
2. The first code card reads "Does your design do something different from the rule on ...?" with the line "One of the closest matches to what you described. Nothing is used until you answer." Click **Show the code**. The box shows the article number, its title, the verbatim sentence, the citation, the line "Code text, verbatim" and the NRC credit.
3. Click **More about this rule** to open the drawer. Scroll the verbatim code text (label "Code text · verbatim", its PDF page and the NRC credit). Open "Why this rule exists" and point at the label that says the national intent statements are explanatory. Show the objective and function chips for the pair (OP3.1 and F03). Close with **Esc**.
4. Choose **Yes, it differs** (A). Answer the other cards (at most three in all) with **Not sure** or **No, it follows**, quickly.
5. If live model access is off, the card reads "This list comes from a keyword search." Use the fallback line.

**Narration.**

> Now the code. Batatis scores every Division B article against her description and offers up to three, each with the code's own words. It commits nothing by itself. She opens the code. The text is verbatim, with its citation. She says her design differs from this rule.

*47 words, 20.1 s at 140 wpm in a 38 s window.*

**If live model access is off when you record, say instead:** Now the code. Batatis looks for the rule her design differs from. With no model access it says so, labels the list as a keyword search, and commits nothing. *(29 words.)*

### A5. The alternative-path cards (1:51 to 2:13, Built)

**Screen.** `#/questions`. Cards with the eyebrow "Your case and proof · Section D".

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
2. Show the Sections A to D panel, with Section C's line "1 rule · looked up from the code, not AI-written" (the count follows the rules she confirmed).
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
2. Show the row: the application title, the applicant, when it was sent, the completeness count, the status and the reviewer column. Press **Pick up**: it claims the application and opens the review.
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

**Screen.** A plain card for 8 seconds, with the EXAMPLE DATA label. Three lines. **Built**: sign-up, the question flow with the intake reader and the code check, Section C by lookup, the Council's form, the officer queue and decision. **Backend, screens in progress**: package review and close-out (open PR #62). **Backend, no screen yet**: the benchmark record, the jurisdiction picker and the coded rules (unreviewed). **Roadmap**: standing-package checklists, accuracy report, Calgary form, other provinces. If a pending screen did land, move its line to **Built**.

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
| Facts shown beside the words they came from, and not used until confirmed | `docs/api/intake.md`, `web/src/calm/ReadCards.tsx`, `web/src/calm/deck.ts` |
| At most five questions, the fork note, up to three quoted choices that commit nothing | `docs/api/intake.md`, `docs/api/identify.md`, `web/src/calm/QuestionDeck.tsx` |
| Section C looked up from the attribution tables | `codedb/README.md`, `docs/api/identify.md` |
| 9.10.15.4.(1) with [F03-OP3.1], PDF p.901 | `docs/research/2026-10-21-source-checks.md` §7 |
| The close-out record lists what to send and keep, with a due date 10 days after the decision (the rule before Dec 1, 2026; the Council's portal rule applies from Dec 1) | `docs/research/2026-10-21-source-checks.md` §1 (IB-2025-11-18 for the 10 days, IB-2026-10-01 for the portal from Dec 1), `docs/api/package-review.md` |
| "Accepted as administratively complete" | `docs/api/accounts-review.md`, `web/src/calm/reviewer/ReviewDetail.tsx` |
| Package review and information request | `docs/api/package-review.md` |
| Screen text quoted above | `web/src/calm/` at commit 309ff03 |
