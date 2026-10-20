import { readdirSync, readFileSync, statSync } from "node:fs"
import { dirname, join, relative } from "node:path"
import { fileURLToPath } from "node:url"

import { patches } from "./linear-patches.mjs"

const webRoot = join(dirname(fileURLToPath(import.meta.url)), "..")
const globalsPath = join(webRoot, "app/globals.css")

const NON_COLOR = new Set(["radius", "ease-out", "duration-fast"])

const sentinels = {
  primary: "#e6e6e6",
  primaryHover: "#f2f2f2",
  ring: "#8a8a8e",
  accentDark: "rgba(255, 255, 255, 0.06)",
  accentLight: "rgba(0, 0, 0, 0.04)",
  forbiddenIndigo: "#5e6ad2",
}

function norm(value) {
  return value.replace(/\s+/g, " ").trim().toLowerCase()
}

function sliceBetween(css, startMarker, endMarker) {
  const start = css.indexOf(startMarker)
  if (start < 0) throw new Error(`missing marker ${startMarker}`)
  const from = start + startMarker.length
  const end = css.indexOf(endMarker, from)
  if (end < 0) throw new Error(`missing end marker ${endMarker}`)
  return css.slice(from, end)
}

function declarations(block) {
  const map = new Map()
  const re = /--([\w-]+)\s*:\s*([^;]+);/g
  for (const match of block.matchAll(re)) {
    const name = match[1]
    const value = match[2].replace(/\/\*.*?\*\//g, "").trim()
    if (map.has(name)) throw new Error(`duplicate --${name} in one binding block`)
    map.set(name, value)
  }
  return map
}

function sameKeys(left, right) {
  const a = [...left.keys()].sort()
  const b = [...right.keys()].sort()
  return a.length === b.length && a.every((key, index) => key === b[index])
}

function channels(input) {
  const value = input.trim().toLowerCase()
  const hex = value.match(/^#([0-9a-f]{6})([0-9a-f]{2})?$/)
  if (hex) {
    const n = hex[1]
    const alpha = hex[2] === undefined ? 255 : Number.parseInt(hex[2], 16)
    return {
      r: Number.parseInt(n.slice(0, 2), 16),
      g: Number.parseInt(n.slice(2, 4), 16),
      b: Number.parseInt(n.slice(4, 6), 16),
      a: alpha / 255,
    }
  }
  const rgb = value.match(
    /^rgba?\(\s*([\d.]+)[\s,]+([\d.]+)[\s,]+([\d.]+)(?:[\s,/]+([\d.]+))?\s*\)$/
  )
  if (!rgb) throw new Error(`unparsed color ${input}`)
  return {
    r: Math.round(Number(rgb[1])),
    g: Math.round(Number(rgb[2])),
    b: Math.round(Number(rgb[3])),
    a: rgb[4] === undefined ? 1 : Number(rgb[4]),
  }
}

function nearColor(actual, expected, tolerance = 1) {
  let got
  let want
  try {
    got = channels(actual)
    want = channels(expected)
  } catch {
    return false
  }
  return (
    Math.abs(got.r - want.r) <= tolerance &&
    Math.abs(got.g - want.g) <= tolerance &&
    Math.abs(got.b - want.b) <= tolerance &&
    Math.abs(got.a - want.a) <= 0.02
  )
}

function walk(dir, out) {
  for (const name of readdirSync(dir)) {
    if (name === "node_modules" || name === ".next" || name === "out" || name === "build") {
      continue
    }
    const path = join(dir, name)
    const stat = statSync(path)
    if (stat.isDirectory()) {
      walk(path, out)
      continue
    }
    if (!/\.(css|ts|tsx|js|mjs|json|md)$/.test(name)) continue
    out.push(path)
  }
}

function assertStatic(errors) {
  const css = readFileSync(globalsPath, "utf8")

  if (/@import\b[^;]*tokens\.css/.test(css)) {
    errors.push("globals.css imports tokens.css")
  }
  if (/@import\b[^;]*variables\.css/.test(css)) {
    errors.push("globals.css imports variables.css")
  }
  if (css.includes("@layer components")) {
    errors.push("globals.css still has @layer components")
  }
  if (!css.includes("@custom-variant dark (&:is(.dark *):not(:is(.light, .light *)));")) {
    errors.push("globals.css dark variant does not exclude .light")
  }
  if (norm(css).includes(sentinels.forbiddenIndigo)) {
    errors.push("globals.css contains indigo #5e6ad2")
  }

  const invariant = declarations(
    sliceBetween(css, "/* @binding invariant */", "/* @binding surface light")
  )
  const light = declarations(
    sliceBetween(css, "/* @binding surface light", "/* @binding surface dark")
  )
  const dark = declarations(sliceBetween(css, "/* @binding surface dark", "@layer base"))

  for (const name of invariant.keys()) {
    if (light.has(name) || dark.has(name)) {
      errors.push(`--${name} is invariant and also on a surface`)
    }
  }
  if (!sameKeys(light, dark)) {
    errors.push("surface light and surface dark property names differ")
  }

  const primary = norm(invariant.get("primary") ?? "")
  const ring = norm(invariant.get("ring") ?? "")
  const hover = norm(invariant.get("primary-hover") ?? "")
  if (primary !== sentinels.primary) {
    errors.push(`--primary is ${invariant.get("primary")}, expected ${sentinels.primary}`)
  }
  if (ring !== sentinels.ring) {
    errors.push(`--ring is ${invariant.get("ring")}, expected ${sentinels.ring}`)
  }
  if (hover !== sentinels.primaryHover) {
    errors.push(
      `--primary-hover is ${invariant.get("primary-hover")}, expected ${sentinels.primaryHover}`
    )
  }

  const accentLight = norm(light.get("accent") ?? "")
  const accentDark = norm(dark.get("accent") ?? "")
  if (accentLight !== norm(sentinels.accentLight)) {
    errors.push(`light --accent is ${light.get("accent")}`)
  }
  if (accentDark !== norm(sentinels.accentDark)) {
    errors.push(`dark --accent is ${dark.get("accent")}`)
  }
  for (const [label, value] of [
    ["light", accentLight],
    ["dark", accentDark],
  ]) {
    if (value === "var(--ring)" || value === sentinels.ring || value.includes("focus-ring")) {
      errors.push(`${label} --accent points at the focus ring`)
    }
  }

  const theme = sliceBetween(css, "@theme inline {", "\n}")
  if (/#[0-9a-f]{3,8}/i.test(theme)) {
    errors.push("@theme inline contains a hex color")
  }
  for (const name of [...invariant.keys(), ...light.keys()]) {
    if (NON_COLOR.has(name)) continue
    const line = `--color-${name}: var(--${name});`
    if (!theme.includes(line)) errors.push(`@theme missing ${line}`)
  }

  const files = []
  walk(webRoot, files)
  const assertFile = join(webRoot, "scripts/assert-linear-theme.mjs")
  const manifestFile = join(webRoot, "scripts/linear-patches.mjs")
  for (const path of files) {
    const text = readFileSync(path, "utf8")
    const rel = relative(webRoot, path)
    if (path !== assertFile && text.toLowerCase().includes(sentinels.forbiddenIndigo)) {
      errors.push(`${rel} contains indigo ${sentinels.forbiddenIndigo}`)
    }
    if (path !== manifestFile && path !== assertFile && text.includes("bg-primary/80")) {
      errors.push(`${rel} still has bg-primary/80`)
    }
  }

  for (const patch of patches) {
    if (patch.op !== "guard") continue
    const text = readFileSync(join(webRoot, patch.file), "utf8")
    if (!text.includes(patch.mustInclude)) {
      errors.push(`${patch.file} missing ${patch.mustInclude}`)
    }
    if (patch.mustNotInclude && text.includes(patch.mustNotInclude)) {
      errors.push(`${patch.file} contains ${patch.mustNotInclude}`)
    }
  }
}

function assertSnapshot(snapshot, hoveredBackground, errors) {
  if (!snapshot.darkClass) errors.push("documentElement is missing class dark")
  if (!nearColor(snapshot.root.primary, sentinels.primary)) {
    errors.push(`computed --primary is ${snapshot.root.primary}`)
  }
  if (!nearColor(snapshot.root.ring, sentinels.ring)) {
    errors.push(`computed --ring is ${snapshot.root.ring}`)
  }
  if (!nearColor(snapshot.root.accent, sentinels.accentDark)) {
    errors.push(`computed --accent is ${snapshot.root.accent}`)
  }
  if (nearColor(snapshot.root.accent, sentinels.ring)) {
    errors.push("computed --accent matches --ring")
  }
  if (!snapshot.cta) errors.push("missing primary-cta")
  else if (!nearColor(snapshot.cta.backgroundColor, sentinels.primary)) {
    errors.push(`primary button background is ${snapshot.cta.backgroundColor}`)
  }
  if (!nearColor(hoveredBackground, sentinels.primaryHover)) {
    errors.push(`primary hover background is ${hoveredBackground}`)
  }
  if (!snapshot.checkbox) errors.push("missing checkbox")
  else if (
    Math.abs(snapshot.checkbox.width - 14) > 0.6 ||
    Math.abs(snapshot.checkbox.height - 14) > 0.6
  ) {
    errors.push(
      `checkbox box is ${snapshot.checkbox.width}x${snapshot.checkbox.height}`
    )
  }
  if (!snapshot.textarea) errors.push("missing textarea")
  else if (snapshot.textarea.resize !== "none") {
    errors.push(`textarea resize is ${snapshot.textarea.resize}`)
  }
  if (!snapshot.nav) errors.push("missing nav-active")
  else {
    if (!nearColor(snapshot.nav.backgroundColor, sentinels.accentDark)) {
      errors.push(`nav active background is ${snapshot.nav.backgroundColor}`)
    }
    if (snapshot.nav.boxShadow !== "none") {
      errors.push(`nav active box-shadow is ${snapshot.nav.boxShadow}`)
    }
  }
  if (!snapshot.sheet) errors.push("missing pdf-sheet")
  else if (!nearColor(snapshot.sheet.background, "#f4f4f5")) {
    errors.push(`pdf sheet --background is ${snapshot.sheet.background}`)
  }
  if (!nearColor(snapshot.root.background, "#080808")) {
    errors.push(`document --background is ${snapshot.root.background}`)
  }
  if (!snapshot.pdfOutline) errors.push("missing pdf-outline")
  else if (!nearColor(snapshot.pdfOutline.backgroundColor, "#f4f4f5")) {
    errors.push(`pdf outline background is ${snapshot.pdfOutline.backgroundColor}`)
  }
  for (const href of snapshot.stylesheets) {
    if (String(href).includes("tokens.css")) {
      errors.push(`stylesheet loaded tokens.css (${href})`)
    }
  }
}

async function readGallery(page) {
  return page.evaluate(() => {
    const read = (selector) => {
      const el = document.querySelector(selector)
      if (!el) return null
      const cs = getComputedStyle(el)
      const box = el.getBoundingClientRect()
      return {
        backgroundColor: cs.backgroundColor,
        boxShadow: cs.boxShadow,
        resize: cs.resize,
        width: box.width,
        height: box.height,
        background: cs.getPropertyValue("--background").trim(),
      }
    }
    const html = getComputedStyle(document.documentElement)
    return {
      darkClass: document.documentElement.classList.contains("dark"),
      root: {
        primary: html.getPropertyValue("--primary").trim(),
        ring: html.getPropertyValue("--ring").trim(),
        accent: html.getPropertyValue("--accent").trim(),
        background: html.getPropertyValue("--background").trim(),
      },
      cta: read('[data-testid="primary-cta"]'),
      checkbox: read('[data-testid="checkbox"]'),
      textarea: read('[data-testid="textarea"]'),
      nav: read('[data-testid="nav-active"]'),
      sheet: read('[data-testid="pdf-sheet"]'),
      pdfOutline: read('[data-testid="pdf-outline"]'),
      stylesheets: [
        ...[...document.styleSheets].map((sheet) => sheet.href || ""),
        ...performance.getEntriesByType("resource").map((entry) => entry.name),
      ],
    }
  })
}

const errors = []
try {
  assertStatic(errors)
} catch (error) {
  errors.push(error instanceof Error ? error.message : String(error))
}

if (errors.length === 0) console.log("static ok")

const galleryUrl = process.env.GALLERY_URL || ""
if (galleryUrl && errors.length === 0) {
  const { chromium } = await import("playwright")
  const browser = await chromium.launch()
  try {
    const page = await browser.newPage({ viewport: { width: 1280, height: 800 } })
    await page.goto(galleryUrl, { waitUntil: "networkidle" })
    await page.waitForFunction(() => document.documentElement.classList.contains("dark"))
    const snapshot = await readGallery(page)
    await page.locator('[data-testid="primary-cta"]').hover()
    await page.waitForFunction(() => {
      const bg = getComputedStyle(
        document.querySelector('[data-testid="primary-cta"]')
      ).backgroundColor
      const match = bg.match(/rgba?\(\s*([\d.]+)[,\s]+([\d.]+)[,\s]+([\d.]+)/)
      if (!match) return false
      return (
        Math.abs(Number(match[1]) - 242) <= 1 &&
        Math.abs(Number(match[2]) - 242) <= 1 &&
        Math.abs(Number(match[3]) - 242) <= 1
      )
    })
    const hoveredBackground = await page.evaluate(
      () => getComputedStyle(document.querySelector('[data-testid="primary-cta"]')).backgroundColor
    )
    assertSnapshot(snapshot, hoveredBackground, errors)
    if (errors.length === 0) console.log("computed ok")
  } finally {
    await browser.close()
  }
}

if (errors.length > 0) {
  for (const error of errors) console.error(error)
  process.exit(1)
}
