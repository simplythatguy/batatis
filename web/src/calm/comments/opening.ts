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

/** Open the native page for a captured case; confirm the rendered case before acknowledging it. */
export function openCommentsPage(caseId: string): Promise<boolean> {
  location.hash = `#/comments?case=${encodeURIComponent(caseId)}`;
  return new Promise((resolve) => {
    const finish = (opened: boolean) => {
      clearTimeout(timer);
      observer.disconnect();
      window.removeEventListener("hashchange", check);
      resolve(opened);
    };
    const check = () => {
      if (location.hash.split("?")[0] !== "#/comments") return finish(false);
      const shown = document.querySelector(".cf-comments[data-application-id]");
      if (shown?.getAttribute("data-application-id") === caseId) finish(true);
    };
    const observer = new MutationObserver(check);
    const timer = window.setTimeout(() => finish(false), 2000);
    observer.observe(document.body, { childList: true, subtree: true, attributes: true, attributeFilter: ["data-application-id"] });
    window.addEventListener("hashchange", check);
    check();
  });
}
