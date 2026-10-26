# Batatis calm design system

Default product look since 2026-10-20 (user decision). It replaces the Linear-style sidebar look; the P0 rules from `.cursor/skills/batatis-ui-linear/SKILL.md` still apply.

Visual contract: [`docs/design/calm-flow-prototype.html`](design/calm-flow-prototype.html) (`?screen=describe|questions|review|application`).
Implementation: `web/src/calm/` with styles in `web/src/calm/calm.css`, loaded after `styles.css`.

## Idea

Simple, quiet and fast. The applicant describes the project or drops plans, answers one question at a time, sees a short review, and downloads the application. The building code stays hidden until the applicant asks for it ("Show the code"). One screen does one job; nothing needs a sidebar.

## Flow

| Stage | Route | Screen | Job |
| --- | --- | --- | --- |
| 01 Describe | `#/` | `Start.tsx` | Public front door: "What are you building?", a composer and attachments (drop anywhere). A description or a file is enough. Start asks for sign-in when needed, then starts reading automatically. Applicant type stays unanswered until the later paperwork question. |
| 02 Questions | `#/questions?focus=<key>` | `QuestionDeck.tsx` + `deck.ts` | One question at a time, ordered by the decisions that shape the application. The journey stages and answerer counts open a map; form letters stay secondary on each card. Before a description exists it asks nothing: one quiet line and a link back to Start (no card, no progress count). Once described, no card re-asks it: the starter questions the description answers are skipped and the proposed alternative offers the description (Yes, use my description / No, I'll write it). |
| 03 Review | `#/review` | `Review.tsx` | What's left, metric tiles, engineer callout, Sections A–D status. |
| 04 Application | `#/application` | `Application.tsx` | Paper preview of Part 1 A–D, gated draft and official PDF, text record. |
| More menu | `#/officer`, `#/references` | existing screens in `.cf-legacy` | Look up code (⌘K), Code library, accuracy report, Officer view. Section C references stay at `#/references`. |
| Accuracy | `#/accuracy` | `web/src/accuracy/AccuracyPage.tsx` | What Batatis guarantees and what we measured, from the bundled `docs/accuracy/report.json` (no engine call). Public: signed-out visitors see it without the shell. Linked from Settings and the More menu, never from the four stages. |
| Code library | `#/code`, `#/code/<article>?filter=attention\|maybe\|all` | `CodeLibrary.tsx` | Optional reading surface, not a stage. |

Legacy hrefs (store gap links, old screens) are translated in `calm/routes.ts`: `#/describe` → Start, `#/code-check` → questions (code cards first), `#/section-c` → references, `#/application?tab=…&focus=field-<id>` → the card for that field, `prof-*` → the Section D card.

### Start and onboarding

Signed-out visitors see Start with a quiet Sign in in the header. They can type and attach before creating an account. The other application routes keep their sign-in gate; the accuracy report remains public. Reviewers still start at their queue.

The composer accepts PDF, JPG, PNG, WebP, TXT and MD. PDF and image files wait for the case before upload; text notes join the description. The helper and drop overlay say "PDF · JPG · PNG · TXT". The text area says "Describe it in a few words, or attach plans and photos". Files alone enable Start. File rows keep their upload/read state, removal and failed-file Retry.

Pressing Start remembers the intent to start through sign-in, sign-up and onboarding. The pre-application text and that intent use tab-scoped `sessionStorage`, never `localStorage`; they clear when the application begins or the person signs out. File objects stay in memory during email sign-in. After a full-page OAuth reload, Start says "Attach your files again" and waits for reattachment, or an explicit choice to use the description alone.

Onboarding asks apply or review. The applicant choice is "I have a building project" with "Owner, designer, builder, engineer or manufacturer" beneath it. There is no applicant-type step. Reviewers still choose their authority and enter its access code. A new application starts with `applicantType: null`; an account's older applicant type is never used to choose one for it. Settings accepts an unanswered applicant type, and changing into or out of the reviewer role keeps the access-code rule.

### Deck order

Start runs intake (`POST /cases/{id}/intake`, docs/api/intake.md) and then code identification over the stream (docs/api/identify.md), both in the save queue. While intake reads, the deck shows one waiting card.

1. **Understand**: one “Here’s what I understood” card, including when the reading already confirmed every value. Each row shows the value, an icon and its sources (file/page or “you”); derived values have a dashed “assumed” chip. “Looks right” confirms waiting rows and saves an acknowledgement of that reading on the case. The acknowledged card adds no open work; a new reading or changed rows asks again. Fix opens that fact’s source and correction controls. Equal values for the same field share a row and keep all their sources. Conflicts and unconfirmed values read from pictures keep individual cards.
2. **Route**: a likely variance gets a short explanation in the applicant’s words. “You may not need a variance” offers “Use the standard way” or “Something is different”; the latter opens one text question. The standard route removes the variance case, proof and departure cards. Product prose can ask “One building, or across Alberta?” without knowing the applicant’s role. Across Alberta shows the engine’s sourced product-acceptance notice; it is separate from the form’s municipality-wide scope.
3. **Project**: deciding facts such as storeys, area, use, sprinklers and distances. Planner questions retain their ranking within their stage. A fact already on the reading card is not asked again.
4. **Rules**: the code check, rule inputs and standing packages. Article wording stays behind Show the code. New questions join at their journey position, including when identification finishes later.
5. **Case**: the six narratives, with their existing content and professional boundaries.
6. **Proof**: the responsible professional and evidence. Inner questions contribute their own counts through the deck item’s `counts` interface; they must not be represented by one finished outer card.
7. **Paperwork**: one “Last details for the form” sheet, with inline rows for owner, “Your part in this project”, representative, mailing address, site address, legal description, permit number, date, municipality-wide scope and office. Known values keep their sources. Today, “same as the site address”, and representative defaults require a tap; Done saves the edited rows together. Each row offers recorded Later; each required open row contributes its own count. Field and gap links open the sheet with the relevant row focused. The office retains its searchable picker and address-based confirmation.

Each card has one answerer: you, your designer, the office or Batatis. Expert determinations show the designer icon and “Usually your designer knows”, with “Ask my designer”. Office-only facts, such as fire-department response statistics, never become applicant questions. A value Batatis derives is a confirmation, never a blank question.

Picking an answer saves and advances. Questions offer “Not sure”; designer questions offer “Ask my designer”. Paperwork offers “Later”. These choices are recorded on the case, stay open for Review and the officer, and do not return automatically. There is no Skip or return pass. The applicant can deliberately revisit an item from the map.

The footer shows the seven stages (only the current stage uses its hue) and nonzero icon counts for you, your designer and the office. Batatis’s confirmations count with you because they wait on your click. The map has one row per stage and open counts by answerer. The end says “Your part is done” only when no required answer waits on you; otherwise it says “N still need you” and links to the first one. Designer questions have Copy questions; office questions are listed under “To confirm with the office”. The primary action is “See my application”.

Another regime (electrical, gas, private sewage, fire, plumbing, energy) shows only the redirect page until the applicant says it is a building-code question; export stays blocked until then. The review retains the fork and pre-application notes. A request for variance (the legal authorization) and an alternative solution (the supporting technical evidence) remain distinct.

Assistant entry points: Ask in the applicant header, Ask in every account page header (`PageHead`: queue, review, settings, notifications) and in the reviewer's code library header, `⌘J`, and field Help. The left rail has no assistant entry (user decision 2026-10-22).

Keyboard: `A` `B` `C` (or `1` `2` `3`) pick a choice, `↵` continues (`⌘↵` inside a text area), `↑` `↓` move through the form, `Esc` closes the drawer. Shell: `⌘B` sidebar (toggle at the far left of the header), `⌘J` assistant (full-height black column), `⌘K` search applications, `⌘⇧K` search the code. Once signed in, all four stages and the code library open in every state; Review and Application show an empty state before a description exists.

Stage navigation (header, and the officer's review steps): icons, and one word for where you are (user decision 2026-10-22, "Option A+B"). Each stage is its icon, in order, with no fill, pill or shadow in any state: the current one shows its one-word name beside its icon at full opacity (an officer step's open count follows the name: `Missing 9`); the others are the icon alone, dimmed (0.6), brightening on hover or keyboard focus (0.85), a locked one fainter still (the current one stays at full strength). Compact cues carry the state in one neutral ink: a small green check mark once done, a thin line at the foot while part of the way through, another officer step's open count as a quiet number beside its icon. Officer step icons: Changes history, Request document, Missing alert, Checks list, Decide scales. Under 360px the stage boxes narrow (30px) so the current name stays clear of the save status. The name and progress show on hover or keyboard focus (one label at a time) and are the accessible name (`aria-current="step"` marks the current one). Shared component: `StageButton` in `web/src/calm/shell/AppHeader.tsx`.

Application name (header and list): just the name, no authority beside it. Names are short subject names from the engine, never the description's first sentence; the applicant renames in place in the header (double-click, F2 or Enter; Enter or blur saves; Escape cancels; no field box) or from the list row's ⋯ → Rename. Saved through `PATCH /cases/{id}/title`; a chosen name always wins and is never shortened in storage.

Application list (sidebar): rows carry no status dot. Pinned rows sit first (a small pin before the name), then active, then Settled; archived rows leave the list for a collapsed "Archived" shelf at the foot (icon, word, count). The ⋯ (glyph only: no fill at rest, hover or press; a focus ring for the keyboard), a right-click and Shift+F10 open one menu with an icon on the left of each item: Rename (only where the title can be edited), Pin or Unpin, Archive or Restore, Delete (after a confirmation that names the application; the server's delete policy decides and its refusal is shown). The menu stays inside the sidebar: never wider than it, never past its left edge, inside the viewport (`shell/placement.ts`). Hovering or keyboard-focusing a row shows a small preview to the right of the sidebar with the summary's real fields only, when there is room (not on phones or touch). Pin and archive go through `PATCH /me/applications/{id}/preferences` and only organise the owner's list; they never withdraw a sent application. The interaction model follows T3 Code's thread sidebar.

### Questions: integration contract

`web/src/calm/journey.ts` owns `Stage`, `Answerer`, `stageOf`, `answererOf`, `orderJourney` and `journeyProgress`. Every deck item carries `stage` and `answerer`; `done` means answered or deliberately deferred for the queue, while `settled` means it is still open for progress. `counts?: Partial<Record<Answerer, { open: number; done: number }>>` replaces the outer item’s one-unit count for nested professional/evidence work and the paperwork sheet’s required rows.

Journey answers use the existing case fact action. `journey.answer.${encodeURIComponent(cardKey)}` contains a JSON `JourneyAnswer` with `key`, `field`, `question`, `stage`, `answerer`, `value` (`not_sure`, `designer`, `later`, or `acknowledged`) and `required`. Understanding uses `acknowledged` and a bounded reading key from `understandingAnswerKey(case, rows)`; this is a completed confirmation, never an open item. `journeyAnswers(case)` reads valid current entries; clearing an annotation uses the existing fact-withdrawal mechanism. Real numeric and detail fields are not filled with uncertainty placeholders. Planner uncertainty also uses `plan.not_sure`, and candidate uncertainty uses the existing `not_sure` decision route. Completeness and Review must read deferrals as open items, deduplicate against the underlying field, retain the assigned answerer, and never treat a recorded deferral as a completed requirement.

`journey.route` stores `standard`, `different` (awaiting one explanation), or `variance`; `journey.departure` keeps that explanation verbatim. Completeness must apply the same standard-route exemption to variance-specific case/proof/departure requirements. `product_scope` stores `site` or `product_acceptance` and must never be aliased to the form’s `scope` (`site`/`jurisdiction`). Its planner question is `intake.product_scope`. The existing engine product-route notice is returned after product acceptance is selected. `journey.package.<id>` retains a standing-package choice, and `journey.rule.<id>` retains a decision to leave a rule out; actual checklist and article decisions still use their existing actions.

## Tokens

**Light mode since 2026-10-22 (user decision):** "visuals > text", light instead of black. Say things with icons, counts and short labels; avoid explanatory sentences.

**Monotone, colour to identify (user correction, 2026-10-22):** the UI is neutral. A hue appears only where it identifies something: the section or step you are in, or items that would otherwise be hard to tell apart in a crowded place. Progress and navigation are grey except the current section, which shows its hue for answered questions and a darker shade of the same hue for the current one (open ones stay grey); the question number takes that shade. The global accent never marks "you are here". Status colours (blocking, warning, done) and the brand mark keep their meaning.

| Token | Value | Use |
| --- | --- | --- |
| `--cf-bg` / `--cf-surface` | `#f5f6f8` / `#fff` | Page / cards, tiles, menus, drawers (with `--cf-shadow`) |
| `--cf-text` / `-2` / `-3` / `-4` | `#14161b` / `#4a505c` / `#6b7280` / `#a3a8b3` | Primary, secondary, faint, quietest text |
| `--cf-line` / `-2` / `-ctl` | ink 8% / 14% / 42% | Every divider, card, chip and button / pressed and state lines / form-control boundary |
| `--cf-accent` | `#f25a2a` | Brand mark, current step, "New". Never a button fill. |
| `--cf-blocking` / `-warning` / `-done` / `-pending` | `#e5484d` / `#f0a20b` / `#18a058` / `#9aa0ab` | Status dots and pills |
| `--cf-hue-*` and `-t` | blue, teal, violet, amber, rose, green, slate (solid + tint) | Identification only (see above). The `.is-blue` … `.is-slate` classes set `--hue`, `--hue-t` and `--hue-s` (a darker shade, at least 5.6:1 on the page, for "you are here" and text). |
| `--cf-primary-bg` / `-text` | `#16181d` / `#fff` | The one primary button (neutral near-black; never indigo or purple) |
| `--cf-focus` | `#6b7280` | Focus rings (neutral) |

Section hues, used only where they identify: **A blue, B teal, C violet, D amber** (the current section in the applicant's question footer, Review badges). The officer's review is drawn in ink (user direction 2026-10-22: one task at a time, no multi-colour tiles): step icons, section letters and check panels are neutral; only status dots keep colour.

Type scale: display 54/1.04 (−3.5%), review headline 40, card question 32 (26 on phones), drawer title 22, lede 18, body 14–15, eyebrow 12 mono.

**No all-caps anywhere** (user decision 2026-10-21): no `text-transform: uppercase` and no uppercase copy. Eyebrows and small mono labels are sentence case. `calm.css` also neutralizes uppercase from the legacy styles inside the shell. Acronyms (NBC, PDF) stay as written.

## Components

- **Top bar**: brand left; centered glass pill group `01 Describe · 02 Questions · 03 Review · 04 Application` (active = faint white fill, completed = green numeral); save status (mono, coloured dot; failure shows its note and Retry; unsaved shows Save now) and the `⋯` menu. Under 860px the pills collapse to one `02/04 Questions` pill with a popover.
- **Buttons** (`.cf-btn`): pill, 44px; `is-primary` is the neutral light fill with a dark `kbd` hint; `is-ghost`, `is-sm`, `is-xs`. Labels never wrap; rows wrap instead of clipping.
- **Chips** (`.cf-chip`, `aria-pressed`): role and authority choices.
- **Eyebrow** (`.cf-eyebrow`): small mono label in sentence case with the accent square; `is-plain` drops it.
- **Question card** (`.cf-q-wrap`): stage and quiet form letter, the question (a short label such as "Request date" when the field is obvious), a context line only when it carries something the control cannot (the applicant's own quote or a professional boundary), then the answer controls. Choices save and advance. Typed answers use Continue; uncertainty is Not sure, Ask my designer or Later. Help opens the reason and the assistant on that card.
- **Answer tiles** (`.cf-answer`): 60px, number hint on the right.
- **Citation chip** (`.cf-cite`): `9.27.3.4.(1) Show the code`; opens the drawer.
- **Code drawer** (`CodeDrawer.tsx`): modal `<dialog>` (focus-trapped, Esc closes, `overscroll-behavior: contain`), right side; bottom sheet under 640px. Shows "Code text · verbatim" only for code-database text, with the NRC credit; "Why this rule exists" = NBC 2020 intent statements labelled explanatory, plus the `differs` note; objectives and functions from the Section C row (or the no-row statement); any AI text in a dashed box labelled "not code text". Links: All code references, Add a code reference (manual search).
- **Metric tiles** (`.cf-metrics`): Complete n/total, Left to answer (+ required count).
- **Rows** (`.cf-row`): dot by severity, label, `Answer →` to the matching card.
- **Engineer callout** (`.cf-engineer`): amber card, shown only when the professional logic says so (`practiceOfEngineering`, `professionalConfirmed`, `isProfessionalHold`), with the sentence "Batatis can list what that evidence must address, but it can't write it."
- **Paper sheet** (`.cf-sheet`): light page; values or `— missing`; citations as small mono chips.
- **Confirm dialog** (`ConfirmDialog`): styled `<dialog>`, never `alert()`.
- **Legacy screens** (`.cf-legacy`, `.cf-embed`): re-theme the old screens through their tokens (fonts, colours, radii, buttons, inputs, details, dialogs).

Motion rules: transitions name their properties (never `all`); hover styles sit behind `@media (hover: hover)`; pressed controls scale to 0.96, never when disabled; movement and blur only under `prefers-reduced-motion: no-preference`.

## P0 rules that carry over

1. Neutral primary CTAs (light grey fill, dark text). Never indigo or purple fills. At most one primary per card or panel.
2. One shared gap source: the deck, Review and the export gate all read `useCase().gaps`.
3. The official export stays disabled while blocking gaps remain or the check is not current; the reason is shown inline.
4. No demo or template leakage, no bracket placeholders. Show the real value or `—` with the gap.
5. Retrieved code text is visually distinct from AI text (solid quote vs dashed AI box).
6. Styled controls only: no browser-default select or checkbox chrome, `resize: none` on text areas.
7. Button labels never wrap or clip.
8. Every control works: no inert buttons, no `href="#"`, no `alert()`.
9. No silent defaults: authority and scope start unanswered; values read from the description carry their source and a way to confirm.
10. Process fields (rationale, risk, mitigation, assumptions, maintenance, qualifications) stay reachable as deck cards.
11. Never fabricate article numbers; never claim compliance or safety; never author Section D professional evidence. Say plainly when an engineer is required.

## Code library and relevance rings

An optional surface for reading the code; the four stages never depend on it.

- **Entry points**: ⌘K / Ctrl+K anywhere in an application (`CodePalette.tsx`), the ⋯ menu ("Look up code", "Code library"), the code drawer ("Open in code library"), Review's Section C row ("Browse the code"). No new top-bar element (the shell is being replaced by a left rail).
- **Palette**: centered glass dialog. Rows show ring · mono id · title · path, one row per article; ↑ ↓ move, ↵ opens the article. Empty query: "Likely related to your project" when scored, otherwise "Score relevance for my project" and the parts.
- **Application context**: one listbox button under the edition line names the application the library reads for, or "No application". The options are the account's own applications (the sidebar's rows, short titles, "Read-only" beside sent or closed ones), never another account's or authority's. Choosing another application opens it through the sidebar's guarded switch (unsaved answers are saved first; a failed save keeps the current one open and says so; a deleted one says so and the list refreshes). "No application" only detaches the library: the open application and its unsaved answers stay as they are, and the stage rings, title, save status, filters, scoring status, rings, band pills, "Add to my application", the Section C link and the assistant's case all leave the library; no scores are read or requested. Without an open application, and for reviewers, the library is always this plain browsing (no "start your application first"). The choice is tab-scoped. Code: `libraryContext.ts`, `codeScope.ts`, `ContextPicker` in `CodeLibrary.tsx`.
- **Library**: two panes. Opening it folds the application list away (⌘B or the header button brings it back; leaving restores it) and the chapters pane takes the list's place: title and edition, a "Search the code" field (opens the palette), filters All · Needs attention · Maybe, the scoring status with the "?" legend, the ARIA tree Part → Section → Subsection → Article (arrow keys, Enter opens, lazy children, auto-expansion, titles wrap to two lines; branch rings show the highest article; filters prune branches) and "Your Section C references" at the foot. Hovering or focusing an article row for 300ms shows a peek: its roots (path), exact %, band, first ~160 characters, objective codes.
- **Reader**: breadcrumb of the roots (buttons that reveal the branch), the article title, `Article <id>` · ring · band pill, then "Add to my application" (same `provisionCandidate` path as the manual search; it becomes a Code check card). The verbatim text is a numbered outline (`codeText.ts` splits sentences, clauses and subclauses without changing a word): each sentence is a disclosure, the first open and the rest as one-line previews, with "Expand all"; clauses hang under it with their own marker column, about 68 characters to the line. Secondary information is folded with counts: Objectives and functions (code chips with their titles; the no-row statement when the table has none), Why this rule exists (NBC 2020 intent, explanatory only), Notes, Referenced articles (cites / cited by). The citation, PDF page and NRC credit sit quietly at the foot. Content is full ink; only metadata is quieter.
- **Room**: when the library itself is narrower than 760px (the assistant open on a 1024px screen, phones) it shows one pane at a time: the chapters, or the reader with a "Chapters" back link; Esc closes the reader and returns focus to its row. The assistant still pushes, never covers.
- **RelevanceRing** (`RelevanceRing.tsx`, the only implementation): 16px (rows, chips, the reader's meta line) or 22px. Track 1.5px white 14%, arc from 12 o'clock with length p, round caps. Green under x ("Unlikely to apply"), amber x ≤ p < y ("Might apply · check this"), red p ≥ y ("Likely applies · address this"), solid grey outline at 0, dashed grey when not scored. Tooltip: exact % to one decimal, band label, "Batatis estimate from your description. Not a compliance decision.", "Estimate version relevance-1", "Out of date" when stale. The label is always available as text (aria-label, band pill), never colour alone.
- **Scores** (`useRelevance.ts`): GET on library or palette open; POST only on "Score relevance for my project" (it costs money). The draft is saved first so the current description is scored. States: checking, not scored, scoring with elapsed seconds, scored · time ago, out of date · Rescore, unavailable · Try again (409 asks for a description; 429 counts down from Retry-After or 15 s; technical detail collapsed). Cut-offs come from `bands.x/y` only when they are fitted (0 < x < y < 1 and a status that is not uncalibrated or placeholder); a legacy relevance-1 placeholder row reads with the benchmark 0.30 / 0.85. Any other response, including the engine's `uncalibrated; display range only` bands and missing or malformed ones, shows every score as "Estimate only": a neutral ring, no Needs attention / Maybe filters, no likely list. Never rescored automatically.
- **Rules**: rings are estimates, never compliance and never the Section C list. Section C remains only what the applicant confirmed. With scores, the library opens on "Needs attention" so only the handful that matter show.
