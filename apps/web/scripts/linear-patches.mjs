export const themeProviderBody = `"use client"

import * as React from "react"
import { ThemeProvider as NextThemesProvider } from "next-themes"

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

export { ThemeProvider }
`

export const patches = [
  {
    op: "replace",
    file: "components/ui/button.tsx",
    find: "hover:bg-primary/80",
    replace: "hover:bg-primary-hover",
  },
  {
    op: "replace",
    file: "components/ui/badge.tsx",
    find: "[a]:hover:bg-primary/80",
    replace: "[a]:hover:bg-primary-hover",
  },
  {
    op: "replace",
    file: "components/ui/bubble.tsx",
    find: "[&>[data-slot=bubble-content]:is(button,a):hover]:bg-primary/80",
    replace: "[&>[data-slot=bubble-content]:is(button,a):hover]:bg-primary-hover",
  },
  {
    op: "replace",
    file: "components/ui/checkbox.tsx",
    find: "size-4 shrink-0",
    replace: "size-[14px] shrink-0",
  },
  {
    op: "replace",
    file: "components/ui/checkbox.tsx",
    find: "border border-input",
    replace: "border border-border-strong",
  },
  {
    op: "replace",
    file: "components/ui/checkbox.tsx",
    find: "[&>svg]:size-3.5",
    replace: "[&>svg]:size-2.5",
  },
  {
    op: "replace",
    file: "components/ui/textarea.tsx",
    find: '"flex field-sizing-content min-h-16',
    replace: '"resize-none flex field-sizing-content min-h-16',
  },
  {
    op: "replace",
    file: "components/ui/sidebar.tsx",
    find: 'const SIDEBAR_WIDTH = "16rem"',
    replace: 'const SIDEBAR_WIDTH = "244px"',
  },
  {
    op: "canonical",
    file: "components/theme-provider.tsx",
    upstreamNeedle: 'defaultTheme="system"',
    body: themeProviderBody,
  },
  {
    op: "guard",
    file: "components/ui/checkbox.tsx",
    mustInclude: "rounded-[4px]",
  },
  {
    op: "guard",
    file: "components/ui/checkbox.tsx",
    mustInclude: "size-[14px]",
  },
  {
    op: "guard",
    file: "components/ui/textarea.tsx",
    mustInclude: "resize-none",
  },
  {
    op: "guard",
    file: "components/ui/sidebar.tsx",
    mustInclude: "data-active:bg-sidebar-accent",
    mustNotInclude: "data-active:ring",
  },
  {
    op: "guard",
    file: "components/ui/sidebar.tsx",
    mustInclude: "data-active:bg-sidebar-accent",
    mustNotInclude: "data-active:border",
  },
  {
    op: "guard",
    file: "components/theme-provider.tsx",
    mustInclude: 'forcedTheme="dark"',
    mustNotInclude: "ThemeHotkey",
  },
]
