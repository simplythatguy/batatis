import assert from "node:assert/strict";
import test from "node:test";
import { componentHarness, nodes, text } from "../../scripts/component-harness.mjs";
import { draft, drafting } from "../../tests/applicant-drafts.fixture.ts";
import { statementDrafts, statementReview } from "../applicantDrafts.ts";
import { emptyCase } from "../intake.ts";
import { PROCESS_FACT, PROCESS_FIELDS } from "../model.ts";
import type { Case } from "../types.ts";

const statement = (id: string, field: string, title: string, over = {}) => ({ ...draft, id, field, title, text: `${title} wording.`, claims: [], questions: [], ...over });
const DRAFTS = [
  statement("d-rationale", "process.rationale", "Rationale"),
  statement("d-risk", "process.risk_assessment", "Risk assessment", { questions: [{ text: "Who lives next door?", routed_to: "applicant" }, { text: "Who signs the fire analysis?", routed_to: "professional" }] }),
  statement("d-mitigation", "process.mitigating_measures", "Mitigating measures"),
  statement("d-qualifications", "process.qualifications", "Qualifications", { text: "", questions: [{ text: "Who is responsible?", routed_to: "applicant" }] }),
];

/** The store as the card reads it, with decisions that commit, or refuse at a chosen draft. */
function store(over: { refuse?: string } = {}) {
  const s = {
    c: { ...emptyCase("homebuilder"), description: "Infill house" } as Case,
    engineId: "case-1", drafting: { ...structuredClone(drafting), drafts: structuredClone(DRAFTS) },
    draftingStale: false, draftActivity: { kind: "idle" }, draftingError: "",
    decisions: [] as string[],
    dispatch(action: { type: string; field: keyof Case["process"]; value: string }) {
      if (action.type === "setProcess") s.c = { ...s.c, process: { ...s.c.process, [action.field]: action.value } };
    },
    generateApplicantDrafts: async () => { s.decisions.push("generate"); return true; },
    async decideApplicantDraft(id: string, decision: string) {
      s.decisions.push(`${decision}:${id}`);
      if (id === over.refuse) { s.draftingError = "This statement was already answered."; return false; }
      const d = s.drafting.drafts.find((x) => x.id === id)!;
      d.status = decision === "accept" ? "accepted" : "rejected";
      const p = PROCESS_FIELDS.find((x) => PROCESS_FACT[x.id] === d.field)!;
      if (decision === "accept") s.c = { ...s.c, process: { ...s.c.process, [p.id]: d.text } };
      return true;
    },
  };
  return s;
}

const harness = (s: ReturnType<typeof store>) => componentHarness(new URL("./StatementReview.tsx", import.meta.url), "StatementReview", {
  "../applicantDrafts": { statementDrafts }, "../model": { PROCESS_FIELDS },
  "../store": { useCase: () => s }, "./begin": { useCurrentApplication: () => ({ locked: false }) },
  "./ApplicantDrafts": { DraftContent: function DraftContent() { return null; } }, "./icons": { Icon24: "Icon24" }, "./ui": { CIcon: "CIcon" },
});
const button = (tree: unknown, label: string) => nodes(tree, (n) => n.type === "button" && text(n) === label);
const rows = (tree: unknown) => nodes(tree, (n) => n.type === "li" && Boolean(nodes(n, (m) => m.type === "summary").length));

test("one screen lists all six statements; Accept all decides each drafted one in turn", async () => {
  const s = store();
  const h = await harness(s);
  let tree = await h.render();
  assert.equal(rows(tree).length, 6);
  assert.match(text(rows(tree)[0]), /Rationale.*Rationale wording\.Draft to review/);
  assert.match(text(rows(tree)[3]), /Assumptions and limitsNot written/, "a statement without a draft stays visible");
  await button(tree, "Accept all")[0].props.onClick();
  tree = await h.render();
  assert.deepEqual(s.decisions, ["accept:d-rationale", "accept:d-risk", "accept:d-mitigation"], "one request at a time; a gap-only draft has nothing to accept");
  assert.equal(button(tree, "Accept all").length, 0);
  assert.match(text(rows(tree)[1]), /Risk assessmentRisk assessment wording\.Written/);
  h.unmount();
});

