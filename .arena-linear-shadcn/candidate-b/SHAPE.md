# Shape — shared variables package + thin Linear adapters

Derived from [USAGE.md](./USAGE.md). Usage is the spec; types serve it.

## Module map

```
packages/design-tokens/          ← hex + geometry recipe (one owner each)
  package.json                   # "@batatis/design-tokens"
  variables.css                  # Linear-domain custom properties ONLY
  patch-recipe.ts                # typed GeometryPatch[] + ThemeDefaults
  exports: "./variables.css", "./patch-recipe"

docs/design/tokens.css           ← eval chrome (classes, fonts, resets)
  @import "../../packages/design-tokens/variables.css";
  /* .btn, checkbox, layout — references vars; no raw hex for shared palette */

apps/web/
  app/globals.css                ← thin bridge: vars → shadcn semantics + @theme
  lib/linear/
    apply-patches.ts             ← idempotent class rewriter (CLI / script)
    theme-defaults.ts            ← re-export ThemeDefaults for provider
  components/linear/
    theme-provider.tsx           ← LinearThemeProvider (dark default policy)
  components/ui/*                ← stock shadcn; only recipe targets get class edits
  app/(dev)/gallery/page.tsx     ← verification lever for apps/web look
  scripts/check-linear-theme.mjs ← assert bridge + recipe targets present
```

Ownership (single writer per invariant):

| Invariant | Owner | Readers |
|-----------|--------|---------|
| Hex / rgba palette | `variables.css` | `tokens.css`, `globals.css` bridge |
| Linear → shadcn name map | `globals.css` bridge only | Tailwind `@theme`, all ui/* |
| Geometry class patches | `patch-recipe.ts` | `apply-patches`, hand edits, check script |
| Product dark default | `ThemeDefaults` → `LinearThemeProvider` | `app/layout.tsx` |
| Eval chrome classes | `tokens.css` | HTML evals only |

## Data structures first

```ts
// packages/design-tokens/patch-recipe.ts

/** Absolute hex/rgba never appear here — only CSS var names or Tailwind class tokens. */
export type CssVarName = `--${string}`

/**
 * One atomic, idempotent edit to a generated ui file.
 * find/replace must be exact class substrings so re-run is a no-op when already applied.
 */
export type GeometryPatch = {
  /** Path relative to apps/web/components/ui */
  file: "button.tsx" | "checkbox.tsx" | "textarea.tsx" | "sidebar.tsx"
  /** Human-readable; check script prints this on failure */
  intent: string
  /** Substring that must disappear (stock shadcn) */
  from: string
  /** Replacement that encodes Linear geometry */
  to: string
}

export type ThemeDefaults = {
  readonly attribute: "class"
  readonly defaultTheme: "dark"
  readonly enableSystem: false
  readonly disableTransitionOnChange: true
}

/** Product chrome policy — light is PDF-sheet routes only, not next-themes "system". */
export const LINEAR_THEME_DEFAULTS: ThemeDefaults = {
  attribute: "class",
  defaultTheme: "dark",
  enableSystem: false,
  disableTransitionOnChange: true,
}

/**
 * Minimum class-patch list from grounding.
 * Hex for hover lives in variables.css as --btn-primary-hover;
 * class strings reference arbitrary values via that var when possible,
 * else the documented Linear class token (hover:bg-[#F2F2F2] only if
 * Tailwind cannot resolve the CSS var in that position — prefer var).
 */
export const LINEAR_GEOMETRY_PATCHES: readonly GeometryPatch[] = [
  {
    file: "button.tsx",
    intent: "primary hover = Linear lift, not primary/80",
    from: "hover:bg-primary/80",
    to: "hover:bg-[var(--btn-primary-hover)]",
  },
  {
    file: "checkbox.tsx",
    intent: "14px square control (not size-4 / 16px)",
    from: "size-4 shrink-0",
    to: "size-[14px] shrink-0",
  },
  {
    file: "checkbox.tsx",
    intent: "smaller check icon inside 14px face",
    from: "size-3.5", // confirm stock indicator class at implement time
    to: "size-2.5",
  },
  {
    file: "textarea.tsx",
    intent: "no resize handles — ensure resize-none on root className",
    from: "flex field-sizing-content min-h-16", // stock prefix; append if absent
    to: "flex field-sizing-content min-h-16 resize-none",
  },
  {
    file: "sidebar.tsx",
    intent: "active nav = sidebar-accent wash only; no ring/border",
    from: "data-active:bg-sidebar-accent data-active:font-medium data-active:text-sidebar-accent-foreground",
    to: "data-active:bg-sidebar-accent data-active:font-medium data-active:text-sidebar-accent-foreground data-active:shadow-none data-active:border-transparent",
  },
]
// TODO: lock `from` strings against the installed radix-nova files at implement time.
// Optional assert-only entries (no rewrite) belong in check-linear-theme.mjs, not here.
```

```ts
// apps/web/lib/linear/apply-patches.ts

