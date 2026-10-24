/**
 * Which application the code library reads for: the open application, or none (plain browsing).
 *
 * The browser holds one open application at a time, so "application" always means the open one:
 * its scores, its Section C and its "Add to my application". Choosing another application opens it
 * through the same guarded switch as the sidebar (unsaved answers are saved first; a failed save
 * keeps the current one open). None only detaches the library: the open application, its unsaved
 * answers and its save state are not touched, and no scores are read or requested.
 *
 * Visit-local and tab-scoped (sessionStorage), like the open application id. Pure apart from that.
 */
import type { ApplicationSummary } from "../api/accounts";
import type { SaveStatus } from "../checkState";
import { groupApplications, readOnly } from "./applications";

/** The None choice in the picker. Never a case id. */
export const NO_APPLICATION = "none";
export const KEEP_OPEN_NOTE = "This application isn’t saved yet, so it stays open. Try again once it’s saved.";

const KEY = "batatis-code-context";
const read = () => { try { return sessionStorage.getItem(KEY) === NO_APPLICATION; } catch { return false; } };

let detached = read();
/** Bumps on every change, so a request started before the change can tell it is out of date. */
let epoch = 0;
const listeners = new Set<() => void>();

export const libraryDetached = () => detached;
export const libraryEpoch = () => epoch;

export function setLibraryDetached(on: boolean) {
  if (on === detached) return;
  detached = on;
  epoch += 1;
  try { if (on) sessionStorage.setItem(KEY, NO_APPLICATION); else sessionStorage.removeItem(KEY); } catch { /* storage unavailable */ }
  for (const l of listeners) l();
}

export function subscribeLibrary(l: () => void) {
  listeners.add(l);
  return () => { listeners.delete(l); };
}

export interface ContextOption {
  id: string;
  title: string;
  readOnly: boolean;
  open: boolean;
}

/**
 * The applications the picker offers: the same rows as the sidebar (the account's own applications,
 * plus this visit's draft before the engine lists it), pinned, then active, then settled. Archived
 * ones stay on their shelf unless they are the open one.
 */
export function contextOptions(items: ApplicationSummary[], openId: string | null): ContextOption[] {
  const g = groupApplications(items);
  const rows = [...g.pinned, ...g.active, ...g.settled, ...g.archived.filter((a) => a.id === openId)];
  return rows.map((a) => ({ id: a.id, title: a.title.trim() || "Untitled application", readOnly: readOnly(a.status), open: a.id === openId }));
}

export interface SwitchDeps {
  inCase: boolean;
  saveStatus: SaveStatus;
  saveDraft: () => Promise<string | null>;
  /** Resolves to an error text, or null once the other application is open. */
  openCase: (id: string) => Promise<string | null>;
  /** After a successful open: clear the last application's visit state and scores. */
  settle: () => void;
}

/** Open another application, keeping the open draft's answers: anything not yet saved is saved first. */
export async function switchApplication(id: string, deps: SwitchDeps): Promise<string | null> {
  const pending = deps.saveStatus === "unsaved" || deps.saveStatus === "saving" || deps.saveStatus === "failed";
  if (deps.inCase && pending && !(await deps.saveDraft())) return KEEP_OPEN_NOTE;
  const error = await deps.openCase(id);
  if (error) return error;
  deps.settle();
  return null;
}

export interface ChooseDeps {
  /** The open application's row id, or null without one. */
  openId: string | null;
  detach: (on: boolean) => void;
  switchTo: (id: string) => Promise<string | null>;
}

/** Apply a picker choice. Resolves to an error text when the context could not change. */
export async function chooseContext(choice: string, deps: ChooseDeps): Promise<string | null> {
  if (choice === NO_APPLICATION) {
    deps.detach(true);
    return null;
  }
  if (choice === deps.openId) {
    deps.detach(false);
    return null;
  }
  const error = await deps.switchTo(choice);
  if (!error) deps.detach(false);
  return error;
}
