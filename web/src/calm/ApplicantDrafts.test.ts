import assert from "node:assert/strict";
import test from "node:test";
import { componentHarness, nodes, text } from "../../scripts/component-harness.mjs";
import { draft, drafting } from "../../tests/applicant-drafts.fixture.ts";
import { draftPassages } from "../applicantDrafts.ts";
import { emptyCase } from "../intake.ts";
import { localField } from "../intakeFields.ts";
import type { AccountPhase } from "./account";

const sourceContext = { sources: drafting.sources, caseId: "case-drafts", c: { files: [], intake: undefined } };
const harness = (name: string, modules = {}) => componentHarness(new URL("./ApplicantDrafts.tsx", import.meta.url), name, {
  "../applicantDrafts": { draftPassages }, "../intakeFields": { localField }, "./ui": { CIcon: "CIcon" },
  "./account": { useAccount: () => ({ phase: "signed-in" }) },
  ...modules,
}, { URL });
const buttons = (tree: unknown, label: string) => nodes(tree, n => n.type === "button" && text(n) === label);

test("claims label assumptions and planned work; quotes are one native disclosure away with original links", async () => {
  const claim = await harness("DraftClaim");
  assert.match(text(await claim.render({ ...sourceContext, claim: draft.claims[0] })), /Assumption/);
  assert.match(text(await claim.render({ ...sourceContext, claim: draft.claims[1] })), /Planned work/);
  const sources = await harness("DraftSources");
  const first = await sources.render({ ...sourceContext, claim: draft.claims[0] });
  assert.equal(nodes(first, n => n.type === "details").length, 1);
  assert.equal(nodes(first, n => n.type === "details")[0].props.open, undefined);
  assert.match(text(first), /Sources 1Project description/);
  assert.equal(text(nodes(first, n => n.type === "blockquote")[0]), "Assume a dry location.\nKeep this exact excerpt.");
  const linked = await sources.render({ ...sourceContext, claim: draft.claims[1] });
  assert.equal(nodes(linked, n => n.type === "a")[0].props.href, "https://example.test/source.pdf");
  assert.match(text(linked), /p\. 2/);
  const untrusted = await sources.render({ ...sourceContext, sources: [{ ...drafting.sources[1], url: "javascript:alert(1)" }], claim: draft.claims[1] });
  assert.equal(nodes(untrusted, n => n.type === "a").length, 0);
  const missing = await sources.render({ ...sourceContext, sources: [], claim: draft.claims[0] });
  assert.match(text(missing), /Unavailable source \(description\)/);
  assert.equal(text(nodes(missing, n => n.type === "blockquote")[0]), draft.claims[0].sources[0].quote);
  const body = await harness("DraftContent");
  assert.match(text(await body.render({ ...sourceContext, draft })), /Still to answerFor your professionalWho will prepare the assessment\?/);
  assert.equal(nodes(await body.render({ ...sourceContext, draft }), n => n.type === "textarea" || n.type === "input").length, 0);
  const assembled = { ...draft, text: `Assumption: ${draft.claims[0].text}\n\nPlan: ${draft.claims[1].text}` };
  const prefixedBody = await body.render({ ...sourceContext, draft: assembled });
  const renderedClaims = [];
  for (const child of nodes(prefixedBody, n => typeof n.type === "function" && n.props.claim)) renderedClaims.push(text(await claim.render(child.props)));
  assert.equal(renderedClaims.filter(line => line.startsWith("Assumption:")).length, 1);
  assert.equal(renderedClaims.filter(line => line.startsWith("Plan:")).length, 1);
  assert.doesNotMatch(renderedClaims.join(""), /Planned work/);
  assert.equal(text(nodes(prefixedBody, n => n.props?.className === "cf-draft-wording")[0]), "", "prefixes do not remain as duplicated prose fragments");
  const inClaim = await claim.render({ ...sourceContext, claim: { ...draft.claims[1], text: `Plan: ${draft.claims[1].text}` } });
  assert.equal((text(inClaim).match(/Plan:/g) ?? []).length, 1);
  assert.doesNotMatch(text(inClaim), /Planned work/);
  for (const h of [claim, sources, body]) h.unmount();
});