export type ApplyPatchesInput = {
  root: string
  patches: readonly GeometryPatch[]
}

export type ApplyPatchesResult = {
  applied: GeometryPatch[]
  alreadyPresent: GeometryPatch[]
  missingFrom: GeometryPatch[] // stock substring not found — needs human
}

/** Idempotent: if `to` already present and `from` absent → alreadyPresent. */
export async function applyGeometryPatches(
  input: ApplyPatchesInput,
): Promise<ApplyPatchesResult> {
  throw new Error("not implemented")
}
```

```ts
// apps/web/components/linear/theme-provider.tsx

import { LINEAR_THEME_DEFAULTS } from "@batatis/design-tokens/patch-recipe"
// thin shell: spreads defaults; allows override only for forceTheme on PDF routes

export function LinearThemeProvider(
  props: Omit<
    React.ComponentProps<typeof NextThemesProvider>,
    keyof ThemeDefaults
  > &
    Partial<ThemeDefaults>,
): React.JSX.Element {
  throw new Error("not implemented")
  // TODO: <NextThemesProvider {...LINEAR_THEME_DEFAULTS} {...props} />
}
```

## Variables file (structure only — no second hex copy)

```css
/* packages/design-tokens/variables.css */
:root {
  /* Surfaces */
  --bg-app: #080808;
  --bg-sidebar: #0c0c0d;
  --bg-panel: #131315;
  --bg-elevated: #19191b;
  --bg-hover: rgba(255, 255, 255, 0.04);
  --bg-active: rgba(255, 255, 255, 0.06);
  --bg-input: #121214;

  /* Borders / focus */
  --border-default: rgba(255, 255, 255, 0.1);
  --border-subtle: rgba(255, 255, 255, 0.06);
  --border-strong: rgba(255, 255, 255, 0.16);
  --focus-ring: #8a8a8e;
  /* NOTE: do NOT export a Linear --accent that means focus-ring.
     Eval tokens.css may keep --accent: var(--focus-ring) as a local alias
     AFTER import, for backward-compatible HTML. App bridge never reads it. */

  /* Text */
  --text-primary: #eeeeef;
  --text-secondary: #9b9ba1;
  --text-inverse: #141415;

  /* Primary CTA */
  --btn-primary-bg: #e6e6e6;
  --btn-primary-text: #141415;
  --btn-primary-hover: #f2f2f2;

  /* Status */
  --status-blocking: #eb5757;
  --status-warning: #f2c94c;
  --status-pending: #8a8a8e;
  --status-done: #4cb782;

  --radius-control: 0.375rem; /* 6px */
  --sidebar-width: 244px;

  /* PDF sheet (light) — consumed by :root light bridge only */
  --pdf-sheet-bg: #f4f4f5;
  --pdf-sheet-text: #1a1a1c;
  --pdf-sheet-muted: #5c5c62;
}
```

## Bridge (`globals.css`) — maps names; does not invent palette

```css
@import "tailwindcss";
@import "tw-animate-css";
@import "shadcn/tailwind.css";
@import "@batatis/design-tokens/variables.css"; /* or relative path */

@theme inline { /* existing --color-* → var(--*) wiring stays */ }

/* Light = PDF sheet only */
:root {
  --background: var(--pdf-sheet-bg);
  --foreground: var(--pdf-sheet-text);
  --primary: var(--btn-primary-bg);
  --primary-foreground: var(--btn-primary-text);
  --ring: var(--focus-ring);
  --accent: rgba(0, 0, 0, 0.04); /* wash, NOT focus-ring */
  --radius: var(--radius-control);
  /* … remaining shadcn semantics → Linear or PDF vars … */
}

