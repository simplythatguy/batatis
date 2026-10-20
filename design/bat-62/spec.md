# BAT-62 phase A: Batatis minimalist redesign spec

Design only: presentation and copy. No engine, `evals/` or `docs/` changes. Baselines: dev @ 64d5027 (`before/dev/`) and **PR #16 @ 8bbccf6** (`before/pr16-8bbccf6/`; older shots in `before/pr16/`). Mockups: `after/01`–`06`; status language: `after-v3/01`–`06`.

**Governing test (aamia, Oct 20):** each screen shows ONE thing to do. Everything else is hidden, collapsed or removed; when in doubt, cut. Guardrails stay, collapsed by default, unless they must be read before an action.

## Principles
1. One task and one primary (`--primary`, bottom-right) per screen. At most ~5 visible blocks.
2. One item open at a time; the rest are one-line rows.
3. Verbatim words (yours or the code's) are labelled. The tool never decides compliance.
4. Every gap-count change says why, at the control that caused it.
5. Plain words first; IDs and section letters muted.

## Global rules

| Rule | Spec |
|---|---|
| Tokens (kit PR #3; eval alias) | `--background` #080808 (`--bg-app`), `--card` #131315 (`--bg-panel`), `--popover` #19191b (`--bg-elevated`), `--sidebar` #0c0c0d, `--muted`/`--accent` white 4%/6% (hover/active), `--input` #121214, `--sidebar-border`/`--border`/`--border-strong` white 6/10/16%, `--foreground`/`--muted-foreground`/`--text-tertiary`, `--primary` #e6e6e6 + `--primary-foreground`, `--ring` (focus only), `--status-blocking/-warning/-pending/-done`, `--code-bg` |
| Nav | 3 steps: Describe · Code check · Application. Officer view, How we checked and Reset become tertiary links in the sidebar footer, under "Checks paperwork, not compliance." The active item gets the `--accent` fill only |
| Header | 48 px (`--header-height`): title, plus one "● N to fix (+1)" button that opens the gap drawer. Warnings live in the drawer |
| Example strip | 32 px: "EXAMPLE DATA · fictional · {label}" with a "Start my own" link. Never dismissed |
| Footer | One status line, ghost Back, one primary. No Save draft. No repeated generic disclaimer; the limitation line stays on verdict-like screens (ruling 1) |
| Saving | **Narrative fields save on input** (debounced ~500 ms), not on blur, so the first fill never gets lost (gap count stuck at 7 in Unc's run). The status reads "Saved", or "Not saved · Retry" on any non-2xx |
| Density | Rows and inputs 32 (`--row-height`, `--input-height`); column 720; `--space-8` between blocks, `--space-4` inside |
| Type | `--text-lg`/600 title, `--text-base` body, `--text-sm` meta. No uppercase except table headers |
| Colour | Status shows as a StatusIcon: colour plus shape, never colour alone (see Status language). Empty fields get the `unconfirmed` mark; `--border-danger` only after a Continue attempt |
| Motion | `--duration-fast` / `--ease-out`; no spinners |
| States | Empty: one line + one action. Loading: pending dot + SSE stage word. Error: "Can't reach the checker. Your work is saved in this browser." + Retry, with raw text under `<details>`. Never blank (dev 06/07) |
| Forms | `autocomplete="off"`; prefilled values say "From your description · Confirm"; selects start empty |
| Place names | Proper case from a display table ("Calgary", never "calgary") in the sidebar, rows and exports |
| Evidence source | **Typed evidence text is never a file.** Never write it as `evidence.<slot>.file_ref` with source type `file`. It goes through POST /cases/{id}/evidence with kind `text` (or as `user_text` facts) and shows "Evidence listed (not reviewed)". Only real uploads are file evidence, shown as "Saved, not read yet" |
| Code text credit | Wherever code text appears (Search rows, Code reference, Section C code text, code-check cards): one shared `CodeCredit` line, muted, under the citation: "Code text: National Research Council of Canada ↗", linking to the NBC 2023 Alberta Edition page on nrc.canada.ca (`…/codes-canada-publications/national-building-code-2023-alberta-edition`, already in `research/precedents/source-catalog/calgary.html`; fallback `…/codes-canada`, used in `evals/ui-artifacts/03-section-c.html`). Never a deep link we made up. #16 uses the same component |
| Code text missing | Never an empty "The code says" box (Unc6 #3): show muted "Code text not loaded" with the citation line, or "Loading code text…" while it loads |
| Privacy notice | One shared `PrivacyNotice`, shown in exactly two places: the sidebar footer and directly under the Describe description box. Never on Application tabs or repeated per field. **Wording comes from #24 / #38**; nothing renders until that text is on dev (no placeholder, no invented text). Not on dev as of round 2 |
| Raw keys | No field id on screen (`professional.fire_suppression`, `ahj_requires_professional`; Unc6 #1). Labels come from a display table; an unknown key falls back to a humanised last segment ("Fire suppression"), never the dotted id |
| Reload and Reset | Reload with a saved case asks "Pick up where you left off?" (Resume / Start again); Reset asks to confirm. Both are one small dialog (Unc6 #10) |
| Field input | Fields keep the typed text in local state and commit to the case after ~300 ms idle (and on blur), so a keystroke re-renders only that field, not the whole tree (Unc6 #8) |
| Professional fields | Every one (engaged engineer/architect, APEGA/AAA number, seal…) offers **"Not sure"** (`not_sure`) and **"Not engaged yet"** (`not_engaged_yet`), always visible. Both route to the officer (engine #26) and never map to "no". Never block the draft; "Not engaged yet" with the engineer flag yes/unknown blocks the official PDF (ruling 6) |

**Jargon renames:** fact kinds "Pointed" → "From your file", "Proposed" → "Our guess · check it", "Computed" → "Worked out". "Attribution table" → "objectives and functions list". "Division B benchmark" / "Main requirement" → "main code rule". "Departure" → "different from the code" ("Departure confirmed" → "You said: different"). "Fact ledger" → "facts". "Accuracy report" → "How we checked". Cryptic chips ("Answer: sheathing membrane", "Confirm storeys") become full sentences.

## Per screen

| Screen (before) → mockup | The one thing | Visible | Collapsed or cut |
|---|---|---|---|
| Landing (pr16 01, 31) → 01 | Pick a role | "Who are you?", "It starts empty. Nothing is filled in for you.", 3 role rows (verbatim), "Or open an example (Example data, fictional)" | Cut: per-example paragraphs ("Cached summary from development case dev-003"), "Roles: …", the sidebar nav and the case block |
| Describe (dev 01, 11; pr16 04–07) → 02 | Confirm or fix the facts | The description collapsed to one line (Edit, "1 file · Saved, not read yet"); "We read these. Confirm or fix."; one-line fact rows; one status line | Behind a row chevron: the quote ("Why we think this"), the jurisdiction explainer and "Why we ask". Cut: the second paste box, the "What is missing" chip wall, the Fact ledger pane, the authority select (now a row). Intake questions (owner, address, storeys, …) stay here; only article-specific "Your words" cards move to Code check (ruling 3) |
| Code check (8bbccf6 10, 11) → 06 | Answer the open card | One card: snippet, citation, AI-written question, Yes/No/Not sure; other cards as one-line rows with status; "None of these fit? Ask the officer · Search the code" | "Before you answer ›". **Search results collapse after an article is added** ("Added 9.x · Undo"). Cut: tabs, card chrome, the engineer and departure paragraphs, "Article ranking isn't available…", the full-width search |
| Application: Applicant A, Project B, Code references C, Your alternative (dev 08–10; pr16 14, 17–19) | Fill the tab's fields | Fields prefilled from confirmed facts; Code references C is a 3-column table (provision · your answer · objectives and functions) with a row expand | Cut: the "Variance template…" meta (the header shows the scope), "Start from my description", "Required", red borders on load, the Section C search and its paragraphs. Section C may become the tab "Section C · Objectives and functions"; `#/section-c` stays deep-linkable and the stepper still shows the code-identification step (ruling 4) |
| Evidence D (8bbccf6 20, 21; pr16 21) → 03 | Resolve the open to-do | One-line professional flag; a "To do" list with one item open; "Done · N" collapsed Professional fields show "Not sure" and "Not engaged yet" (see global rule); either one → "Sent to the officer. Not blocking the draft." (official PDF: ruling 6). Limitation line kept: "Recommendations only…" (ruling 1) Typed evidence → "Evidence listed (not reviewed)". "Why?" holds the reasons plus "A sales-rep email is not an engineering judgement." Cut: "depends. depends.", the 18-select form ("Not answered" after set), raw `needs_professional`. The route-card slot stays hidden until `installed` |
| Check completeness (8bbccf6 24, 25) → 05 | Fix the first item | Title "3 items to fix before the PDF"; one row list with Fix links; the notice (must be read first; ruling 1) | Cut: the 4× repeated "Example PDFs are not yet labelled", "Current missing items", long "appears to be missing…" sentences, the second Close |
| Officer view (8bbccf6 27, 28) → 04 | Copy the information request | "N items need attention", the package line, one list of one-line groups, the limitation line "does not decide whether the design complies or is safe" (ruling 1) | Now reviews the loaded case (8bbccf6). Behind chevrons: group items and reviewer notes. "Preview request" is ghost. Cut: the engineer paragraph (moved to the D row "Why?"), the duplicate "Online review unavailable" ×3, the full-width Retry |
| How we checked, dialogs (pr16 30, 31) | Read / confirm | Definition + engineer-needed line; dialog title + ≤2 lines; "AI-agent simulated" next to every tester quote, timing or persona result (ruling 5) | Duplicate fact list cut. Reset keeps "Cleared. Nothing from the previous case is kept." |

**Facts panel fields** (Backy draft BAT-65, **names may change, agreed with Backy**): `applicant_role`, `owner_name`, `municipal_address`, `legal_description`, `permit_number`, `municipality`, `jurisdiction_scope`, `occupancy`, `storeys`, `building_area_m2`, `dwelling_units`, `sprinklered`, `product_or_assembly`, `installation_status`, `claimed_provisions`, `claimed_exemptions`, `proposed_alternative` (departure clause only), `required_acceptable_solution`, `evidence_items`.
- Order: asserted, missing, low, then medium confidence. High confidence collapses into "Look right · N" with "Confirm these N" (PR 2, ruling 2: each fact shows its quote; recorded per fact as `user_click` with the quote, never one blob; reserved facts and low/unknown confidence never in the bulk set).
- Status chips: extracted → "Check", corrected → "Corrected by you", missing → "Missing".
- `claimed_exemptions` get the Needs evidence chip and never a Confirm.
- After PATCH: "Gap check re-ran: +2 new … · 1 cleared".

## Must-keep, shortened
1. Routing: "Not sure? It goes to the officer as an open question." / "An officer reviews and decides."
2. "Checks that information is present. Not a finding that the design complies."
3. "EXAMPLE DATA · fictional" and "Model-checked from your words. Nothing counts until you confirm."

## Guardrails kept

| Guardrail | Where | State | Wording |
|---|---|---|---|
| EXAMPLE DATA | Strip, dialog note, exports | Visible | "EXAMPLE DATA · fictional · {label}" |
| AI-agent simulated | Next to every tester quote, timing or persona result; How we checked | Visible wherever test results are cited; footer link only on screens citing none (ruling 5) | "Our user tests so far are AI-agent simulated sessions, not real users." |
| Model-checked | Facts heading meta; How we checked | Visible, one meta line | as above |
| Not sure → officer | Every question | Visible option | "Not sure? It goes to the officer as an open question." · "Open question for the officer: {question}" |
| Non-finding / limitation line | Check completeness dialog; Officer screen; Section D (ruling 1) | Visible on every verdict-like screen | as above; D: "Recommendations only…"; Officer: "does not decide whether the design complies or is safe" |
| Unsigned, Part 2 blank | Export dialog; Officer package line | Visible before export | "The PDF is unsigned, with officer Part 2 left blank." |
| Edition and page links | Each citation line | Visible on the open card; collapsed in rows | "NBC(AE) 2023 · 2nd printing · Div B 9.25.5.2.(1)(b) · PDF p.1000 ↗" |
| Professional flags | D flag row; Officer D row | Visible line; reasons under Why? | "Engineer or architect: {likely needed / not decided yet} · not a licence decision" |
| Needs evidence chip | Facts row; Officer claims row | Visible chip | "Needs evidence · officer will check" |
| Code text credit (round 2) | Next to every piece of code text | Visible, one muted line | "Code text: National Research Council of Canada ↗" |
| **Must-have:** professional "Not sure" / "Not engaged yet" | Every Section D professional field | Visible, never collapsed | Options "Not sure" (`not_sure`) and "Not engaged yet" (`not_engaged_yet`) → "Sent to the officer. Not blocking the draft." Engineer flag yes/unknown + "Not engaged yet" blocks the official PDF: "Routed to the officer: whether a registered professional is required" (ruling 6) |

## Karen items
- **In:** `autocomplete="off"`. The sales-rep line (under Why?, inline on vendor evidence). The route-card slot (hidden until `installed` + `route_options`). Needs evidence, merged with `claimed_exemptions`. The gap-delta line. "Saved, not read yet". The authority row (PATCH /cases/{id}).
- ~~**Cut:** "Continue your case or start new?"~~ **Reinstated (round 2, Unc6 #10):** Unc's cold GC run on 4a4c122 reopened the previous person's case on reload with no prompt, and Reset had no confirm. Reload with a saved case asks "Pick up where you left off?"; Reset asks to confirm (global rule "Reload and Reset").
- **Cut for now:** the GC entry "my work failed inspection" (needs `route_options`).

## Karen rulings (Oct 20)
1. **No** to "disclaimer only in sidebar and export". The repeated generic banner goes; the limitation line stays on every verdict-like screen: Section D ("Recommendations only…"), Officer ("does not decide whether the design complies or is safe"), Check completeness dialog.
2. **Yes** to bulk "Confirm these N" (PR 2), if: each fact shows its source quote; confirmation recorded per fact (`user_click` with the quote), never one blob; reserved facts (professional/seal, occupancy, anything tied to the engineer flag) excluded, confirmed individually or routed to the officer; low/unknown confidence never in the bulk set.
3. **No.** Intake gaps (owner, address, storeys, …) stay in Describe. Only article-specific "Your words" cards move to Code check.
4. **Conditional yes** to Section C as a tab: `#/section-c` stays deep-linkable; tab label "Section C · Objectives and functions"; the stepper still shows the code-identification step. Flag for Peery and #20.
5. **No** wherever test results are cited: "AI-agent simulated" sits next to any tester quote, timing or persona result. Footer link only on screens that cite none.
6. **Yes, draft only:** if the engineer flag is yes or unknown, "Not engaged yet" still **blocks** the official application PDF (gap: "Routed to the officer: whether a registered professional is required"). Non-blocking for the draft; always routed to the officer.
7. **Yes**, but never imply a pilot happened: "A pilot would use a real house as the test site", never "our pilot site".

Copy change everywhere: "Not sure? The officer will ask." → "Not sure? It goes to the officer as an open question."

## Perf and bugs (not design)
31 console errors; 3–9 s lag; blank Section C states (dev 06/07); dev 14 "No blocking gaps" with 15 open; the Section D tab shows Alternative content (pr16 20, still in 8bbccf6 20/21); the unknown route renders Describe; the 8 s timeout, 429 and 503 export need plain states.

## Cut list, PR 1 (stage 1)

| # | Removed or collapsed | Screen | Before shot | Guardrail |
|---|---|---|---|---|
| 1 | The 70 px "18 blocking · 4 warning · Review gaps" strip → header "N to fix" button | All | 8bbccf6 10 | None |
| 2 | The "What is missing" chip wall and the "appears to be missing" list | Describe | pr16 04, 03 | None (still in the drawer) |
| 3 | The Fact ledger pane → one "Facts · 10 · 4 to check" row | Describe | dev 01, pr16 06 | Collapsed (model-checked meta stays) |
| 4 | The footer disclaimer repeated on every screen | All | pr16 02–25 | Kept on verdict-like screens: D, Officer, Check completeness (ruling 1); sidebar line elsewhere |
| 5 | The 2-line example banner + button → 32 px strip | All | 8bbccf6 10 | None (label kept) |
| 6 | Sidebar group labels; Officer and Accuracy → footer links; Section C → Application tab (`#/section-c` kept; stepper keeps the code-ID step, ruling 4) | All | 8bbccf6 10 | Collapsed (How we checked one click away; "AI-agent simulated" inline where results are cited, ruling 5) |
| 7 | Placeholder screens "Not built yet", "No evaluation runs yet" | Officer, Accuracy (dev) | dev 12, 13 | None |
| 8 | One primary per screen: Save draft, Back and Search → ghost; full-width Search buttons removed | All | 8bbccf6 10, 24 | None |
| 9 | Code check paragraphs (engineer, departure, "Article ranking isn't available…") → one line | Code check | 8bbccf6 10 | Collapsed (engineer note under Why? on D) |
| 10 | Card chrome: "1 of 3", "Code text / The code says", "Code reference" disclosure | Code check | 8bbccf6 11 | None (citation line kept) |
| 11 | Red borders on empty fields at load | Application | pr16 17, 8bbccf6 20 | None |
| 12 | Repeated lines in the export dialog ("Example PDFs are not yet labelled" ×4) | Export | 8bbccf6 25 | None (EXAMPLE note kept once) |
| 13 | Officer engineer + scope paragraphs → one package line | Officer | 8bbccf6 27 | Collapsed |
| 14 | Section C prefilled search + three explainer blocks | Section C | pr16 14, dev 05 | None |
| 15 | Add "Not sure" (`not_sure`) and "Not engaged yet" (`not_engaged_yet`) to every professional select and map both to the officer, never "no"; non-blocking for the draft, blocking for the official PDF per ruling 6. Section D is owned by #16 | Evidence D | 8bbccf6 20, 21 | **Adds** a must-have (visible) |
| 16 | Typed evidence stops being written as a `file_ref` file fact; it becomes kind `text` / `user_text` and shows "Evidence listed (not reviewed)" | Evidence D | pr16 21 | None |

## Staged rollout (Submission 1: Oct 29, 2026)
Branch **`ui/minimal-redesign` off `origin/dev`**, one PR per stage, re-cut from dev after each merge. Each stage stays demo-able. **#16 (@8bbccf6) merges first.** If it slips past Oct 22, PR 1 ships the dev-side items (1, 3, 5–8, 10, 14) and the rest follow #16.

| PR | Scope | Demo after merge | Depends on |
|---|---|---|---|
| 1 · Cut list + tokens/shell (Oct 21–22) | Items 1–16; kit token names; save-on-input; proper-case places | Same flows, a third of the clutter; a professional can be marked "Not engaged yet" | #16 for items 2, 4, 9, 12, 13, 15, 16; #26 for the officer routing (map to `unknown` client-side until it lands) |
| 2 · Describe + facts (Oct 22–24) | Facts panel, "Confirm these N" (ruling 2), delta line, authority row, jargon renames | Paste → confirm facts → see the gap change explained | #16; Backy BAT-65 PATCH + `gaps_summary` (until then #16 facts + client-side delta) |
| 3 · Code check (Oct 23–25) | One open card, collapse-after-add, Not sure → officer, "None of these fit" | Answer 3 cards, continue unblocked | #16 @8bbccf6 identify-decision client; Backy #12 fields |
| 4 · Application + Evidence (Oct 24–27) | C as a tab (ruling 4 conditions); D to-do list; route-card slot | Fill A/B from facts; answer D as a to-do list | #16; #26 sales-rep rule; `route_options` later |
| 5 · Officer + export (Oct 26–28) | One-list Officer, export dialog | Check completeness → fix → text record; copy request | #16; Backy structured 409 `reasons`; example PDF stamp |

Freeze Oct 28: re-shoot with `shoot-*.mjs` and compare to `after/`.

### Route ownership (Backy, Oct 20)
A stage wires a route **only once it is on dev**. Until then the screen keeps its local fallback and says nothing about the engine (at most one plain line per screen, never "isn't available on this engine yet"; Unc6 #6). A 404/405 from a route that should exist hides the control instead of showing an error wall.

| Route | On dev? | Owner PR | May wire in |
|---|---|---|---|
| GET /cases/{id}/gaps | yes (#30 adds `?shape=v2` later) | — | PR 2 (header counts, delta line); `?shape=v2` only after #30 merges |
| GET /cases/{id}/professional | yes | — | PR 4 (D professional flag) |
| POST /section-c, GET /code/{id}, GET /code/search | yes | — | PR 1 (in use), PR 3 (search) |
| POST /description, GET /facts | no | #36 | PR 2, after #36 is on dev |
| POST / DELETE /cases/{id}/evidence | no | #30 (not #23) | PR 4, after #30 is on dev |
| POST /completeness (POST only, no GET) | no | draft #11 | PR 5, after #11 is on dev |
| GET /information-request | no | draft #12 | PR 5, after #12 is on dev |

Round 2 check: `web/` on this branch calls only POST /section-c and GET /code/{id} from screens (the client also defines POST /cases, GET /cases/{id}, POST /cases/{id}/facts and GET /code/search, all on dev). No call to a not-on-dev route, so nothing needed a guard.

### Unc6 (cold GC run on #16 @4a4c122) → where each is fixed

| # | Issue | Fix | Stage |
|---|---|---|---|
| 1 | Raw ids "Confirm professional.fire_suppression" | Display table + humanised fallback (global rule "Raw keys") | **PR 1** (dev labels); #16's professional keys in PR 4 |
| 3 | Empty "The code says" box; citation hidden under Code reference | `CodeText`: "Code text not loaded" + citation always visible | **PR 1** (cards, Section C); search rows PR 3 |
| 3 | "fire stopping" / "3.1.9.1" miss 3.1.9.1 | Engine search recall (not UI) | Backy; PR 3 shows "No match · try another word · Ask the officer" |
| 4 | Dialog wall of 16 lines; not-a-finding line off screen | Group repeated gaps; notice above the list | **PR 1** (dev dialog); #16's export dialog PR 5 |
| 5 | No "Not engaged yet" | Professional options (global rule) | PR 4 (needs #16 Section D) |
| 6 | "isn't available on this engine yet" ×4, "Searching the code database…", "Open Not sure" | Route ownership rule; plain stage words | PR 3 (Code check), PR 4 (Section C tab), PR 5 (Officer) |
| 7 | Officer: items twice, ~8 blocks above Copy request, "Practice of engineering is unknown." | One list; only title, tally, package and limitation lines above it (`after-v3/04`) | PR 5 |
| 8 | Typing lag in D fields; count jumps 9→20→18 unexplained | Local field state + debounced commit; delta line | **PR 1** (dev fields); D fields PR 4; delta line PR 2 |
| 9 | Pasted brief dumped into Proposed alternative | Dev's "Start from my description" was cut in PR 1; intake fills only the departure clause (`proposed_alternative`) | PR 1 (dev), PR 2 (#16 intake) |
| 10 | Reload reopens previous case silently; Reset no confirm | Resume prompt + Reset confirm | **PR 1** |
| 11 | "Evidence types to consider" ×17; F03/OS1.2 unexplained | Once per screen (`after-v3/03`); codes keep their `title` tooltip and the plain name | PR 4 |
| 2 | Filled answers still listed as missing | Engine/sync bug (not UI) | Backy; PR 5 re-checks with the 409 `reasons` |
| 12 | Thin advice (variance vs fix, vendor letter unreviewed) | Sales-rep line under Why? (Karen items); rest is content | PR 4 |

## Status language

**Direction (aamia, Oct 20):** marks do the talking, not counts and sentences. Red = blocks the PDF or is a problem; yellow = needs you or the officer (including Not sure); green = nothing left for you; **blue-grey info = for your information, nothing to do** (4th, neutral state, required by PR #40's gap severity `info`, e.g. a Calgary form notice). Mockups: `after-v3/01`–`06` (open any of them with `#light` for the light check). Green never means "complies": its labels say what the user did ("Confirmed by you"), never "OK", "Pass" or "Compliant".

**Never colour alone.** Each status has its own container shape, so it still reads in greyscale or with colour blindness: **blocked = solid octagon** (stop sign) with a knocked-out glyph; **attention = tinted rounded square** with a stroked glyph; **ok = bare glyph**, no container; **info = tinted circle** with a stroked `i`. Every mark has `role="img"` plus an `aria-label`, or sits `aria-hidden` next to visually hidden text. Status colour goes on the mark only; text next to it stays `--foreground`/`--muted-foreground`.

### Tokens

The kit's `--status-*` values are invariant (the same in both modes) and fail on light surfaces: on #fff, `#eb5757` 3.48, `#f2c94c` 1.59, `#4cb782` 2.50, `#8a8a8e` 3.44. So they become mode-scoped. Dark keeps the kit values; light gets darker values of the same hues. Ratios use WCAG 2.x relative luminance, with alpha composited onto the surface. They were hand-computed (this session had no shell), so re-check them with a tool in PR 1. Targets: every status colour reaches ≥ 4.5 on every surface in its mode (so it is safe even as text); icons and tiles ≥ 3.

| Token | Dark | Light | Dark contrast: card #131315 · popover #19191b · muted row #1c1c1e · bg #080808 | Light contrast: card #fff · bg #f4f4f5 · muted #eeeeef | Use |
|---|---|---|---|---|---|
| `--status-blocking` | #eb5757 | **#c42b2b** | 5.33 · 5.04 · 4.89 · 5.75 | 5.63 · 5.13 · 4.86 | Solid octagon fill (`blocked`) |
| `--status-warning` | #f2c94c | **#855800** | 11.69 · 11.06 · 10.72 · 12.62 | 6.19 · 5.63 · 5.34 | Glyph and edge of the attention square |
| `--status-done` | #4cb782 | **#18733a** | 7.43 · 7.02 · 6.81 · 8.01 | 5.91 · 5.38 · 5.10 | Bare ok glyph |
| `--status-pending` | #8a8a8e | **#6b6b70** | 5.40 · 5.10 · 4.95 · 5.82 | 5.30 · 4.82 · 4.57 | Not a status: neutral glyphs (file, saved) |
| `--status-warning-soft` (new) | `#f2c94c` @ 14% | `#855800` @ 10% | Glyph on tint: 8.74 · 8.06 · 7.80 | Glyph on tint: 5.36 (on card) · 4.67 (on muted) | Attention square fill |
| `--status-warning-line` (new) | `#f2c94c` @ 40% | `#855800` @ 40% | (decorative edge, glyph carries contrast) | same | Attention square inset border |
| `--status-on-solid` (new) | #141415 | #ffffff | On the octagon: 5.29 (octagon vs card 5.33) | On the octagon: 5.63 (octagon vs card 5.63) | Glyph knocked out of the octagon |
| `--status-info` (new, round 2) | **#7cb0f7** | **#1d5bb8** | 8.32 · 7.87 · 7.62 · 8.97 | 6.48 · 5.90 · 5.59 | Glyph and edge of the info circle |
| `--status-info-soft` / `-line` (new) | `#7cb0f7` @ 14% / 40% | `#1d5bb8` @ 10% / 40% | Glyph on tint: 6.55 · 6.12 · 5.89 | Glyph on tint: 5.60 (card) · 5.12 (bg) · 4.84 (muted) | Info circle fill / inset edge |

Info is a sky blue, not the indigo the system bans (#5E6AD2 stays banned for CTAs, focus and nav). `docs/design/tokens.css` aliases `--status-info` to pending grey; the web app overrides it in `web/src/styles.css` (round 2, hand-computed ratios, same WCAG 2.x method; re-check with a tool).

Light warning was first `#8f5f00`; it fails on the tint over muted rows (4.20), hence `#855800`. **Neutral text found in the check:** dark `--text-tertiary` #808086 is 4.73 on card but **4.47 on popover and 4.33 on muted rows** (fails). Disclaimers, meta and dialog notes therefore use `--muted-foreground` (dark 6.71 · 6.35 · 6.16; light #5c5c62 6.64 · 6.04 · 5.73), and tertiary is kept for chevrons and decoration only. The v3 mockups already do this.

### Icon map

Glyphs: lucide (ISC, inline paths, no network) unless marked *web*, meaning the existing `Icon` set in `web/src/components.tsx`. **Bold** kinds are the two additions to the six requested.

| State | `kind` | Default `status` | Glyph | Shape | Colour token | `aria-label` |
|---|---|---|---|---|---|---|
| Blocked / missing, blocks the PDF | `blocked` | blocked | `x` (as in `octagon-x`) | Solid octagon | `--status-blocking` + `--status-on-solid` | "Blocks the PDF: {what}" |
| Official PDF locked | `pdf-locked` | blocked | `lock` | Solid octagon | same | "Official PDF locked: {reason}" |
| Open question / Not sure | `open-question` | attention | `circle-help` (the `?` stroke) | Tinted square | `--status-warning` (+ soft, line) | "Open question for the officer: {question}" |
| Needs a professional | `needs-professional` | attention; **blocked** when ruling 6 locks the official PDF | `hard-hat` | Tinted square, or octagon when blocked | warning, or blocking | "Engineer or architect: {not decided yet / likely needed}" |
| Confirmed / corrected / answered | `confirmed` | ok | `circle-check` | Bare | `--status-done` | "Confirmed by you" · "Corrected by you" · "Answered" |
| Evidence listed | `evidence-listed` | ok | `list-checks` | Bare | `--status-done` | "Evidence listed (not reviewed)" |
| **Not confirmed yet / missing field** | `unconfirmed` | attention | `circle-dashed` | Tinted square | warning | "Not confirmed yet" · "Missing" |
| **Needs evidence (claimed exemption)** | `needs-evidence` | attention | `file-search` | Tinted square | warning | "Needs evidence, officer will check" |
| **Info / notice (gap severity `info`)** | `info` | info | `info` (the `i` stroke) | Tinted circle | `--status-info` (+ soft, line) | "For your information: {notice}" |
| Generic (no kind given) | — | any | blocked `x` · attention `!` (`triangle-alert` stroke) · ok `circle-check` · info `i` | by status | by status | required prop |
| Saved, not read yet (upload) | none (not a status) | — | *web* `file` | Bare | `--muted-foreground` | Text stays visible |

Sizes: 18 px (rows), 14 px `sm` (inline, tabs, footer), 24 px `lg` (dialog title). The glyph never goes below 9 px inside a 14 px container.

### Component API sketch (PR 1, `web/src/components.tsx`)

```tsx
type Status = "blocked" | "attention" | "ok" | "info";
type Kind = "blocked" | "open-question" | "confirmed" | "needs-professional"
  | "pdf-locked" | "evidence-listed" | "unconfirmed" | "needs-evidence" | "info";

// Mark only. role="img" + aria-label={label}. status defaults from kind (table above).
function StatusIcon(p: { status?: Status; kind?: Kind; label: string; size?: "sm" | "md" | "lg" }): JSX.Element;

// Mark + optional visible text (neutral colour). With text, the mark is aria-hidden and
// `label` goes into an sr-only span when it adds to the text; otherwise it behaves as StatusIcon.
function StatusBadge(p: { status?: Status; kind?: Kind; label: string; text?: ReactNode; size?: "sm" | "md" }): JSX.Element;
```
- `label` is a required prop, so TypeScript rejects a mark without an accessible name.
- Glyphs live in a 24-unit `STATUS_GLYPHS` map. The 16-unit `Icon` set (file, upload, close, chevron) stays as is.
- `StatusPill({dot})` maps blocking→blocked, warning→attention, done→ok; `pending` becomes plain text (no mark).
- CSS: `.si.blocked` uses `clip-path` for the octagon; `.si.attention` uses `--status-warning-soft` + an inset `--status-warning-line`; `.si.ok` is a bare glyph (see any `after-v3` file).
- Nav steps and Application tabs show the worst mark in that step or tab. Info never counts as "worst": it only shows when nothing else is open.
- **Info is never counted** as to fix or attention: the header control shows it as its own circle and number after the other two, the drawer lists it last under "For your information · not counted", the completeness dialog lists it under the fix list, and it never disables Continue or the PDF. `Gap.severity` gains `"info"` for display (round 2); the dev model produces none until #40.
- Repeated gaps of one kind (same group, ≥ 3) collapse into one row with an expander, e.g. "16 code clauses missing supporting evidence" (Unc6 #4). Same component in the drawer and the dialog.
- Counts stay next to marks; the full sentence is the accessible name, plus a `title` tooltip.

### Text this replaces

| Screen | Before (v2) | After (v3) |
|---|---|---|
| All, header | "● 14 to fix (+1)" | octagon `14` `+1` · square `!` `4` · circle `i` `1` (only when an info gap exists); aria "14 to fix before the PDF, 1 new… 4 need attention. 1 notice for your information, not counted. Open the gap list." |
| All, sidebar | Step numbers 1 · 2 · 3 | Step marks (worst state in the step) |
| Application tabs | "Evidence D · 3", "A · 1" counts | Tab marks |
| Describe | "● Missing" pill | `unconfirmed` square (aria "Missing"); the empty input says the rest |
| Describe | "● Corrected by you" pill | `confirmed` glyph (aria "Corrected by you") |
| Describe | "Check" chip | `unconfirmed` square + Confirm button |
| Describe | "● Needs evidence · officer will check" | `needs-evidence` square; **guardrail text kept** |
| Describe | Delta "● Gap check re-ran: +2 new … · 1 cleared" | Marks before `+2` and `1`; the reason stays (principle 4) |
| Describe | "Saved · 4 facts still need you. You can come back." | "Saved · ◌ 4" (sr "facts still need you") |
| Code check | "1 of 3" | Cut; footer shows one mark per card |
| Code check | "● Not sure · officer will ask" row pill | `open-question` square |
| Code check | "● Same as the code" pill | `confirmed` glyph; the answer stays as plain text |
| Code check | Footer "2 of 3 answered · Not sure is fine, the officer will ask" | Three marks (sr "2 of 3 answered"); the card gets the **required** "Not sure? It goes to the officer as an open question." (v2 used the old copy) |
| Evidence D | "● Engineer or architect…" dot | `needs-professional` square; **wording kept** |
| Evidence D | Not sure / Not engaged yet inside a dropdown menu | Always-visible segmented options (must-have: never collapsed) |
| Evidence D | "● Not engaged yet · sent to the officer as a professional flag. Not blocking." | Square hard hat "Sent to the officer. Not blocking the draft." + octagon lock "Official PDF · Routed to the officer: whether a registered professional is required" (ruling 6) |
| Evidence D | "To answer" / "Add evidence" pills | `unconfirmed` square / octagon + Add evidence button |
| Evidence D | "Done · 3 · authority requirement answered · 1 upload… · 1 Not sure…" | Three marks with short labels; "Evidence listed (not reviewed)" kept |
| Officer | Pills "Engineer or architect: not decided yet", "Needs evidence", "Officer to ask" | Leading marks per group; guardrail wording kept in the row text; "Open question for the officer: {q}" |
| Officer | "N items need attention" with no breakdown | Plus a tally: octagon `14` · square `4`; package line gets the lock |
| Export | Red dots | Octagons with kind glyphs (x, hard hat); title gets the lock; footer "Official PDF" lock |
| Export | "· or mark 'Not engaged yet'" | Cut: with the engineer flag not decided, it would not unlock the PDF (ruling 6) |
| Landing | — | Adds a one-line legend of the three marks and neutral role glyphs |

**Stays as text, never a mark (Karen):** the limitation line on D ("Recommendations only. You write the evidence and the answers. This does not decide that the design complies or is safe."), Officer ("…does not decide whether the design complies or is safe") and the Check completeness dialog; "Checks that information is present. Not a finding that the design complies."; "The PDF is unsigned, with officer Part 2 left blank."; "EXAMPLE DATA · fictional"; "Model-checked from your words. Nothing counts until you confirm."; "Not sure? It goes to the officer as an open question."; "AI-agent simulated" next to any cited test result (none of the six v3 screens cite one, so it stays on How we checked); "Saved, not read yet"; "Evidence listed (not reviewed)"; "not a licence decision".

**Round 2 mockup edits (`after-v3` only):** 02, 03, 06 header control show an info example; 05 moves the not-a-finding line above the list and groups the evidence gaps; 06 adds the NRC credit line; 03 shows "Evidence types to consider" once; 03's field-row class no longer collides with the sidebar line (it overflowed the sidebar); sidebar footer links no longer break inside a label.

**v2 gaps fixed in v3:** the D limitation line was missing; Code check had the old "officer will ask" copy and "1 of 3"; the export hint contradicted ruling 6; D's must-have options sat in a menu.
