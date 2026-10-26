import assert from "node:assert/strict";
import test from "node:test";
import { componentHarness, nodes, text } from "../../../scripts/component-harness.mjs";
import * as packageView from "./packageView.ts";

const base = { case_id: "c1", outcome: "accept", decided_at: "2026-10-26T10:00:00Z", issued_on: null, issued_by_name: null, due_date: null, days_remaining: null,
  sent: false, sent_at: null, sent_by_name: null, overdue: false, record_package: { send_to_council: [{ label: "Variance copy" }], retain_on_file: [], basis: [], note: "" } };

test("acceptance shows technical review next; refusal has no Council copy", async () => {
  const h = await componentHarness(new URL("./CloseOutPanel.tsx", import.meta.url), "CloseOutPanel", { "./packageView": packageView });
  let tree = await h.render({ c: base });
  assert.match(text(tree), /Administratively complete · technical review next/);
  assert.match(text(tree), /Variance not issued yet/);
  assert.doesNotMatch(text(tree), /Send to the Council|Due /);
  tree = await h.render({ c: { ...base, outcome: "refuse" } });
  assert.match(text(tree), /Refusal recorded/);
  assert.doesNotMatch(text(tree), /Variance not issued yet|Copy to the Council|Send/);
  h.unmount();
});

test("recording an issuance uses the picked date; Mark as sent appears only after issuance", async () => {
  const calls: string[] = [], changes: unknown[] = [];
  const issued = { ...base, issued_on: "2026-10-20", due_date: "2026-10-30", days_remaining: 4 };
  const h = await componentHarness(new URL("./CloseOutPanel.tsx", import.meta.url), "CloseOutDue", {
    "./packageView": packageView, "../DatePicker": { DatePicker: "DatePicker" },
    "../../api/packageReview": { packageReview: { recordIssued: async (_id: string, date: string) => { calls.push(date); return issued; } } },
  });
  const props = { c: base, canMark: true, onChange: (c: unknown) => changes.push(c) };
  let tree = await h.render(props);
  assert.equal(nodes(tree, n => n.type === "button" && text(n) === "Mark as sent").length, 0);
  nodes(tree, n => n.type === "button" && text(n) === "Record variance issued")[0].props.onClick(); tree = await h.render();
  nodes(tree, n => n.type === "DatePicker")[0].props.onChange("2026-10-20"); tree = await h.render();
  nodes(tree, n => n.type === "button" && text(n) === "Record date")[0].props.onClick(); tree = await h.render();
  assert.deepEqual(calls, ["2026-10-20"]); assert.equal(changes[0], issued);
  tree = await h.render({ ...props, c: issued });
  assert.ok(nodes(tree, n => n.type === "button" && text(n) === "Mark as sent").length);
  assert.match(text(tree), /Due Oct 30/);
  h.unmount();
});
