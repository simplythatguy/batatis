/**
 * Who is signed in and which applications they have. Optional by design: an engine without the
 * accounts routes (404, or a browser that cannot send credentials) leaves the app in the
 * single-visit flow it had before.
 */
import { useSyncExternalStore } from "react";
import { accounts, auth, notAvailable, type ApplicationPreferences, type ApplicationSummary, type User } from "../api/accounts";
import { EngineError } from "../api/client";
import { probeAuth } from "../api/engineAuth";
import { replaceAccountRequests } from "../api/requestLifetime";

export type AccountPhase = "probing" | "anonymous" | "signed-out" | "signed-in";

export interface AccountState {
  phase: AccountPhase;
  user: User | null;
  /** null until loaded; [] when signed in with none. */
  applications: ApplicationSummary[] | null;
  listError: string;
  loadingList: boolean;
  /** The server needs an access code to sign in: the sign-in page asks for one and nothing else. */
  codeLogin: boolean;
}

let state: AccountState = { phase: "probing", user: null, applications: null, listError: "", loadingList: false, codeLogin: false };
let session = 0;
let listRequest = 0;
let listController: AbortController | null = null;
let listPatches = new Map<string, Partial<ApplicationSummary>>();
const listeners = new Set<() => void>();
const set = (next: Partial<AccountState>) => {
  const changed = (next.phase !== undefined && next.phase !== state.phase) || (next.user !== undefined && next.user !== state.user);
  if (changed) {
    session++;
    listRequest++;
    listController?.abort();
    listController = null;
    next = { applications: null, loadingList: false, listError: "", ...next };
  }
  state = { ...state, ...next };
  if (changed) replaceAccountRequests();
  for (const l of listeners) l();
};

let booted = false;

/** Probe once at start. 200 → signed in; 401 → accounts exist, not signed in; else anonymous. */
export function bootAccount() {
  if (booted) return;
  booted = true;
  const token = session;
  void probeAuth().then(async (p) => {
    if (token !== session) return;
    if (p.status === 200) {
      const body = p.body as { user?: User } | User | null;
      const user = (body && "user" in body ? body.user : (body as User | null)) ?? null;
      set({ phase: user ? "signed-in" : "anonymous", user });
      const settled = session;
      if (user) void auth.signInMode().then((mode) => { if (settled === session) set({ codeLogin: mode === "code" }); }, () => {});
      if (user) await refreshApplications();
      return;
    }
    if (p.status !== 401) return set({ phase: "anonymous" });
    // The sign-in page is decided before anything draws, so a code-only server never flashes the Start page.
    const mode = await auth.signInMode().catch(() => "password" as const);
    if (token !== session) return;
    set({ phase: "signed-out", codeLogin: mode === "code" });
  });
}

export async function refreshApplications() {
  if (state.phase !== "signed-in") return;
  const token = session, request = ++listRequest;
  const controller = new AbortController();
  const patches = new Map<string, Partial<ApplicationSummary>>();
  listPatches = patches;
  listController?.abort();
  listController = controller;
  const current = () => token === session && request === listRequest && state.phase === "signed-in";
  set({ loadingList: true, listError: "" });
  try {
    const applications = await accounts.applications(controller.signal);
    if (!current()) return;
    set({ applications: applications.map(a => ({ ...a, ...patches.get(a.id) })), loadingList: false });
  } catch (e) {
    if (!current()) return;
    if (e instanceof EngineError && e.status === 401) {
      set({ phase: "signed-out", user: null });
      return;
    }
    if (notAvailable(e)) set({ applications: null, loadingList: false, phase: "anonymous", user: null });
    else set({ loadingList: false, listError: e instanceof EngineError ? e.detail : "The list did not load." });
  } finally {
    if (listController === controller) listController = null;
  }
}

/** Patch one row locally after an action (submit, read), before the next refresh. */
export function patchApplication(id: string, patch: Partial<ApplicationSummary>) {
  if (!state.applications) return;
  // A receipt overlays its unread count on the pending list, without discarding newer status.
  // A workflow acknowledgement invalidates an earlier list that could roll that status back.
  if (listController) listPatches.set(id, { ...listPatches.get(id), ...patch });
  if (patch.status !== undefined) listRequest++;
  set({ applications: state.applications.map((a) => (a.id === id ? { ...a, ...patch } : a)), ...(patch.status !== undefined ? { loadingList: false } : {}) });
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
    // 404: already deleted elsewhere, or not this account's; the list is re-read from the server.
    if (e instanceof EngineError && e.status === 404) {
      void refreshApplications();
      return "This application isn’t available any more.";
    }
    return failure(e, "It wasn’t deleted.");
  }
  if (state.applications) set({ applications: state.applications.filter((a) => a.id !== id) });
  return null;
}

/** Changes on sign-in, sign-out and onboarding, even when the same person signs back in. */
export const accountSession = () => session;

/** The current state outside React (route tables, sign-in actions). */
export function getAccountState(): AccountState {
  return state;
}

export const getAccountPhase = (): AccountPhase => state.phase;

/** Tests, the stub harness, and the sign-in / onboarding / sign-out actions. */
export function setAccountState(next: Partial<AccountState>) {
  set(next);
}

export function subscribeAccount(l: () => void) {
  listeners.add(l);
  return () => listeners.delete(l);
}

export function useAccount(): AccountState {
  return useSyncExternalStore(subscribeAccount, () => state, () => state);
}

export function initials(name: string | null | undefined, email?: string): string {
  const src = (name || email || "").trim();
  if (!src) return "";
  const parts = src.split(/[\s@._-]+/).filter(Boolean);
  return ((parts[0]?.[0] ?? "") + (parts[1]?.[0] ?? "")).toUpperCase();
}
