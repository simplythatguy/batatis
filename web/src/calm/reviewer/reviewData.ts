/** The reviewer's queue and per-case blocking counts, shared by the queue table and the review page. */
import { useSyncExternalStore } from "react";
import { review, type QueueApplication } from "../../api/accounts";
import { engine, EngineError } from "../../api/client";

export interface QueueState {
  phase: "idle" | "loading" | "ready" | "error";
  rows: QueueApplication[];
  error: string;
  /** Blocking gap count per case id (from GET /cases/{id}/gaps), filled lazily. */
  blocking: Record<string, number>;
}

let state: QueueState = { phase: "idle", rows: [], error: "", blocking: {} };
const listeners = new Set<() => void>();
const set = (next: Partial<QueueState>) => {
  state = { ...state, ...next };
  for (const l of listeners) l();
};

let inflight: Promise<void> | null = null;

export function loadQueue(): Promise<void> {
  if (inflight) return inflight;
  if (state.phase !== "ready") set({ phase: "loading", error: "" });
  inflight = review
    .queue()
    .then((rows) => {
      set({ phase: "ready", rows, error: "" });
      void fillBlocking(rows.map((r) => r.id));
    })
    .catch((e) => set({ phase: state.rows.length ? "ready" : "error", error: e instanceof EngineError ? e.detail : "The queue didn’t load." }))
    .finally(() => {
      inflight = null;
    });
  return inflight;
}

/** Replace one row after a claim, release or decision, before the next refresh. */
export function patchRow(id: string, patch: Partial<QueueApplication>) {
  set({ rows: state.rows.map((r) => (r.id === id ? { ...r, ...patch } : r)) });
}

export function setBlocking(id: string, n: number) {
  set({ blocking: { ...state.blocking, [id]: n } });
}

const asked = new Set<string>();

/** Gap checks for rows without a count, three at a time (each runs the completeness checker). */
async function fillBlocking(ids: string[]) {
  const todo = ids.filter((id) => !asked.has(id));
  todo.forEach((id) => asked.add(id));
  const worker = async () => {
    for (let id = todo.shift(); id; id = todo.shift()) {
      try {
        const gaps = await engine.gaps(id);
        setBlocking(id, gaps.filter((g) => g.severity === "blocking").length);
      } catch {
        asked.delete(id);
      }
    }
  };
  await Promise.all([worker(), worker(), worker()]);
}

function subscribe(l: () => void) {
  listeners.add(l);
  return () => listeners.delete(l);
}

export function useQueue(): QueueState {
  return useSyncExternalStore(subscribe, () => state, () => state);
}
