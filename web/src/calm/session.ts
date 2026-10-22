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
  /** Skipped in this visit. */
  skipped: string[];
  /** The deck already came back once to skipped cards; the next end is the finish card. */
  wrapped: boolean;
  /** Cards the applicant continued past (Section D, optional cards). */
  seen: string[];
  /** PDFs waiting for the engine case id before upload. */
  held: HeldFile[];
  uploading: string[];
  /** The applicant chose "Not sure" for the reviewing authority (the case keeps it empty). */
  authorityUnsure: boolean;
  /** Start was pressed: read the description (intake, then the code check) once the new case has rendered. */
  readAfterStart: boolean;
  /** Before an application exists: the description, files and role being prepared (Start and the deck share them). */
  draft: string;
  draftFiles: HeldFile[];
  role: ApplicantType | null;
}

const EMPTY: Session = { queue: [], index: 0, skipped: [], wrapped: false, seen: [], held: [], uploading: [], authorityUnsure: false, readAfterStart: false, draft: "", draftFiles: [], role: null };

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
