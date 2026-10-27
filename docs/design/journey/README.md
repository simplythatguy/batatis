# The applicant journey: first screen to last question

Decided 2026-10-26. Storyboards of the two directions compared: [`storyboard.html`](storyboard.html).

Batatis reads everything first, asks only what it cannot know, asks the person who can know it, and asks in the order that decides the application. The applicant always sees how much is left and who it is waiting on.

## Directions compared

| | A · Read first, then one question at a time | B · The draft with holes |
| --- | --- | --- |
| Screen | One question per screen | The whole application as blocks; each hole opens a sheet |
| Where you stand | Footer: steps and counts by who answers | The board itself |
| Fit with the design rules | One thing per screen, minimal text | Six blocks at once; needs the drafts to exist first |
| Risk | Can feel endless without honest counts | Busy; first-timers face everything at once |

**Chosen: A, with B's block map as the "where you stand" view.** The footer's counts open the map (one row per stage, counts by who answers); the end screen is that map. One thing per screen stays the rule.

## 1. Front door

- No wall before the product. Signed-out visitors land on Start. Pressing Start asks them to sign in or sign up; the description and files stay in the page, and the application starts right after sign-in.
- Onboarding asks one thing: apply or review. The applicant option reads "I have a building project" (owner, designer, builder, engineer or manufacturer). There is no applicant-type step and no "variance" word before Batatis knows a variance is needed.
- Start needs a description **or** a file. Plans alone are enough.
- Start accepts PDF, images (JPG, PNG, WebP) and text notes.
- Start never asks who is applying. "Your part in this project" is a paperwork question (owner, designer or architect, engineer, builder or contractor, manufacturer, someone else), skipped when the documents already say it.

## 2. What is read

- The description, every sentence. A question ("Can I build a two-storey house in Edmonton with bigger windows?") describes the plan and is read like a statement.
- PDFs: the text of every page (up to 200), and the semantic pass over all text pages, in chunks, not only the first five.
- Image-only pages and image files go to a vision pass when AI is on. Anything read from a picture is a proposal with the page or photo as its source, and is confirmed by the applicant.
- Each file says what was actually read: "Read · 12 of 12 pages", "Read · 60 of 140 pages", "2 drawings looked at", or "Pictures not read: AI is off".
- The same fact in several places is one fact with several sources.
- File life: a file added later is read automatically; a failed upload stays with Retry; removing a file removes the unconfirmed answers that came only from it and says how many; reopening an application shows its files.

## 3. Who answers what

Every question has one answerer.

| Answerer | What | How it is asked |
| --- | --- | --- |
| You | Facts about the project and the people | A normal question with Not sure |
| Your designer | Expert determinations: Part 4 design, fire-resistance ratings, hazard classes, reserved professional judgement, assembly layers not in the plans | "Usually your designer knows" and the answer "Ask my designer", which records it; these collect into one list the applicant can send |
| The office | Facts only the authority holds: fire-department response times, local intake steps | Never asked. Listed under "To confirm with the office" |
| Batatis | Anything it can derive: the office from the site address, today's date (marked as a default), "same as the site address" | A one-tap confirmation, never a blank question |

Asking less:

- Facts read from the applicant's words and files are confirmed together on one screen, "Here's what I understood": one click confirms all, any row can be fixed. Only conflicts and facts read from pictures get their own question.
- One fact, one question. The professional screen reuses the project's facts (use, storeys, area, Part 4) and only asks what applies to this project type.
- Picking an answer moves on. There is no second OK click.

## 4. Order

Stages, in this order. The form section letter stays on each card as quiet secondary text; Review and the application still follow the form (A–D).

1. **Understand**: reading, then "Here's what I understood".
2. **Route**: variance or the code's standard way; one site or product acceptance.
3. **Project**: facts that change which rules apply (storeys, area, use, sprinklers, distances, what is beside the wall).
4. **Rules**: the code check, rule inputs, standing packages.
5. **Case**: the six narratives (drafts come from the writing work).
6. **Proof**: the responsible professional and evidence.
7. **Paperwork**: owner, your part, representative, mailing address, legal description, permit number, date, office.

## 5. Route

- Variance likely: one card says so, with the reason in the applicant's words, and moves on.
- Variance not indicated: "You may not need a variance". **Use the standard way** removes the variance stages and points to the usual permit documents and evidence of compliance. **Something is different** asks what, then continues.
- Unclear: no card; the first rule decisions settle it.
- Products: "One building, or across Alberta?" Across Alberta is product acceptance (for example a CCMC evaluation), not a site variance, and is stored apart from a municipality-wide variance.

## 6. Office

One searchable field: Calgary, Edmonton, or any other Alberta place, which resolves to "your accredited municipality or the Alberta Safety Codes Authority" with the Safety Codes Council's Where to get a permit link. Not sure is allowed; the site address settles it later. When the address names the place, the office is a one-tap confirmation.

## 7. Uncertainty

- Every question offers **Not sure** (designer questions: **Ask my designer**). The answer is recorded, is not asked again, and stays visible on Review and to the officer as an open item.
- Skip is gone. Paperwork offers **Later**, which is recorded and listed on Review, and does not come back by itself.

## 8. Progress

- The footer shows the stage steps and counts by answerer: you, your designer, the office. Counts are the real number of open questions, including the professional and evidence questions.
- The end says "Your part is done" only when nothing required is waiting on the applicant. Otherwise it says how many still need them.

## 9. Answers

- A two-part question is two questions.
- Distances and areas accept units (m, ft, ft and in, m², ft²), convert to metric, and keep what was typed. "4 feet" is 1.22 m.

## Hard lines

Never invent a fact; label what was read, what was assumed and what was confirmed. Never claim compliance. Keep the standard-way path and the variance path apart. Keep the data portable across Alberta's jurisdictions (no office hard-coded into the journey).
