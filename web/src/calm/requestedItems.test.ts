import assert from "node:assert/strict";
import test from "node:test";
import { emptyCase } from "../intake.ts";
import { reducer } from "../model.ts";
import type { Gap } from "../types.ts";
import { requestedItemLabel, requestedItemRow, requestedMessageBody } from "./requestedItems.ts";

const item = { gap_id: "D04:legal_description", field: "section_b.legal_description", note: "Please add the legal description." };
const gap: Gap = { id: "detail-legalDescription", field: "legalDescription", label: "Legal description missing", severity: "blocking", href: "#/application?tab=B&focus=field-legalDescription" };

test("legacy body-only instructions and freeform comments retain their text", () => {
  const body = `Officer comment.\n\n- ${item.note}\n- Keep this freeform comment.\n1. ${item.note}\n\nReview and resubmit.`;
  assert.equal(requestedMessageBody(body, []), body, "no structured data means no text removal");
  assert.equal(requestedMessageBody(body, [item]), "Officer comment.\n\n- Keep this freeform comment.\n\nReview and resubmit.");
  const freeform = `Please consider this: ${item.note}\n- ${item.note} Keep the attached sketch too.`;
  assert.equal(requestedMessageBody(freeform, [item]), freeform, "do not remove prose or extended officer comments");
});

test("historical standalone bullets compare exact text with folded whitespace only", () => {
  assert.equal(requestedMessageBody("Note.\n\n• Please  add the legal description.", [item]), "Note.");
  assert.equal(requestedMessageBody("- A different instruction.", [item]), "- A different instruction.");
  assert.equal(requestedItemLabel({ field: "section_b.legal_description" }), "Legal description");
});

test("current gaps route by canonical field when the stored gap id changed", () => {
  const c = emptyCase("contractor");
  const row = requestedItemRow(c, [gap], item, true);
  assert.equal(row.state, "open");
  assert.equal(row.tone, "blocking");
  assert.equal(row.href, "#/application?focus=field-legalDescription");
  assert.equal(row.label, item.note);
});

test("saved answers await human confirmation, unsaved changes cannot claim it", () => {
  const c = reducer(emptyCase("contractor"), { type: "setDetail", field: "legalDescription", value: "Lot 7 Block 8 Plan 9", section: "B" });
  const pending = requestedItemRow(c, [], item, true);
  assert.equal(pending.state, "pending");
  assert.equal(pending.status, "Awaiting officer confirmation");
  assert.equal(pending.tone, "pending");
  assert.equal(requestedItemRow(c, [], item, false).state, "unsaved");
  assert.equal(requestedItemRow(c, [gap], item, true, true).state, "open", "a current gap wins over a populated field");
});

test("unknown custom instructions stay for review until a current check can support progress", () => {
  const c = emptyCase("contractor");
  const custom = { gap_id: "historical-custom", note: "Review the drawing legend as discussed." };
  assert.equal(requestedItemRow(c, [], custom, true).state, "review");
  assert.equal(requestedItemRow(c, [], custom, true).href, "#/application");
  assert.equal(requestedItemRow(c, [], custom, true, true).state, "pending");
  const warning = requestedItemRow(c, [{ ...gap, submissionBlocking: false }], item, true);
  assert.equal(warning.tone, "warning", "officer handoffs are not unconditional red applicant blockers");
});
