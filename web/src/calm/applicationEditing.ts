import { useSyncExternalStore } from "react";

const pauses = new Set<symbol>();
const listeners = new Set<() => void>();
const publish = () => { for (const listener of listeners) listener(); };

export const applicationEditsPaused = () => pauses.size > 0;

/** Fence callbacks synchronously, before React disables the mounted editors. */
export function pauseApplicationEdits() {
  const token = Symbol();
  pauses.add(token); publish();
  return () => { if (pauses.delete(token)) publish(); };
}

/** Saved work (a finished job's output, its chained start) waits for the pause instead of being dropped. */
export function whenEditsResume(): Promise<void> {
  if (!applicationEditsPaused()) return Promise.resolve();
  return new Promise(resolve => {
    const check = () => { if (!applicationEditsPaused()) { listeners.delete(check); resolve(); } };
    listeners.add(check);
  });
}

export function useApplicationEditsPaused() {
  return useSyncExternalStore(listener => { listeners.add(listener); return () => { listeners.delete(listener); }; }, applicationEditsPaused, applicationEditsPaused);
}
