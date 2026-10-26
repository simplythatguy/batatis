/**
 * Visit-local UI state for the calm flow: the deck's session queue, files waiting for an
 * engine case, and the check the Start button asked for. Nothing here is case data and
 * nothing is persisted; Start over clears it.
 */
import { useSyncExternalStore } from "react";
import type { ApplicantType } from "../types";

export interface HeldFile {
  id: string;
  file: File;
}

export interface Session {
  /** Deck keys in the order this visit asks them. */
  queue: string[];
  index: number;
  /** Cards the applicant continued past (Section D, optional cards). */
  seen: string[];
  /** PDFs waiting for the engine case id before upload. */
  held: HeldFile[];
  uploading: string[];
  /** Start was pressed: read the description (intake, then the code check) once the new case has rendered. */
  readAfterStart: boolean;
  /** Before an application exists: the description, files and role being prepared (Start and the deck share them). */
  draft: string;
  draftFiles: HeldFile[];
  role: ApplicantType | null;
  /** The applicant's choice on each offered standing package (checklist id → yes or no). */
  packages: Record<string, "yes" | "no">;
}

const EMPTY: Session = { queue: [], index: 0, seen: [], held: [], uploading: [], readAfterStart: false, draft: "", draftFiles: [], role: null, packages: {} };

let state: Session = EMPTY;
const listeners = new Set<() => void>();

export function getSession(): Session {
  return state;
}

export function updateSession(patch: Partial<Session> | ((s: Session) => Partial<Session>)) {
  const next = typeof patch === "function" ? patch(state) : patch;
  state = { ...state, ...next };
  for (const l of listeners) l();
}

export function resetSession(keep: Partial<Session> = {}) {
  state = { ...EMPTY, ...keep };
  for (const l of listeners) l();
}

function subscribe(l: () => void) {
  listeners.add(l);
  return () => listeners.delete(l);
}

export function useSession(): Session {
  return useSyncExternalStore(subscribe, getSession, getSession);
}
