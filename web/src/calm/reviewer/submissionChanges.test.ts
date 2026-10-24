import assert from "node:assert/strict";
import test from "node:test";
import { visibleSubmissionChanges } from "./submissionChanges";

test("old evidence description copies count once while history stays unchanged", () => {
  const facts = { field: "evidence.report.description", before: "Synthetic A", after: "Synthetic B" };
  const listing = { ...facts, field: "evidence.report.listing.description" };
  const legal = { field: "legal_description", before: "Lot A", after: "Lot C" };
  const history = [listing, legal, facts];
  assert.deepEqual(visibleSubmissionChanges(history), [legal, facts]);
  assert.deepEqual(history, [listing, legal, facts]);
});

test("a conflicting legacy listing or listing-only change remains reviewable", () => {
  const fact = { field: "evidence.report.description", before: "Synthetic A", after: "Synthetic B" };
  const conflict = { ...fact, field: "evidence.report.listing.description", after: "Different legacy value" };
  const onlyListing = { ...fact, field: "evidence.other.listing.description" };
  assert.deepEqual(visibleSubmissionChanges([fact, conflict, onlyListing]), [fact, conflict, onlyListing]);
});
