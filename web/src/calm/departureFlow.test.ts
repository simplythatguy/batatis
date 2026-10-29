import assert from "node:assert/strict";
import test from "node:test";
import { componentHarness, nodes, text } from "../../scripts/component-harness.mjs";
import { emptyCase } from "../intake.ts";
import { planFactAnswer, planInput } from "../intakeView.ts";
import { getGaps, reducer } from "../model.ts";
import type { Action } from "../model.ts";
import type { Candidate, Case, Fact } from "../types.ts";
import * as deck from "./deck.ts";
import * as journey from "./journey.ts";
import * as calendarDate from "./calendarDate.ts";
import { CLAIM_NOTE, CLAIM_WORDS, DEPARTURE_MAX, departureComparison } from "./departure.ts";

const DESCRIPTION = "Owner: Larkspur Example Ltd.\nRepresentative: Priya Natarajan\nMailing address: 100 Example St, Edmonton\n\nWe are building a two-storey house on a narrow lot.";
const card: Candidate = {
  id: "w", topic: "Unprotected openings", provision: "9.10.15.4.(1)", part: 9, benchmark: false, identified: true, suggestion: "search",
  quote: { text: "The unprotected openings shall not exceed the limits in Table 9.10.15.4.", citation: "9.10.15.4.(1)", source: "code" },
  departure: "", clarifyingQuestion: "", answer: "yes",
};
const alternative = (value: string): Fact => ({ id: "alt", field: "alternative", value, kind: "pointed", status: "confirmed", confidence: null, formula: null, inputs: [], source: { type: "user_text", ref: "intake:description", quote: value } });
const departureCase = (facts: Fact[] = []): Case => ({ ...emptyCase("owner"), description: DESCRIPTION, candidates: [card], facts });

/** The question deck opened on the departure card; `onDeparture` records what Confirm sends. */
async function mounted(initial: Case, refusal: string | null = null) {
  let c = initial;
  let session = { queue: [] as string[], index: 0, seen: [] as string[], packages: {}, ruleUnsure: [], authorityUnsure: false };
  const updateSession = (patch) => { session = { ...session, ...(typeof patch === "function" ? patch(session) : patch) }; };
  const dispatch = (action: Action) => { c = reducer(c, action); };
  const sent: string[] = [];
  // The card's typed words and picks, kept across renders.
  const typed = { value: "", choices: {} as Record<string, string> };
  const h = await componentHarness(new URL("./QuestionDeck.tsx", import.meta.url), "CaseDeck", {
    "../store": { useCase: () => ({ c, dispatch, gaps: getGaps(c), engineId: "case-test", sectionCLookup: { source: "live" }, reading: { intake: "done", identify: "done", busy: null }, drafting: null, requestCheck() {} }) },
    "../screens/CodeCheck": { useCandidateAnswer: () => ({ onAnswer() {}, onDeparture: async (_cand, words: string) => { sent.push(words); return refusal; }, decisionNoteFor: () => "" }) },
    "./deck": deck,
    "./departure": await import("./departure.ts"),
    "./journey": journey,
    "./calendarDate": calendarDate,
    "../intakeView": { NOT_SURE: "Not sure", planFactAnswer, planInput },
    "../model": await import("../model.ts"),
    "../intakeFields": await import("../intakeFields.ts"),
    "../provisions": await import("../provisions.ts"),
    "./session": { getSession: () => session, useSession: () => session, updateSession },
    "./begin": { useCurrentApplication: () => ({ app: { status: "draft" }, locked: false, readOnly: false }) },
    "./useDeckExtras": { useDeckExtras: () => ({ options: {}, extras: { failed: {}, checklists: null } }) },
    "./account": { useAccount: () => ({ user: { id: "test", role: "applicant" } }) },
    "./useQuestionDraft": { useQuestionDraft: () => ({ value: typed.value, setValue: (v) => { typed.value = typeof v === "function" ? v(typed.value) : v; }, choices: typed.choices, setChoices: (v) => { typed.choices = typeof v === "function" ? v(typed.choices) : v; }, conflict: null, confirmValue() {} }) },
    "./assistant/assistant": { setAssistantContext() {} },
    "./assistant/questionContext": { questionContext: () => ({}) },
    "./applications": { readOnlyStatus: () => ({}) },
    "../api/sync": { engineGeneration: () => 1 },
    "./icons": { Icon24: "icon" },
  }, { location: { hash: "#/questions", replace() {} }, window: {}, document: { addEventListener() {}, removeEventListener() {} } });
  const render = async () => { await h.render({ focus: `dep-${card.id}`, codeFirst: false }); return h.render({ focus: `dep-${card.id}`, codeFirst: false }); };
  const ok = (tree) => nodes(tree, (n) => n.type?.name === "OkRow")[0];
  const shown = (tree) => nodes(tree, (n) => n.type?.name === "CardBody")[0];
  return { h, render, ok, shown, sent, typed };
}

