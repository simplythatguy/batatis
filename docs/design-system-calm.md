# Batatis calm design system

Default product look since 2026-10-20 (user decision). It replaces the Linear-style sidebar look; the P0 rules from `.cursor/skills/batatis-ui-linear/SKILL.md` still apply.

Visual contract: [`docs/design/calm-flow-prototype.html`](design/calm-flow-prototype.html) (`?screen=describe|questions|review|application`).
Implementation: `web/src/calm/` with styles in `web/src/calm/calm.css`, loaded after `styles.css`.

## Idea

Simple, quiet and fast. The applicant describes the project or drops plans, answers one question at a time, sees a short review, and downloads the application. The building code stays hidden until the applicant asks for it ("Show the code"). One screen does one job; nothing needs a sidebar.

## Flow

| Stage | Route | Screen | Job |
| --- | --- | --- | --- |
| 01 Describe | `#/` | `Start.tsx` | Role (required), description, plans (drag and drop anywhere), reviewing authority. Start runs the explicit check. |
| 02 Questions | `#/questions?focus=<key>` | `QuestionDeck.tsx` + `deck.ts` | One card at a time, derived from the case and the shared gaps. |
| 03 Review | `#/review` | `Review.tsx` | What's left, metric tiles, engineer callout, Sections A–D status. |
| 04 Application | `#/application` | `Application.tsx` | Paper preview of Part 1 A–D, gated draft and official PDF, text record. |
| More menu | `#/officer`, `#/references`, `#/accuracy` | existing screens in `.cf-legacy` | Officer view, all code references (Section C), accuracy report. |

Legacy hrefs (store gap links, old screens) are translated in `calm/routes.ts`: `#/describe` → Start, `#/code-check` → questions (code cards first), `#/section-c` → references, `#/application?tab=…&focus=field-<id>` → the card for that field, `prof-*` → the Section D card.

### Deck order

1. "Check what we read": facts proposed from the applicant's words (confirm or Not right).
2. Code check: one card per candidate (Yes / No / Not sure; storeys takes a number). Not sure shows the clarifying question; it stays an open question for the officer.
3. Open questions (text).
4. Reviewing authority, then Section A/B fields that are required and empty (choices as pills, date as a styled date input). Permit is optional and offered once.
5. The alternative-path case, written by the applicant: rationale, risk assessment, mitigating measures, assumptions and limits, maintenance, qualifications. "What to include" holds the prompts. Batatis never writes these.
6. Section D (one card): the existing `Recommendations` component (professional questions, then evidence documents), restyled. It is done when no Section D gap remains and the applicant has continued past it.

Skip moves on; at the end of the pass the deck comes back once to skipped cards, then shows the finish card ("That's everything for now" → Review my application).

Keyboard: `1` `2` `3` pick a choice, `↵` continues (`⌘↵` inside a text area), `Esc` closes the drawer.

## Tokens

| Token | Value | Use |
| --- | --- | --- |
| `--cf-bg` | `#08090b` | Page |
| `--cf-text` / `-2` / `-3` | `#f4f4f5` / `#a3a6ad` / `#7b7f87` | Primary, secondary, faint text |
| `--cf-line` / `-2` | white 8% / 14% | Hairlines, control borders |
| `--cf-glass` | `rgba(20,22,26,.62)` + blur 24px | Cards, panels, drawer, menus |
| `--cf-inset` | white 2.5% | Tiles, answer buttons |
| `--cf-accent` | `#ff6a3d` | Brand mark and eyebrow square only. Never a button fill. |
| `--cf-blocking` / `-warning` / `-done` / `-pending` | `#f87171` / `#fbbf24` / `#4ade80` / `#8b8b94` | Status dots only |
| `--cf-primary-bg` / `-text` | `#ededed` / `#0b0b0c` | The one primary button |
| `--cf-focus` | `#9a9aa2` | Focus rings (neutral) |
| `--cf-font` | Inter Variable (optical sizing) | Text |
| `--cf-mono` | Geist Mono Variable | Eyebrows, citations, counters, kbd hints |
| Radii | card 28, tile 18, control 14, pill 999 | |

Type scale: display 54/1.04 (−3.5%), review headline 40, card question 32 (26 on phones), drawer title 22, lede 18, body 14–15, eyebrow 12 mono uppercase +9% tracking.

## Components

- **Top bar**: brand left; centered glass pill group `01 Describe · 02 Questions · 03 Review · 04 Application` (active = faint white fill, completed = green numeral); save status (mono, coloured dot; failure shows its note and Retry; unsaved shows Save now) and the `⋯` menu. Under 860px the pills collapse to one `02/04 Questions` pill with a popover.
- **Buttons** (`.cf-btn`): pill, 44px; `is-primary` is the neutral light fill with a dark `kbd` hint; `is-ghost`, `is-sm`, `is-xs`. Labels never wrap; rows wrap instead of clipping.
- **Chips** (`.cf-chip`, `aria-pressed`): role and authority choices.
- **Eyebrow** (`.cf-eyebrow`): mono uppercase with the accent square; `is-plain` drops it.
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
