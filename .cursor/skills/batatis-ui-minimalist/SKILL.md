---
name: batatis-ui-minimalist
description: "Minimalist Batatis UI, the user's standing direction: icons before words, visuals over sentences, one thing at a time, short question labels with help on demand, short renamable titles, icon-and-count metadata. Use when designing, changing or reviewing any Batatis screen, navigation, title, question, list row, card, banner, label or UI copy."
---

# Batatis minimalist UI

The user has asked for pure minimalism again and again: light mode, a monotone UI, visuals over text, one thing on screen at a time. This skill decides **how much** goes on screen. `batatis-ui-linear` (P0 rules) and `docs/design-system-calm.md` (tokens, section colours) still decide how it looks.

## The test for every element

For each word, line, icon and control ask: does the person need it **now** to take the next step? Keep it. Needed later or only sometimes? Move it one step away. Never needed? Cut it.

1. **Icons before words.** Navigation, stages, status and counts are icons (with a ring, dot or badge for state); the name is the accessible name and a label on hover or keyboard focus, not a persistent row of text. Keep a visible word only where an icon would be ambiguous.
2. **Visual first.** A dot, icon, count, ring, colour or progress bar carries the meaning; the words left are short labels (one to three words), not explanations.
3. **One thing at a time.** One question, one job and one primary action (neutral near-black) per screen. Secondary actions go in ⋯ or a ghost button.
4. **Progressive disclosure.** Reasons, detail, history, code text and technical text sit one click or hover away: tooltip, drawer, `<details>`, the next screen.
5. **Compact metadata.** Icon then number (a message icon and `2`), never "2 new messages". The number always has its icon; a zero shows nothing.
6. **Breathing room.** Generous padding (sidebar rows `14px 16px`), selection as a soft fill, no decorative lines, edge bars or borders.
7. **Obvious questions are a label and a control.** "Request date" and a date field, then OK · Skip · Help. A subtitle that restates the field, "answer to continue" or "press Enter" lines, and a repeated "ask the assistant" invitation all go. The reason and the assistant sit behind the one Help entry on the card (the assistant exists for routine explanation); show text up front only when the control cannot carry it: the applicant's own quote, a validation error, a decision or professional boundary.
8. **Titles are short names the person can change.** A title is a subject or purpose name of a few words ("Infill sheathing"), never the first sentence of the description and never with the city, status or code numbers attached; that context lives where it is used. Automatic names wait until there is real content to name; a name the person chose always wins and is never shortened in storage (the screen may ellipsize it). Rename in place wherever the title shows (double-click, F2 or Enter; Enter or blur saves; Escape cancels; caret at the end, no field box), and from the list row's ⋯.
9. **Monotone; colour identifies.** Neutral by default. A hue marks where the person is (the current section or step, in a darker shade of its own hue) or tells crowded items apart; status dots keep their meaning. Never colour every section at once, never the global accent for "you are here", never a button fill.

## Minimal, never hidden

Minimalism moves information; it keeps every capability reachable. These stay visible on the screen they matter to:

- why an action is unavailable: a short visible hint, the full reason in `title` and for screen readers;
- errors, each with its retry;
- blocking gaps, the administrative-completeness boundary ("not a design approval"), refusal reasons with the appeal notice.

Every icon-only control or icon metadata has an accessible name and a hover label. When colour or an icon carries a status, the same status exists as text for screen readers. Familiar icons only (message, search, compose, close); anything less obvious keeps its one-word label.

## Example: application sidebar row

- Before: `● Returned · 2 new messages`
- After: no status dot at all (user decision 2026-10-22); the message icon and `2` at the row's right edge (the SVG `msg` icon, not an emoji), with "Returned · 2 new messages" as screen-reader text. With no unread messages the row keeps its short status line ("Returned · fix and resubmit") and no icon.
- Details one step away: hovering or keyboard-focusing a row shows a small card to the right of the sidebar (status, authority, reviewer, answered count, unread, last update), one icon and a few words per line. Actions sit behind the row's ⋯ (glyph only, no fill), a right-click or Shift+F10: one icon-left menu with Rename, Pin, Archive or Restore, Delete. Archived rows wait on a collapsed "Archived" shelf with its count.
- Code: `statusLine()` and `previewFacts()` in `web/src/calm/applications.ts`, `Row` in `web/src/calm/shell/ApplicationList.tsx`, `RowMenu` and `RowPreview` in `web/src/calm/shell/`.

