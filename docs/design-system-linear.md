# Batatis design system (Linear-default)

Default product look for all Batatis UI. Agents apply this **without** being asked to “make it Linear.”

**Formal UI seal = Opus 5.5.** Composer reviews are provisional.

| Resource | Path |
| --- | --- |
| Tokens | [`docs/design/tokens.css`](./design/tokens.css) |
| References | [`docs/design/linear-reference/`](./design/linear-reference/) |
| Skill | [`.cursor/skills/batatis-ui-linear/SKILL.md`](../.cursor/skills/batatis-ui-linear/SKILL.md) |
| Shared gaps | [`evals/ui-artifacts/shared-gaps.js`](../evals/ui-artifacts/shared-gaps.js) |
| Smoke | [`evals/ui-artifacts/smoke.mjs`](../evals/ui-artifacts/smoke.mjs) |
| Captures | [`evals/ui-artifacts/screenshots.mjs`](../evals/ui-artifacts/screenshots.mjs) |

## Opus P0 (blocking)

1. **Primary CTA = neutral** — `#E6E6E6` fill + dark text. Not indigo/purple filled buttons.
2. **Active nav = faint fill** — `rgba(255,255,255,~0.06)`; no accent ring/glow.
3. **One gap source** across intake / SCO / export.
4. **Gate** complete/download/admin-complete while blocking gaps remain.
5. **No demo/template leakage** — no `[bracket]` placeholders, no `present` / `from registry` in place of real values.
6. **Styled** select / checkbox / textarea (no browser defaults; no resize handle). Checkbox = 14px square, hairline, checked `#E6E6E6` + dark check.
7. **Buttons** `white-space: nowrap`; `.btn-row` wraps (never clips via `overflow-x`).
8. **Previews equal sources** — PDF / SCO values come from the same objects as the Section C table; gates name unconfirmed articles.
9. **Every control works** — nav = links, actions change visible state, styled `<dialog>` not `alert()`, disabled reasons inline.
10. **No silent defaults** — unanswered selects start empty; prefilled values are marked.
11. **Panes scroll, not the page.**
12. **No "Required" without a gap** — required-but-missing items are shared gaps (warning minimum); status cells are pills with dots.

`--focus-ring: #8a8a8e` (neutral grey) is for **focus only**, not button identity. Never indigo/`#5E6AD2`.

## Token map

| Role | Token | Value |
| --- | --- | --- |
| App bg | `--bg-app` | `#080808` |
| Active nav | `--bg-active` | `rgba(255,255,255,0.06)` |
| Primary CTA | `--btn-primary-bg` / `--btn-primary-text` | `#e6e6e6` / `#141415` |
| Focus | `--focus-ring` | `#8a8a8e` (neutral rings only) |
| Blocking / warn / pending / done | `--status-*` | red / amber / grey / green |
| PDF sheet | `--pdf-sheet-bg` | `#f4f4f5` (light) |

## Blind UI evals

`evals/battle-prompts/ui-blind/` · artifacts `evals/ui-artifacts/`.
