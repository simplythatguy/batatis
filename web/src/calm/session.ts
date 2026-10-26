/**
 * Visit-local UI state for the calm flow: the deck's session queue, files waiting for an
 * engine case, and the check the Start button asked for. Only the pre-application text and
 * start intent survive a reload, in this tab's sessionStorage. Start over clears them.
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
  /** Files waiting for the engine case id before upload. */
  held: HeldFile[];
  uploading: string[];
  /** The applicant chose "Not sure" for the reviewing authority (the case keeps it empty). */
  authorityUnsure: boolean;
  /** Start was pressed: read the description (intake, then the code check) once the new case has rendered. */
  readAfterStart: boolean;
  /** Before an application exists: the description, files and role being prepared (Start and the deck share them). */
  draft: string;
  draftFiles: HeldFile[];
  /** Start was pressed before sign-in; resume after authentication and onboarding. */
  startRequested: boolean;
  /** This tab reloaded with attachments; File objects cannot survive that navigation. */
  draftFilesLost: boolean;
  role: ApplicantType | null;
  /** The applicant's choice on each offered standing package (checklist id → yes or no). */
  packages: Record<string, "yes" | "no">;
  /** Coded-rule inputs answered Not sure: not asked again in this visit. */
  ruleUnsure: string[];
}

const EMPTY: Session = { queue: [], index: 0, skipped: [], wrapped: false, seen: [], held: [], uploading: [], authorityUnsure: false, readAfterStart: false, draft: "", draftFiles: [], startRequested: false, draftFilesLost: false, role: null, packages: {}, ruleUnsure: [] };

const DRAFT_KEY = "batatis.start-draft.v1";

function restoredDraft(): Partial<Session> {
  try {
    const saved: unknown = JSON.parse(sessionStorage.getItem(DRAFT_KEY) ?? "null");
    if (!saved || typeof saved !== "object" || !("draft" in saved) || typeof saved.draft !== "string") return {};
    return {
      draft: saved.draft,
      startRequested: "startRequested" in saved && saved.startRequested === true,
      draftFilesLost: "hadFiles" in saved && saved.hadFiles === true,
    };
  } catch {
    return {};
  }
}

let state: Session = { ...EMPTY, ...restoredDraft() };
const listeners = new Set<() => void>();

function persistDraft() {
  try {
    const hadFiles = state.draftFiles.length > 0 || state.draftFilesLost;
    if (state.draft || hadFiles || state.startRequested) {
      sessionStorage.setItem(DRAFT_KEY, JSON.stringify({ draft: state.draft, startRequested: state.startRequested, hadFiles }));
    } else sessionStorage.removeItem(DRAFT_KEY);
  } catch {
    /* Storage unavailable: the draft still lives in this page. */
  }
}

export function getSession(): Session {
  return state;
}

export function updateSession(patch: Partial<Session> | ((s: Session) => Partial<Session>)) {
  const next = typeof patch === "function" ? patch(state) : patch;
  state = { ...state, ...next };
  persistDraft();
  for (const l of listeners) l();
}

export function resetSession(keep: Partial<Session> = {}) {
  state = { ...EMPTY, ...keep };
  persistDraft();
  for (const l of listeners) l();
}

function subscribe(l: () => void) {
  listeners.add(l);
  return () => listeners.delete(l);
}

export function useSession(): Session {
  return useSyncExternalStore(subscribe, getSession, getSession);
}
