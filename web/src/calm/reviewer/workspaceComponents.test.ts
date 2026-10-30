import assert from "node:assert/strict";
import test from "node:test";
import { componentHarness, nodes, text } from "../../../scripts/component-harness.mjs";
import * as packageView from "./packageView.ts";
import * as workspaceView from "./workspaceView.ts";

const finding = { key: "legal", section: "B", field: "legal_description", label: "plan number", status: "not_found", severity: "blocking", routed_to: "applicant",
  message: "Your application has an unclear plan number.", problem: null, defect_class: null,
  citations: ["NBC(AE) 2023 p2, Div B, Sentence 9.10.9.16.(1) [PDF p.702]"], pointers: [
    { file: "form.pdf", page: 1, quote: "A complete quote. ".repeat(40), form_field: null, bbox: null },
    { file: "plan.pdf", page: 3, quote: "The second pointer", form_field: null, bbox: null },
  ] };
const files = [{ name: "form.pdf", file_id: "form" }, { name: "plan.pdf", file_id: "plan" }];
const state = (over = {}) => ({ key: "legal", state: "ask", locked: false, reason: null, note: "", at: null, by_name: null, ...over });
const deps = { "./workspaceView": workspaceView, "./packageView": packageView, "../usePresence": { usePresence: (open: boolean) => ({ mounted: open, leaving: false }) } };
const button = (tree: unknown, match: (n: { props: Record<string, unknown> }) => boolean) => nodes(tree, (n) => n.type === "button" && match(n))[0];
const json = (v: unknown) => JSON.parse(JSON.stringify(v));

test("a finding is named in a few words from its own status and label", () => {
  assert.equal(workspaceView.findingTitle({ ...finding, status: "blank", label: "signature date" } as never), "Signature date is blank");
  assert.equal(workspaceView.findingTitle(finding as never), "Couldn’t read the plan number");
});

test("a row opens in place to every source quote in full, with a chip per file", async () => {
  const h = await componentHarness(new URL("./OfficerReview.tsx", import.meta.url), "FindingRow", deps);
  const props = { row: { finding, state: state(), askable: true }, caseId: "c1", files, editable: true, onCall() {}, onAddOwn() {} };
  let tree = await h.render(props);
  assert.equal(nodes(tree, (n) => n.type === "q").length, 0, "the evidence waits one tap away");
  button(tree, (n) => n.props["aria-expanded"] !== undefined).props.onClick(); tree = await h.render();
  const evidence = nodes(tree, (n) => (n.type as { name?: string })?.name === "Evidence")[0];
  assert.ok(evidence, "opening the row shows its evidence");
  const shown = (evidence.type as (p: unknown) => unknown)(evidence.props);
  assert.deepEqual(nodes(shown, (n) => n.type === "q").map(text), finding.pointers.map((p) => p.quote), "every quote, never cut");
  assert.deepEqual(nodes(shown, (n) => n.props?.fileId).map((n) => [n.props.fileId, n.props.page]), [["form", 1], ["plan", 3]]);
  h.unmount();
});

test("✕ on a required item asks why, and the reason is the whole dismissal", async () => {
  const calls: unknown[] = [];
  const h = await componentHarness(new URL("./OfficerReview.tsx", import.meta.url), "FindingRow", deps);
  let tree = await h.render({ row: { finding, state: state(), askable: true }, caseId: "c1", files, editable: true, onCall: (e: unknown) => calls.push(e), onAddOwn() {} });
  button(tree, (n) => String(n.props["aria-label"] ?? "").startsWith("Don’t ask")).props.onClick(); tree = await h.render();
  assert.equal(calls.length, 0, "a required item never disappears without a reason");
  button(tree, (n) => text(n) === "I checked it").props.onClick();
  assert.deepEqual(json(calls), [{ key: "legal", state: "dismissed", reason: "checked", note: "" }]);
  h.unmount();
});

test("a locked item can't be dropped and says so; a look-first item offers Ask", async () => {
  const calls: unknown[] = [], own: unknown[] = [];
  const h = await componentHarness(new URL("./OfficerReview.tsx", import.meta.url), "FindingRow", deps);
  let tree = await h.render({ row: { finding, state: state({ locked: true }), askable: true }, caseId: "c1", files, editable: true, onCall() {}, onAddOwn() {} });
  assert.equal(button(tree, (n) => String(n.props["aria-label"] ?? "").startsWith("Don’t ask")), undefined);
  assert.match(text(tree), /Required/);
  tree = await h.render({ row: { finding, state: state({ state: "verify" }), askable: true }, caseId: "c1", files, editable: true, onCall: (e: unknown) => calls.push(e), onAddOwn: (f: unknown) => own.push(f) });
  button(tree, (n) => text(n).startsWith("Ask")).props.onClick();
  assert.equal(json(calls)[0].state, "ask");
  tree = await h.render({ row: { finding, state: state({ state: "verify" }), askable: false }, caseId: "c1", files, editable: true, onCall: (e: unknown) => calls.push(e), onAddOwn: (f: unknown) => own.push(f) });
  button(tree, (n) => text(n).startsWith("Ask")).props.onClick();
  assert.equal(own.length, 1, "with no drafted item, Ask writes the officer's own");
  h.unmount();
});

