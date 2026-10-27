import assert from "node:assert/strict";
import test from "node:test";
import type { QueueApplication } from "../../api/accounts.ts";
import { applicantLine, completenessView, filterQueue, reviewerCell, rowAction, sentLabel, sinceLabel, statusPill, tabCounts } from "./queue.ts";

const ME = "u-dana";
const OTHER = { reviewer_id: "u-jordan", reviewer_name: "Jordan Tran", claimed_at: "2026-10-21T09:00:00Z" };
const MINE = { reviewer_id: ME, reviewer_name: "Dana Ross", claimed_at: "2026-10-21T09:00:00Z" };
const row = (over: Partial<QueueApplication>): QueueApplication => ({
  id: "c", title: "Exterior stair riser height", applicant: { name: "Mira Kaur", applicant_type: "homebuilder" }, authority: "edmonton",
  status: "submitted", submitted_at: "2026-10-21T08:00:00Z", updated_at: "2026-10-21T08:00:00Z", completeness: null, claim: null,
  decision: null, unread_messages: 0, ...over,
});

const rows = [
  row({ id: "new" }),
  row({ id: "other", status: "in_review", claim: OTHER, title: "Basement suite egress window", applicant: { name: "Northline Builds", applicant_type: "contractor" } }),
  row({ id: "mine", status: "in_review", claim: MINE, submitted_at: "2026-10-21T10:00:00Z" }),
  row({ id: "ret", status: "returned", claim: MINE }),
  row({ id: "acc", status: "accepted", claim: OTHER }),
  row({ id: "ref", status: "refused", claim: MINE }),
];

test("tab counts and filters", () => {
  assert.deepEqual(tabCounts(rows, ME), { all: 6, new: 1, resubmitted: 0, mine: 2, returned: 1, accepted: 1, refused: 1 });
  assert.deepEqual(filterQueue(rows, "refused", "", ME).map(r => r.id), ["ref"]);
  assert.deepEqual(filterQueue(rows, "mine", "", ME).map((r) => r.id), ["mine", "ret"]);
  assert.deepEqual(filterQueue(rows, "all", "northline", ME).map((r) => r.id), ["other"]);
  assert.deepEqual(filterQueue(rows, "all", "contractor", ME).map((r) => r.id), ["other"]);
  assert.equal(filterQueue(rows, "all", "", ME)[0].id, "mine", "newest sent first");
  assert.equal(applicantLine(rows[1]), "Northline Builds · general contractor");
});

test("refusal has its own queue tab and final gate, even with a retained claim", () => {
  const refused = row({ id: "refused", status: "refused", claim: MINE, decision: { outcome: "refuse", by_name: "Dana Ross", at: "2026-10-22T10:00:00Z" } });
  // The shared rows already hold a refused application; this one has a recorded decision.
  const all = [...rows.filter((r) => r.status !== "refused"), refused];
  assert.deepEqual(tabCounts(all, ME), { all: 6, new: 1, resubmitted: 0, mine: 2, returned: 1, accepted: 1, refused: 1 });
  assert.deepEqual(filterQueue(all, "refused", "", ME), [refused]);
  assert.deepEqual(filterQueue(all, "returned", "", ME).map((r) => r.id), ["ret"]);
  assert.deepEqual(statusPill(refused.status, true), { label: "Refused", tone: "blocking" });
  assert.equal(rowAction(refused, ME), "view");

});

test("resubmissions have their own filter and await explicit review even with a kept reservation", () => {
  const revised = row({ submission_number: 2, claim: MINE });
  const unclaimed = row({ id: "unclaimed-revision", submission_number: 3 });
  assert.deepEqual(tabCounts([revised, unclaimed], ME), { all: 2, new: 0, resubmitted: 2, mine: 1, returned: 0, accepted: 0, refused: 0 });
  assert.equal(rowAction(revised, ME), "resume");
  assert.equal(rowAction(revised, OTHER.reviewer_id), "view");
  assert.equal(rowAction(unclaimed, ME), "claim");
  assert.deepEqual(statusPill("submitted", true, 2), { label: "Resubmitted", tone: "warning" });
  assert.deepEqual(statusPill("submitted", false, 3), { label: "Resubmitted", tone: "warning" });
});

test("claim state labels and row actions", () => {
  assert.deepEqual(reviewerCell(rows[0], ME), { name: null, label: "—", mine: false });
  assert.deepEqual(reviewerCell(rows[1], ME), { name: "Jordan Tran", label: "Jordan Tran", mine: false });
  assert.deepEqual(reviewerCell(rows[2], ME), { name: "Dana Ross", label: "You", mine: true });
  assert.deepEqual(rows.map((r) => rowAction(r, ME)), ["claim", "view", "open", "view", "view", "view"]);
  assert.deepEqual(statusPill("submitted", false), { label: "New", tone: "accent" });
  assert.deepEqual(statusPill("in_review", true), { label: "In review", tone: "warning" });
  assert.deepEqual(statusPill("returned", true), { label: "Returned", tone: "blocking" });
  assert.deepEqual(statusPill("accepted", true), { label: "Accepted", tone: "done" });
});



test("completeness ring from the row or from the gaps, never invented", () => {
  assert.deepEqual(completenessView({ answered: 9, total: 12 }, null), { pct: 75, label: "75%" });
  assert.deepEqual(completenessView(null, null), { pct: null, label: "—" });
  assert.deepEqual(completenessView(null, 0), { pct: 100, label: "Complete" });
  assert.deepEqual(completenessView(null, 2), { pct: 0, label: "2 missing" });
});



test("sent and since labels", () => {
  const now = new Date(2026, 9, 21, 15, 0).getTime();
  assert.equal(sentLabel(new Date(2026, 9, 21, 9, 12).toISOString(), now), "Today, 9:12 AM");
  assert.equal(sentLabel(new Date(2026, 9, 20, 9, 12).toISOString(), now), "Yesterday");
  assert.equal(sentLabel(new Date(2026, 9, 19, 9, 12).toISOString(), now), "Oct 19");
  assert.equal(sentLabel(null, now), "—");
  assert.equal(sinceLabel(new Date(2026, 9, 21, 14, 14).toISOString(), now), "since 2:14 PM");
});
