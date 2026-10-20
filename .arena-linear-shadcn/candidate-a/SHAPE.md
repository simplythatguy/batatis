# Shape — token-map kit

The core structure is the **binding table**: three marked blocks in `apps/web/app/globals.css`. One row is one shadcn custom property. Hex and `rgba` are written there and nowhere else. Linear names (`--bg-app`, `--btn-primary-bg`, `--focus-ring`, `--accent` as a ring) are comments on a row. They are not custom properties in this file.

A **patch manifest** is the only other spec. It holds class-string edits for geometry Tailwind utilities already set, plus the theme-provider lock. Consumers never import it.

```ts
type CssValue = string // hex, rgba(), or var(--same-table-token)

type TokenKind = "color" | "length" | "timing"

/** Roles that share one value in both palettes. Declared once on :root. */
type InvariantVar =
  | "primary"
  | "primary-foreground"
  | "primary-hover"
  | "ring"
  | "destructive"
  | "radius"
  | "status-blocking"
  | "status-warning"
  | "status-pending"
  | "status-done"
  | "ease-out"
  | "duration-fast"

/** Roles whose light and dark values differ. Same keys in both surface blocks. */
type SurfaceVar =
  | "background"
  | "foreground"
  | "card"
  | "card-foreground"
  | "popover"
  | "popover-foreground"
  | "secondary"
  | "secondary-foreground"
  | "muted"
  | "muted-foreground"
  | "accent"
  | "accent-foreground"
  | "border"
  | "border-strong"
  | "input"
  | "chart-1"
  | "chart-2"
  | "chart-3"
  | "chart-4"
  | "chart-5"
  | "sidebar"
  | "sidebar-foreground"
  | "sidebar-primary"
  | "sidebar-primary-foreground"
  | "sidebar-accent"
  | "sidebar-accent-foreground"
  | "sidebar-border"
  | "sidebar-ring"

type BindingRow = {
  shadcnVar: InvariantVar | SurfaceVar
  kind: TokenKind
  /** Comment only. Not emitted as a CSS variable. */
  linearName: string
  value: CssValue
}

type BindingTable = {
  /** One assignment. Not repeated under .dark or .light. */
  invariant: Record<InvariantVar, BindingRow>
  /** Key sets are identical. The assert parser rejects a key present on only one side. */
  surface: {
    light: Record<SurfaceVar, BindingRow>
    dark: Record<SurfaceVar, BindingRow>
  }
}
```

`sidebar-primary`, `sidebar-primary-foreground`, `sidebar-accent`, `sidebar-accent-foreground`, and `sidebar-ring` are `var(--primary)`, `var(--primary-foreground)`, `var(--accent)`, `var(--accent-foreground)`, and `var(--ring)`. Their hex lives on the target row. `status-pending` and `--ring` share the literal `#8a8a8e` and stay separate rows: pending is a status, the ring is focus.

## Binding table (the values)

Markers are the parser's handles. `@theme inline` stays a derived alias list: `--color-<var>: var(--<var>)` for every `kind: "color"` row, including the two new ones `--color-primary-hover` and `--color-border-strong`. No hex inside `@theme`.

