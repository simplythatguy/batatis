import { randomBytes } from "node:crypto"
import { readFileSync, renameSync, writeFileSync } from "node:fs"
import { dirname, join } from "node:path"
import { fileURLToPath } from "node:url"

import { patches } from "./linear-patches.mjs"

const webRoot = join(dirname(fileURLToPath(import.meta.url)), "..")

function count(haystack, needle) {
  let found = 0
  let from = 0
  while (from <= haystack.length) {
    const at = haystack.indexOf(needle, from)
    if (at < 0) return found
    found += 1
    from = at + needle.length
  }
  return found
}

function writeAtomic(path, body) {
  const tmp = `${path}.${randomBytes(4).toString("hex")}.tmp`
  writeFileSync(tmp, body)
  renameSync(tmp, path)
}

function applyReplace(root, patch) {
  if (patch.replace.includes(patch.find)) {
    throw new Error(
      `${patch.file}: find is a substring of replace (${JSON.stringify(patch.find)})`
    )
  }

  const path = join(root, patch.file)
  const text = readFileSync(path, "utf8")
  const findCount = count(text, patch.find)
  const replaceCount = count(text, patch.replace)

  if (replaceCount > 0 && findCount === 0) {
    return { status: "unchanged", file: patch.file, op: patch.op }
  }

  if (findCount === 1 && replaceCount === 0) {
    writeAtomic(path, text.replace(patch.find, patch.replace))
    return { status: "applied", file: patch.file, op: patch.op }
  }

  throw new Error(
    `${patch.file}: expected find once and replace absent, or replace present and find absent (find ${findCount}, replace ${replaceCount}, needle ${JSON.stringify(patch.find)})`
  )
}

function applyCanonical(root, patch) {
  const path = join(root, patch.file)
  const text = readFileSync(path, "utf8").replace(/\r\n/g, "\n")
  const body = patch.body.replace(/\r\n/g, "\n")

  if (text === body) {
    return { status: "unchanged", file: patch.file, op: patch.op }
  }

  if (text.includes(patch.upstreamNeedle)) {
    writeAtomic(path, body)
    return { status: "applied", file: patch.file, op: patch.op }
  }

  throw new Error(
    `${patch.file}: contents are neither the upstream needle nor the canonical body`
  )
}

function applyGuard(root, patch) {
  const text = readFileSync(join(root, patch.file), "utf8")
  if (!text.includes(patch.mustInclude)) {
    throw new Error(`${patch.file}: missing ${JSON.stringify(patch.mustInclude)}`)
  }
  if (patch.mustNotInclude && text.includes(patch.mustNotInclude)) {
    throw new Error(
      `${patch.file}: still contains ${JSON.stringify(patch.mustNotInclude)}`
    )
  }
  return { status: "unchanged", file: patch.file, op: patch.op }
}

function applyOne(root, patch) {
  if (patch.op === "replace") return applyReplace(root, patch)
  if (patch.op === "canonical") return applyCanonical(root, patch)
  if (patch.op === "guard") return applyGuard(root, patch)
  throw new Error(`unknown patch op ${patch.op}`)
}

const results = []
for (const patch of patches) {
  results.push(applyOne(webRoot, patch))
}

for (const result of results) {
  console.log(`${result.status}\t${result.op}\t${result.file}`)
}