.dark {
  --background: var(--bg-app);
  --foreground: var(--text-primary);
  --card: var(--bg-panel);
  --popover: var(--bg-elevated);
  --primary: var(--btn-primary-bg);
  --primary-foreground: var(--btn-primary-text);
  --muted: var(--bg-hover);
  --muted-foreground: var(--text-secondary);
  --accent: var(--bg-active);          /* wash — deliberate collision avoid */
  --accent-foreground: var(--text-primary);
  --destructive: var(--status-blocking);
  --border: var(--border-default);
  --input: var(--bg-input);
  --ring: var(--focus-ring);
  --sidebar: var(--bg-sidebar);
  --sidebar-accent: var(--bg-active);
  --sidebar-border: var(--border-subtle);
  --sidebar-ring: var(--focus-ring);
  --radius: var(--radius-control);
}

@layer base {
  /* focus-visible → var(--ring); textarea resize-none as safety net */
}

/* DELETE current @layer components hex/size overrides once class patches land.
   Bridge must not be a second geometry owner. */
```

## Data flow

```
variables.css (hex)
    ├─► tokens.css (eval classes use var(--btn-primary-bg) etc.)
    └─► globals.css bridge (shadcn --primary := var(--btn-primary-bg))
            └─► Tailwind utilities on components/ui/*

patch-recipe.ts (geometry policy)
    ├─► applyGeometryPatches (after shadcn overwrite)
    ├─► check-linear-theme.mjs (CI / local assert)
    └─► LinearThemeProvider (dark default)
```

Call chain for a screen author: `page → ui/Button → CSS vars`. ≤3 files. Patch authors: `patch-recipe → apply-patches → ui file`.

## Public surface (what callers import)

Deep for feature authors:

- `@/components/ui/*` — unchanged shadcn API
- `@/components/linear/theme-provider` — one provider with dark baked in

Narrow for maintainers (not feature code):

- `@batatis/design-tokens/patch-recipe` — recipe + ThemeDefaults
- `@/lib/linear/apply-patches` — regenerate helper

Not public: raw hex maps in TS, bridge internals, eval class names.

## Invariants encoded in types / structure

1. Hex appears only in `variables.css` (structure encodes “one list”; check script fails if `globals.css` matches `/#[0-9a-f]{3,8}/` outside comments for palette keys — optional hard gate).
2. `ThemeDefaults.defaultTheme` is literally `"dark"` — cannot pass `"system"` without widening the type at the call site (Partial override is explicit).
3. `GeometryPatch.file` is a closed union of recipe targets — agents cannot invent a 64th file without extending the type.
4. `applyGeometryPatches` is idempotent — second run does not double-patch.
5. shadcn `--accent` never aliases Linear focus `--accent`; bridge uses `--bg-active`.

## Deliberately does not do

- No parallel `components/linear/button.tsx` wrapping forest.
- No `@import` of eval chrome into the app.
- No rewriting all 63 components.
- No treating `@layer components` as the geometry SoT (grounding: utilities win).
- No npm publish / complex build for the package — CSS + TS source exports only.

## Verification lever

1. `apps/web` build succeeds.
2. `app/(dev)/gallery/page.tsx` renders Button (default), Checkbox, Textarea, SidebarMenuButton active — visual/ coarser: Playwright or a small `scripts/check-linear-theme.mjs` that:
   - asserts `globals.css` imports variables and maps `--primary` → `var(--btn-primary-bg)`;
   - asserts each `LINEAR_GEOMETRY_PATCHES[].to` appears in the target file;
   - fails if stock `from` still present without `to`.
3. HTML evals keep `evals/ui-artifacts/smoke.mjs` (unchanged path: `tokens.css`).

## Package wiring (minimal)

No turbo required day one. `apps/web/package.json`:

```json
"dependencies": {
  "@batatis/design-tokens": "file:../../packages/design-tokens"
}
```

`packages/design-tokens/package.json` exports:

```json
{
  "name": "@batatis/design-tokens",
  "exports": {
    "./variables.css": "./variables.css",
    "./patch-recipe": "./patch-recipe.ts"
  }
}
```

If `file:` + TS export is awkward for the eval HTML tree, evals keep relative `@import` of the same `variables.css` path — one file on disk either way.
