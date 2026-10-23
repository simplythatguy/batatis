/**
 * Notifications for the signed-in person (GET /me/notifications). One store shared by the rail
 * bell and the #/notifications page. A server without the route (404) is "unavailable", not an error.
 */
import { useSyncExternalStore } from "react";
import { notAvailable, notifications as api, type AppNotification, type Role } from "../../api/accounts";
import { setAccountState } from "../account";

export type NotificationsPhase = "idle" | "loading" | "ready" | "unavailable" | "error";

export interface NotificationsState {
  phase: NotificationsPhase;
  items: AppNotification[];
  unread: number;
  /** Ids that were unread when the panel last opened; they stay highlighted while it is open. */
  fresh: string[];
}

let state: NotificationsState = { phase: "idle", items: [], unread: 0, fresh: [] };
const listeners = new Set<() => void>();
const set = (next: Partial<NotificationsState>) => {
  state = { ...state, ...next };
  for (const l of listeners) l();
};

let inflight: Promise<void> | null = null;

export function loadNotifications(): Promise<void> {
  if (state.phase === "unavailable") return Promise.resolve();
  if (inflight) return inflight;
  if (state.phase === "idle") set({ phase: "loading" });
  inflight = api
    .list()
    .then((r) => set({ phase: "ready", items: sortNewest(r.notifications), unread: r.unread }))
    .catch((e) => {
      const status = (e as { status?: number }).status;
      // The session ended: drop what the previous person could see and let the gate ask to sign in.
      if (status === 401) {
        set({ phase: "idle", items: [], unread: 0, fresh: [] });
        setAccountState({ phase: "signed-out", user: null, applications: null });
        return;
      }
      set(notAvailable(e) && status !== 0 ? { phase: "unavailable", items: [], unread: 0 } : { phase: state.items.length ? "ready" : "error" });
    })
    .finally(() => {
      inflight = null;
    });
  return inflight;
}

/** Opening the panel marks everything read on the server; the rows that were new stay marked for this view. */
export async function openedPanel(): Promise<void> {
  await loadNotifications();
  if (state.phase !== "ready") return;
  const fresh = state.items.filter((n) => !n.read).map((n) => n.id);
  set({ fresh });
  if (!state.unread && !fresh.length) return;
  try {
    await api.markAllRead();
    set({ unread: 0, items: state.items.map((n) => ({ ...n, read: true })) });
  } catch {
    /* the dot stays; the next poll tries again */
  }
}

let pollers = 0;
let timer = 0;
const onFocus = () => void loadNotifications();

/** Ref-counted polling (every minute while visible, and on window focus). Returns the stop function. */
export function startPolling(ms = 60_000): () => void {
  pollers++;
  void loadNotifications();
  if (pollers === 1) {
    timer = window.setInterval(() => { if (document.visibilityState === "visible") void loadNotifications(); }, ms);
    window.addEventListener("focus", onFocus);
  }
  return () => {
    pollers--;
    if (pollers === 0) {
      window.clearInterval(timer);
      window.removeEventListener("focus", onFocus);
    }
  };
}

export function resetNotifications() {
  state = { phase: "idle", items: [], unread: 0, fresh: [] };
  for (const l of listeners) l();
}

function subscribe(l: () => void) {
  listeners.add(l);
  return () => listeners.delete(l);
}

export function useNotifications(): NotificationsState {
  return useSyncExternalStore(subscribe, () => state, () => state);
}

/* —— Pure helpers —— */

export function sortNewest(items: AppNotification[]): AppNotification[] {
  return [...items].sort((a, b) => Date.parse(b.created_at) - Date.parse(a.created_at));
}

const VERB: Record<string, string> = {
  submitted: "sent",
  resubmitted: "resent",
  in_review: "started reviewing",
  returned: "returned",
  accepted: "accepted",
  refused: "refused",
  withdrawn: "withdrew",
};

/**
 * The row text ("Dana Ross returned Hempcrete walls", "Dana Ross sent a message about …").
 * Status events with a known status are worded here so the order reads naturally; anything
 * else uses the server's summary, then a generic fallback.
 */
export function notificationText(n: Pick<AppNotification, "summary" | "kind" | "status" | "actor" | "case_title">): string {
  const who = n.actor?.name?.trim();
  const title = n.case_title?.trim();
  if (n.kind === "status" && who && title && n.status && VERB[n.status]) {
    // A reviewer moving an application back to "submitted" released their claim; they did not send it.
    if (n.status === "submitted" && n.actor?.role === "reviewer") return `${who} stopped reviewing ${title}`;
    if (n.status === "accepted") return `${who} accepted ${title} as administratively complete`;
    return `${who} ${VERB[n.status]} ${title}`;
  }
  if (n.summary && n.summary.trim()) return n.summary.trim();
  if (n.kind === "message") return `${who || "Someone"} sent a message about ${title || "your application"}`;
  return `${who || "Someone"} updated ${title || "your application"}`;
}

/** Stable, unique React keys even when the server repeats an id (two events in the same second). */
export function rowKeys(items: Pick<AppNotification, "id">[]): string[] {
  const seen = new Map<string, number>();
  return items.map((n) => {
    const k = seen.get(n.id) ?? 0;
    seen.set(n.id, k + 1);
    return k ? `${n.id}#${k}` : n.id;
  });
}

/** Where a row leads: the review page for reviewers, the application for applicants. */
export function notificationHref(n: Pick<AppNotification, "case_id">, role: Role | null | undefined): string {
  const id = encodeURIComponent(n.case_id);
  return role === "reviewer" ? `#/review/${id}` : `#/application?case=${id}`;
}

/** "now", "5 min", "3 h", "Yesterday", "Oct 19". */
export function shortTime(iso: string, now = Date.now()): string {
  const t = Date.parse(iso);
  if (!Number.isFinite(t)) return "";
  const s = Math.max(0, Math.round((now - t) / 1000));
  if (s < 60) return "now";
  if (s < 3600) return `${Math.floor(s / 60)} min`;
  const d = new Date(t);
  const today = new Date(now);
  const startOfToday = new Date(today.getFullYear(), today.getMonth(), today.getDate()).getTime();
  if (t >= startOfToday) return `${Math.floor(s / 3600)} h`;
  if (t >= startOfToday - 86400000) return "Yesterday";
  return d.toLocaleDateString("en-US", { month: "short", day: "numeric" });
}
