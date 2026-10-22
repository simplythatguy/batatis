/**
 * Application names. Short subject names come from the engine once it has read the case; the
 * applicant can rename any editable application from the header or the list, and that name wins.
 * Saved through PATCH /cases/{id}/title, which trims to one line (1 to 500 characters).
 */
import { engine, EngineError } from "../api/client";
import type { Case as EngineCase } from "../api/types.gen";
import { patchApplication } from "./account";

export const TITLE_MAX = 500;
export const TITLE_EMPTY = "Give it a name.";

/** One line, single spaces, trimmed: what the server stores. Never shortened. */
export const normalizeTitle = (raw: string) => raw.replace(/\s+/g, " ").trim();

/** Save a name, then show the saved name in the application list. */
export async function saveTitle(id: string, title: string): Promise<EngineCase> {
  const saved = await engine.renameCase(id, title);
  patchApplication(id, { title: saved.title ?? title });
  return saved;
}

export function titleError(e: unknown): string {
  if (!(e instanceof EngineError)) return "The name didn’t save. Try again.";
  if (e.status === 0) return "The name didn’t save: the server didn’t respond.";
  if (e.status === 404 || e.status === 405) return /case not found/i.test(`${e.detail} ${e.technical}`) ? "This application no longer exists." : "Renaming isn’t available on this server yet.";
  if (e.status === 422) return `Use a name of 1 to ${TITLE_MAX} characters.`;
  if (e.status === 409) return "The application changed somewhere else. Try again.";
  if (e.status === 403) return "A sent or closed application can’t be renamed.";
  return "The name didn’t save. Try again.";
}
