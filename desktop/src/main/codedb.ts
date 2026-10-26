/**
 * The code database is chosen deliberately on this computer, never shipped in the installer. A chosen
 * file must be the NBC(AE) 2023 2nd printing build the engine expects; the app keeps its own copy.
 */
import { createHash } from "node:crypto";
import { copyFile, mkdir, readFile, rename, rm } from "node:fs/promises";
import { dirname } from "node:path";
import { DatabaseSync } from "node:sqlite";

const REQUIRED_TABLES = ["meta", "docs", "provisions", "provisions_fts", "attributions", "definitions", "intents"];

export type Inspection = { ok: true; build: string } | { ok: false; reason: string };

export function inspectCodeDb(file: string, expectedBuild: string): Inspection {
  let db: DatabaseSync;
  try {
    db = new DatabaseSync(file, { readOnly: true });
  } catch {
    return { ok: false, reason: "That file isn’t a code database." };
  }
  try {
    const tables = new Set(db.prepare("SELECT name FROM sqlite_master WHERE type IN ('table', 'view')").all().map((row) => String(row.name)));
    if (REQUIRED_TABLES.some((name) => !tables.has(name))) return { ok: false, reason: "That file isn’t a Batatis code database." };
    const build = db.prepare("SELECT value FROM meta WHERE key = 'build_version'").get()?.value;
    if (typeof build !== "string" || build !== expectedBuild) {
      return { ok: false, reason: "That code database was built by a different version of Batatis." };
    }
    const edition = db.prepare("SELECT label FROM docs WHERE doc = 'NBC-AE' AND citable = 1").get()?.label;
    if (typeof edition !== "string" || !/\b2023\b/.test(edition) || !/\bp2\b/.test(edition)) {
      return { ok: false, reason: "That code database isn’t the NBC(AE) 2023 2nd printing." };
    }
    return { ok: true, build };
  } catch {
    return { ok: false, reason: "That file isn’t a Batatis code database." };
  } finally {
    db.close();
  }
}

/** Copy, then check the copy, then replace: the active database is never a partial file. */
export async function importCodeDb(source: string, target: string, expectedBuild: string): Promise<Inspection & { sha256?: string }> {
  await mkdir(dirname(target), { recursive: true });
  const partial = `${target}.partial`;
  await rm(partial, { force: true });
  await copyFile(source, partial);
  const checked = inspectCodeDb(partial, expectedBuild);
  if (!checked.ok) {
    await rm(partial, { force: true });
    return checked;
  }
  const sha256 = createHash("sha256").update(await readFile(partial)).digest("hex");
  await rename(partial, target);
  return { ...checked, sha256 };
}
