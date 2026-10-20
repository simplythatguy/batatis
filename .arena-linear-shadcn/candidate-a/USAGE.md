# Token-map kit

Product screens import the shadcn components that are already in the app. Those components render the Linear charcoal theme. Callers do not pass colors, token names, or a wrapper.

## Quickstart

1. Import from `@/components/ui/*`.
2. Leave the root theme provider alone. It forces `dark` on `<html>`. Product chrome stays charcoal, including after a reload.
3. Wrap a printable PDF preview in `className="light"`. That class selects the light surface rows of the same binding table. `--primary` stays the shared grey.
4. Change a color by editing one row of the binding table in `apps/web/app/globals.css`. Hex and `rgba` values live only in that table.
5. Change non-token geometry (checkbox size, the primary hover utility, textarea resize, sidebar width) in `apps/web/scripts/linear-patches.mjs`, then apply:

```bash
node apps/web/scripts/apply-linear-patches.mjs
```

6. After `shadcn add --overwrite`, run apply again. The CLI rewrites component class strings. The binding table survives. Apply puts the geometry patches back. Then prove it:

```bash
# apps/web dev server already listening on :3000
GALLERY_URL=http://127.0.0.1:3000/gallery node apps/web/scripts/assert-linear-theme.mjs
```

`/gallery` is a fixture. It imports the same `@/components/ui/*` modules product screens use. The script reads the binding table and the computed primary button color.

Do not `@import` `docs/design/tokens.css`. That file is the HTML-eval stylesheet. The Next app reads `app/globals.css` (`components.json` → `tailwind.css`).

## Call sites

### Primary action

```tsx
import { Button } from "@/components/ui/button"

export function IntakeFooter({ canContinue }: { canContinue: boolean }) {
  return (
    <Button type="submit" disabled={!canContinue}>
      Continue
    </Button>
  )
}
```

The default variant fills from `--primary` (`#e6e6e6`) with `--primary-foreground` (`#141415`). Hover fills from `--primary-hover` (`#f2f2f2`). The call site has no color class.

### Checklist control

```tsx
import { Checkbox } from "@/components/ui/checkbox"

export function AssumptionRow({
  checked,
  onCheckedChange,
}: {
  checked: boolean
  onCheckedChange: (next: boolean) => void
}) {
  return (
    <Checkbox
      checked={checked}
      onCheckedChange={(value) => onCheckedChange(value === true)}
      aria-label="Confirmed by applicant"
    />
  )
}
```

The checkbox is a 14px square with a 4px radius and a 10px check icon. Callers do not pass a size.

### PDF sheet inside the dark shell

```tsx
import { Button } from "@/components/ui/button"

export function ExportPreview() {
  return (
    <section className="light" aria-label="PDF preview">
      <Button variant="outline" data-testid="pdf-download">
        Download
      </Button>
    </section>
  )
}
```

The section reads the light surface rows (sheet background `#f4f4f5`). The outline button uses its light utilities because a `.light` subtree is excluded from the `dark` variant. The page around the section stays on the dark rows.
