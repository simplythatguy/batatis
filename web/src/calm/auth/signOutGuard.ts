import { useSyncExternalStore } from "react";
import { failureText } from "../../api/client";

let saveBeforeLeaving: (() => Promise<string | null>) | null = null;
let state = { pending: false, error: "" };
let active: Promise<boolean> | null = null;
let lifetime = 0;
const listeners = new Set<() => void>();
const publish = (next: typeof state) => { state = next; for (const listener of listeners) listener(); };

export function registerSignOutGuard(save: () => Promise<string | null>) {
  saveBeforeLeaving = save;
  return () => { if (saveBeforeLeaving === save) saveBeforeLeaving = null; };
}

export function guardedSignOut(leave: () => Promise<void>): Promise<boolean> {
  if (active) return active;
  const token = lifetime;
  publish({ pending: true, error: "" });
  const promise = (async () => {
    try {
      const error = await saveBeforeLeaving?.();
      if (token !== lifetime) return false;
      if (error) { publish({ pending: false, error }); return false; }
      await leave();
      if (token === lifetime) publish({ pending: false, error: "" });
      return true;
    } catch (error) {
      if (token === lifetime) publish({ pending: false, error: failureText(error) });
      return false;
    }
  })();
  active = promise;
  void promise.finally(() => { if (active === promise) active = null; });
  return promise;
}

export const signOutStatus = () => state;
export function resetSignOutStatus() { lifetime++; active = null; publish({ pending: false, error: "" }); }
const subscribe = (listener: () => void) => { listeners.add(listener); return () => { listeners.delete(listener); }; };
export function useSignOutStatus() {
  return useSyncExternalStore(subscribe, signOutStatus, signOutStatus);
}
