/**
 * A comments link for another application (`#/comments?case=<id>`) opens it through the shell's
 * guarded switch first. When that switch fails (a save failed, the application is gone or not
 * yours), the shell records why here, so the page says so instead of showing another file's thread.
 */
import { useSyncExternalStore } from "react";

let problem: { id: string; text: string } | null = null;
const listeners = new Set<() => void>();

export function setOpenProblem(next: { id: string; text: string } | null) {
  problem = next;
  for (const l of listeners) l();
}

export function useOpenProblem() {
  return useSyncExternalStore((l) => { listeners.add(l); return () => listeners.delete(l); }, () => problem, () => problem);
}
