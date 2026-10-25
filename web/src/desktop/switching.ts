/**
 * Before the desktop host changes person or workspace, this visit's work must be saved and confirmed.
 * Anything that cannot be confirmed keeps the current person and their unsaved work on screen.
 */
import type { SaveStatus } from "../checkState";

export interface VisitState {
  phase: "who" | "case";
  saveStatus: SaveStatus;
  submitting: boolean;
  submissionDispatched: boolean;
  /** Uploads in flight, and files waiting for the application to exist. */
  uploading: number;
  held: number;
  /** A description or files prepared on Start but not started yet; there is nothing to save them into. */
  unstarted: boolean;
}

export interface SwitchDeps {
  /** Live state: the session store and the save state as of this call, not a render snapshot. */
  read: () => VisitState;
  saveDraft: () => Promise<string | null>;
  /** The store's own acknowledgement that the latest save reached the engine. */
  saved: () => boolean;
}

const PENDING: ReadonlySet<SaveStatus> = new Set(["unsaved", "saving", "failed"]);

/** Resolves to the reason the switch must wait, or null once everything is saved. */
export async function saveBeforeSwitch(deps: SwitchDeps): Promise<string | null> {
  const before = deps.read();
  if (before.submitting || before.submissionDispatched) return "Wait for the submission to finish.";
  if (before.uploading > 0) return "Wait for the upload to finish.";
  if (before.phase === "who" && before.unstarted) return "Start or clear the description first. It isn’t saved yet.";
  if (before.phase === "case" && before.saveStatus === "gone") return "This application can’t be saved any more. Keep a draft first.";
  if (before.phase === "case" && PENDING.has(before.saveStatus)) {
    const id = await deps.saveDraft();
    if (!id || !deps.saved()) return "Your answers didn’t save. Try again.";
  }
  // Read again: the save may have created the application its waiting files were held for.
  const after = deps.read();
  if (after.uploading > 0 || after.held > 0) return "Files are still uploading. Try again in a moment.";
  return null;
}
