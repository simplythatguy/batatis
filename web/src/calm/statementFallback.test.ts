import assert from "node:assert/strict";
import test from "node:test";
import { componentHarness, nodes, text } from "../../scripts/component-harness.mjs";
import { statementFallbackNote } from "../applicantDrafts.ts";
import { emptyCase } from "../intake.ts";
import { planFactAnswer, planInput } from "../intakeView.ts";
import { getGaps, reducer } from "../model.ts";
import type { Action } from "../model.ts";
import type { Case } from "../types.ts";
import * as deck from "./deck.ts";
import * as journey from "./journey.ts";
import * as calendarDate from "./calendarDate.ts";

const ERROR = "Drafting is unavailable right now. Try again in a minute.";
const varianceCase = (): Case => reducer({ ...emptyCase("owner"), description: "A house with a thinner wall." }, { type: "setDetail", field: "journey.route", value: "variance", section: "B" });

/** The question deck after "Draft my case" failed: the six statement cards are back. */
async function mounted(initial: Case, focus: string) {
  let c = initial;
  let session = { queue: [] as string[], index: 0, seen: [] as string[], packages: {}, ruleUnsure: [], authorityUnsure: false };
  const updateSession = (patch) => { session = { ...session, ...(typeof patch === "function" ? patch(session) : patch) }; };
  const dispatch = (action: Action) => { c = reducer(c, action); };
  const h = await componentHarness(new URL("./QuestionDeck.tsx", import.meta.url), "CaseDeck", {
    "../store": { useCase: () => ({ c, dispatch, gaps: getGaps(c), engineId: "case-test", sectionCLookup: { source: "live" }, reading: { intake: "done", identify: "done", busy: null }, drafting: null, requestCheck() {} }) },
    "../screens/CodeCheck": { useCandidateAnswer: () => ({ onAnswer() {}, decisionNoteFor: () => "" }) },
    "./deck": deck,
    "./journey": journey,
    "./calendarDate": calendarDate,
    "../intakeView": { NOT_SURE: "Not sure", planFactAnswer, planInput },
    "../model": await import("../model.ts"),
    "../intakeFields": await import("../intakeFields.ts"),
    "../provisions": await import("../provisions.ts"),
    "./session": { getSession: () => session, useSession: () => session, updateSession },
    "./begin": { useCurrentApplication: () => ({ app: { status: "draft" }, locked: false, readOnly: false }) },
    "./useDeckExtras": { useDeckExtras: () => ({ options: { statements: "cards" }, extras: { failed: {}, checklists: null }, fallbackNote: statementFallbackNote({ phase: "signed-in", readOnly: false, drafting: null, error: ERROR }) }) },
    "./account": { useAccount: () => ({ user: { id: "test", role: "applicant" } }) },
    "./useQuestionDraft": { useQuestionDraft: (_a, _g, _e, _k, saved) => ({ value: saved, setValue() {}, choices: {}, setChoices() {}, conflict: null, confirmValue() {} }) },
    "./assistant/assistant": { setAssistantContext() {} },
    "./assistant/questionContext": { questionContext: () => ({}) },
    "./applications": { readOnlyStatus: () => ({}) },
    "../api/sync": { engineGeneration: () => 1 },
    "./icons": { Icon24: "icon" },
  }, { location: { hash: "#/questions", replace() {} }, window: {}, document: { addEventListener() {}, removeEventListener() {} } });
  const render = async () => { await h.render({ focus, codeFirst: false }); return h.render({ focus, codeFirst: false }); };
  return { h, render };
}

const alerts = (tree) => nodes(tree, (n) => n.props?.role === "alert").map(text);

test("a failed Draft my case says why once, on the first statement card it falls back to", async () => {
  let m = await mounted(varianceCase(), "field-rationale");
  let tree = await m.render();
  assert.equal(nodes(tree, (n) => n.type?.name === "CardBody")[0].props.item.key, "field-rationale");
  assert.ok(alerts(tree).some((a) => a.includes(ERROR)), "the drafting error is on the first statement card");
  m.h.unmount();
  m = await mounted(varianceCase(), "field-risk");
  tree = await m.render();
  assert.equal(nodes(tree, (n) => n.type?.name === "CardBody")[0].props.item.key, "field-risk");
  assert.ok(!alerts(tree).some((a) => a.includes(ERROR)), "and on no other");
  m.h.unmount();
  // A written first statement hands the note to the first one still open.
  const written = reducer(varianceCase(), { type: "setProcess", field: "rationale", value: "The wall is thinner to fit the lot." });
  m = await mounted(written, "field-risk");
  tree = await m.render();
  assert.ok(alerts(tree).some((a) => a.includes(ERROR)));
  m.h.unmount();
});

test("the fallback note names a failure or an empty result, and nothing when the review stands", () => {
  const base = { phase: "signed-in" as const, readOnly: false };
  assert.equal(statementFallbackNote({ ...base, drafting: null, error: ERROR }), ERROR);
  assert.equal(statementFallbackNote({ ...base, drafting: { drafts: [], stale: false }, error: "" }), "No statements were drafted.");
  assert.equal(statementFallbackNote({ ...base, drafting: null, error: "" }), "", "nothing drafted yet: the review offers to draft");
  assert.equal(statementFallbackNote({ ...base, phase: "signed-out", drafting: null, error: "" }), "", "signed out was never offered drafting");
  assert.equal(statementFallbackNote({ ...base, readOnly: true, drafting: null, error: ERROR }), "");
});