```css
/* @binding dark-variant
   A .light subtree is the PDF sheet. It must not match dark: utilities,
   or those utilities keep painting over the light rows. */
@custom-variant dark (&:is(.dark *):not(:is(.light, .light *)));

/* @binding invariant */
:root {
  --primary: #e6e6e6;            /* --btn-primary-bg */
  --primary-foreground: #141415; /* --text-inverse */
  --primary-hover: #f2f2f2;      /* --btn-primary-hover */
  --ring: #8a8a8e;               /* --focus-ring. Not --accent. */
  --destructive: #eb5757;
  --radius: 0.375rem;            /* 6px control radius */
  --status-blocking: #eb5757;
  --status-warning: #f2c94c;
  --status-pending: #8a8a8e;
  --status-done: #4cb782;
  --ease-out: cubic-bezier(0.2, 0.8, 0.2, 1);
  --duration-fast: 120ms;
}

/* @binding surface light — :root so a non-dark document matches; .light so a PDF island matches */
:root,
.light {
  --background: #f4f4f5;
  --foreground: #1a1a1c;
  --card: #ffffff;
  --card-foreground: #1a1a1c;
  --popover: #ffffff;
  --popover-foreground: #1a1a1c;
  --secondary: #eeeeef;
  --secondary-foreground: var(--primary-foreground);
  --muted: #eeeeef;
  --muted-foreground: #5c5c62;
  --accent: rgba(0, 0, 0, 0.04);          /* wash. Never var(--ring). */
  --accent-foreground: var(--primary-foreground);
  --border: rgba(0, 0, 0, 0.1);
  --border-strong: rgba(0, 0, 0, 0.16);
  --input: #ffffff;
  --chart-1: #8a8a8e;
  --chart-2: #5c5c62;
  --chart-3: #4cb782;
  --chart-4: #f2c94c;
  --chart-5: #eb5757;
  --sidebar: var(--background);
  --sidebar-foreground: var(--foreground);
  --sidebar-primary: var(--primary);
  --sidebar-primary-foreground: var(--primary-foreground);
  --sidebar-accent: var(--accent);
  --sidebar-accent-foreground: var(--accent-foreground);
  --sidebar-border: rgba(0, 0, 0, 0.08);
  --sidebar-ring: var(--ring);
}

/* @binding surface dark — product chrome. Later source order overrides :root on html.dark.
   A descendant .light sets its own properties, which beat inherited dark values. */
.dark {
  --background: #080808;
  --foreground: #eeeeef;
  --card: #131315;
  --card-foreground: #eeeeef;
  --popover: #19191b;
  --popover-foreground: #eeeeef;
  --secondary: #19191b;
  --secondary-foreground: #eeeeef;
  --muted: rgba(255, 255, 255, 0.04);
  --muted-foreground: #9b9ba1;
  --accent: rgba(255, 255, 255, 0.06);
  --accent-foreground: #eeeeef;
  --border: rgba(255, 255, 255, 0.1);
  --border-strong: rgba(255, 255, 255, 0.16);
  --input: #121214;
  --chart-1: #9b9ba1;
  --chart-2: #8a8a8e;
  --chart-3: #4cb782;
  --chart-4: #f2c94c;
  --chart-5: #eb5757;
  --sidebar: #0c0c0d;
  --sidebar-foreground: #9b9ba1;
  --sidebar-primary: var(--primary);
  --sidebar-primary-foreground: var(--primary-foreground);
  --sidebar-accent: var(--accent);
  --sidebar-accent-foreground: var(--accent-foreground);
  --sidebar-border: rgba(255, 255, 255, 0.06);
  --sidebar-ring: var(--ring);
}
```

Invariants encoded in this layout, checked by the parser (`per encode-lessons-in-structure`):

- A property in `invariant` is absent from both surface blocks.
- `surface.light` and `surface.dark` have the same property names.
- `.dark` `--accent` text is `rgba(255, 255, 255, 0.06)`. `.light` `--accent` text is `rgba(0, 0, 0, 0.04)`. Neither is `var(--ring)` or `#8a8a8e`.
- `--primary` text is `#e6e6e6`. `--ring` text is `#8a8a8e`. `--primary-hover` text is `#f2f2f2`.
- The file contains no `@import` of `docs/design/tokens.css` and no `@layer components`.
- `@theme inline` maps each color row with `var(--<name>)` only.

`@layer utilities` status dots and `.label-pill` stay. They read `--status-*`. `@layer base` drops the `textarea { resize: none }` rule so the class patch is the only resize writer.

## Patch manifest

Owner: `apps/web/scripts/linear-patches.mjs`. Imported by the apply and assert scripts. App routes and `components/**` do not import it. `eslint.config.mjs` bans that import (`per` importable-internals).

```ts
type ReplacePatch = {
  op: "replace"
  file: string // relative to apps/web
  find: string
  replace: string
}

type GuardPatch = {
  op: "guard"
  file: string
  mustInclude: string
  mustNotInclude?: string
}

/** Whole-file write. Used when the edit deletes code, not a class token. */
type CanonicalPatch = {
  op: "canonical"
  file: "components/theme-provider.tsx"
  /** Present only on the pre-patch file. */
  upstreamNeedle: 'defaultTheme="system"'
  body: string
}

type Patch = ReplacePatch | GuardPatch | CanonicalPatch
```

Replace rows (exact needles from the current files):

| File | find | replace |
| --- | --- | --- |
| `components/ui/button.tsx` | `hover:bg-primary/80` | `hover:bg-primary-hover` |
| `components/ui/badge.tsx` | `[a]:hover:bg-primary/80` | `[a]:hover:bg-primary-hover` |
| `components/ui/bubble.tsx` | `[&>[data-slot=bubble-content]:is(button,a):hover]:bg-primary/80` | `[&>[data-slot=bubble-content]:is(button,a):hover]:bg-primary-hover` |
| `components/ui/checkbox.tsx` | `size-4 shrink-0` | `size-3.5 shrink-0` |
| `components/ui/checkbox.tsx` | `border border-input` | `border border-border-strong` |
| `components/ui/checkbox.tsx` | `[&>svg]:size-3.5` | `[&>svg]:size-2.5` |
| `components/ui/textarea.tsx` | `flex field-sizing-content min-h-16` | `resize-none flex field-sizing-content min-h-16` |
| `components/ui/sidebar.tsx` | `const SIDEBAR_WIDTH = "16rem"` | `const SIDEBAR_WIDTH = "244px"` |

