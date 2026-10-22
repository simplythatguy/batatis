---
name: batatis-ui-minimalist
description: "Minimalist Batatis UI, the user's standing direction: icons before words, visuals over sentences, one thing at a time, short question labels with help on demand, icon-and-count metadata. Use when designing, changing or reviewing any Batatis screen, navigation, question, list row, card, banner, label or UI copy."
---

# Batatis minimalist UI

The user has asked for pure minimalism again and again: light mode, one colour per section, visuals over text, one thing on screen at a time. This skill decides **how much** goes on screen. `batatis-ui-linear` (P0 rules) and `docs/design-system-calm.md` (tokens, section colours) still decide how it looks.

## The test for every element

For each word, line, icon and control ask: does the person need it **now** to take the next step? Keep it. Needed later or only sometimes? Move it one step away. Never needed? Cut it.

1. **Icons before words.** Navigation, stages, status and counts are icons (with a ring, dot or badge for state); the name is the accessible name and a label on hover or keyboard focus, not a persistent row of text. Keep a visible word only where an icon would be ambiguous.
2. **Visual first.** A dot, icon, count, ring, colour or progress bar carries the meaning; the words left are short labels (one to three words), not explanations.
3. **One thing at a time.** One question, one job and one primary action (neutral near-black) per screen. Secondary actions go in ⋯ or a ghost button.
4. **Progressive disclosure.** Reasons, detail, history, code text and technical text sit one click or hover away: tooltip, drawer, `<details>`, the next screen.
5. **Compact metadata.** Icon then number (a message icon and `2`), never "2 new messages". The number always has its icon; a zero shows nothing.
6. **Breathing room.** Generous padding (sidebar rows `14px 16px`), selection as a soft fill, no decorative lines, edge bars or borders.
7. **Obvious questions are a label and a control.** "Request date" and a date field, then OK · Skip · Help. A subtitle that restates the field, "answer to continue" or "press Enter" lines, and a repeated "ask the assistant" invitation all go. The reason and the assistant sit behind the one Help entry on the card (the assistant exists for routine explanation); show text up front only when the control cannot carry it: the applicant's own quote, a validation error, a decision or professional boundary.
8. **Colour with a job.** Section hue (A blue, B teal, C violet, D amber) or a status dot. Accent marks one thing; it never fills a button.

## Minimal, never hidden

Minimalism moves information; it keeps every capability reachable. These stay visible on the screen they matter to:

- why an action is unavailable: a short visible hint, the full reason in `title` and for screen readers;
- errors, each with its retry;
- blocking gaps, the administrative-completeness boundary ("not a design approval"), refusal reasons with the appeal notice.

Every icon-only control or icon metadata has an accessible name and a hover label. When colour or an icon carries a status, the same status exists as text for screen readers. Familiar icons only (message, search, compose, close); anything less obvious keeps its one-word label.

## Example: application sidebar row

- Before: `● Returned · 2 new messages`
- After: `●` message icon `2` (the SVG `msg` icon, not an emoji), with "Returned · 2 new messages" as the hover title and screen-reader text. With no unread messages the row keeps its short status line ("Returned · fix and resubmit") and no icon.
- Code: `statusLine()` in `web/src/calm/applications.ts`, `Row` in `web/src/calm/shell/ApplicationList.tsx`.

## Example: stage navigation

- Before: `1 Describe  2 Questions  3 Review  4 Application` with thin underlines.
- After: four icons, each in a progress ring joined by a hairline: green ring and check badge when done, tinted when current, faded when locked. "Questions, 40% done" is the accessible name and the hover/focus label. The officer's review steps use the same control with their step hue and an open-count badge.
- Code: `StageButton` and `StageRings` in `web/src/calm/shell/AppHeader.tsx`, `StepTabs` in `web/src/calm/reviewer/PackageReview.tsx`.

## Example: a question card

- Before: "What date is this request?" / "The date you submit this request." / date field / "Answer to continue, or skip for now." / OK · Why we ask · Skip for now / "Not sure what this means? Ask the assistant".
- After: "Request date" / date field / OK · Skip · Help.
- Code: titles and context in `web/src/calm/deck.ts`, the card shell and `HelpButton` in `web/src/calm/QuestionDeck.tsx`.

## Check before handing off

Render the changed screen at desktop (about 1440 wide) and phone (about 390 wide) and look at the screenshots. Done when every remaining sentence earns its place by the test above, nothing clips or wraps badly, focus and hover labels work, and each removed sentence is either redundant or one step away.
