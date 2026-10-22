import assert from "node:assert/strict";
import test from "node:test";
import type { QueueApplication } from "../../api/accounts.ts";
import { localDraft, decisionItems, messageProblem, returnableGaps } from "./decision.ts";
import { applicantLine, completenessView, decisionGate, filterQueue, reviewerCell, rowAction, sentLabel, sinceLabel, statusPill, tabCounts } from "./queue.ts";

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
];

test("tab counts and filters", () => {
  assert.deepEqual(tabCounts(rows, ME), { all: 5, new: 1, mine: 2, returned: 1, accepted: 1 });
  assert.deepEqual(filterQueue(rows, "mine", "", ME).map((r) => r.id), ["mine", "ret"]);
  assert.deepEqual(filterQueue(rows, "all", "northline", ME).map((r) => r.id), ["other"]);
  assert.deepEqual(filterQueue(rows, "all", "contractor", ME).map((r) => r.id), ["other"]);
  assert.equal(filterQueue(rows, "all", "", ME)[0].id, "mine", "newest sent first");
  assert.equal(applicantLine(rows[1]), "Northline Builds · general contractor");
});

test("claim state labels and row actions", () => {
  assert.deepEqual(reviewerCell(rows[0], ME), { name: null, label: "—", mine: false });
  assert.deepEqual(reviewerCell(rows[1], ME), { name: "Jordan Tran", label: "Jordan Tran", mine: false });
  assert.deepEqual(reviewerCell(rows[2], ME), { name: "Dana Ross", label: "You", mine: true });
  assert.deepEqual(rows.map((r) => rowAction(r, ME)), ["claim", "view", "open", "view", "view"]);
  assert.deepEqual(statusPill("submitted", false), { label: "New", tone: "accent" });
  assert.deepEqual(statusPill("in_review", true), { label: "In review", tone: "warning" });
  assert.deepEqual(statusPill("returned", true), { label: "Returned", tone: "blocking" });
  assert.deepEqual(statusPill("accepted", true), { label: "Accepted", tone: "done" });
});

test("only the current claimer decides; blocking gaps allow return only", () => {
  assert.deepEqual(decisionGate(rows[2], ME, 0), { canReturn: true, canAccept: true, reason: "" });
  assert.equal(decisionGate(rows[2], ME, null).canAccept, false); // completeness still loading or failed
  assert.equal(decisionGate(rows[2], ME, 2).canAccept, false);
  assert.equal(decisionGate(rows[2], ME, 2).canReturn, true);
  assert.match(decisionGate(rows[1], ME, 0).reason, /^Jordan Tran is reviewing this/);
  assert.match(decisionGate(rows[0], ME, 0).reason, /^Start reviewing/);
  assert.equal(decisionGate(rows[4], ME, 0).canReturn, false);
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
  assert.match(d, /- Owner name missing\n- Professional involvement not yet confirmed/);
  assert.doesNotMatch(d, /approv|complies|compliant|safe/i);
  assert.equal(localDraft([]), "");
  assert.match(messageProblem("short"), /At least 10 characters · 5 so far/);
  assert.equal(messageProblem("Please add the owner name."), "");
});
