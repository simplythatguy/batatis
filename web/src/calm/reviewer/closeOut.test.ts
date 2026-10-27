import assert from "node:assert/strict";
import test from "node:test";
import { componentHarness, nodes, text } from "../../../scripts/component-harness.mjs";
import * as packageView from "./packageView.ts";

const base = { case_id: "c1", outcome: "accept", decided_at: "2026-10-26T10:00:00Z", issued_on: null, issued_by_name: null, due_date: null, days_remaining: null,
  sent: false, sent_at: null, sent_by_name: null, overdue: false,
  record_package: { send_to_council: [{ label: "Copy of the variance as issued", detail: "", present: true }], retain_on_file: [{ label: "Decision record", detail: "", present: true }], basis: [], note: "" } };
/** The text, plus step titles (the harness keeps child components as nodes with their props). */
const words = (tree: unknown) => [text(tree), ...nodes(tree, (n) => typeof n.props?.title === "string").map((n) => n.props.title)].join(" ");
const button = (tree: unknown, label: string) => nodes(tree, (n) => n.type === "button" && text(n).includes(label));

test("after an acceptance nothing is due until the variance is issued; a refusal sends nothing", async () => {
  const h = await componentHarness(new URL("./CloseOutPanel.tsx", import.meta.url), "CloseOutPanel", { "./packageView": packageView });
  let tree = await h.render({ c: base, canRecord: true, onChange() {} });
  assert.match(words(tree), /Variance not issued/);
  assert.doesNotMatch(text(tree), /Due |To send|Mark as sent/);
  tree = await h.render({ c: { ...base, outcome: "refuse" }, canRecord: true, onChange() {} });
  assert.doesNotMatch(words(tree), /Variance not issued|To send|Mark as sent/);
  h.unmount();
});

test("recording the issue date uses the picked date; Mark as sent appears only after issuance", async () => {
  const calls: string[] = [], changes: unknown[] = [];
  const issued = { ...base, issued_on: "2026-10-20", due_date: "2026-10-30", days_remaining: 4 };
  const h = await componentHarness(new URL("./CloseOutPanel.tsx", import.meta.url), "CloseOutPanel", {
    "./packageView": packageView, "../DatePicker": { DatePicker: "DatePicker" },
    "../../api/packageReview": { packageReview: { recordIssued: async (_id: string, date: string) => { calls.push(date); return issued; } } },
  });
  const props = { c: base, canRecord: true, onChange: (c: unknown) => changes.push(c) };
  let tree = await h.render(props);
  assert.equal(button(tree, "Mark as sent").length, 0);
  button(tree, "Record the issue date")[0].props.onClick(); tree = await h.render();
  nodes(tree, (n) => n.type === "DatePicker")[0].props.onChange("2026-10-20"); tree = await h.render();
  button(tree, "Save")[0].props.onClick(); tree = await h.render();
  assert.deepEqual(calls, ["2026-10-20"]);
  assert.equal(changes[0], issued);
  tree = await h.render({ ...props, c: issued });
  assert.ok(button(tree, "Mark as sent").length);
  assert.match(text(tree), /Due Oct 30/);
  h.unmount();
});

test("someone who didn't decide can read the close-out but not record anything", async () => {
  const h = await componentHarness(new URL("./CloseOutPanel.tsx", import.meta.url), "CloseOutPanel", { "./packageView": packageView });
  const tree = await h.render({ c: base, canRecord: false, onChange() {} });
  assert.equal(button(tree, "Record the issue date").length, 0);
  h.unmount();
});