test("the review shows the headline, the list and only the actions it is given", async () => {
  const h = await componentHarness(new URL("./OfficerReview.tsx", import.meta.url), "OfficerReview", deps);
  const tree = await h.render({ headline: "Ask for 2 things.", lede: "", rows: [{ finding, state: state(), askable: true }], rulebook: [], dismissed: [], own: [],
    caseId: "c1", files, editable: true, targets: [], itemLimit: 600,
    sections: [{ id: "B", title: "Project", icon: "file", summary: "1 to ask", tone: "blocking" }],
    actions: null, onCall() {}, onAddOwn() {}, onAdd() {}, onOwnText() {}, onOwnTarget() {}, onOwnRemove() {}, onSection() {} });
  assert.match(text(tree), /Ask for 2 things\./);
  assert.equal(nodes(tree, (n) => (n.type as { name?: string })?.name === "FindingRow").length, 1);
  assert.equal(nodes(tree, (n) => n.type === "button" && /Accept|Return|Refuse/.test(text(n))).length, 0, "no decision without the gate's actions");
  h.unmount();
});

test("a recorded determination is dated like the rest of the app, not by the browser's locale string", async () => {
  // QA 2026-10-28: "QA4-REF-001 · recorded by qa4-officer · 10/28/2026, 7:45:31 PM".
  const queue = await import("./queue.ts");
  const at = "2026-10-20T01:45:31Z";
  const resolution = { required: true, scope: "the rated assembly", basis: "An engineer takes responsibility.", reference: "REF-1", by_name: "Officer", at };
  const screen = { resolution, required: "yes", mandatory_required: false };
  const h = await componentHarness(new URL("./ProfessionalRequirement.tsx", import.meta.url), "ProfessionalRequirement", {
    "../../api/client": { engine: { professional: async () => screen } }, "../../api/accounts": { AccountsError: class {} },
    "../ui": { Modal: () => null }, "./queue": queue,
  });
  const tree = await h.render({ c: { id: "c1", version: 3, professional_resolutions: [resolution] }, editable: false, busy: false, unresolved: false, onResolve: async () => {} });
  const line = text(tree);
  assert.ok(line.includes(`REF-1 · recorded by Officer · ${queue.sentLabel(at)}`), line);
  assert.ok(!line.includes(new Date(at).toLocaleString()), line);
});

test("the professional requirement is decided on its own row, and a drafted question is named by itself", async () => {
  const h = await componentHarness(new URL("./OfficerReview.tsx", import.meta.url), "FindingRow", deps);
  const professional = { ...finding, key: "professional_requirement:requirement_unresolved", field: "professional_requirement", label: "professional involvement" };
  let tree = await h.render({ row: { finding: professional, state: state({ state: "verify", locked: true }), askable: false }, caseId: "c1", files, editable: true,
    onCall() {}, onAddOwn() {}, action: { type: "button", props: { children: "Decide" }, key: null } });
  assert.equal(button(tree, (n) => text(n).startsWith("Ask")), undefined, "the officer decides it; it is not asked of the applicant");
  assert.match(text(tree), /Decide/);
  const question = { ...finding, key: "draft-question:draft_1:0", field: "drafting.questions.draft_1.0", label: "Open question from the drafted wording",
    message: "Who inspects the door closers, and how often?", status: "missing", severity: "warning" };
  tree = await h.render({ row: { finding: question, state: state({ key: question.key }), askable: true }, caseId: "c1", files, editable: true, onCall() {}, onAddOwn() {} });
  assert.match(text(tree), /Who inspects the door closers, and how often\?/);
  assert.doesNotMatch(text(button(tree, (n) => n.props["aria-expanded"] !== undefined && text(n).length > 0)), /Open question from the drafted wording/);
  h.unmount();
});

test("an unchecked relevance screen says so in plain words", () => {
  const view = packageView.officerFinding({ key: "section_c.relevance:presence", field: "section_c.relevance", label: "relevance of the cited provision", problem: "lookup_skipped",
    message: "Keyword screening was skipped for 9.10.11.2.(2) because no topic rule is available; relevance remains uncertain." });
  assert.equal(view.title, "Relevance of the cited provision");
  assert.doesNotMatch(view.note, /Keyword screening|topic rule/);
});