`components/theme-provider.tsx` is not a substring swap. The hotkey, `isTypingTarget`, and the `useTheme` import leave with it, so the patch is a canonical file body. Apply writes that body when `defaultTheme="system"` is present. When the file already equals the canonical body, apply no-ops. Any other contents throw. A needle that is only a prefix of its replacement (`enableSystem` inside `enableSystem={false}`, `flex field-sizing-content` inside `resize-none flex field-sizing-content`) is illegal: the second run would see both strings and throw. Every `find` above disappears after a successful replace.

`size-3.5` is 14px. `size-2.5` is 10px. `rounded-[4px]` is already on the checkbox and is a guard, not a replace. Badge and bubble are in the manifest because they are the other `primary/80` writers on a primary fill. One hover token covers all three.

Guards:

| File | must include | must not include |
| --- | --- | --- |
| `components/ui/checkbox.tsx` | `rounded-[4px]` | |
| `components/ui/sidebar.tsx` | `data-active:bg-sidebar-accent` | `data-active:ring`, `data-active:border` |
| `components/theme-provider.tsx` | `forcedTheme="dark"` | `ThemeHotkey` |

Theme-provider target shape after apply. The hotkey function and its `useTheme` import go away in the same edit; a leftover function fails the guard and the unused-symbol lint.

```tsx
function ThemeProvider({
  children,
  ...props
}: React.ComponentProps<typeof NextThemesProvider>) {
  return (
    <NextThemesProvider
      attribute="class"
      defaultTheme="dark"
      enableSystem={false}
      forcedTheme="dark"
      disableTransitionOnChange
      {...props}
    >
      {children}
    </NextThemesProvider>
  )
}
```

`layout.tsx` already renders `<ThemeProvider>{children}</ThemeProvider>` and does not pass a theme prop. `forcedTheme` wins over a stored `localStorage` value.

## Signatures

```ts
type ApplyStatus = "applied" | "unchanged"

type PatchNeedleMissing = {
  kind: "needle-missing"
  file: string
  find: string
}

type PatchAmbiguous = {
  kind: "ambiguous"
  file: string
  find: string
  replace: string
}

/**
 * Merge one patch into a file.
 * find present, replace absent, find occurs once → write replace.
 * replace present, find absent → unchanged (second run is a no-op).
 * both present, or neither present, or find occurs twice → throw.
 * find must not be a substring of replace.
 * A crash mid-file-list is recovered by running again.
 */
function applyPatch(root: string, patch: ReplacePatch): ApplyResult {
  throw new Error("not implemented")
}

/**
 * File equals body → unchanged.
 * File contains upstreamNeedle → write body.
 * Otherwise throw. A hand edit that is neither upstream nor canonical
 * is not merged.
 */
function applyCanonical(root: string, patch: CanonicalPatch): ApplyResult {
  throw new Error("not implemented")
}

function applyAll(root: string, patches: Patch[]): ApplyResult[] {
  throw new Error("not implemented")
}

type Sentinel = {
  primary: "#e6e6e6"
  primaryHover: "#f2f2f2"
  ring: "#8a8a8e"
  accentDark: "rgba(255, 255, 255, 0.06)"
  accentLight: "rgba(0, 0, 0, 0.04)"
  forbiddenIndigo: "#5e6ad2"
}

/**
 * Static, always: parse the three marked blocks; check the invariants
 * listed above; grep apps/web for `bg-primary/80` and for the indigo
 * literal outside this script; run every guard.
 * Computed, when GALLERY_URL is set: Playwright opens /gallery.
 * Bodies stay pure after the CSS text and the DOM snapshot are in hand.
 */
function assertTheme(args: {
  webRoot: string
  galleryUrl: string | null
  sentinels: Sentinel
}): void {
  throw new Error("not implemented")
}
```

Computed checks on `/gallery` (normalize hex and `rgb()` to channels before compare):