test("the panel generates once per click, selects one draft, accepts/rejects through the store, and retains decided wording", async () => {
  const writes: unknown[] = [];
  let locked = false;
  const store = {
    c: { ...emptyCase("homebuilder"), description: "Unit description" }, engineId: "case-drafts", applicationIdentity: "unit-case",
    drafting: structuredClone(drafting), draftingStale: false, draftActivity: { kind: "idle" }, draftingError: "", submitting: false, saveStatus: "saved",
    generateApplicantDrafts: async () => { writes.push("generate"); },
    decideApplicantDraft: async (id: string, decision: string) => { writes.push([id, decision]); },
    retryApplicantDrafts: async () => { writes.push("retry"); },
  };
  const h = await harness("ApplicantDrafts", {
    "../store": { useCase: () => store }, "./begin": { useCurrentApplication: () => ({ locked }) },
    "../router": { useRoute: () => ({ params: new URLSearchParams() }) },
  });
  let tree = await h.render();
  assert.match(text(tree), /Draft/);
  assert.equal(nodes(tree, n => n.type === "article").length, 1);
  buttons(tree, "Draft my application")[0].props.onClick();
  buttons(tree, "Accept")[0].props.onClick();
  buttons(tree, "Reject")[0].props.onClick();
  assert.deepEqual(writes, ["generate", [draft.id, "accept"], [draft.id, "reject"]]);
  store.drafting = { ...store.drafting, drafts: [{ ...draft, status: "accepted" }] };
  tree = await h.render();
  assert.match(text(tree), /Accepted by you.*sources are retained/);
  assert.equal(buttons(tree, "Accept").length, 0);
  const content = nodes(tree, n => typeof n.type === "function" && n.props.draft)[0];
  assert.deepEqual(content.props.sources, drafting.sources);

  store.drafting = { ...store.drafting, drafts: [...store.drafting.drafts, { ...draft, id: "new-generation", title: "Fresh risk draft" }] };
  tree = await h.render();
  assert.equal(nodes(tree, n => n.type === "article")[0].props["aria-label"], "Fresh risk draft", "a new generation opens its fresh wording instead of leaving an older acceptance selected");
  assert.equal(nodes(tree, n => n.type === "article").length, 1);

  store.drafting = { ...store.drafting, drafts: [{ ...draft, id: "questions-only", title: "Qualifications", field: "process.qualifications", text: "", claims: [] }] };
  tree = await h.render();
  assert.equal(buttons(tree, "Accept")[0].props.disabled, true);
  assert.equal(buttons(tree, "Reject")[0].props.disabled, false);
  assert.match(text(tree), /No wording to accept/);
  buttons(tree, "Reject")[0].props.onClick();
  assert.deepEqual(writes.at(-1), ["questions-only", "reject"]);

  store.drafting = structuredClone(drafting);
  store.draftingStale = true;
  tree = await h.render();
  assert.equal(buttons(tree, "Accept")[0].props.disabled, true);
  assert.equal(buttons(tree, "Reject")[0].props.disabled, true);
  assert.equal(buttons(tree, "Draft my application")[0].props.disabled, false);
  assert.match(text(tree), /Written from older answers\. Draft again before you accept it\./);
  store.draftingStale = false;
  locked = true;
  tree = await h.render();
  for (const name of ["Draft my application", "Accept", "Reject"]) assert.equal(buttons(tree, name)[0].props.disabled, true);
  assert.match(text(tree), /read-only/);
  locked = false;
  store.draftActivity = { kind: "generating" };
  tree = await h.render();
  assert.match(text(tree), /a few minutes/);
  assert.equal(buttons(tree, "Accept")[0].props.disabled, true);
  store.draftActivity = { kind: "idle" };
  store.draftingError = "Drafting service unavailable.";
  tree = await h.render();
  assert.match(text(nodes(tree, n => n.props?.role === "alert")[0]), /Drafting service unavailable/);
  buttons(tree, "Try again")[0].props.onClick();
  assert.equal(writes.at(-1), "retry");
  h.unmount();
});

