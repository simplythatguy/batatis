# BAT-62 PR 1: build notes (ui/minimal-redesign, off dev @ adb7f88)

Edited only `web/src/` (plus `R/spec.md` for Task 1). Not committed. `npm run typecheck` and `npm run build` pass.
**Not visually verified.** Building a static copy for file:// screenshots needed approval that wasn't available, and dev servers were off-limits. Re-shoot with `shoot-redesign.mjs pr1` before review.

## Cut list, PR 1

| # | Item | Status | Where |
|---|---|---|---|
| 1 | Gap strip → header "● N to fix" + drawer | **Done.** Blocking count on the button, notes count beside it, and one right-side drawer (To fix / Notes, each row links to the fix and closes the drawer) | `components.tsx` (`GapControl`, `PanelHeader`), `styles.css` (`.gap-control`, `.drawer*`) |
| 2 | "What is missing" chip wall | **Done on dev** (dev's version was the `GapStrip` chip grid; the gap list now lives only in the drawer). pr16's "appears to be missing" list: **deferred (#16)** | `components.tsx` (GapStrip removed) |
| 3 | Fact ledger pane → one row | **Done.** "Facts · 10 · 4 to check" is a collapsed row; the model-checked line stays visible under it; gap links open the row and focus the fact | `case-parts.tsx` (`FactLedger`), `router.ts` (opens `<details>` around a focus target), `screens/Describe.tsx` |
| 4 | Repeated footer disclaimer | **Done on dev / n/a.** Dev had no repeated banner. The sidebar has "Checks paperwork, not compliance."; the limitation line is kept in the completeness dialog and the drawer (ruling 1). D/Officer lines: **deferred (#16)** | `App.tsx`, `screens/Application.tsx`, `components.tsx` |
| 5 | Example banner → 32 px strip | **Partial.** "EXAMPLE DATA · fictional · {role} · {title}" strip, never dismissed. No "Start my own" link: dev has no empty-case flow (it comes with #16's role picker) | `App.tsx`, `styles.css` (`.example-strip`) |
| 6 | Sidebar groups out; 3 steps; footer links; C as a tab | **Done, with one limit.** Steps 1 Describe · 2 Code check · 3 Application; group labels cut; footer has the case, "Checks paperwork, not compliance." and Reset. Section C is the Application tab "Section C · Objectives and functions". `#/section-c` still deep-links to it and `?tab=C` works too. Code check (the code-ID step) stays in the stepper. **Officer view / How we checked links are wired but hidden** (`ready: false`) because both screens are placeholders on dev (item 7); flip `ready` when #16 lands | `App.tsx` (`STEPS`, `FOOT_LINKS`), `screens/Application.tsx` |
| 7 | Placeholder screens | **Done.** Both are out of the sidebar. The routes still render a one-line empty state plus one action; "Accuracy report" is renamed "How we checked" | `screens/Placeholders.tsx` |
| 8 | One primary per screen | **Done.** Describe: Continue. Code check: ghost Back + Continue. Application: ghost Back + Check completeness. Dev had no Save draft or Search buttons | screens |
| 9 | Code check paragraphs → one line | **Done** (dev intro → one meta line). The engineer/departure paragraphs and "Article ranking isn't available" are not on dev: **deferred (#16)** | `screens/CodeCheck.tsx` |
| 10 | Card chrome | **Done.** Cut "1 of 3", the "Code text / The code says" label, the "Code reference" disclosure and the filter tabs. The citation line sits under the quote | `screens/CodeCheck.tsx`, `components.tsx` (`Citation`) |
| 11 | Red borders on load | **Done.** Empty fields show a grey pending dot; the red border appears only after Check completeness is clicked. Check completeness is now always enabled and opens "N items to fix" with Fix links (or "No blocking items"). This is presentation only: no gap or blocking rule changed | `screens/Application.tsx`, `case-parts.tsx`, `styles.css` (`.checked .field.is-empty`) |
| 12 | Export dialog repeats | **Deferred (#16)** (no export on dev). The completeness dialog has the "Example data · fictional" note once | — |
| 13 | Officer paragraphs | **Deferred (#16)** | — |
| 14 | Section C search + explainers | **Done.** Dev had no Section C search. The explainer paragraph is now one line plus the source label. Intent and the AI explanation sit behind one "Intent and explanation" row. The table drops the Intent column (it lives in that row) | `screens/SectionC.tsx` (`SectionCBody`) |
| 15 | Professional "Not sure" / "Not engaged yet" | **Deferred (#16).** Dev has no professional field (no Section D) | — |
| 16 | Typed evidence not a file fact | **Deferred (#16) / n/a.** Dev has no evidence code path (no `evidence.<slot>.file_ref` writes); nothing to fix | — |

Other shell items:
- **Kit tokens:** the kit names and values go in `styles.css :root` (`--background`, `--card`, `--popover`, `--sidebar*`, `--muted`, `--accent`, `--input`, `--border(-strong)`, `--primary(-foreground/-hover)`, `--ring`, `--text-tertiary`, `--border-danger`, `--code-bg`) plus `--strip-height` and `--column-width` (720). Shell, primary button, nav, inputs, drawer and strip use them. `docs/design/tokens.css` is untouched and still supplies the base components.
- **Jargon renames:** fact kinds: Pointed → "From your file" / "From your words" (by source type), Proposed → "Our guess · check it", Computed → "Worked out". "Main requirement" → "Main code rule". "Departure confirmed" → "You said: different" and "Not a departure" → "Same as the code". "Attribution table" → "objectives and functions list". "Fact ledger" → "Facts". "Accuracy report" → "How we checked". Gap chips are now sentences: only `label` strings changed in `model.ts`, and every gap, severity and href is unchanged.
- **autocomplete="off":** on every applicant field, the description, the question answers and the process textareas (`case-parts.tsx`, `Describe.tsx`).
- **Proper-cased places:** display table in `places.ts`, applied to the place fields (`site.climate`, `municipalAddress`, `mailingAddress`) in `displayValue`. Stored values are untouched.
- **Save on input:** dev already dispatched on every keystroke (never on blur). The browser copy is now written 500 ms after the last edit and flushed on `pagehide` (`store.tsx`). The footer reads "Saved in this browser". "Not saved · Retry" needs the engine PATCH (PR 2).

## Guardrails as built

| Guardrail | Where it lives now |
|---|---|
| EXAMPLE DATA · fictional | 32 px strip on every screen (`App.tsx`); sidebar "{role} · Example data"; completeness dialog footer |
| AI-agent simulated | Not on dev (no tester results are cited anywhere). Lands with How we checked (#16), inline next to results (ruling 5) |
| Model-checked | Visible meta line under the Facts row (`FactLedger`) |
| Not sure → officer | Code check: a "Not sure" button on every card, with "Not sure? It goes to the officer as an open question." Choosing it shows "Open question for the officer: {question}". Describe questions show the same line |
| Non-finding notice (ruling 1) | Completeness dialog and gap drawer: "Checks that information is present. Not a finding that the design complies." Sidebar: "Checks paperwork, not compliance." |
| Unsigned, Part 2 blank | Not on dev (no export) → #16 |
| Edition and page | `Citation` line on every Code check card and the Section C detail: "NBC(AE) 2023 · 2nd printing · Div B 9.25.5.2.(1) · PDF p.1000". The Code check header keeps "NBC(AE) 2023 · 2nd printing". **No ↗ link:** dev has no code-PDF URL, and I did not invent one |
| Professional / engineer flags | Not on dev → #16 |
| Needs evidence chip | Not on dev → #16 / PR 2 |
| AI-written labels | "AI-written question" under each card question; "AI-written · Explanation, not code text" in Section C |
| "Batatis never drafts these" | Kept on the Alternative tab and the details disclosure |

## Karen rulings applied
- **Spec:** a "Karen rulings (Oct 20)" section replaces "Check with Karen". I fixed the contradicting lines (Footer, Professional fields, Describe/Application/D/Officer/How-we-checked rows, facts order, must-keep 1, the guardrail rows for AI-agent simulated / Not sure / non-finding / professional, cut items 4, 6, 15, and PR 2/4 scope).
- **In code:**
  - (1) The limitation line stays in the completeness dialog.
  - (3) Intake questions and the A/B details stay in Describe.
  - (4) C is a tab with the agreed label; `#/section-c` is kept and the stepper shows Code check.
  - Copy change: "Not sure? It goes to the officer as an open question." is used everywhere.
- **Nothing to apply on dev:** (2) bulk confirm is PR 2. (5) No test results are cited. (6) There is no professional field or export. (7) No pilot copy exists.

## Deferred and risky
- **Not sure still blocks on dev.** "Not sure" stays a blocking gap in `model.ts` (domain rule, untouched), so Continue on Code check is still disabled. The card says "Until officer routing is connected, answer Yes or No here once you know to continue." Real routing needs #26.
- **Flag for Peery and #20 (ruling 4):** Code check's Continue now lands on Application › Section C (`#/section-c`). Back from Application goes to Code check.
- **Footer links are hidden:** Officer view and How we checked stay hidden until those screens exist. Reset still restores the example case (dev behaviour), not an empty one.
- **Section C width:** the table now sits in the 720 px column. Check it at 1440×900 in the re-shoot.
- **Out of scope for PR 1:** per spec, one-open-card Code check, the facts panel and "Look right · N", the description collapse, the gap delta line and the authority row go to PR 2/3. Everything #16-only waits for #16: role picker, Section D, officer review, export, "Start my own" and typed-evidence handling.

## Round 2

`npm run typecheck` and `npm run build` pass. Not committed. Still **not visually verified** in the app: running node or vite for a static copy needs approval that wasn't available. I re-checked the `after-v3` PNGs by eye; they were not re-rendered after my HTML edits.

### 1. Status language
- **Spec:** added a 4th neutral state, **info**: a tinted circle with an `i` glyph. Tokens: `--status-info` dark #7cb0f7 / light #1d5bb8, plus `-soft` and `-line`. Contrast is AA on every surface (dark 7.6–9.0, light 5.6–6.5; the glyph on its tint is ≥ 4.84). Ratios are hand-computed because node needed approval, so re-check them with a tool. Info is never counted as to fix or attention and never blocks. I also added the grouping rule for repeated gaps.
- **`after-v3`:** 02, 03 and 06 now show the header control as octagon · square · circle `1` (a Calgary form notice). R/after and R/after-v2 are untouched.
- **Built:** `StatusIcon` and `StatusBadge` in `components.tsx`:
  - States: blocked, attention, ok, info.
  - Kinds: blocked, open-question, confirmed, needs-professional, pdf-locked, evidence-listed, unconfirmed, needs-evidence, info. All kinds are exported for #16.
  - Glyphs are inline lucide paths; there are no new dependencies.
  - Every mark has `role="img"` and an `aria-label`, or is `aria-hidden` with an sr-only label next to it.
  - `label` is a required prop, so TypeScript rejects a mark without an accessible name.
  - A bare count is read once.
  - The octagon falls back to an outline in forced-colours mode.
- **Gap type:** `Gap.severity` gains `"info"` (`types.ts`). The model still produces none.
- **Applied:**
  - Header control: marks and numbers, with the full sentence as the aria-label and title.
  - Drawer: groups "To fix", "Needs attention" and "For your information · not counted".
  - Sidebar steps: the worst mark per step replaces the step number.
  - Fact rows: a confirmed or not-confirmed mark replaces the "Check" pill and the "Confirmed by you" line.
  - Facts summary, question header and Describe footer: a mark plus a count replaces "N to check" / "N open" / "N facts still need you".
  - Code-check cards: a mark per answer replaces the status pill, the Not sure button carries the `?` mark, and the footer shows one mark per card (sr "2 of 3 answered").
  - Application tabs: a mark replaces the count.
  - Section C: a mark per answer. "Differs from NBC 2020 intent" is now an **info** badge, not a warning.
  - Completeness dialog: an lg mark on the title.
  - Empty fields: the unconfirmed mark replaces the dot.
- **Text cut:** status sentences that a mark now says. Kept as text: every Karen disclaimer, "Not sure? It goes to the officer as an open question.", "Model-checked…", EXAMPLE DATA, and "Checks that information is present. Not a finding that the design complies."
- **Deferred to the #16 follow-up:** Section D items, officer missing items and the PDF lock. The kinds are ready for them.

### 2. Route ownership
`web/` screens call only POST /section-c and GET /code/{id}. The client also defines POST /cases, GET /cases/{id}, POST /cases/{id}/facts and GET /code/search. All of these are on dev, and nothing calls a not-on-dev route, so no guard was needed. The spec's rollout section now has a "Route ownership" table (route → on dev? → owner PR → stage that may wire it) and the rule that a route is wired only once it is on dev.

### 3. Privacy notice
dev's `web/` has no privacy wording; the repo's privacy text is in `docs/` plans, not UI copy. So nothing is built. The spec has the plan: one shared `PrivacyNotice`, shown once in the sidebar footer and once under the Describe description box, never on Application tabs, with wording from #24/#38.

### 4. NRC credit
- `CodeCredit` is one shared component: a muted "Code text: National Research Council of Canada ↗" line that opens in a new tab with an aria-label.
- It is used through `CodeText`, which now renders every code text block (code-check cards, the Section C detail).
- **Link:** `https://nrc.canada.ca/en/certifications-evaluations-standards/codes-canada/codes-canada-publications/national-building-code-2023-alberta-edition`. It is already in the repo (`research/precedents/source-catalog/calgary.html:1162`), so I did not use the generic fallback. The generic `…/codes-canada` URL is also in the repo (`evals/ui-artifacts/03-section-c.html:85`).
- **Not on dev:** Search rows and the "Code reference" disclosure; #16 should use `CodeCredit` there.
- Added to the spec (global rule + guardrail row) and to `after-v3/06` as its own line under the citation; on the same line it wrapped mid-phrase. 06 is the only v3 mockup that shows code text.

### 5. Unc6 (#16 @4a4c122)
| Item | PR 1 on dev | Elsewhere |
|---|---|---|
| Raw keys | `factLabel` falls back to a humanised last segment, never the dotted id; the two keys Unc saw have labels (`model.ts`, display only) | #16 keys: PR 4 |
| Empty "The code says" | `CodeText` shows muted "Code text not loaded" / "Loading code text…" plus the citation | Search rows: PR 3 |
| Dialog wall + notice off screen | The notice now sits above the list. Repeated gaps of one kind (≥ 3) collapse into one expandable row ("5 required fields are empty"); the list scrolls inside the dialog. The drawer uses the same `GapList` | #16 export dialog: PR 5; `after-v3/05` updated |
| Reload / Reset | A reload with a changed case asks "Pick up where you left off?" (Resume / Start again; Escape = Resume). Reset asks to confirm (`ConfirmDialog`). This reverses the earlier Karen-items cut, recorded in the spec | — |
| Typing lag | `useDraft` (`draft.ts`): description, A/B fields and alternative-path fields keep the text locally and commit ~300 ms after typing stops, on blur and on unmount. A keystroke re-renders only that field | D fields: PR 4 |
| Brief dumped into Proposed alternative | dev's "Start from my description" was already cut in round 1 | #16 intake: PR 2 |
| Officer dedupe, ~8 blocks, "isn't available…" | n/a on dev | PR 5; noted in `after-v3/04` |
| Professional Not sure / Not engaged yet | n/a on dev | PR 4; already in `after-v3/03` |
| "Evidence types to consider" ×17 | n/a on dev | PR 4; shown once in `after-v3/03` |

All of these are in the spec under "Unc6 → where each is fixed".

### `after-v3` overflow fixes
- **03:** the field-row class `.f` collided with the sidebar's `.f` line, so "Checks paperwork, not compliance." took the 230 px grid and ran past the sidebar edge. Field rows are now `.pf`.
- **02, 03, 04, 06:** sidebar footer links broke inside a label ("Officer / view"); they now wrap whole.

### Risks
- `--status-info` overrides `tokens.css`'s grey alias in the web app only; `docs/design/tokens.css` is untouched.
- The resume prompt compares the saved case to the fixture. Typing and then deleting text still counts as changed, because fact ids are new.
- A field edit made less than 300 ms before the tab closes can be lost: the draft commits on blur but not on `pagehide`.
- "Not sure" still blocks Continue on dev (`model.ts` rule untouched). So the code-check card shows a yellow `?` while its gap is red in the drawer. Both are accurate until #26.
