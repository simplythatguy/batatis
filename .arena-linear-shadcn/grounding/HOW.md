# Grounding (how explainer summary)

Source: how agent 60361fac-926c-47c5-b1c6-d1e0aaf05c9f

## Constraints that bind any design

1. Do not `@import docs/design/tokens.css` into the Next app. That file owns HTML-eval chrome (`.btn`, native checkbox, Google Fonts). Evals link it; the app must not.
2. Theme binding for shadcn lives in `apps/web/app/globals.css` (`components.json` → `tailwind.css`).
3. Map Linear hex onto shadcn semantic vars. `--primary` = `#E6E6E6`, `--primary-foreground` = `#141415`, `--ring` = `#8a8a8e`. Never indigo/`#5E6AD2`.
4. shadcn `--accent` = faint wash `rgba(255,255,255,0.06)` (active/hover). Do NOT point it at tokens.css `--accent` (focus-ring alias).
5. Product chrome defaults to dark charcoal. Light `:root` palette is PDF-sheet only. Force `defaultTheme="dark"` (or always `.dark` on product shell).
6. `@layer components` CSS loses to Tailwind utilities. Geometry patches (`size-4`→14px checkbox, `hover:bg-primary/80`→`#F2F2F2`) must be class edits on the component files.
7. ~63 components already generated under `apps/web/components/ui/`. Prefer variable map + few class patches over rewriting all files.
8. `smoke.mjs` only covers HTML evals, not `apps/web`. App proof needs its own check (build + gallery page).
9. Re-running `shadcn add` overwrites class patches; variable map survives.

## Hex map (dark product)

background #080808, card #131315, popover #19191b, sidebar #0c0c0d, input #121214,
foreground #eeeeef, muted-foreground #9b9ba1, primary #E6E6E6 / fg #141415,
ring #8a8a8e, accent/sidebar-accent rgba(255,255,255,0.06), border rgba(255,255,255,0.1),
destructive #eb5757, status warning #f2c94c pending #8a8a8e done #4cb782.
radius base 0.375rem (6px). Primary hover #F2F2F2.

## Class-patch list (minimum)

- button.tsx: default hover → #F2F2F2 (not primary/80)
- checkbox.tsx: 14px square, 4px radius, smaller check icon
- textarea.tsx: resize-none
- sidebar: keep data-active:bg-sidebar-accent; no active ring/border; optional width 244px
- theme-provider: defaultTheme dark
