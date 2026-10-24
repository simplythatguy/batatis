import assert from "node:assert/strict";
import test from "node:test";
import type { Message } from "../../api/accounts";
import { mergeThreadMessages } from "./threadMessages.ts";

const message = (id: string, created_at: string, read_by_me = false): Message => ({
  id, created_at, read_by_me, body: id, kind: "message", items: [],
  author: { id: "officer", name: "Synthetic officer", role: "reviewer" },
});

test("an older thread snapshot retains a newly acknowledged notice once, in chronological order", () => {
  const first = message("first", "2026-10-22T08:00:00Z");
  const sent = message("sent", "2026-10-22T08:00:01Z", true);
  const colleague = message("colleague", "2026-10-22T01:00:00.500-07:00");
  const previous = [first, sent], incoming = [first, colleague];
  const merged = mergeThreadMessages(previous, incoming)!;
  assert.deepEqual(merged.map(m => m.id), ["first", "colleague", "sent"]);
  assert.deepEqual(mergeThreadMessages(merged, incoming), merged, "repeated old snapshots cannot duplicate messages");
  assert.deepEqual(previous, [first, sent]);
  assert.deepEqual(incoming, [first, colleague]);
});

test("read receipts are monotonic whichever acknowledgement arrives last", () => {
  const unread = message("notice", "2026-10-22T08:00:00Z");
  const read = { ...unread, read_by_me: true };
  assert.equal(mergeThreadMessages([read], [unread])![0].read_by_me, true);
  assert.equal(mergeThreadMessages([unread], [read])![0].read_by_me, true);
  assert.equal(unread.read_by_me, false, "merging does not mutate an older response");
});

test("a send already observed by a snapshot keeps one immutable id and server timestamp tie order", () => {
  const first = message("first", "2026-10-22T08:00:00Z");
  const sent = message("sent", first.created_at, true);
  assert.deepEqual(mergeThreadMessages([first, sent], [first, sent])!.map(m => m.id), ["first", "sent"]);
  assert.deepEqual(mergeThreadMessages([sent], [first])!.map(m => m.id), ["first", "sent"]);
  assert.equal(mergeThreadMessages(null, null), null);
  assert.deepEqual(mergeThreadMessages([sent], null), [sent], "a failed read preserves acknowledged history");
});
