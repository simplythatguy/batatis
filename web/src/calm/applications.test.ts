import assert from "node:assert/strict";
import test from "node:test";
import type { ApplicationSummary } from "../api/accounts.ts";
import { groupApplications, readOnly, statusLine } from "./applications.ts";

const NOW = Date.parse("2026-10-21T12:00:00Z");
const app = (over: Partial<ApplicationSummary>): ApplicationSummary => ({
  id: "c1", title: "NorthCore CX exterior sheathing board", status: "draft", authority: "edmonton",
  updated_at: "2026-10-21T11:59:30Z", submitted_at: null, completeness: { answered: 10, total: 16 },
  unread_messages: 0, reviewer: null, ...over,
});

test("status lines: draft, in review, returned with news, settled", () => {
  assert.deepEqual(statusLine(app({}), NOW), { text: "Draft · 63% · just now", tone: "grey", attention: false });
  assert.equal(statusLine(app({ completeness: null, updated_at: "2026-10-18T12:00:00Z" }), NOW).text, "Draft · 3 d ago");
  assert.equal(statusLine(app({ status: "in_review" }), NOW).text, "In review · Edmonton");
  assert.equal(statusLine(app({ status: "submitted", authority: null }), NOW).text, "Submitted");
  assert.deepEqual(statusLine(app({ status: "returned", unread_messages: 1 }), NOW), { text: "Returned · 1 new message", tone: "accent", attention: true });
  assert.equal(statusLine(app({ status: "returned", unread_messages: 3 }), NOW).text, "Returned · 3 new messages");
  assert.equal(statusLine(app({ status: "returned" }), NOW).text, "Returned · fix and resubmit");
  assert.equal(statusLine(app({ status: "accepted", authority: "calgary" }), NOW).text, "Accepted · Calgary");
});

test("the list groups settled applications and searches titles", () => {
  const apps = [
    app({ id: "a", title: "Old draft", updated_at: "2026-10-01T00:00:00Z" }),
    app({ id: "b", title: "Rooftop deck guard height", status: "accepted" }),
    app({ id: "c", title: "Hempcrete walls", status: "returned", updated_at: "2026-10-21T10:00:00Z" }),
    app({ id: "d", title: "Basement egress", status: "withdrawn" }),
  ];
  const g = groupApplications(apps);
  assert.deepEqual(g.active.map((a) => a.id), ["c", "a"]);
  assert.deepEqual(g.settled.map((a) => a.id).sort(), ["b", "d"]);
  assert.deepEqual(groupApplications(apps, "hemp").active.map((a) => a.id), ["c"]);
  assert.equal(readOnly("in_review"), true);
  assert.equal(readOnly("returned"), false);
  assert.equal(readOnly("draft"), false);
});

import { answerBlocks } from "./assistant/assistant.ts";

test("assistant answers split prose and quoted code text", () => {
  assert.deepEqual(answerBlocks("Cladding is the outer finish. The sentence says:\n> Gypsum sheathing, rigid insulation\n> shall not be used.\nSo if the nails only grip the foam, that departs."), [
    { kind: "p", text: "Cladding is the outer finish. The sentence says:" },
    { kind: "quote", text: "Gypsum sheathing, rigid insulation shall not be used." },
    { kind: "p", text: "So if the nails only grip the foam, that departs." },
  ]);
  assert.deepEqual(answerBlocks("One.\n\nTwo."), [{ kind: "p", text: "One." }, { kind: "p", text: "Two." }]);
});
