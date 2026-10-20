# Cross-judge verdict

Reviewer: `grok-4.7-high-fast` (arena cross-judge pool). Opus 5.5 was unavailable, so this is not an Opus seal and not an env battle-test pass.

**Base: candidate A (token-map kit).** Totals: A 12 / B 9.

## Scores

| # | Criterion | A | B |
| --- | --- | ---: | ---: |
| 1 | Honors how constraints | 2 | 1 |
| 2 | Interface depth (`@/components/ui/*`, almost no extra API) | 2 | 2 |
| 3 | Color survives `shadcn add --overwrite`; geometry has a clear story | 2 | 1 |
| 4 | Verification lever that proves `apps/web` | 2 | 1 |
| 5 | Smallest safe surface (no parallel component forest) | 2 | 2 |
| 6 | Distinct organizing structure | 2 | 2 |
| | **Total** | **12** | **9** |

## Why A is the base

A’s core is one binding table in `apps/web/app/globals.css`: invariant rows once on `:root`, surface rows twice with the same keys, Linear names as comments. Callers keep importing `@/components/ui/*`. A PDF island is `className="light"`. The dark variant excludes that island, so `dark:` utilities do not paint over the sheet. `forcedTheme="dark"` plus deletion of the `d` hotkey matches the current `theme-provider.tsx` (`defaultTheme="system"`, `ThemeHotkey`) and keeps a stored preference from flipping product chrome.

The patch manifest’s needles match the installed files: `hover:bg-primary/80` on button and badge, the bubble default-variant hover string, checkbox `size-4 shrink-0` / `[&>svg]:size-3.5` / existing `rounded-[4px]`, and `SIDEBAR_WIDTH = "16rem"`. Apply is fail-closed and idempotent (a `find` that is a prefix of `replace` is illegal). After overwrite, color stays in the table; geometry is re-applied. Proof is Playwright on `/gallery` against computed `--primary` `#e6e6e6`, hover `#f2f2f2`, 14×14 checkbox, `resize: none`, active-nav wash, sheet vs shell backgrounds, and no loaded `tokens.css`.

B is a real alternative shape (shared Linear-named variables + a shadcn bridge), not a copy of A. It is the wrong base because the written bridge is incomplete, the geometry recipe is not idempotent, and the apps/web check never reads computed style.

## Grafts to take from B

1. **One palette file that eval CSS imports.** A leaves `#e6e6e6` and the rest of the charcoal hexes in both `globals.css` and `docs/design/tokens.css`. Take B’s import direction: a variables file owns those values; `tokens.css` imports it and keeps `.btn`, Google Fonts, and the eval-only alias `--accent: var(--focus-ring)` after the import. The app still must not `@import` `tokens.css`. A’s marked blocks stay the shadcn map (`--accent` = wash, `--ring` = `#8a8a8e`). Do not adopt B’s second provider or the ellipsis bridge.

2. **Literal 14px checkbox face.** B’s `size-[14px]` is the grounding size even if the root font size changes. A’s `size-3.5` is 14px only at a 16px root. Keep A’s specific icon needle (`[&>svg]:size-3.5` → a 10px icon); do not take B’s bare `from: "size-3.5"`.

## Red flags

### Candidate A (base)

- **Split ownership of hex.** The binding table and `docs/design/tokens.css` both store the same palette. Graft 1 is the fix. A’s assert sentinels cover the app file only.
- **Small caller leak, sealed internals.** PDF previews must know `className="light"`. The patch manifest is eslint-banned from `app/**` and `components/**`. Linear names are comments. There is no wrapper and no second button component.
- **Sharp edge, already named.** Any `.light` subtree drops every `dark:` utility. The gallery outline button is the check for that.
- Bubble’s `tinted` variant still runs `oklch(from var(--primary) …)`. A leaves that as an open question; the default-variant `primary/80` needle is the one that matches `bubble.tsx` today.

### Candidate B

- **Pass-through.** `LinearThemeProvider` is specified as `{...LINEAR_THEME_DEFAULTS} {...props}`. `lib/linear/theme-defaults.ts` only re-exports the recipe. `forcedTheme` stays on the public props, so a layout can still force a light shell.
- **Split ownership.** The bridge writes a raw light `--accent: rgba(0, 0, 0, 0.04)` while the invariant says hex lives only in `variables.css`. `@layer base` keeps a textarea `resize-none` “safety net” beside the class patch. `--sidebar-width: 244px` is never applied; `sidebar.tsx` still sets `--sidebar-width` from `SIDEBAR_WIDTH = "16rem"`. `badge.tsx` still has `[a]:hover:bg-primary/80`, outside the recipe. The existing `components/theme-provider.tsx` is not retired.
- **Information leakage.** Patched classes call `var(--btn-primary-hover)`, so Linear names enter shadcn files. `@batatis/design-tokens/patch-recipe` is a workspace export with no import ban.
- **Shallow module.** The provider adds no behavior beyond the spread. The check script greps source strings. `variables.css` is the `:root` block of `tokens.css` plus radius and an unused width. The bridge uses an ellipsis for the rest of the shadcn map.
- **Geometry story does not hold.** Textarea `from` is a prefix of `to`, so the second apply still sees `from`. Checkbox `from: "size-3.5"` is a TODO. `applyGeometryPatches` returns `missingFrom` for a human instead of failing closed. Sidebar “no ring/border” is implemented by appending `shadow-none` and `border-transparent` on a string that already has neither `data-active:ring` nor `data-active:border`.

## Distinctness

These are different owners, not two layouts of one kit. A writes hex onto shadcn variables and treats Linear names as comments. B writes hex onto Linear variables and makes `globals.css` a rename bridge that eval CSS also reads. Keep A’s table, parser, fail-closed apply, in-place theme provider, and computed `/gallery` proof. Add B’s shared palette file and the literal 14px size.
