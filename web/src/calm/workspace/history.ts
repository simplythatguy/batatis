export interface HistoryEntry { id: string; at: string; block: string; label: string; before: string; after: string; by: "you" | "ai" | "restore" }
export const HISTORY_LIMIT = 300;
export const EDIT_IDLE_MS = 1500;
export const entryId = () => globalThis.crypto.randomUUID();

export function historyEntry(block: string, label: string, before: string, after: string, by: HistoryEntry["by"], at = new Date().toISOString()): HistoryEntry | null {
  return before === after ? null : { id: entryId(), at, block, label, before, after, by };
}
export function mergeHistory(...lists: readonly (readonly HistoryEntry[])[]): HistoryEntry[] {
  return [...new Map(lists.flat().map(e => [e.id, e])).values()].sort((a, b) => a.at.localeCompare(b.at)).slice(-HISTORY_LIMIT);
}
export function inverseEntry(entry: HistoryEntry, current: string): HistoryEntry | null {
  return current === entry.after ? historyEntry(entry.block, entry.label, current, entry.before, "restore") : null;
}
export function acceptedAI(entries: readonly HistoryEntry[], block: string, text: string): string | undefined {
  const latest = [...entries].reverse().find(e => e.block === block);
  return latest?.by === "ai" && latest.after === text ? latest.at : undefined;
}

/** The same entry ids survive retries. New entries arriving during a batch are never acknowledged early. */
export class HistoryQueue {
  private pending = new Map<string, HistoryEntry>();
  private running: Promise<void> | null = null;
  get size() { return this.pending.size; }
  add(entry: HistoryEntry) { this.pending.set(entry.id, entry); }
  flush(post: (entries: HistoryEntry[]) => Promise<unknown>): Promise<void> {
    if (this.running) return this.running;
    this.running = (async () => {
      while (this.pending.size) {
        const batch = [...this.pending.values()].slice(0, 30);
        await post(batch);
        for (const entry of batch) this.pending.delete(entry.id);
      }
    })().finally(() => { this.running = null; });
    return this.running;
  }
}

/** Coalesce typing per block; composition is controlled by the editor and never scheduled mid-IME. */
export class EditCommits {
  private edits = new Map<string, { label: string; before: string; after: string; timer: ReturnType<typeof setTimeout> }>();
  private commit: (entry: HistoryEntry) => void;
  constructor(commit: (entry: HistoryEntry) => void) { this.commit = commit; }
  change(block: string, label: string, before: string, after: string) {
    const previous = this.edits.get(block);
    if (previous) clearTimeout(previous.timer);
    this.edits.set(block, { label, before: previous?.before ?? before, after,
      timer: setTimeout(() => this.flush(block), EDIT_IDLE_MS) });
  }
  flush(block?: string) {
    for (const [id, value] of this.edits) {
      if (block !== undefined && id !== block) continue;
      clearTimeout(value.timer);
      this.edits.delete(id);
      const entry = historyEntry(id, value.label, value.before, value.after, "you");
      if (entry) this.commit(entry);
    }
  }
}

/** Kept for the current application visit even when a question card temporarily replaces the paper. */
export class HistoryJournal {
  readonly queue = new HistoryQueue();
  readonly edits = new EditCommits(entry => this.add(entry));
  private listeners = new Set<() => void>();
  private snapshot: { entries: HistoryEntry[]; pending: number } = { entries: [], pending: 0 };
  getSnapshot = () => this.snapshot;
  subscribe = (listener: () => void) => { this.listeners.add(listener); return () => { this.listeners.delete(listener); }; };
  private publish(entries: HistoryEntry[]) {
    this.snapshot = { entries, pending: this.queue.size };
    for (const listener of this.listeners) listener();
  }
  load(entries: readonly HistoryEntry[]) { this.publish(mergeHistory(entries, this.snapshot.entries)); }
  add(entry: HistoryEntry) { this.queue.add(entry); this.publish(mergeHistory(this.snapshot.entries, [entry])); }
  async flush(post: (entries: HistoryEntry[]) => Promise<unknown>) {
    try { await this.queue.flush(post); }
    finally { this.publish(this.snapshot.entries); }
  }
}
