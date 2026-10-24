import assert from "node:assert/strict";
import test from "node:test";
import type { QueueApplication } from "../../api/accounts.ts";
import { localDraft, decisionItems, messageProblem, returnableGaps } from "./decision.ts";
import { applicantLine, completenessView, decisionGate, filterQueue, reviewerCell, rowAction, sentLabel, sinceLabel, statusPill, tabCounts, withPackage } from "./queue.ts";

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
  for (const blocking of [null, 0, 2]) {
    const gate = decisionGate(refused, ME, blocking);
    assert.deepEqual(gate, { canReturn: false, canAccept: false, canRefuse: false, reason: "Administrative refusal recorded. This application is closed and read-only." });
    assert.deepEqual(withPackage(gate, { state: "current", blocking: 0 }), gate);
  }
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
  assert.equal(decisionGate(revised, ME, 0).canAccept, false);
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

test("only the current claimer decides; blocking gaps hold acceptance while allowing return or refusal", () => {
  assert.deepEqual(decisionGate(rows[2], ME, 0), { canReturn: true, canAccept: true, canRefuse: true, reason: "" });
  assert.equal(decisionGate(rows[2], ME, null).canRefuse, true);
  assert.equal(decisionGate(rows[2], ME, 2).canRefuse, true);
  assert.equal(decisionGate(rows[1], ME, 0).canRefuse, false);
  assert.equal(decisionGate(rows[5], ME, 0).canRefuse, false);
  assert.equal(rowAction(rows[5], ME), "view");
  assert.equal(statusPill("refused", true).label, "Refused");
  assert.equal(decisionGate(rows[2], ME, null).canAccept, false); // completeness still loading or failed
  assert.equal(decisionGate(rows[2], ME, 2).canAccept, false);
  assert.equal(decisionGate(rows[2], ME, 2).canReturn, true);
  assert.match(decisionGate(rows[1], ME, 0).reason, /^Jordan Tran is reviewing this/);
  assert.match(decisionGate(rows[0], ME, 0).reason, /^Pick up/);
  assert.equal(decisionGate(rows[4], ME, 0).canReturn, false);
});

test("completeness ring from the row or from the gaps, never invented", () => {
  assert.deepEqual(completenessView({ answered: 9, total: 12 }, null), { pct: 75, label: "75%" });
  assert.deepEqual(completenessView(null, null), { pct: null, label: "—" });
  assert.deepEqual(completenessView(null, 0), { pct: 100, label: "Complete" });
  assert.deepEqual(completenessView(null, 2), { pct: 0, label: "2 missing" });
});

test("officer-owned professional determination points to the available action and retains acceptance hold", () => {
  assert.deepEqual(decisionGate(rows[2], ME, 1, true), {
    canReturn: true, canAccept: false, canRefuse: true,
    reason: "Record the professional determination below before accepting as complete.",
  });
  assert.match(decisionGate(rows[2], ME, 3, true).reason, /remaining 2 required items/);
  assert.match(decisionGate(rows[1], ME, 1, true).reason, /^Jordan Tran is reviewing/);
  assert.equal(decisionGate(rows[2], ME, null, true).canAccept, false);
});

test("sent and since labels", () => {
  const now = new Date(2026, 9, 21, 15, 0).getTime();
  assert.equal(sentLabel(new Date(2026, 9, 21, 9, 12).toISOString(), now), "Today, 9:12 AM");
  assert.equal(sentLabel(new Date(2026, 9, 20, 9, 12).toISOString(), now), "Yesterday");
  assert.equal(sentLabel(new Date(2026, 9, 19, 9, 12).toISOString(), now), "Oct 19");
  assert.equal(sentLabel(null, now), "—");
  assert.equal(sinceLabel(new Date(2026, 9, 21, 14, 14).toISOString(), now), "since 2:14 PM");
});

test("return items, the local draft and the message rule", () => {
  const gaps = [
    { id: "g1", section: "D" as const, field: "professional_requirement", message: "Professional involvement not yet confirmed", severity: "warning" as const },
    { id: "g2", section: "A" as const, field: "owner_name", message: "Owner name missing", severity: "blocking" as const },
    { id: "g3", section: "B" as const, field: "x", message: "Calgary has its own form", severity: "info" as const },
  ];
  assert.deepEqual(returnableGaps(gaps).map((g) => g.id), ["g2", "g1"]);
  assert.deepEqual(decisionItems(gaps, new Set(["g2"])), [{ gap_id: "g2", field: "owner_name", note: "Owner name missing" }]);
  const d = localDraft(["Owner name missing", "Professional involvement not yet confirmed"]);
  assert.match(d, /administratively complete/);
  assert.match(d, /requested items are listed below/);
  assert.doesNotMatch(d, /Owner name missing|Professional involvement not yet confirmed/);
  assert.doesNotMatch(d, /approv|complies|compliant|safe/i);
  assert.equal(localDraft([]), "");
  assert.match(messageProblem("short"), /At least 10 characters · 5 so far/);
  assert.equal(messageProblem("Please add the owner name."), "");
});