- `documentElement` class includes `dark`.
- Computed `--primary` is `#e6e6e6`, `--ring` is `#8a8a8e`, `--accent` is the dark wash, and `--accent` is not `--ring`.
- `[data-testid="primary-cta"]` background is `#e6e6e6`. After hover, background is `#f2f2f2`.
- `[data-testid="checkbox"]` border box is 14×14px.
- `[data-testid="textarea"]` computed `resize` is `none`.
- `[data-testid="nav-active"]` background is the dark wash; `box-shadow` is `none`.
- Inside `[data-testid="pdf-sheet"]`, computed `--background` is `#f4f4f5` while `documentElement`'s `--background` stays `#080808`.
- The outline button inside the sheet does not resolve to the `dark:bg-input/30` wash.
- No loaded stylesheet URL contains `tokens.css`.

Gallery fixture, `apps/web/app/gallery/page.tsx`, imports only public UI modules:

```tsx
import { Button } from "@/components/ui/button"
import { Checkbox } from "@/components/ui/checkbox"
import { Textarea } from "@/components/ui/textarea"
import {
  Sidebar,
  SidebarContent,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  SidebarProvider,
} from "@/components/ui/sidebar"

export default function GalleryPage() {
  return (
    <main data-testid="gallery">
      <Button data-testid="primary-cta">Continue</Button>
      <Checkbox data-testid="checkbox" defaultChecked />
      <Textarea data-testid="textarea" defaultValue="Note" />
      <SidebarProvider>
        <Sidebar>
          <SidebarContent>
            <SidebarMenu>
              <SidebarMenuItem>
                <SidebarMenuButton isActive data-testid="nav-active">
                  Intake
                </SidebarMenuButton>
              </SidebarMenuItem>
            </SidebarMenu>
          </SidebarContent>
        </Sidebar>
      </SidebarProvider>
      <section className="light" data-testid="pdf-sheet">
        <Button variant="outline" data-testid="pdf-outline">
          Download
        </Button>
      </section>
    </main>
  )
}
```

`SidebarMenuButton` calls `useSidebar()`, so the fixture wraps `SidebarProvider`. Playwright is an `apps/web` devDependency used only by the assert script.

## Module map

| Module | Owns | Callers |
| --- | --- | --- |
| `app/globals.css` marked blocks | Binding table, dark-variant selector, `@theme` aliases | Tailwind, every UI component, the parser |
| `scripts/linear-patches.mjs` | Patch list | apply, assert |
| `scripts/apply-linear-patches.mjs` | Merge after shadcn overwrite | theme author, CLI |
| `scripts/assert-linear-theme.mjs` | Sentinels, key parity, computed proof | theme author, CI |
| `app/gallery/page.tsx` | Fixture DOM | assert script |
| `components/ui/*` | shadcn public components, patch output | product screens |
| `components/theme-provider.tsx` | Forced dark class on `<html>` | `app/layout.tsx` |

Data flow is two steps. Authoring writes the table or the manifest. Runtime reads CSS variables through the existing utilities. The apply script is the merge point between the shadcn CLI (upstream class strings) and the manifest (`per separate-before-serializing-shared-state`). Product components do not write either store.

Validation sits in `assertTheme` at the file and browser boundary. Component render paths trust the variables (`per boundary-discipline`).

## What this kit does not do

- It does not export a `LinearButton`, a token provider, or a `cn` theme helper.
- It does not define `--bg-app`, `--btn-primary-*`, or `--focus-ring` in the app.
- It does not restyle the other ~60 generated components. They already consume the semantic variables.
- It does not treat `@layer components` attribute selectors as a styling path. That block is deleted. Utilities beat it, and a second path is a second way to paint a button.

## Interface depth

The product public surface is the existing `@/components/ui/*` exports plus the `light` class on a PDF subtree. Hidden behind that: the accent/ring name collision, the utility-versus-layer cascade, the shadcn overwrite merge, and the dark-shell versus light-sheet split. A caller does not learn those to put a grey Continue button on the page.

## Red-flag screen

- **Shallow module.** The surface callers learn is one import path they already have. The table and the merger hold the policy.
- **Information leakage.** Linear variable names are comments. Components keep using shadcn utilities. Hex does not appear in TSX.
- **Temporal decomposition.** Parse, apply, and assert are tools over one table and one manifest. They are not layered representations of a theme object.
- **Pass-through.** No wrapper forwards props into `Button`.
- **Split ownership.** The table has one writer. Class strings have one merger (apply) after the CLI. The deleted `@layer components` block is the writer this removes.
- **Two ways.** Hover color is `--primary-hover` referenced from the patched utility. Resize is `resize-none` on `Textarea`. A repo grep for `bg-primary/80` fails the assert.
- **Importable internals.** The manifest lives in `scripts/` and is eslint-banned from `app/**` and `components/**`.
- **Hand-synced list.** Surface key parity is derived by the parser. `@theme` color lines are checked against color rows. The assert script repeats four sentinels and the forbidden indigo literal, not the palette.
