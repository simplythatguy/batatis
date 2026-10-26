import assert from "node:assert/strict";
import test from "node:test";
import { componentHarness, nodes, text } from "../../../scripts/component-harness.mjs";
import * as packageView from "./packageView.ts";
import * as workspaceView from "./workspaceView.ts";
import * as requestDraft from "./requestDraft.ts";
import { reviewSession, workspaceFor } from "./tests/workspaceHarness.mjs";

const finding = { key: "legal", section: "B", field: "legal_description", label: "plan number couldn’t be read", status: "not_found", severity: "blocking", routed_to: "officer",
  message: "Your application has an unclear plan number.", problem: null, defect_class: null,
  citations: ["NBC(AE) 2023 p2, Div B, Sentence 9.10.9.16.(1) [PDF p.702]"], pointers: [
    { file: "form.pdf", page: 1, quote: "A complete quote. ".repeat(40), form_field: null, bbox: null },
    { file: "plan.pdf", page: 3, quote: "The second pointer", form_field: null, bbox: null },
  ] };
const state = { key: "legal", state: "verify", locked: false, reason: null, note: "", at: null, by_name: null };
const limits = { intro: 2000, item_text: 600, items: 50, text: 6000 };
const files = [{ name: "form.pdf", file_id: "form" }, { name: "plan.pdf", file_id: "plan" }];

test("a finding shows every source in full, with its file and page, and stays required while unverified", async () => {
  const h = await componentHarness(new URL("./FindingCard.tsx", import.meta.url), "FindingCard", { "./workspaceView": workspaceView, "./packageView": packageView });
  const props = { finding, state, item: undefined, caseId: "c1", files, limits, editable: true, onDisposition() {}, onText() {} };
  let tree = await h.render(props);
  assert.match(text(tree), /Look first · still required/);
  nodes(tree, (n) => n.type === "button" && n.props["aria-expanded"] !== undefined)[0].props.onClick();
  tree = await h.render();
  assert.deepEqual(nodes(tree, (n) => n.type === "q").map(text), finding.pointers.map((p) => p.quote), "every quote, never cut");
  assert.deepEqual(nodes(tree, (n) => n.props?.fileId).map((n) => [n.props.fileId, n.props.page]), [["form", 1], ["plan", 3]]);
  assert.match(text(tree), /The application has an unclear plan number/, "read in the officer's voice");
  h.unmount();
});

test("a locked finding can't be dismissed and says why; Dismiss records a reason", async () => {
  const edits: unknown[] = [];
  const h = await componentHarness(new URL("./FindingCard.tsx", import.meta.url), "FindingCard", { "./workspaceView": workspaceView, "./packageView": packageView });
  const props = { finding: { ...finding, status: "blank" }, state: { ...state, state: "ask", locked: true }, item: undefined, caseId: "c1", files, limits, editable: true,
    onDisposition: (e: unknown) => edits.push(e), onText() {} };
  let tree = await h.render(props);
  assert.equal(nodes(tree, (n) => n.props?.["data-action"] === "dismiss")[0].props.disabled, true);
  assert.match(text(tree), /Required by the completeness rules/);
  tree = await h.render({ ...props, state: { ...state, state: "ask" } });
  nodes(tree, (n) => n.props?.["data-action"] === "dismiss")[0].props.onClick();
  tree = await h.render();
  assert.equal(JSON.stringify(edits.at(-1)), JSON.stringify({ key: "legal", state: "dismissed", reason: null, note: "" }));
  tree = await h.render({ ...props, state: { ...state, state: "dismissed" } });
  nodes(tree, (n) => n.type === "button" && text(n) === "I checked it")[0].props.onClick();
  assert.equal(JSON.parse(JSON.stringify(edits.at(-1))).reason, "checked");
  h.unmount();
});

test("the request shows the server's text, never a local rendering of unsaved edits", async () => {
  const h = await componentHarness(new URL("./RequestPanel.tsx", import.meta.url), "RequestPanel", { "./workspaceView": workspaceView, "./requestDraft": requestDraft, "./queue": await import("./queue.ts") });
  const session = reviewSession(3);
  const draft = { state: requestDraft.initialDraft(session), pending: false, problem: "", dispatch() {}, save: async () => {} };
  let tree = await h.render({ session, applicant: "Mira", draft, limits, asked: 1, targets: [], questions: [], editable: true });
  assert.equal(text(nodes(tree, (n) => n.type === "pre")[0]), "Exact server preview");
  const dirty = { ...draft, pending: true, state: { ...draft.state, save: { kind: "dirty" }, content: { ...draft.state.content, intro: "New unsaved text" } } };
  tree = await h.render({ session, applicant: "Mira", draft: dirty, limits, asked: 1, targets: [], questions: [], editable: true });
  assert.equal(text(nodes(tree, (n) => n.type === "pre")[0]), "Exact server preview");
  assert.ok(nodes(tree, (n) => n.props?.draft?.state?.save?.kind === "dirty").length, "the save state shows the unsaved edit");
  h.unmount();
});

test("decisions wait for saved edits, and Accept follows only the server's gate", () => {
  const ready = workspaceFor(3, 1, { gate: { can_accept: true, reason: "" }, tally: { required: 9, to_check: 0, verify: 0, dismissed: 0, rulebook: 0, asked: 2 } });
  assert.equal(workspaceView.workspaceDecision({ workspace: ready, editable: true, pending: false, busy: false }).canAccept, true, "the browser trusts gate.can_accept rather than recounting");
  const pending = workspaceView.workspaceDecision({ workspace: ready, editable: true, pending: true, busy: false });
  assert.deepEqual([pending.canAccept, pending.canReturn], [false, false]);
  const stale = workspaceView.workspaceDecision({ workspace: workspaceFor(3, 1, { current: false, gate: { can_accept: false, reason: "The application changed after this review." } }), editable: true, pending: false, busy: false });
  assert.equal(stale.canAccept, false);
  assert.equal(stale.acceptReason, "The application changed after this review.");
});

test("the decision bar names why Accept is off", async () => {
  const h = await componentHarness(new URL("./ReviewRail.tsx", import.meta.url), "DecisionBar", {});
  const d = { version: 3, savedAt: "saved 9:14 AM", asked: 5, busy: false, canReturn: true, returnWhy: "", canAccept: false, acceptWhy: "3 required items are open", canRefuse: true, onReturn() {}, onAccept() {}, onRefuse() {} };
  const tree = await h.render({ d });
  assert.equal(nodes(tree, (n) => n.type === "button" && text(n).includes("Accept"))[0].props.disabled, true);
  assert.ok(nodes(tree, (n) => n.type === "button" && text(n) === "Return with 5 items").length);
  assert.match(text(tree), /3 required items are open/);
  h.unmount();
});
