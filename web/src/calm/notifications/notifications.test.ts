import assert from "node:assert/strict";
import test from "node:test";
import { notificationHref, notificationText, rowKeys, shortTime, sortNewest } from "./notifications.ts";

const actor = { name: "Dana Ross", role: "reviewer" as const };

test("notification text reads naturally for status events and messages", () => {
  assert.equal(notificationText({ kind: "status", status: "returned", actor, case_title: "Hempcrete walls", summary: "" }), "Dana Ross returned Hempcrete walls");
  assert.equal(notificationText({ kind: "status", status: "in_review", actor, case_title: "Hempcrete walls", summary: "x" }), "Dana Ross started reviewing Hempcrete walls");
  assert.equal(
    notificationText({ kind: "status", status: "accepted", actor, case_title: "Rooftop deck", summary: "Dana Ross accepted as administratively complete Rooftop deck" }),
    "Dana Ross accepted Rooftop deck as administratively complete",
  );
  assert.equal(notificationText({ kind: "message", status: null, actor, case_title: "Hempcrete walls", summary: "Dana Ross sent a message" }), "Dana Ross sent a message");
  assert.equal(notificationText({ kind: "message", status: null, actor: null, case_title: null, summary: "" }), "Someone sent a message about your application");
  assert.equal(notificationText({ kind: "status", status: "submitted", actor: { name: "Mira Kaur", role: "applicant" }, case_title: "A", summary: "" }), "Mira Kaur sent A");
  assert.equal(notificationText({ kind: "status", status: "submitted", actor, case_title: "A", summary: "" }), "Dana Ross stopped reviewing A");
  assert.equal(notificationText({ kind: "status", status: "something_new", actor, case_title: "A", summary: "" }), "Dana Ross updated A");
});

test("rows lead to the review page for reviewers and the application for applicants", () => {
  assert.equal(notificationHref({ case_id: "case_1" }, "reviewer"), "#/review/case_1");
  assert.equal(notificationHref({ case_id: "case_1" }, "applicant"), "#/application?case=case_1");
});

test("duplicate ids still get unique keys; newest first", () => {
  assert.deepEqual(rowKeys([{ id: "a" }, { id: "a" }, { id: "b" }]), ["a", "a#1", "b"]);
  const s = sortNewest([
    { id: "1", created_at: "2026-10-20T10:00:00Z" },
    { id: "2", created_at: "2026-10-21T10:00:00Z" },
  ] as never);
  assert.deepEqual(s.map((n) => n.id), ["2", "1"]);
});

test("short times", () => {
  const now = new Date(2026, 9, 21, 15, 0).getTime();
  assert.equal(shortTime(new Date(2026, 9, 21, 14, 59, 30).toISOString(), now), "now");
  assert.equal(shortTime(new Date(2026, 9, 21, 14, 55).toISOString(), now), "5 min");
  assert.equal(shortTime(new Date(2026, 9, 21, 11, 0).toISOString(), now), "4 h");
  assert.equal(shortTime(new Date(2026, 9, 20, 11, 0).toISOString(), now), "Yesterday");
  assert.equal(shortTime(new Date(2026, 9, 12, 11, 0).toISOString(), now), "Oct 12");
});
