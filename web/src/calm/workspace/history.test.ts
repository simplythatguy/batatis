import assert from "node:assert/strict";
import test from "node:test";
import { acceptedAI, EditCommits, HistoryQueue, historyEntry, inverseEntry, mergeHistory, type HistoryEntry } from "./history.ts";

const entry = (before: string, after: string, by: HistoryEntry["by"] = "you") => historyEntry("process.risk_assessment", "Risk", before, after, by)!;
test("blur commits coalesce a block's typing, skip no-ops and keep different blocks independent", () => {
  const entries: HistoryEntry[] = [], edits = new EditCommits(e => entries.push(e));
  edits.change("risk", "Risk", "Old", "O");
  edits.change("risk", "Risk", "O", "New risk");
  edits.change("owner", "Owner", "Ada", "Adele");
  edits.flush("risk");
  assert.deepEqual(entries.map(e => [e.block, e.before, e.after]), [["risk", "Old", "New risk"]]);
  edits.flush();
  assert.equal(entries[1].block, "owner");
  edits.change("risk", "Risk", "New risk", "New risk");
  edits.flush();
  assert.equal(entries.length, 2);
});
test("undo is an inverse change and never overwrites words changed since that entry", () => {
  const e = entry("before", "accepted", "ai");
  assert.equal(inverseEntry(e, "edited again"), null);
  const undo = inverseEntry(e, "accepted")!;
  assert.deepEqual([undo.before, undo.after, undo.by], ["accepted", "before", "restore"]);
  assert.equal(acceptedAI([e], e.block, "accepted"), e.at);
  assert.equal(acceptedAI([e, undo], e.block, "before"), undefined);
});
test("a failed history batch stays queued and a concurrent new entry is sent only in its own batch", async () => {
  const q = new HistoryQueue(), a = entry("a", "b"), b = entry("b", "c");
  q.add(a);
  await assert.rejects(q.flush(async () => { throw new Error("offline"); }));
  assert.equal(q.size, 1);
  const batches: string[][] = [];
  await q.flush(async entries => { batches.push(entries.map(e => e.id)); if (batches.length === 1) q.add(b); });
  assert.deepEqual(batches, [[a.id], [b.id]]);
  assert.equal(q.size, 0);
});
test("loaded and local history deduplicate ids, sort by time and retain the newest 300", () => {
  const entries = Array.from({ length: 305 }, (_, i) => ({ ...entry("a", "b"), at: new Date(i * 1000).toISOString() }));
  const merged = mergeHistory(entries, entries.slice(-20));
  assert.equal(merged.length, 300);
  assert.equal(merged[0].id, entries[5].id);
  assert.equal(merged.at(-1)?.id, entries.at(-1)?.id);
});

test("an idle block commits at 1.5 seconds after the most recent keystroke", t => {
  t.mock.timers.enable({ apis: ["setTimeout"] });
  const entries: HistoryEntry[] = [], edits = new EditCommits(e => entries.push(e));
  edits.change("risk", "Risk", "old", "a");
  t.mock.timers.tick(1200);
  edits.change("risk", "Risk", "a", "ab");
  t.mock.timers.tick(1499);
  assert.equal(entries.length, 0);
  t.mock.timers.tick(1);
  assert.deepEqual(entries.map(e => [e.before, e.after]), [["old", "ab"]]);
});

test("accepted AI provenance stays on a block through later applicant edits", () => {
  const ai = entry("before", "AI accepted", "ai"), edit = entry("AI accepted", "Applicant refined it");
  assert.equal(acceptedAI([ai, edit], ai.block, edit.after), ai.at);
});