test("a refused decision stops Accept all and says so; the rest stay waiting", async () => {
  const s = store({ refuse: "d-risk" });
  const h = await harness(s);
  let tree = await h.render();
  await button(tree, "Accept all")[0].props.onClick();
  tree = await h.render();
  assert.deepEqual(s.decisions, ["accept:d-rationale", "accept:d-risk"]);
  assert.equal(s.drafting.drafts.find((d) => d.id === "d-mitigation")?.status, "draft");
  const alert = nodes(tree, (n) => n.props?.role === "alert")[0];
  assert.match(text(alert), /Accepted 1 of 3\. The rest are still waiting\. This statement was already answered\./);
  assert.equal(button(tree, "Accept all").length, 1, "the remaining drafts can be accepted again");
  h.unmount();
});

test("gap answers join the statement after it is accepted; professional questions are routed, not asked", async () => {
  const s = store();
  const h = await harness(s);
  let tree = await h.render();
  assert.equal(nodes(rows(tree)[1], (n) => n.type === "input").length, 0, "nothing is appended before the wording is accepted");
  await button(tree, "Accept all")[0].props.onClick();
  tree = await h.render();
  const input = nodes(rows(tree)[1], (n) => n.type === "input");
  assert.equal(input.length, 1);
  assert.match(text(rows(tree)[1]), /For your professionalWho signs the fire analysis\?/);
  input[0].props.onChange({ target: { value: "A detached garage on the east lot." } });
  tree = await h.render();
  button(rows(tree)[1], "Add")[0].props.onClick();
  tree = await h.render();
  assert.equal(s.c.process.risk, "Risk assessment wording.\n\nA detached garage on the east lot.");
  assert.match(text(rows(tree)[1]), /AddedWho lives next door\?/);
  // A draft with no wording asks its questions straight away; the answer becomes the statement.
  const only = nodes(rows(tree)[5], (n) => n.type === "input")[0];
  only.props.onChange({ target: { value: "Jordan Lee, the owner." } });
  tree = await h.render();
  button(rows(tree)[5], "Add")[0].props.onClick();
  assert.equal(s.c.process.qualifications, "Jordan Lee, the owner.");
  h.unmount();
});

test("before any draft the card offers to draft; while drafting it shows progress", async () => {
  const s = store();
  s.drafting = null as unknown as typeof s.drafting;
  const h = await harness(s);
  let tree = await h.render();
  assert.equal(rows(tree).length, 6);
  button(tree, "Draft my case")[0].props.onClick();
  assert.deepEqual(s.decisions, ["generate"]);
  s.draftActivity = { kind: "generating" };
  tree = await h.render();
  assert.equal(button(tree, "Draft my case").length, 0);
  assert.match(text(nodes(tree, (n) => n.props?.role === "status")[0]), /Drafting your case/);
  s.draftActivity = { kind: "idle" };
  s.drafting = { ...structuredClone(drafting), drafts: structuredClone(DRAFTS) };
  s.draftingStale = true;
  tree = await h.render();
  assert.equal(button(tree, "Accept all").length, 0, "stale drafts are never accepted");
  assert.equal(button(tree, "Draft again").length, 1);
  h.unmount();
});

