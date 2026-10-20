# Synthesis — Linear shadcn theme

## Base

**candidate-a (token-map kit).** Cross-judge [Arena cross-judge theme sketches](ffd9b976-a080-46dc-ad12-3541fbf1c681): A 12 / B 9. Parent agree.

Callers keep `@/components/ui/*`. Colors live in marked binding blocks in `apps/web/app/globals.css`. Geometry is an idempotent patch script. Product chrome uses `forcedTheme="dark"`. PDF islands use `className="light"` with a dark-variant exclusion. Proof is `/gallery` plus computed-style assert.

## Grafts from candidate-b

1. Extract shared palette hex into `packages/design-tokens/variables.css` (or `docs/design/variables.css`). `docs/design/tokens.css` imports it for evals. App binding table either duplicates via comments pointing at that file for now, or `@import`s variables and maps into shadcn names without importing eval chrome. Keep eval `--accent: var(--focus-ring)` only inside `tokens.css`.
2. Checkbox face uses `size-[14px]` (literal), not only `size-3.5`. Keep A’s icon needle specificity.

## Rejected from B

- `LinearThemeProvider` as required feature import (use forced dark on existing ThemeProvider).
- Bridge that leaves Linear names in component class strings (`var(--btn-primary-hover)` in ui files). Prefer `--primary-hover` on the shadcn table + `@theme`.
- Incomplete / non-idempotent textarea replace shape.
- Source-grep-only check (must read computed style on gallery).

## Next implementation step

Rewrite binding blocks in `globals.css`, force dark, apply geometry patches, add gallery + assert lever, extract shared variables file for evals.
