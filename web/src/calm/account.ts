/**
 * Who is signed in and which applications they have. Optional by design: an engine without the
 * accounts routes (404, or a browser that cannot send credentials) leaves the app in the
 * single-visit flow it had before.
 */
import { useSyncExternalStore } from "react";
import { accounts, notAvailable, type ApplicationPreferences, type ApplicationSummary, type User } from "../api/accounts";
import { EngineError } from "../api/client";
import { probeAuth } from "../api/engineAuth";

export type AccountPhase = "probing" | "anonymous" | "signed-out" | "signed-in";

export interface AccountState {
  phase: AccountPhase;
  user: User | null;
  /** null until loaded; [] when signed in with none. */
  applications: ApplicationSummary[] | null;
  listError: string;
  loadingList: boolean;
}

let state: AccountState = { phase: "probing", user: null, applications: null, listError: "", loadingList: false };
const listeners = new Set<() => void>();
const set = (next: Partial<AccountState>) => {
  state = { ...state, ...next };
  for (const l of listeners) l();
};

let booted = false;

/** Probe once at start. 200 → signed in; 401 → accounts exist, not signed in; else anonymous. */
export function bootAccount() {
  if (booted) return;
  booted = true;
  void probeAuth().then(async (p) => {
    if (p.status === 200) {
      const body = p.body as { user?: User } | User | null;
      const user = (body && "user" in body ? body.user : (body as User | null)) ?? null;
      set({ phase: user ? "signed-in" : "anonymous", user });
      if (user) await refreshApplications();
      return;
    }
    set({ phase: p.status === 401 ? "signed-out" : "anonymous" });
  });
}

export async function refreshApplications() {
  if (state.phase !== "signed-in") return;
  set({ loadingList: true, listError: "" });
  try {
    const applications = await accounts.applications();
    set({ applications, loadingList: false });
  } catch (e) {
    if (notAvailable(e)) set({ applications: null, loadingList: false, phase: "anonymous" });
    else set({ loadingList: false, listError: e instanceof EngineError ? e.detail : "The list did not load." });
  }
}

/** Patch one row locally after an action (submit, read), before the next refresh. */
export function patchApplication(id: string, patch: Partial<ApplicationSummary>) {
  if (!state.applications) return;
  set({ applications: state.applications.map((a) => (a.id === id ? { ...a, ...patch } : a)) });
}

const failure = (e: unknown, fallback: string) => (e instanceof EngineError ? e.detail : fallback);

/**
 * Pin, unpin, archive or restore one of the owner's applications. Only the server's answer changes
 * the list (no local-only success); the case itself, and any unsaved answers in it, are untouched.
 * Resolves to an error text, or null when saved.
 */
export async function setApplicationPreferences(id: string, patch: ApplicationPreferences): Promise<string | null> {
  try {
    const saved = await accounts.preferences(id, patch);
    patchApplication(id, saved);
    return null;
  } catch (e) {
    return failure(e, "That didn’t save.");
  }
}

/** Delete an owned application for good. The row leaves the list only after the server's 204. */
export async function deleteApplication(id: string): Promise<string | null> {
  try {
    await accounts.deleteCase(id);
  } catch (e) {
    return failure(e, "It wasn’t deleted.");
  }
  if (state.applications) set({ applications: state.applications.filter((a) => a.id !== id) });
  return null;
}

/** The current state outside React (route tables, sign-in actions). */
export function getAccountState(): AccountState {
  return state;
}

export const getAccountPhase = (): AccountPhase => state.phase;

/** Tests, the stub harness, and the sign-in / onboarding / sign-out actions. */
export function setAccountState(next: Partial<AccountState>) {
  set(next);
}

function subscribe(l: () => void) {
  listeners.add(l);
  return () => listeners.delete(l);
}

export function useAccount(): AccountState {
  return useSyncExternalStore(subscribe, () => state, () => state);
}

export function initials(name: string | null | undefined, email?: string): string {
  const src = (name || email || "").trim();
  if (!src) return "";
  const parts = src.split(/[\s@._-]+/).filter(Boolean);
  return ((parts[0]?.[0] ?? "") + (parts[1]?.[0] ?? "")).toUpperCase();
}
