import assert from "node:assert/strict";
import test from "node:test";
import { componentHarness, nodes, text } from "../../../scripts/component-harness.mjs";
import * as packageView from "./packageView.ts";
import * as workspaceView from "./workspaceView.ts";
import { initialDraft } from "./requestDraft.ts";
import { reviewSession, workspaceFor } from "./tests/workspaceHarness.mjs";

const finding = { key: "legal", section: "B", field: "legal_description", label: "Plan number couldn’t be read", status: "not_found", severity: "blocking", routed_to: "officer", message: "Your application has an unclear plan number.",
  citations: ["NBC(AE) 2023 p2, Div B, Sentence 9.10.9.16.(1) [PDF p.702]"], pointers: [
    { file: "form.pdf", page: 1, quote: "A complete quote. ".repeat(40), form_field: null },
    { file: "plan.pdf", page: 3, quote: "The second pointer", form_field: null },
  ] };
const state = { key: "legal", state: "verify", locked: false, reason: null, note: "", at: null, by_name: null };
const limits = { intro: 2000, item_text: 600, items: 50, text: 6000 };

test("a finding exposes every full source, and a locked dismissal has a visible reason", async () => {
  const h = await componentHarness(new URL("./FindingCard.tsx", import.meta.url), "FindingCard", { "./workspaceView": workspaceView, "./packageView": packageView });
  const props = { finding, state, item: undefined, caseId: "c1", files: [{ name: "form.pdf", file_id: "form" }, { name: "plan.pdf", file_id: "plan" }], limits, editable: true, onDisposition() {}, onText() {} };
  let tree = await h.render(props);
  assert.match(text(tree), /Look first · still required/);
  nodes(tree, n => n.type === "button" && n.props["aria-expanded"] !== undefined)[0].props.onClick(); tree = await h.render();
  const quotes = nodes(tree, n => n.type === "q").map(text);
  assert.deepEqual(quotes, finding.pointers.map(p => p.quote));
  const links = nodes(tree, n => n.props?.fileId);
  assert.deepEqual(links.map(n => [n.props.fileId, n.props.page]), [["form", 1], ["plan", 3]]);
  assert.match(text(tree), /The application has an unclear plan number/);
  tree = await h.render({ ...props, state: { ...state, locked: true } });
  assert.equal(nodes(tree, n => n.props?.["data-action"] === "dismiss")[0].props.disabled, true);
  assert.match(text(tree), /Completeness rules still require this/);
  h.unmount();
});

test("the rail displays the server tally and saved text; unsaved typing disables decisions", async () => {
  const h = await componentHarness(new URL("./RequestRail.tsx", import.meta.url), "RequestRail", { "./workspaceView": workspaceView, "./queue": await import("./queue.ts") });
  const session = reviewSession(3);
  const workspace = workspaceFor(3, 1, { tally: { required: 9, to_check: 7, dismissed: 4, verify: 2, asked: 8, rulebook: 3 }, gate: { can_accept: true, reason: "" } });
  const props = { caseId: "c1", session, workspace, filter: "all", onFilter() {}, tab: "request", onTab() {},
    draft: { state: initialDraft(session), pending: false, problem: "", dispatch() {}, save: async () => {} }, editable: true, busy: false,
    targets: [], questions: [], messages: [], onMessages() {}, me: "officer", messageDraft: "", onMessageDraft() {}, onReturn() {}, onAccept() {}, onRefuse() {}, readOnlyReason: "", refreshMessages() {} };
  let tree = await h.render(props);
  assert.equal(nodes(tree, n => n.type === "pre").map(text)[0], session.information_request.text);
  assert.equal(nodes(tree, n => n.type === "button" && text(n) === "Accept")[0].props.disabled, false, "the browser trusts gate.can_accept rather than recounting the tally");
  assert.ok(nodes(tree, n => n.type === "button" && text(n) === "Return with 8 items").length);
  assert.match(text(tree), /2 look first/);
  tree = await h.render({ ...props, draft: { ...props.draft, pending: true, state: { ...props.draft.state, save: { kind: "dirty" }, content: { ...props.draft.state.content, intro: "New unsaved text" } } } });
  assert.equal(nodes(tree, n => n.type === "pre").map(text)[0], session.information_request.text, "a local rendering never replaces the server preview");
  assert.equal(nodes(tree, n => n.type === "button" && text(n) === "Accept")[0].props.disabled, true);
  assert.equal(nodes(tree, n => n.type === "button" && text(n) === "Return with 8 items")[0].props.disabled, true);
  assert.match(text(tree), /Save the request changes first/);
  h.unmount();
});

test("a stale review keeps a disabled decision foot with the server reason", async () => {
  const h = await componentHarness(new URL("./RequestRail.tsx", import.meta.url), "RequestRail", { "./workspaceView": workspaceView, "./queue": await import("./queue.ts") });
  const session = reviewSession(3);
  const workspace = workspaceFor(3, 1, { current: false, gate: { can_accept: false, reason: "The saved application changed after this review." } });
  const tree = await h.render({ caseId: "c1", session, workspace, filter: "all", onFilter() {}, tab: "request", onTab() {}, draft: null, editable: false, showDecision: true, busy: false, messages: [], me: "officer", readOnlyReason: "Changed · review again" });
  assert.equal(nodes(tree, n => n.type === "button" && text(n) === "Accept")[0].props.disabled, true);
  assert.ok(text(tree).includes(workspace.gate.reason));
  h.unmount();
});
