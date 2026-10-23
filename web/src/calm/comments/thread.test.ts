import assert from "node:assert/strict";
import { test } from "node:test";
import type { Message } from "../../api/accounts.ts";
import { arrange, displayedIds, earlierStartsOpen, itemsRepeatBody, noticeLine, shouldMarkRead, unshownRequests } from "./thread.ts";

const officer = { id: "officer", name: "Morgan", role: "reviewer" as const };
const me = { id: "applicant", name: "Mira", role: "applicant" as const };
const msg = (id: string, minute: number, over: Partial<Message> = {}): Message => ({
  id, body: `body ${id}`, author: officer, items: [], kind: "message", created_at: `2026-10-22T12:${String(minute).padStart(2, "0")}:00Z`, read_by_me: false, ...over,
});

test("the newest decision leads; later correspondence follows in order; earlier history newest first", () => {
  const note = msg("n", 1);
  const firstReturn = msg("d1", 2, { kind: "decision", read_by_me: true });
  const status = msg("s", 3, { kind: "status", read_by_me: true });
  const refusal = msg("d2", 4, { kind: "decision" });
  const reply = msg("r", 5, { author: me, read_by_me: true });
  const follow = msg("f", 6);
  const t = arrange([follow, refusal, status, note, reply, firstReturn]);
  assert.equal(t.latest?.id, "d2");
  assert.deepEqual(t.since.map((m) => m.id), ["r", "f"]);
  assert.deepEqual(t.earlier.map((m) => m.id), ["s", "d1", "n"]);
});

test("without a decision the newest officer note leads; an applicant-only thread has no lead", () => {
  assert.equal(arrange([msg("a", 1), msg("b", 2)]).latest?.id, "b");
  const own = arrange([msg("x", 1, { author: me })]);
  assert.equal(own.latest, null);
  assert.deepEqual(own.earlier.map((m) => m.id), ["x"]);
});

test("every message is displayed, so an earlier unread note is never cleared unseen", () => {
  const t = arrange([msg("old", 1), msg("d", 2, { kind: "decision" }), msg("after", 3)]);
  assert.deepEqual([...displayedIds(t)].sort(), ["after", "d", "old"]);
});

test("read only when visible, for this application, with every unread on screen", () => {
  const messages = [msg("a", 1), msg("b", 2, { read_by_me: true }), msg("s", 3, { kind: "status" })];
  const all = new Set(["a", "b", "s"]);
  assert.equal(shouldMarkRead({ messages, displayed: all, visible: true, sameApplication: true }), true);
  assert.equal(shouldMarkRead({ messages, displayed: all, visible: false, sameApplication: true }), false, "hidden tab");
  assert.equal(shouldMarkRead({ messages, displayed: all, visible: true, sameApplication: false }), false, "another application now");
  assert.equal(shouldMarkRead({ messages, displayed: new Set(["b"]), visible: true, sameApplication: true }), false, "an unread one not shown");
  assert.equal(shouldMarkRead({ messages: null, displayed: all, visible: true, sameApplication: true }), false, "still loading");
  // Only status lines unread: nothing counted, nothing to clear.
  assert.equal(shouldMarkRead({ messages: [msg("s", 1, { kind: "status" })], displayed: new Set(["s"]), visible: true, sameApplication: true }), false);
});

test("the top notice is one short line per status, and nothing for drafts or accepted files", () => {
  assert.equal(noticeLine("returned"), "Returned for changes");
  assert.equal(noticeLine("refused"), "Refused · read-only");
  assert.equal(noticeLine("in_review"), "Information requested");
  assert.equal(noticeLine("draft"), null);
  assert.equal(noticeLine("accepted"), null);
});

test("an item list the message body already spells out is not listed again", () => {
  const spelled = msg("d", 1, { kind: "decision", body: "Please provide:\n1. Owner name\n2. Site address", items: [{ note: "Owner name", field: "owner_name" }, { note: "Site address", field: "civic_address" }] });
  const short = msg("e", 2, { kind: "decision", body: "Returned for administrative information.", items: [{ note: "Owner name", field: "owner_name" }] });
  assert.equal(itemsRepeatBody(spelled), true);
  assert.equal(itemsRepeatBody(short), false, "items the body doesn't spell out stay listed");
  assert.equal(itemsRepeatBody(msg("f", 3)), false);
});

test("a sent information request already in the thread as the officer's message is not shown twice", () => {
  const request = { intro: "To continue the administrative review, please provide the items below.", items: ["Owner name"], sent_at: "2026-10-22T12:05:00Z", sent_by_name: "Morgan" };
  const posted = msg("r", 5, { body: `${request.intro}\n\n1. Owner name` });
  assert.deepEqual(unshownRequests([request], [posted]), [], "the thread already shows it");
  assert.deepEqual(unshownRequests([request], [msg("x", 1)]), [request], "a request the thread lacks still shows");
  const blank = { ...request, intro: "  " };
  assert.deepEqual(unshownRequests([blank], [posted]), [blank], "an empty intro never matches by accident");
});

test("earlier history starts folded, unless it holds something unread (nothing unread is ever hidden)", () => {
  const t = arrange([msg("old", 1, { read_by_me: true }), msg("d", 2, { kind: "decision" })]);
  assert.equal(earlierStartsOpen(t, new Set(["d"])), false, "read history waits behind one click");
  const u = arrange([msg("old", 1), msg("d", 2, { kind: "decision" })]);
  assert.equal(earlierStartsOpen(u, new Set(["old", "d"])), true, "an unread earlier note is shown before the thread is marked read");
});
