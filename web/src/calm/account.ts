/**
 * Who is signed in and which applications they have. Optional by design: an engine without the
 * accounts routes (404, or a browser that cannot send credentials) leaves the app in the
 * single-visit flow it had before.
 */
import { useSyncExternalStore } from "react";
import { accounts, notAvailable, type ApplicationSummary, type User } from "../api/accounts";
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

/** Tests and the stub harness. */
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
