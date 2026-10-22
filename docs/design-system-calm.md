# Batatis calm design system

Default product look since 2026-10-20 (user decision). It replaces the Linear-style sidebar look; the P0 rules from `.cursor/skills/batatis-ui-linear/SKILL.md` still apply.

Visual contract: [`docs/design/calm-flow-prototype.html`](design/calm-flow-prototype.html) (`?screen=describe|questions|review|application`).
Implementation: `web/src/calm/` with styles in `web/src/calm/calm.css`, loaded after `styles.css`.

## Idea

Simple, quiet and fast. The applicant describes the project or drops plans, answers one question at a time, sees a short review, and downloads the application. The building code stays hidden until the applicant asks for it ("Show the code"). One screen does one job; nothing needs a sidebar.

## Flow

| Stage | Route | Screen | Job |
| --- | --- | --- | --- |
| 01 Describe | `#/` | `Start.tsx` | One headline and the composer: description and plans (drag and drop anywhere). No privacy copy, no chips: the role comes from onboarding; without one, Start asks "Who is applying?" as its next step (A B C, then the application starts). The reviewing authority is a Section B question. Start runs the explicit check. Start is the only place the project is described. |
| 02 Questions | `#/questions?focus=<key>` | `QuestionDeck.tsx` + `deck.ts` | Typeform questions in form order (A, B, C, D), derived from the case and the shared gaps. Footer progress per section with a popover and up/down. Before a description exists it asks nothing: one quiet line and a link back to Start (no card, no progress count). Once described, no card re-asks it: the starter questions the description answers are skipped and the proposed alternative offers the description (Yes, use my description / No, I'll write it). |
| 03 Review | `#/review` | `Review.tsx` | What's left, metric tiles, engineer callout, Sections A–D status. |
| 04 Application | `#/application` | `Application.tsx` | Paper preview of Part 1 A–D, gated draft and official PDF, text record. |
| More menu | `#/officer`, `#/references`, `#/accuracy` | existing screens in `.cf-legacy` | Look up code (⌘K), Code library, Officer view, accuracy report. Section C references stay at `#/references`. |
| Code library | `#/code`, `#/code/<article>?filter=attention\|maybe\|all` | `CodeLibrary.tsx` | Optional reading surface, not a stage. |

Legacy hrefs (store gap links, old screens) are translated in `calm/routes.ts`: `#/describe` → Start, `#/code-check` → questions (code cards first), `#/section-c` → references, `#/application?tab=…&focus=field-<id>` → the card for that field, `prof-*` → the Section D card.

### Deck order

Start runs intake (`POST /cases/{id}/intake`, docs/api/intake.md) and then code identification over the stream (docs/api/identify.md), both in the save queue. While intake reads, the deck shows one waiting card.

1. "Check what we read": one card per thing intake read, with the applicant's words marked, where they came from (description, PDF and page, form field) and how sure we are. Confirm or Not right (a confirmed empty answer; the field is asked again). A unit conversion and the same words read twice are one card. Files that could not be read say so, with the reason.
2. The planner's questions (at most five, as the API ranks them), each with its why; Not sure is always allowed and never blocks. The fork note (the API's wording, the two halves kept apart) sits on the first one. A field a planner card asks is not asked again on its form card.
3. Reviewing authority (answered by confirming the site's municipality when it is Edmonton or Calgary), then the remaining Section A/B fields.
4. Which rules apply: stage progress while identification runs, then committed articles and at most three quoted choices (Yes / No / Not sure through the decision route; the article number and code sentence behind "Show the code"), plus rules added from the library. "I could not narrow this down" and the keyword fallback are labelled. The rest of the ranking stays in the library.
5. The applicant's own case (rationale, risk, mitigation, assumptions, maintenance, qualifications). Batatis never writes these.
6. Section D (one card).

Another regime (electrical, gas, private sewage, fire, plumbing, energy) shows only the redirect page until the applicant says it is a building-code question; export stays blocked until then. The review shows the fork note and the pre-application note ("Before you submit").

Plain language first: the footer and eyebrows say About you, Your project, Which rules apply, Your case and proof, with the form's letter as quiet secondary text. Each section's list explains its part of the form, and one line says what the form is on first use.

Skip moves on; at the end of the pass the deck comes back once to skipped cards, then shows the finish card ("That's everything for now" → Review my application).

Keyboard: `A` `B` `C` (or `1` `2` `3`) pick a choice, `↵` continues (`⌘↵` inside a text area), `↑` `↓` move through the form, `Esc` closes the drawer. Shell: `⌘B` sidebar (toggle at the far left of the header), `⌘J` assistant (full-height black column), `⌘K` search applications, `⌘⇧K` search the code. All four stages and the code library open in every state; Review and Application show an empty state before a description exists.

## Tokens

| Token | Value | Use |
| --- | --- | --- |
| `--cf-bg` | `#08090b` | Page |
| `--cf-text` / `-2` / `-3` | `#f4f4f5` / `#a3a6ad` / `#7b7f87` | Primary, secondary, faint text |
| `--cf-line` / `-2` / `-ctl` | white 7% / 13% / 36% | Every divider, card, chip and button / pressed and state lines / form-control boundary (underline inputs, 3:1) |
| `--cf-glass` | `rgba(20,22,26,.62)` + blur 24px | Cards, panels, drawer, menus |
| `--cf-inset` | white 2.5% | Tiles, answer buttons |
| `--cf-accent` | `#ff6a3d` | Brand mark, question number and arrow, current tick. Never a button fill. No eyebrow squares. |
| `--cf-blocking` / `-warning` / `-done` / `-pending` | `#f87171` / `#fbbf24` / `#4ade80` / `#8b8b94` | Status dots only |
| `--cf-primary-bg` / `-text` | `#ededed` / `#0b0b0c` | The one primary button |
| `--cf-focus` | `#9a9aa2` | Focus rings (neutral) |
| `--cf-font` | Inter Variable (optical sizing) | Text |
| `--cf-mono` | Geist Mono Variable | Eyebrows, citations, counters, kbd hints |
| Radii | card 28, tile 18, control 14, pill 999 | |

Type scale: display 54/1.04 (−3.5%), review headline 40, card question 32 (26 on phones), drawer title 22, lede 18, body 14–15, eyebrow 12 mono.

**No all-caps anywhere** (user decision 2026-10-21): no `text-transform: uppercase` and no uppercase copy. Eyebrows and small mono labels are sentence case. `calm.css` also neutralizes uppercase from the legacy styles inside the shell. Acronyms (NBC, PDF) stay as written.

## Components

- **Top bar**: brand left; centered glass pill group `01 Describe · 02 Questions · 03 Review · 04 Application` (active = faint white fill, completed = green numeral); save status (mono, coloured dot; failure shows its note and Retry; unsaved shows Save now) and the `⋯` menu. Under 860px the pills collapse to one `02/04 Questions` pill with a popover.
- **Buttons** (`.cf-btn`): pill, 44px; `is-primary` is the neutral light fill with a dark `kbd` hint; `is-ghost`, `is-sm`, `is-xs`. Labels never wrap; rows wrap instead of clipping.
- **Chips** (`.cf-chip`, `aria-pressed`): role and authority choices.
- **Eyebrow** (`.cf-eyebrow`): small mono label in sentence case with the accent square; `is-plain` drops it.
- **Card** (`.cf-card.cf-glass`): eyebrow, question, one muted context line, controls, then the footer (Why we ask · Skip for now · Continue). Two ghost cards peek behind. It enters with opacity, 12px translateY and 4px blur over 300ms ease-out; under reduced motion only the opacity changes.
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
- **Library**: two panes. Opening it folds the application list away (⌘B or the header button brings it back; leaving restores it) and the chapters pane takes the list's place: title and edition, a "Search the code" field (opens the palette), filters All · Needs attention · Maybe, the scoring status with the "?" legend, the ARIA tree Part → Section → Subsection → Article (arrow keys, Enter opens, lazy children, auto-expansion, titles wrap to two lines; branch rings show the highest article; filters prune branches) and "Your Section C references" at the foot. Hovering or focusing an article row for 300ms shows a peek: its roots (path), exact %, band, first ~160 characters, objective codes.
- **Reader**: breadcrumb of the roots (buttons that reveal the branch), the article title, `Article <id>` · ring · band pill, then "Add to my application" (same `provisionCandidate` path as the manual search; it becomes a Code check card). The verbatim text is a numbered outline (`codeText.ts` splits sentences, clauses and subclauses without changing a word): each sentence is a disclosure, the first open and the rest as one-line previews, with "Expand all"; clauses hang under it with their own marker column, about 68 characters to the line. Secondary information is folded with counts: Objectives and functions (code chips with their titles; the no-row statement when the table has none), Why this rule exists (NBC 2020 intent, explanatory only), Notes, Referenced articles (cites / cited by). The citation, PDF page and NRC credit sit quietly at the foot. Content is full ink; only metadata is quieter.
- **Room**: when the library itself is narrower than 760px (the assistant open on a 1024px screen, phones) it shows one pane at a time: the chapters, or the reader with a "Chapters" back link; Esc closes the reader and returns focus to its row. The assistant still pushes, never covers.
- **RelevanceRing** (`RelevanceRing.tsx`, the only implementation): 16px (rows, chips, the reader's meta line) or 22px. Track 1.5px white 14%, arc from 12 o'clock with length p, round caps. Green under x ("Unlikely to apply"), amber x ≤ p < y ("Might apply · check this"), red p ≥ y ("Likely applies · address this"), solid grey outline at 0, dashed grey when not scored. Tooltip: exact % to one decimal, band label, "Batatis estimate from your description. Not a compliance decision.", "Estimate version relevance-1", "Out of date" when stale. The label is always available as text (aria-label, band pill), never colour alone.
- **Scores** (`useRelevance.ts`): GET on library or palette open; POST only on "Score relevance for my project" (it costs money). The draft is saved first so the current description is scored. States: checking, not scored, scoring with elapsed seconds, scored · time ago, out of date · Rescore, unavailable · Try again (409 asks for a description; 429 counts down from Retry-After or 15 s; technical detail collapsed). Cut-offs come from `bands.x/y`; 0.2 / 0.6 are placeholders used only when a response has none. Never rescored automatically.
- **Rules**: rings are estimates, never compliance and never the Section C list. Section C remains only what the applicant confirmed. With scores, the library opens on "Needs attention" so only the handful that matter show.
