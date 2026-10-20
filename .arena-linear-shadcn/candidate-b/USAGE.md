# Usage — shared variables + thin Linear adapters

Product UI stays shadcn: screens import `@/components/ui/*` and get Linear charcoal without a second component forest. Hex lives once. Geometry policy lives once. After `shadcn add --overwrite`, color comes back for free; geometry is re-applied from a typed recipe, not by hunting `@layer` overrides.

## Quickstart (app author)

```tsx
// app/layout.tsx
import { LinearThemeProvider } from "@/components/linear/theme-provider"
import { Button } from "@/components/ui/button"
import { Checkbox } from "@/components/ui/checkbox"

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body>
        {/* defaultTheme="dark"; light reserved for PDF sheet routes */}
        <LinearThemeProvider>{children}</LinearThemeProvider>
      </body>
    </html>
  )
}

// any feature screen — no Linear-specific props
export function SubmitBar() {
  return (
    <div className="flex items-center gap-2">
      <Checkbox id="ack" />
      <Button type="submit">Continue</Button>
    </div>
  )
}
```

Primary CTA renders `#E6E6E6` on `#141415` text; hover is `#F2F2F2` (not `primary/80`). Checkbox is a 14px square. No indigo. No import of `docs/design/tokens.css` into the Next app.

## Call site 1 — feature code (happy path)

```tsx
import { Button } from "@/components/ui/button"
import { Textarea } from "@/components/ui/textarea"
import { SidebarMenuButton } from "@/components/ui/sidebar"

export function VarianceNav({ active }: { active: boolean }) {
  return (
    <>
      <SidebarMenuButton isActive={active}>Section A</SidebarMenuButton>
      <Textarea placeholder="Assumptions / limits" />
      <Button>Export PDF</Button>
    </>
  )
}
```

Caller never touches `--btn-primary-bg`, patch recipes, or shadcn bridge maps. Interface depth: one import path, Linear look.

## Call site 2 — regenerating a shadcn component

```bash
npx shadcn@latest add button --overwrite
```

Color still correct (vars survive). Geometry may regress (`hover:bg-primary/80` returns). Fix from the recipe owner:

```ts
// apps/web/scripts/apply-linear-patches.ts  (or manual edit guided by recipe)
import { LINEAR_GEOMETRY_PATCHES } from "@batatis/design-tokens/patch-recipe"
import { applyGeometryPatches } from "@/lib/linear/apply-patches"

// Idempotent: running twice leaves the same class strings.
await applyGeometryPatches({
  root: "apps/web/components/ui",
  patches: LINEAR_GEOMETRY_PATCHES,
})
```

Agents do not invent new hover hexes. They open the recipe, apply, done.

## Call site 3 — HTML eval author (unchanged chrome)

```html
<link rel="stylesheet" href="/docs/design/tokens.css" />
<button class="btn btn-primary">Continue</button>
```

`tokens.css` still owns `.btn`, native checkbox chrome, Google Fonts. It `@import`s the shared variables file; it does not redefine `#e6e6e6`. Evals keep linking `tokens.css`. The app never does.

## What you do not do

- Do not `@import docs/design/tokens.css` from `apps/web/app/globals.css`.
- Do not paste the same hex into `globals.css`, `tokens.css`, and a TS const.
- Do not rewrite all ~63 `components/ui/*` files by hand.
- Do not point shadcn `--accent` at Linear `--accent` (focus-ring alias). Bridge maps `--accent` → `--bg-active`.
- Do not rely on `@layer components` alone for checkbox size / primary hover — Tailwind utilities win; class patches own geometry.