## Example: stage navigation

- Before: `1 Describe  2 Questions  3 Review  4 Application` with thin underlines.
- After: four icons, in order, never with a fill, pill or shadow (at rest, current, hover, pressed or focus). Only the current one shows its one-word name beside its icon, at full opacity (`Describe`, `Questions`, `Review`, `Application`); the others are the icon alone, dimmed and brighter on hover or keyboard focus, fainter when locked (user decision 2026-10-22, "Option A+B"; it replaces "never with words beside them"). Compact cues keep the state in one neutral ink: a small green check mark when done, a thin line at the foot while part of the way through. "Questions, 40% done" is the accessible name and the hover/focus label (one label open at a time).
- Code: `StageButton` and `StageRings` in `web/src/calm/shell/AppHeader.tsx`.

## Example: the officer's review

- One screen, the same layout as the applicant's Review (user correction 2026-10-26: the three-place deck was "too much"; a review is a list you scan, not a deck you page through). No header stages, no steps, no Next.
- A headline that counts ("Ask for 3 things.", "Complete. Ready to accept."), one quiet lede line only when the application was resent ("Since version 2: 1 fixed · 1 new").
- "To ask": one row per item, a status dot (a ring when it couldn't be read: look first) and a few words. The row opens in place to the applicant's own words in full and a chip per source file. ✕ means don't ask; a required item asks why with three one-tap reasons, no note. A rule-required item says "Required" and has no ✕. "Add your own" is a link. What isn't asked folds under "Not asking · n".
- The card: the four sections (icon, letter, a short count) open the application at that section; then the one primary (Accept when complete, otherwise "Return · n"), and "Completeness only". Messages and the menu (⋯) hold everything else.
- The application one step away is not a paper form with coloured dots (user correction 2026-10-26: "a child playing around with colors and circles on a document"). It is sections headed like the card (icon tile, title, faint letter), then label and value lines in one ink. "Not given" in grey, never red. A line with an open item gets a light shade and one word (Asking, Look first, Not asking, with a count when several share a line).
- Opening an application nobody has picked up picks it up; "Stop reviewing" (⋯) goes back to the queue.
- Code: `web/src/calm/reviewer/ReviewWorkspace.tsx`, `OfficerReview.tsx`, `ReadSheet.tsx`.

## Example: an application title

- Before: `SYNTHETIC HTTP administrative review fixture  Edmonton` across the header.
- After: `Infill sheathing`, renamed in place in the header or via the row's ⋯ → Rename; the authority stays in the application.
- Code: `EditableTitle` and `RenameDialog` in `web/src/calm/shell/`, `renameCase` in `web/src/store.tsx`.
- Reference (read only, the interaction to match, not its styling or features): Irsal's `components/studio/editable-title.tsx`, `AGENTS.md` (inline renaming rule) and `docs/STUDIO-UI.md` (automatic names), under `~/Documents/Irsal/Irsal Website/Irsal/`.

## Example: a question card

- Before: "What date is this request?" / "The date you submit this request." / date field / "Answer to continue, or skip for now." / OK · Why we ask · Skip for now / "Not sure what this means? Ask the assistant".
- After: "Request date" / date field / OK · Skip · Help.
- Code: titles and context in `web/src/calm/deck.ts`, the card shell and `HelpButton` in `web/src/calm/QuestionDeck.tsx`.

## Check before handing off

Render the changed screen at desktop (about 1440 wide) and phone (about 390 wide) and look at the screenshots. Done when every remaining sentence earns its place by the test above, nothing clips or wraps badly, focus and hover labels work, and each removed sentence is either redundant or one step away.
