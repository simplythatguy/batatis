/**
 * The code library's application context as hooks (the rules live in libraryContext.ts).
 *
 * On the library (`#/code…`, the palette opened there included) the context is the open application
 * unless the person chose None, or there is no application to read for: no open case, or a reviewer
 * (reviewers browse the code; they have no application of their own). Everywhere else (the
 * application's own screens, the code drawer on a question card) it is always the open application.
 */
import { createContext, useContext, useSyncExternalStore } from "react";
import type { ApplicationSummary } from "../api/accounts";
import { useCase } from "../store";
import { useAccount } from "./account";
import { libraryDetached, subscribeLibrary } from "./libraryContext";

export type CodeScope = "application" | "none";

const onLibrary = () => /^#\/code(?:[/?]|$)/.test(location.hash);
/** One window listener for every ring that asks, however many are on screen. */
const hashListeners = new Set<() => void>();
const onHash = () => { for (const l of hashListeners) l(); };
function subscribeHash(l: () => void) {
  if (!hashListeners.size) window.addEventListener("hashchange", onHash);
  hashListeners.add(l);
  return () => {
    hashListeners.delete(l);
    if (!hashListeners.size) window.removeEventListener("hashchange", onHash);
  };
}

/** The person chose None for the library (visit-local). */
export function useLibraryDetached(): boolean {
  return useSyncExternalStore(subscribeLibrary, libraryDetached, libraryDetached);
}

export function useCodeScope(): CodeScope {
  const library = useSyncExternalStore(subscribeHash, onLibrary, () => false);
  const detached = useLibraryDetached();
  const { phase } = useCase();
  const reviewer = useAccount().user?.role === "reviewer";
  if (!library) return "application";
  return detached || phase !== "case" || reviewer ? "none" : "application";
}

/** What the shell shares with the picker: the sidebar's rows and its guarded switch. */
export interface ApplicationSwitch {
  items: ApplicationSummary[];
  /** The open application's row id ("this-visit" before the engine has one), or null. */
  openId: string | null;
  /** The id being opened, while a switch runs. */
  opening: string | null;
  /** Resolves to an error text, or null once the application is open. */
  switchTo: (id: string) => Promise<string | null>;
}

export const ApplicationSwitchContext = createContext<ApplicationSwitch | null>(null);
export const useApplicationSwitch = () => useContext(ApplicationSwitchContext);
