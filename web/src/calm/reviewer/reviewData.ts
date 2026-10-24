/** Account-scoped queue reads, shared by queue/detail and the existing notification poll. */
import { useSyncExternalStore } from "react";
import { QueueSessionChanged, review, type QueueApplication } from "../../api/accounts";
import { engine, EngineError } from "../../api/client";
import { accountSession, getAccountState, setAccountState, subscribeAccount } from "../account";
import { getNotificationsState, subscribeNotifications } from "../notifications/notifications";

export interface QueueState {
  phase: "idle" | "loading" | "ready" | "error";
  rows: QueueApplication[];
  error: string;
  /** Blocking gap count per case id (from GET /cases/{id}/gaps), filled lazily. */
  blocking: Record<string, number>;
}

const empty = (): QueueState => ({ phase: "idle", rows: [], error: "", blocking: {} });
let state = empty();
const listeners = new Set<() => void>();
const set = (next: Partial<QueueState>) => {
  state = { ...state, ...next };
  for (const l of listeners) l();
};

let owner = accountSession();
let generation = 0;
let controller: AbortController | null = null;
let inflight: Promise<void> | null = null;
let patches = new Map<string, Partial<QueueApplication>>();
let seen = new Set<string>();
const asked = new Map<string, string>();
const reviewer = () => {
  const { phase, user } = getAccountState();
  return phase === "signed-in" && user?.role === "reviewer" && Boolean(user.authority);
};

subscribeAccount(() => {
  if (owner === accountSession()) return;
  owner = accountSession();
  generation++;
  controller?.abort();
  controller = null;
  inflight = null;
  patches = new Map();
  asked.clear();
  seen.clear();
  state = empty();
  for (const l of listeners) l();
});

subscribeNotifications(() => {
  const notes = getNotificationsState();
  if (!reviewer() || notes.phase !== "ready") return;
  const keys = notes.items.map(n => JSON.stringify([n.id, n.created_at, n.status]));
  const fresh = keys.some(key => !seen.has(key));
  seen = new Set(keys);
  // Read markers are not queue events. No second polling timer.
  if (fresh && listeners.size) void loadQueue(true);
});

export function loadQueue(refresh = false): Promise<void> {
  if (!reviewer()) return Promise.resolve();
  if (inflight && !refresh) return inflight;
  controller?.abort();
  const ctl = new AbortController(), token = ++generation, session = accountSession();
  const overlay = new Map<string, Partial<QueueApplication>>();
  patches = overlay;
  controller = ctl;
  const current = () => token === generation && session === accountSession() && reviewer();
  if (state.phase !== "ready") set({ phase: "loading", error: "" });
  const user = getAccountState().user!;
  const request = review.queue(ctl.signal, { id: user.id, authority: user.authority })
    .then(rows => {
      if (!current()) return;
      const fresh = rows.map(row => ({ ...row, ...overlay.get(row.id) }));
      const ids = new Set(fresh.map(row => row.id));
      set({ phase: "ready", rows: fresh, error: "", blocking: Object.fromEntries(Object.entries(state.blocking).filter(([id]) => ids.has(id))) });
      void fillBlocking(fresh, ctl.signal, current);
    })
    .catch(e => {
      if (!current()) return;
      if (e instanceof EngineError && e.status === 401) {
        setAccountState({ phase: "signed-out", user: null });
        return;
      }
      if (e instanceof QueueSessionChanged) {
        asked.clear();
        set({ phase: "error", rows: [], blocking: {}, error: e.detail });
        return;
      }
      set({ phase: state.rows.length ? "ready" : "error", error: e instanceof EngineError ? e.detail : "The queue didn’t load." });
    })
    .finally(() => { if (inflight === request) inflight = null; });
  inflight = request;
  return request;
}

/** Pending queue responses overlay acknowledged actions, so they cannot undo a claim. */
export function patchRow(id: string, patch: Partial<QueueApplication>, session = accountSession()) {
  if (session !== accountSession() || !reviewer()) return;
  patches.set(id, { ...patches.get(id), ...patch });
  set({ rows: state.rows.map(r => r.id === id ? { ...r, ...patch } : r) });
}

export function setBlocking(id: string, n: number) {
  if (reviewer()) set({ blocking: { ...state.blocking, [id]: n } });
}

/** Re-check changed submissions/content, three reads at a time, within the same session. */
async function fillBlocking(rows: QueueApplication[], signal: AbortSignal, current: () => boolean) {
  const todo = rows.filter(row => asked.get(row.id) !== row.updated_at);
  const worker = async () => {
    for (let row = todo.shift(); row && current(); row = todo.shift()) {
      try {
        const gaps = await engine.gaps(row.id, signal);
        if (!current()) return;
        asked.set(row.id, row.updated_at);
        setBlocking(row.id, gaps.filter(g => g.severity === "blocking").length);
      } catch { /* A later notification or manual refresh can retry. */ }
    }
  };
  await Promise.all([worker(), worker(), worker()]);
}

function subscribe(l: () => void) {
  listeners.add(l);
  return () => listeners.delete(l);
}

export function useQueue(): QueueState {
  return useSyncExternalStore(subscribe, getQueueState, getQueueState);
}

export const getQueueState = () => state;
