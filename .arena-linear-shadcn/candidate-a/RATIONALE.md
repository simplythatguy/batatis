# Rationale

Candidate runner: grok-4.7-high-fast. Opus was unavailable.

## Problem

Batatis product UI is a generated shadcn tree (`radix-nova`, CSS variables, `apps/web/app/globals.css`) that should look like the Linear charcoal system: neutral primary `#e6e6e6`, focus ring `#8a8a8e`, faint active wash, 14px checkbox, dark product chrome, light PDF sheet. `docs/design/tokens.css` cannot be imported. It is the HTML-eval sheet: it loads Google Fonts, styles `.btn` and native controls, and sets `--accent` to the focus ring. shadcn already uses `--accent` as the hover wash. About 63 components under `components/ui/` consume semantic variables, and `shadcn add --overwrite` rewrites their class strings. `@layer components` rules in the current `globals.css` lose to utilities such as `hover:bg-primary/80` and `size-4`, so the hover and checkbox rules already in that file do not paint. `smoke.mjs` covers HTML evals only. The app needs its own proof.

## Usage (caller's view)

Full quickstart: `USAGE.md`.

Product code imports `@/components/ui/*` and stops. A Continue button is `<Button type="submit">Continue</Button>` from `@/components/ui/button`. A checklist row is `<Checkbox checked onCheckedChange />` from `@/components/ui/checkbox` with no size prop. A PDF preview is `<section className="light">` around the same `Button`. Theme authors change a color in the binding table, change geometry in `scripts/linear-patches.mjs`, run `apply-linear-patches.mjs`, and run `assert-linear-theme.mjs` against `/gallery`.

## Shape

The binding table in `globals.css` is the core structure. Invariant rows (`--primary`, `--primary-hover`, `--ring`, status, radius) are declared once on `:root`. Surface rows are declared twice, under `:root, .light` and under `.dark`, with the same property names. Aliases such as `--sidebar-primary: var(--primary)` point back into the table. `@theme inline` only adds `--color-*: var(--*)` lines so utilities can see new rows (`primary-hover`, `border-strong`).

The `dark` variant becomes `&:is(.dark *):not(:is(.light, .light *))`. Otherwise a PDF island inside `html.dark` still matches every `dark:` utility and the light column of the table never reaches those controls. `ThemeProvider` uses `forcedTheme="dark"` and drops the `d` hotkey, so a stored preference cannot swap product chrome onto the sheet palette.

Geometry that a utility already sets is a replace row in the patch manifest: button, badge, and bubble `primary/80` become `primary-hover`; checkbox `size-4` becomes `size-3.5` (14px) and the check icon becomes `size-2.5`; textarea gains `resize-none`; sidebar width becomes `244px`. Guards keep `rounded-[4px]` and `data-active:bg-sidebar-accent`, and reject `data-active:ring` / `data-active:border`. Apply is idempotent: a second run no-ops; a missing needle or a file that contains both strings throws. The `@layer components` block is deleted so it cannot disagree with the utilities (`per` two-ways).

`assertTheme` parses the marked blocks (key parity, sentinel text, no `tokens.css` import, no indigo literal, no remaining `bg-primary/80`) and, given `GALLERY_URL`, reads computed style on `/gallery` through Playwright. Sentinels in the script are the oracle for four colors. The rest of the palette is not copied into the script (`per` hand-synced list). Validation is that script; render code trusts the variables (`per boundary-discipline`).

Public surface for product callers: existing component exports, plus `className="light"` on a sheet. Hidden: the accent/ring collision, the cascade, the CLI merge, the two palettes (`per` interface depth). The manifest is an authoring input under `scripts/`, eslint-banned from app code.

## Synthesis decision

Filled by arena.

## Tradeoffs accepted

- We accept a re-apply step after `shadcn add --overwrite` in exchange for product imports that stay `@/components/ui/*`.
- We accept a short sentinel list in the assert script (`--primary`, `--primary-hover`, `--ring`, both accent washes, and the forbidden indigo literal) in exchange for not mirroring the whole palette.
- We accept Geist, already loaded by `next/font`, in exchange for leaving the tokens.css font import out of the app.
- We accept `Button`'s existing `rounded-lg` (~8px from the radius scale) in exchange for a patch list that only touches geometry the utilities get wrong today.
- We accept removing the `d` theme hotkey in exchange for product chrome that stays dark.
- We accept badge and bubble in the same hover patch as `Button` in exchange for one `--primary-hover` row. A `primary/80` left behind would paint a different grey on the same token.
- We accept chart literals that match some status hexes in exchange for keeping chart roles off the status map.
- We accept a Playwright devDependency in exchange for a computed check the HTML smoke script cannot make.

## Alternatives considered

- **Unlayered `[data-slot]` overrides in `globals.css`.** They would beat utilities, so the current `@layer components` attempt almost worked. The component file would still say `hover:bg-primary/80` and `size-4`. An agent editing `button.tsx` follows that string. Callers of the CSS file and callers of the component learn two mechanisms for one paint. Rejected. The class string an agent opens is the geometry spec; the table is the color spec.
- **`@import` `docs/design/tokens.css` and alias `--primary: var(--btn-primary-bg)`.** One line hides the hex, and it also pulls eval chrome, Google Fonts, and `--accent: var(--focus-ring)` into the Next app. shadcn `--accent` would become the ring. The collision is the bug this table exists to prevent. Rejected.
- **A TypeScript object that emits `globals.css`.** `SurfaceVar` as a mapped type would make key parity unrepresentable to violate. It also makes a generator the second writer of the file `components.json` already points at. Rejected. The CSS blocks are the table; the parser fails the build when the two surface key sets diverge.
- **Wrapper components around `Button` and `Checkbox`.** A wrapper can hide hover and size, and every screen must remember to import it while `@/components/ui/button` still compiles. That is a shallow module: the policy leaks into the import choice, and the short path skips it. Rejected.

## Open questions and risks

- Should the default `Button` move from `rounded-lg` (~8px) to `rounded-md` (6px, `--radius`)?
- The bubble `tinted` variant runs `oklch(from var(--primary) …)` on a neutral grey. Is that variant on a product surface, and should it stay?
- After the checkbox border patch, `group-has-[:focus-visible]/field-label:not-data-checked:border-input` still names `border-input`. Does that field-label state need `border-border-strong` too?
- Does the narrowed `dark` variant selector change specificity enough to disturb `dark:` utilities outside `.light`? The gallery outline button inside the sheet is the check; a product page that nests `.light` for any other reason would opt out of `dark:` as well.
- `shadcn add` might later rewrite `@theme inline` or the top of `globals.css`. The parser fails closed if a color row loses its alias or if hex shows up inside `@theme`. Is that failure enough, or does the table need a second file the CLI does not touch?

## Next implementation step

Rewrite the three marked blocks in `apps/web/app/globals.css`, point the `dark` variant at the `.light` exclusion, delete the `@layer components` overrides and the base `textarea` resize rule, then add `linear-patches.mjs` and run apply once.