test("guidance loads only on disclosure and keeps reviewer prompts plus sourced precedent structure together", async () => {
  let reads = 0;
  const field = { id: "risk_assessment", label: "Risk", prompt: "Describe what may go wrong.", citation: "Source guidance",
    reviewer_looks_for: ["Identify affected people."], example: { label: "Structure example", must_address: ["Describe limits."], precedents: [
      { title: "Reference case", issuer: "Unit issuer", pdf_page: 4, url: "https://example.test/precedent.pdf", structure: "Explain the conditions.", edition: "Earlier edition" },
    ] } };
  const h = await harness("DraftGuidance", {
    "../store": { useCase: () => ({ engineId: "case-drafts", applicationIdentity: "unit-case" }) },
    "../api/client": { engine: { processFields: async () => { reads++; return [field]; } } },
  });
  let tree = await h.render({ field: "process.risk_assessment" });
  assert.equal(reads, 0);
  tree.props.onToggle({ currentTarget: { open: true } });
  tree = await h.render();
  assert.equal(reads, 1);
  assert.equal(nodes(tree, n => n.type === "details").length, 1);
  assert.match(text(tree), /Describe what may go wrong.*Identify affected people.*Explain the conditions/s);
  assert.match(text(tree), /scope, status and edition/);
  assert.equal(nodes(tree, n => n.type === "a")[0].props.href, "https://example.test/precedent.pdf");
  h.unmount();
});

test("anonymous and signed-out visitors see Sign in with disabled writes, while status reasons and sources stay available", async () => {
  const writes: unknown[] = [];
  let phase: AccountPhase = "anonymous", locked = false;
  const store = {
    c: { ...emptyCase("homebuilder"), description: "Unit description" }, engineId: "case-drafts", applicationIdentity: "unit-case",
    drafting: structuredClone(drafting), draftingStale: false, draftActivity: { kind: "idle" },
    draftingError: "Earlier request failed.", submitting: false, saveStatus: "saved",
    generateApplicantDrafts: async () => { writes.push("generate"); },
    decideApplicantDraft: async (id: string, decision: string) => { writes.push([id, decision]); },
    retryApplicantDrafts: async () => { writes.push("retry"); },
  };
  const h = await harness("ApplicantDrafts", {
    "../store": { useCase: () => store }, "./account": { useAccount: () => ({ phase }) },
    "./begin": { useCurrentApplication: () => ({ locked }) },
    "../router": { useRoute: () => ({ params: new URLSearchParams() }) },
  });
  const signIn = (tree: unknown) => nodes(tree, n => n.type === "a" && text(n) === "Sign in");
  for (const next of ["anonymous", "signed-out"] satisfies AccountPhase[]) {
    phase = next;
    const tree = await h.render();
    assert.match(text(tree), /Sign in to draft or decide application wording/);
    assert.equal(signIn(tree)[0].props.href, "#/signin");
    assert.equal(buttons(tree, "Try again").length, 0, "the authentication reason replaces retry");
    for (const label of ["Draft my application", "Accept", "Reject"]) {
      const button = buttons(tree, label)[0];
      assert.equal(button.props.disabled, true, `${next}: ${label}`);
      button.props.onClick();
    }
    assert.equal(writes.length, 0, `${next}: even a direct handler invocation cannot call the store`);
    const content = nodes(tree, n => typeof n.type === "function" && n.props.draft)[0];
    assert.deepEqual(content.props.sources, drafting.sources);
    assert.equal(content.props.draft.id, draft.id);
  }
  phase = "probing";
  let tree = await h.render();
  assert.match(text(tree), /Checking sign-in/);
  assert.equal(signIn(tree).length, 0);
  assert.equal(buttons(tree, "Draft my application")[0].props.disabled, true);

  phase = "signed-out";
  for (const state of ["read-only", "submitting", "gone", "busy"]) {
    locked = state === "read-only";
    store.submitting = state === "submitting";
    store.saveStatus = state === "gone" ? "gone" : "saved";
    store.draftActivity = { kind: state === "busy" ? "generating" : "idle" };
    tree = await h.render();
    assert.equal(signIn(tree).length, 0, `${state} keeps priority over the sign-in reason`);
    assert.match(text(tree), state === "gone" ? /deleted or expired/ : state === "busy" ? /a few minutes/ : /read-only/);
    for (const label of [state === "busy" ? "Drafting…" : "Draft my application", "Accept", "Reject", "Try again"]) {
      for (const button of buttons(tree, label)) { assert.equal(button.props.disabled, true); button.props.onClick(); }
    }
    assert.equal(writes.length, 0);
  }
  phase = "signed-in";
  locked = false;
  store.submitting = false;
  store.saveStatus = "saved";
  store.draftActivity = { kind: "idle" };
  tree = await h.render();
  assert.equal(signIn(tree).length, 0);
  for (const label of ["Draft my application", "Accept", "Reject"]) {
    const button = buttons(tree, label)[0];
    assert.equal(button.props.disabled, false);
    button.props.onClick();
  }
  assert.deepEqual(writes, ["generate", [draft.id, "accept"], [draft.id, "reject"]]);
  h.unmount();
});
