import assert from "node:assert/strict";
import test from "node:test";
import { componentHarness, nodes, text } from "../../../scripts/component-harness.mjs";
import * as packageView from "./packageView.ts";
import * as workspaceView from "./workspaceView.ts";
import * as requestDraft from "./requestDraft.ts";
import { reviewSession, workspaceFor } from "./tests/workspaceHarness.mjs";

const finding = { key: "legal", section: "B", field: "legal_description", label: "plan number", status: "not_found", severity: "blocking", routed_to: "applicant",
  message: "Your application has an unclear plan number.", problem: null, defect_class: null,
  citations: ["NBC(AE) 2023 p2, Div B, Sentence 9.10.9.16.(1) [PDF p.702]"], pointers: [
    { file: "form.pdf", page: 1, quote: "A complete quote. ".repeat(40), form_field: null, bbox: null },
    { file: "plan.pdf", page: 3, quote: "The second pointer", form_field: null, bbox: null },
  ] };
const state = { key: "legal", state: "verify", locked: false, reason: null, note: "", at: null, by_name: null };
const limits = { intro: 2000, item_text: 600, items: 50, text: 6000 };
const files = [{ name: "form.pdf", file_id: "form" }, { name: "plan.pdf", file_id: "plan" }];
const item = { key: "ir_legal", id: "ir_legal", finding_key: "legal", saved: true, text: "Please confirm the plan number.", included: false, target: { section: "B", field: "legal_description", label: "Section B · Legal description" } };
const step = { finding, state, item, own: false, where: "B · Legal description", value: "Lot 12", before: undefined };
const deps = { "./workspaceView": workspaceView, "./packageView": packageView };
const choice = (tree: unknown, label: string) => nodes(tree, (n) => n.type === "button" && n.props.className === "cf-choice" && text(n).includes(label))[0];

test("a finding is named in a few words from its own status and label", () => {
  assert.equal(workspaceView.findingTitle({ ...finding, status: "blank", label: "signature date" } as never), "Signature date is blank");
  assert.equal(workspaceView.findingTitle(finding as never), "Couldn’t read the plan number");
});

test("one finding shows every source quote in full, a chip per file, and stays unchosen while it needs a look", async () => {
  const h = await componentHarness(new URL("./FindingStep.tsx", import.meta.url), "FindingStep", deps, { document: { addEventListener() {}, removeEventListener() {} } });
  const tree = await h.render({ step, caseId: "c1", files, limits, editable: true, last: false, canBack: false, onCall() {}, onText() {}, onAddOwn() {}, onNext() {}, onBack() {} });
  assert.deepEqual(nodes(tree, (n) => n.type === "q").map(text), finding.pointers.map((p) => p.quote), "every quote, never cut");
  assert.deepEqual(nodes(tree, (n) => n.props?.fileId).map((n) => [n.props.fileId, n.props.page]), [["form", 1], ["plan", 3]]);
  assert.equal(choice(tree, "Ask for it").props["aria-pressed"], false);
  assert.equal(choice(tree, "Dismiss").props["aria-pressed"], false);
  h.unmount();
});

test("a locked finding can't be dismissed and says why; Dismiss records the call", async () => {
  const calls: unknown[] = [];
  const h = await componentHarness(new URL("./FindingStep.tsx", import.meta.url), "FindingStep", deps, { document: { addEventListener() {}, removeEventListener() {} } });
  const props = { step: { ...step, state: { ...state, locked: true } }, caseId: "c1", files, limits, editable: true, last: false, canBack: false,
    onCall: (e: unknown) => calls.push(e), onText() {}, onAddOwn() {}, onNext() {}, onBack() {} };
  let tree = await h.render(props);
  assert.equal(choice(tree, "Dismiss").props.disabled, true);
  assert.match(text(tree), /Required by the completeness rules/);
  tree = await h.render({ ...props, step });
  choice(tree, "Dismiss").props.onClick();
  assert.equal(JSON.parse(JSON.stringify(calls.at(-1))).state, "dismissed");
  h.unmount();
});

test("a finding with no drafted item offers Add to request instead of a dead Ask", async () => {
  const added: unknown[] = [];
  const h = await componentHarness(new URL("./FindingStep.tsx", import.meta.url), "FindingStep", deps, { document: { addEventListener() {}, removeEventListener() {} } });
  const tree = await h.render({ step: { ...step, item: undefined }, caseId: "c1", files, limits, editable: true, last: true, canBack: true,
    onCall() {}, onText() {}, onAddOwn: (f: unknown) => added.push(f), onNext() {}, onBack() {} });
  choice(tree, "Add to request").props.onClick();
  assert.equal(added.length, 1);
  assert.ok(nodes(tree, (n) => n.type === "button" && text(n).startsWith("Decide")).length, "the last finding leads to Decide");
  h.unmount();
});

test("Decide shows the server's text, never a local rendering, and Accept follows only the server's gate", async () => {
  const h = await componentHarness(new URL("./DecideStage.tsx", import.meta.url), "DecideStage", { "./workspaceView": workspaceView, "./requestDraft": requestDraft, "./queue": await import("./queue.ts") });
  const session = reviewSession(3);
  const draft = { state: { ...requestDraft.initialDraft(session), save: { kind: "dirty" } }, pending: true, problem: "", dispatch() {}, save: async () => {} };
  const choices = { canReturn: false, canAccept: false, canRefuse: true, why: "Save the request changes first.", busy: false, onReturn() {}, onAccept() {}, onRefuse() {} };
  const base = { session, applicant: "Mira", status: "in_review", decidedAt: null, editable: true, targets: [], questions: [], outcome: null, messages: null, unread: 0, messagesAsk: 0 };
  let tree = await h.render({ ...base, workspace: workspaceFor(3, 1, { tally: { required: 9, to_check: 0, verify: 0, dismissed: 0, rulebook: 0, asked: 2 } }), draft, choices });
  assert.equal(text(nodes(tree, (n) => n.type === "pre")[0]), "Exact server preview");
  assert.match(text(tree), /Return with 2 items/);
  assert.match(text(tree), /Save the request changes first\./, "why the decision waits is on screen");
  tree = await h.render({ ...base, workspace: workspaceFor(3, 1), draft: null, choices: { ...choices, canReturn: true, canAccept: true, why: "" } });
  assert.match(text(tree), /Ready to accept/);
  assert.equal(nodes(tree, (n) => n.type === "button" && text(n).includes("Accept"))[0].props.className.includes("is-primary"), true, "the one primary action follows the gate");
  h.unmount();
});
