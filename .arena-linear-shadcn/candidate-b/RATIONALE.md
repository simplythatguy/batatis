# Rationale — shared variables package + thin Linear adapters

## Problem

Batatis needs one Linear charcoal look across HTML evals (`docs/design/tokens.css` + class chrome) and the Next/shadcn app (`apps/web/app/globals.css` + ~63 generated components). Today hex and geometry policy are duplicated: palette comments in `globals.css`, the same values in `tokens.css`, and fragile `@layer components` overrides that lose to Tailwind utilities (`hover:bg-primary/80`, `size-4`). Grounding forbids importing eval chrome into the app, forbids indigo, requires `--accent` = faint wash (not the eval focus-ring alias), and requires dark as the product default. Color mapping survives `shadcn add --overwrite`; class geometry does not. The non-obvious part is giving both surfaces one hex owner and one geometry owner without standing up a second component library or hand-editing every ui file.

## Usage (caller's view)

See [USAGE.md](./USAGE.md). Feature authors import `@/components/ui/*` plus `LinearThemeProvider`. Maintainers re-apply geometry from `@batatis/design-tokens/patch-recipe` after overwrite. Eval authors keep linking `tokens.css`.

## Shape

See [SHAPE.md](./SHAPE.md).

Load-bearing decisions:

1. **Split knowledge, not pipeline stages.** Variables (palette) and patch-recipe (geometry) are two domain owners inside one package. The app bridge only renames Linear → shadcn. Eval `tokens.css` only adds chrome. Per encode-lessons-in-structure / single source of truth: hex is not copied into TS or into the bridge.
2. **Bridge is a map, not a second palette.** `globals.css` sets `--primary: var(--btn-primary-bg)` etc. Deliberate non-map: shadcn `--accent` ← `--bg-active`, never the eval `--accent` focus alias.
3. **Geometry policy is a typed recipe + idempotent applier**, not `@layer` hope. Closed `GeometryPatch["file"]` union keeps the patch surface small (button, checkbox, textarea, sidebar). Per boundary-discipline: validate/apply at the regenerate boundary; trust components afterward.
4. **Interface depth for feature callers is maximal:** zero Linear API beyond the theme provider. Complexity (hex ownership, accent collision, overwrite recovery) hides behind the package + adapter. Maintainers get a small explicit recipe surface — that is the trade for surviving shadcn regeneration without a wrapper forest.
5. **Delete competing geometry writers.** Once class patches land, remove hex/size rules from `@layer components` so there is one way to do primary hover and checkbox size (red-flag: two ways / split ownership).

Red-flag screen: not a shallow “edit globals only” module; not pass-through re-exports without dark-default policy; internals (`variables.css` hex, bridge maps) are not the feature import path; no hand-synced hex lists across three files.

## Synthesis decision

*Filled in by arena after comparing candidates.*

## Tradeoffs accepted

- We accept a tiny `file:` package (or path-imported CSS) in exchange for a real single owner of hex that both eval and app can consume without `@import tokens.css`.
- We accept a closed list of class patches (and occasional re-apply after overwrite) in exchange for not forking ~63 components.
- We accept that `@layer components` cannot be the geometry SoT (utilities win) in exchange for an honest regenerate story via `applyGeometryPatches`.
- We accept `enableSystem: false` on product chrome in exchange for never accidentally shipping “system light” as the app shell (light remains PDF-sheet `:root`).
- We accept a maintainer-facing recipe API in exchange for keeping the feature-author API as stock shadcn.

## Alternatives considered

1. **Just edit `globals.css` (map hex + `@layer` overrides).** Hides nothing durable: overwrite restores `primary/80` / `size-4`; hex still duplicated with `tokens.css`; `@layer` loses to utilities. Exposes callers to “why doesn’t my checkbox shrink?” with no owner. Rejected for split ownership and two ways.
2. **Fork / wrap all ui components under `components/linear/*`.** Deep for theming control, but a parallel forest: large public surface, every `shadcn add` becomes a merge tax, agents copy whichever tree they open first. Rejected for interface width and two ways.
3. **CSS-only shared file with no typed recipe.** Solves hex ownership but leaves geometry as folklore in chat/docs; agents re-invent patches after overwrite. Rejected for hand-synced list / information leakage of geometry policy.

## Open questions and risks

- Should `@batatis/design-tokens` be a real workspace package now, or is path `@import` of `packages/design-tokens/variables.css` enough until a second app appears?
- For primary hover, can Tailwind reliably use `hover:bg-[var(--btn-primary-hover)]` everywhere, or do we need a one-line `@theme` color token (`--color-primary-hover`) so the recipe never embeds hex?
- Checkbox indicator SVG size: exact stock class string in radix-nova may differ — confirm at implement time before freezing `from`/`to`.
- Is a gallery route under `app/(dev)/` acceptable for the apps/web verification lever, or should the check be headless-only (`check-linear-theme.mjs`)?
- When PDF sheet needs light, do we force `theme="light"` on that route only, or a separate layout without `LinearThemeProvider`?

## Next implementation step

Extract `packages/design-tokens/variables.css` from the shared palette in `docs/design/tokens.css`, point both `tokens.css` and `apps/web/app/globals.css` at it with the shadcn bridge maps, and add `patch-recipe.ts` plus `LinearThemeProvider` with `defaultTheme: "dark"`.