test("the review screen replaces the six cards only while drafting can run", () => {
  const record = { drafts: DRAFTS, stale: false };
  assert.equal(statementReview({ phase: "signed-in", readOnly: false, drafting: null, error: "" }), true, "nothing drafted yet: offer to draft");
  assert.equal(statementReview({ phase: "probing", readOnly: false, drafting: null, error: "" }), true, "no flicker while sign-in is checked");
  assert.equal(statementReview({ phase: "signed-out", readOnly: false, drafting: null, error: "" }), false);
  assert.equal(statementReview({ phase: "signed-in", readOnly: true, drafting: record, error: "" }), false);
  assert.equal(statementReview({ phase: "signed-in", readOnly: false, drafting: null, error: "Drafting is unavailable." }), false, "a failed drafting request (offline, no provider) falls back");
  assert.equal(statementReview({ phase: "signed-in", readOnly: false, drafting: record, error: "This statement was already answered." }), true, "a refused decision stays on the review");
  assert.equal(statementReview({ phase: "signed-in", readOnly: false, drafting: { drafts: [], stale: false }, error: "" }), false, "nothing drafted for the statements");
  const latest = statementDrafts({ drafts: [DRAFTS[0], { ...DRAFTS[0], id: "d-rationale-2" }] });
  assert.equal(latest.get("rationale")?.id, "d-rationale-2");
  assert.equal(latest.has("assumptions"), false);
});

test("while any draft waits, gap answers and own wording wait too, with one hint", async () => {
  const s = store();
  const h = await harness(s);
  let tree = await h.render();
  const hint = () => nodes(tree, (n) => n.props?.className === "cf-note" && /Accept or reject the drafts first/.test(text(n)));
  assert.equal(hint().length, 1);
  const gapInput = nodes(rows(tree)[5], (n) => n.type === "input")[0];
  assert.equal(gapInput.props.disabled, true, "a gap answer would make the waiting drafts stale");
  assert.equal(button(rows(tree)[5], "Add")[0].props.disabled, true);
  assert.equal(button(rows(tree)[3], "Write it")[0].props.disabled, true, "so would writing a statement");
  await button(rows(tree)[1], "Accept")[0].props.onClick();
  tree = await h.render();
  assert.equal(nodes(rows(tree)[1], (n) => n.type === "input")[0].props.disabled, true, "still held while others wait");
  assert.equal(button(rows(tree)[1], "Edit")[0].props.disabled, true);
  await button(tree, "Accept all")[0].props.onClick();
  tree = await h.render();
  assert.equal(hint().length, 0);
  assert.equal(nodes(rows(tree)[5], (n) => n.type === "input")[0].props.disabled, false);
  assert.equal(button(rows(tree)[3], "Write it")[0].props.disabled, false);
  s.draftingStale = true;
  s.drafting.drafts[0] = { ...s.drafting.drafts[0], id: "d-rationale-2", status: "draft" };
  s.c = { ...s.c, process: { ...s.c.process, rationale: "" } };
  tree = await h.render();
  assert.equal(button(rows(tree)[3], "Write it")[0].props.disabled, false, "stale drafts are drafted again, so writing is not held");
  h.unmount();
});

test("a gap answer is added once, even after leaving the review and coming back", async () => {
  const s = store();
  let h = await harness(s);
  let tree = await h.render();
  await button(tree, "Accept all")[0].props.onClick();
  const add = async () => {
    tree = await h.render();
    nodes(rows(tree)[1], (n) => n.type === "input")[0].props.onChange({ target: { value: "A detached garage on the east lot." } });
    tree = await h.render();
    button(rows(tree)[1], "Add")[0].props.onClick();
  };
  await add();
  h.unmount();
  // Coming back (or reloading) forgets which answers were added; the statement still holds it once.
  h = await harness(s);
  await add();
  assert.equal(s.c.process.risk, "Risk assessment wording.\n\nA detached garage on the east lot.");
  h.unmount();
  // An answer that merely appears inside the wording is still added as its own paragraph.
  h = await harness(s);
  tree = await h.render();
  nodes(rows(tree)[1], (n) => n.type === "input")[0].props.onChange({ target: { value: "garage" } });
  tree = await h.render();
  button(rows(tree)[1], "Add")[0].props.onClick();
  assert.equal(s.c.process.risk, "Risk assessment wording.\n\nA detached garage on the east lot.\n\ngarage");
  h.unmount();
});