test("without the applicant's words for the design, the departure card asks them to write it and never sends the description", async () => {
  for (const facts of [[], [alternative("")]]) {
    const m = await mounted(departureCase(facts));
    let tree = await m.render();
    assert.equal(m.shown(tree).props.item.kind, "departure");
    assert.equal(m.ok(tree).props.label, "Write it", "writing the departure is the card's one action");
    m.ok(tree).props.onOk();
    tree = await m.render();
    assert.equal(m.sent.length, 0, "nothing is recorded before the applicant writes it");
    assert.equal(m.shown(tree).props.picked, "edit", "Write it opens the text box");
    assert.equal(m.shown(tree).props.draft, "", "the text box starts empty, not with the description");
    assert.equal(m.ok(tree).props.label, "Continue");
    assert.equal(m.ok(tree).props.disabled, true, "an empty departure cannot be sent");
    m.h.unmount();
  }
});

test("Confirm records exactly the words the card shows", async () => {
  const words = `${"The east wall has larger windows facing the neighbour than the table allows. ".repeat(3)}The wall keeps its rating.`;
  const m = await mounted(departureCase([alternative(words)]));
  let tree = await m.render();
  assert.equal(m.ok(tree).props.label, "Confirm");
  const lines = departureComparison(departureCase([alternative(words)]), card, null);
  assert.ok(lines.departure.length > 220 && lines.departure.length <= DEPARTURE_MAX);
  m.ok(tree).props.onOk();
  await m.render();
  assert.deepEqual(m.sent, [lines.departure], "Confirm sends the comparison's departure line");
  const compare = await componentHarness(new URL("./DepartureCompare.tsx", import.meta.url), "DepartureCompare", {});
  const card2 = await compare.render({ lines, onEdit() {} });
  assert.equal(text(nodes(card2, (n) => n.type === "q")[0]), lines.departure, "the card shows every word Confirm records");
  m.h.unmount();
});

test("words the engine refuses open the words to edit with a short note, and nothing is sent", async () => {
  const m = await mounted(departureCase([alternative("We want approval to sell it across Alberta.")]));
  let tree = await m.render();
  m.ok(tree).props.onOk();
  tree = await m.render();
  assert.equal(m.sent.length, 0, "the browser never sends a departure the engine refuses");
  assert.equal(m.shown(tree).props.picked, "edit");
  assert.equal(m.shown(tree).props.draft, "We want approval to sell it across Alberta.");
  assert.equal(m.shown(tree).props.note, CLAIM_NOTE);
  m.typed.value = "A wider window than the table allows, facing the neighbour.";
  tree = await m.render();
  m.ok(tree).props.onOk();
  await m.render();
  assert.deepEqual(m.sent, ["A wider window than the table allows, facing the neighbour."]);
  m.h.unmount();
});

test("the browser's refusal words behave like the engine's", () => {
  for (const words of ["We want approval to sell it across Alberta.", "The wall complies.", "It is SAFE.", "Fire safety is kept."]) assert.match(words, CLAIM_WORDS);
  for (const words of ["The design departs from the acceptable solution.", "A thinner assembly than the table allows.", "Safeguards stay in place."]) assert.doesNotMatch(words, CLAIM_WORDS);
});
