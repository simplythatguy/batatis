---
name: batatis-ui-linear
description: Default Batatis product UI/UX system. Always produce Linear-caliber, ruthlessly simplified interfaces (no feature loss) without the user needing to say Linear. Use for any applicant, SCO, intake, ranking, Section C, export, or product chrome work. Pair with batatis-ui-opus (Claude Opus 5.5 for implementation AND review).
---

# Batatis UI — Linear-default system

## Mandate (always on for product UI)

Agents **always** ship spectacular, simplified product UI matching this system — **without** the prompt saying “make it Linear.”

- **Simplify ruthlessly; never drop capabilities.**
- **Bug-free bar:** working controls; focus visible; empty/error states; gates while gaps open.
- **Formal UI seal = Opus 5.5** (Composer reviews are provisional only). See `../batatis-ui-opus/SKILL.md`.

References: `../../../docs/design/linear-reference/`  
Tokens: `../../../docs/design/tokens.css`  
Doc: `../../../docs/design-system-linear.md`  
Shared gaps: `../../../evals/ui-artifacts/shared-gaps.js`  
Smoke: `../../../evals/ui-artifacts/smoke.mjs` · Captures: `../../../evals/ui-artifacts/screenshots.mjs`

## Opus P0 (must not fail)

| # | Rule |
| --- | --- |
| 1 | **Neutral primary CTAs** — `.btn-primary` = light grey fill `#E6E6E6` + dark text (`--btn-primary-*`). **Never** indigo/purple/violet filled buttons (incl. `#5e6ad2`). |
| 2 | **Active nav** = `--bg-active` faint fill `rgba(255,255,255,0.05–0.07)` + full-strength text. **No** border, ring, glow, coloured outline. |
| 3 | **One shared gap source** — `shared-gaps.js` (or equivalent). Same blocking list on intake banner, SCO gaps, export gate. |
| 4 | **Gating** — disable (or confirm-with-gap-list) complete / download / admin-complete while blocking gaps remain (`data-requires-no-blocking-gaps`). |
| 5 | **No demo/template leakage** — no “demo” rows; no bracket placeholders (`[linked excerpt]`); no status words standing in for values (`present`, `from registry`). Render the real value or `—` + gap. |
| 6 | **Styled controls** — custom select, 14px thin-border checkbox (neutral checked), `resize: none` on textareas. No browser-default chrome. |
| 7 | **Labels never wrap, rows never clip** — `.btn` is `white-space: nowrap`; `.btn-row` uses `flex-wrap: wrap` (never `overflow-x` scroll that hides a button). Shorten labels for narrow detail panes. |
| 8 | **One data model, derived everywhere** — fields, article status, Section C and Section D live in one state object; gaps, counts, summaries and previews are computed from it and recompute on input. Preview text must equal the table values. Gates name the unconfirmed articles. |
| 9 | **Every control works** — nav items are links; Back/Continue navigate; each action changes visible state (saved note, dialog, status, download). No inert buttons, no `href="#"`, no native `alert()` — use a styled `<dialog>`. Disabled controls show their reason inline. |
| 10 | **No silent defaults** — unanswered selects start at "Select…" with empty styling; prefilled values carry a marker (inferred, defaulted) and a way to confirm. |
| 11 | **Panes scroll, the page does not** — fixed-height shell; list, detail and preview panes own their overflow. |

`--focus-ring` / `--accent` (`#5e6ad2`) = **focus rings only** (and optional sparse status). Not CTA identity, not active nav.

## Visual language

| Pillar | Rule |
| --- | --- |
| Surfaces | Charcoal layers; depth from value shifts |
| Borders | 1px low-contrast |
| Type | Inter-like sans; labels ≥11px, secondary ≥ readable contrast |
| Grid | 8px; form rows ~32px; inputs ≤36px; prefer 2-col property grids |
| Color | Status dots only for meaning: blocking=red, warning=amber, pending=grey, done=green. Colour on the **dot**, not spam-coloured text |
| Lookup / source | Neutral `.label-pill` (thin border, muted text) — not green text |
| Layout | Sidebar + main; list+detail for review |
| Icons | Thin-stroke nav icons |
| Code vs AI | `.cite-block` (no leading indent dump) ≠ `.ai-explain` |
| PDF preview | Light sheet (`--pdf-sheet-bg`) — do not imply the PDF is charcoal |

## Status map (single)

`blocking` → `--status-blocking` · `warning` → `--status-warning` · `pending` → `--status-pending` · `done` → `--status-done`

## Anti-patterns (material fail)

- Indigo/purple **filled** primary buttons or active-nav rings
- Composer “PASS” treated as formal seal
- Divergent gap lists across intake / SCO / export
- Live demo rows; browser-default checkbox/select; wrapping button labels; clipped buttons in narrow panes
- `[placeholder]` strings or `present` / `from registry` instead of real values in previews
- Mark admin-complete / Download enabled while blocking gaps open
- Inert nav/footer controls, `alert()`, selects defaulting silently, gap lists typed by hand instead of derived
- Green “lookup” text spam; disc bullets; missing status dots on queue rows

## Implementation checklist

1. Load `docs/design/tokens.css`.
2. Neutral `.btn-primary`; ≤1 primary CTA per viewport footer.
3. Active nav = faint fill only.
4. Wire `shared-gaps.js` (or one source) on intake + SCO + export; cross-check before ship.
5. Gate complete/download/admin-complete on blocking gaps.
6. Styled checkbox/select/textarea; nowrap labels in wrapping rows (nothing clipped); thin-stroke icons.
7. Status dots from the single map; lookup = neutral pills.
8. Required empties: `.field.is-empty` + status dot (not placeholder-only).
9. Run `node evals/ui-artifacts/smoke.mjs` (chrome, clipping, leakage, every control, cross-screen happy path), then `screenshots.mjs`.
10. Opus 5.5 re-seal against `evals/battle-prompts/ui-blind/README.md`.
