import assert from "node:assert/strict";
import test from "node:test";
import { componentHarness, nodes, text } from "../../scripts/component-harness.mjs";
import { emptyCase } from "../intake.ts";
import { planFactAnswer, planInput } from "../intakeView.ts";
import { getGaps, reducer } from "../model.ts";
import type { Action } from "../model.ts";
import type { Case } from "../types.ts";
import * as deck from "./deck.ts";
import * as journey from "./journey.ts";
import * as calendarDate from "./calendarDate.ts";

const blank = () => emptyCase("owner");
const field = (id: string, value: string | number) => ({ id, field: id, value, kind: "pointed" as const, status: "unconfirmed" as const, source: { type: "user_text" as const, ref: "intake:description", quote: String(value) } });

function plannedCase(status: "likely" | "not_indicated" | "unknown" = "unknown", fields: string[] = []): Case {
  const c = blank();
  const questions = fields.map((field) => ({ id: `intake.${field}`, field, text: `${field}?`, why: "Why it is asked.", unblocks: [], splits: [], priority: "critical" as const, kind: "missing" as const, provision: null }));
  return { ...c, description: "Our house will use a different wall assembly.", intake: { text: "Our house will use a different wall assembly.", facts: [], factIds: [], record: {
    ran_at: "2026-10-26", text_sha256: null, pointers: [], files: [], conflicts: [], unresolved_citations: [], model: { status: "off", model: null, reason: null, pointed: 0, proposed: 0, dropped: 0, input_tokens: 0, output_tokens: 0 },
    plan: { next: "questions", scope: { status: "in_scope", regime: null, message: null, cue: null, start: null, end: null, scores: {}, override_allowed: true }, fork: { variance_needed: status, explanation: "The route is not a technical decision.", cues: ["different wall assembly"], halves: [] }, questions, asked: questions, not_sure: [], pre_application: { jurisdiction_id: null, jurisdiction_name: null, resolved_by: null, steps: [] }, route_notice: null, candidates_seen: 0 },
  } } };
}

async function mounted(initial: Case, focus: string | null = null, answerError: string | null = null) {
  let c = initial;
  let session = { queue: [] as string[], index: 0, seen: [] as string[], packages: {}, ruleUnsure: [], authorityUnsure: false };
  const updateSession = (patch) => { session = { ...session, ...(typeof patch === "function" ? patch(session) : patch) }; };
  const actions: Action[] = [];
  const dispatch = (action: Action) => { actions.push(action); c = reducer(c, action); };
  let choices: Record<string, string> = {};
  const reading = { intake: "done", identify: "done", busy: null };
  const h = await componentHarness(new URL("./QuestionDeck.tsx", import.meta.url), "CaseDeck", {
    "../store": { useCase: () => ({ c, dispatch, gaps: getGaps(c), engineId: "case-test", sectionCLookup: { source: "live" }, reading, requestCheck() {}, answerPlan: async (q, value) => {
      if (answerError) return answerError;
      if (value === "Not sure" && c.intake?.record.plan) c = reducer(c, { type: "noteIntakeRecord", record: { ...c.intake.record, plan: { ...c.intake.record.plan, not_sure: [...c.intake.record.plan.not_sure, q.id] } } });
      else dispatch({ type: "setDetail", field: q.field, value, section: "B" });
      return null;
    } }) },
    "../screens/CodeCheck": { useCandidateAnswer: () => ({ onAnswer: (cand, answer) => dispatch({ type: "answerCandidate", id: cand.id, answer }), decisionNoteFor: () => "" }) },
    "./deck": deck,
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
    "./useQuestionDraft": { useQuestionDraft: (_a, _g, _e, _k, saved) => ({ value: saved, setValue() {}, choices, setChoices: (next) => { choices = typeof next === "function" ? next(choices) : next; }, conflict: null, confirmValue() {} }) },
    "./assistant/assistant": { setAssistantContext() {} },
    "./assistant/questionContext": { questionContext: () => ({}) },
    "./applications": { readOnlyStatus: () => ({}) },
    "../api/sync": { engineGeneration: () => 1 },
    "../config": await import("../config.ts"),
    "./icons": { Icon24: "icon" },
  }, { location: { hash: "#/questions", replace() {} }, window: {}, document: { addEventListener() {}, removeEventListener() {} } });
  const render = async () => { await h.render({ focus, codeFirst: false }); return h.render({ focus, codeFirst: false }); };
  const shown = (tree) => nodes(tree, (node) => node.type?.name === "CardBody")[0];
  return { h, render, shown, actions, dispatch, case: () => c, session: () => session };
}

test("Looks right confirms every reading and advances in one click", async () => {
  const m = await mounted({ ...blank(), facts: [field("storeys", 2), field("occupancy", "single_family")] });
  let tree = await m.render();
  assert.equal(m.shown(tree).props.item.kind, "understood");
  const primary = nodes(tree, (node) => node.type?.name === "OkRow")[0];
  assert.equal(primary.props.label, "Looks right");
  primary.props.onOk();
  tree = await m.render();
  assert.equal(m.actions.filter((action) => action.type === "confirmFacts").length, 1);
  assert.ok(m.case().facts.filter((f) => f.field === "storeys" || f.field === "occupancy").every((f) => f.status === "confirmed"));
  assert.notEqual(m.shown(tree)?.props.item.kind, "understood");
  m.h.unmount();
});

test("auto-confirmed readings still ask for acknowledgement once, and a new reading asks again", async () => {
  const read = { ...field("owner", "Dana Whitfield."), status: "confirmed" as const };
  const initial = plannedCase();
  const c = { ...initial, facts: [read], intake: { ...initial.intake!, facts: [read], factIds: [read.id] } };
  const m = await mounted(c);
  let tree = await m.render();
  const understood = m.shown(tree)?.props.item;
  assert.equal(understood?.kind, "understood");
  assert.equal(understood.rows[0].copy.value, "Dana Whitfield");
  assert.equal(journey.journeyProgress([understood]).open.batatis, 1);
  nodes(tree, (node) => node.type?.name === "OkRow")[0].props.onOk();
  tree = await m.render();
  assert.notEqual(m.shown(tree)?.props.item.kind, "understood");
  const saved = JSON.parse(JSON.stringify(m.case()));
  assert.ok(!deck.buildDeck(saved, []).some((i) => i.kind === "understood"));
  const acknowledged = deck.buildDeck(saved, [], { includeDone: true }).find((i) => i.kind === "understood")!;
  assert.equal(journey.journeyProgress([acknowledged]).open.batatis, 0);
  assert.ok(!deck.buildDeck(saved, getGaps(saved)).some((i) => i.kind === "understood"));
  assert.ok(saved.facts.filter((f) => f.field.startsWith("journey.answer.")).every((f) => !f.field.includes("Dana") && f.field.length < 100));
  const address = { ...field("municipalAddress", "10234 87 Ave NW, Edmonton"), status: "confirmed" as const };
  const reread = { ...saved, facts: [...saved.facts, address], intake: { ...saved.intake, facts: [read, address], factIds: [read.id, address.id] } };
  assert.ok(deck.buildDeck(reread, []).some((i) => i.kind === "understood"));
  m.dispatch({ type: "restoreIntake", result: { facts: [read, address], record: saved.intake.record }, text: saved.description });
  tree = await m.render();
  nodes(tree, (node) => node.type?.name === "OkRow")[0].props.onOk();
  tree = await m.render();
  assert.equal(m.shown(tree)?.props.item.kind, "understood", "a prior visit to the card cannot suppress a new reading");
  m.h.unmount();
});

test("Looks right on a site read as Edmonton proposes Edmonton as the reviewing office", async () => {
  const site = { ...field("municipality", "Edmonton"), status: "confirmed" as const };
  const address = { ...field("municipalAddress", "0000 Example Crescent NW, Edmonton, AB"), status: "confirmed" as const };
  const initial = plannedCase();
  const m = await mounted({ ...initial, facts: [site, address], intake: { ...initial.intake!, facts: [site, address], factIds: [site.id, address.id] } });
  let tree = await m.render();
  assert.equal(m.shown(tree)?.props.item.kind, "understood");
  assert.equal(m.case().authority, "");
  nodes(tree, (node) => node.type?.name === "OkRow")[0].props.onOk();
  tree = await m.render();
  assert.equal(m.case().authority, "edmonton", "the applicant only confirms the proposed office");
  m.h.unmount();
});

test("description rows show you, while a derived value retains its dashed assumed chip", async () => {
  const c = plannedCase();
  const own = field("owner", "Dana Whitfield.");
  const derived = { ...field("building_area_m2", 140), kind: "computed" as const, inputs: [] };
  c.facts = [own, derived];
  const h = await componentHarness(new URL("./ReadCards.tsx", import.meta.url), "UnderstoodFacts", {
    "../store": { useCase: () => ({ c, dispatch() {} }) },
    "../model": await import("../model.ts"), "../intakeView": await import("../intakeView.ts"),
    "./journey": journey, "./icons": { Icon24: "icon" },
  });
  const tree = await h.render({ item: deck.buildDeck(c, []).find((i) => i.kind === "understood") });
  assert.ok(nodes(tree, (node) => node.type === "span" && node.props.className === "cf-source-chip" && text(node) === "you").length > 0);
  assert.ok(nodes(tree, (node) => node.type === "span" && node.props.className === "cf-source-chip is-assumed" && text(node) === "assumed").length > 0);
  assert.doesNotMatch(text(tree), /Dana Whitfield\./);
  h.unmount();
});

test("a choice saves and advances without a second OK", async () => {
  const m = await mounted(plannedCase("likely"));
  let tree = await m.render();
  assert.equal(m.shown(tree).props.item.key, "route");
  m.shown(tree).props.onPick("variance");
  tree = await m.render();
  assert.equal(journey.routeChoice(m.case()), "variance");
  assert.notEqual(m.shown(tree)?.props.item.key, "route");
  assert.equal(nodes(tree, (node) => node.type === "button" && text(node) === "Skip").length, 0);
  m.h.unmount();
});

test("Later is recorded through case actions and survives a fresh visit", async () => {
  const m = await mounted(blank(), "field-owner");
  let tree = await m.render();
  const body = m.shown(tree);
  assert.equal(body.props.focusRow, "field-owner");
  const row = body.props.item.paperworkRows.find((row) => row.key === "field-owner");
  m.dispatch(journey.journeyAnswerAction(row, "later"));
  body.props.onPaperworkDone();
  await m.render();
  const saved = JSON.parse(JSON.stringify(m.case()));
  assert.equal(journey.journeyAnswers(saved).get("field-owner")?.value, "later");
  assert.ok(getGaps(saved).some((g) => g.field === "owner"));
  assert.ok(!deck.buildDeck(saved, getGaps(saved)).some((i) => i.key === "field-owner"));
  m.h.unmount();
});

test("the office's response-time question never becomes an applicant card", async () => {
  const c = { ...blank(), questions: [{ id: "response", field: "fire_response_over_10_min", text: "Fire department response time?", why: "The office holds this statistic." }] };
  const all = deck.buildDeck(c, [], { includeDone: true });
  assert.equal(all.find((i) => i.ref === "response")?.answerer, "office", "the field determines the answerer, not the question ID");
  assert.ok(!deck.buildDeck(c, []).some((i) => i.ref === "response"));
  const m = await mounted(c);
  m.session().queue = ["q-response"];
  const tree = await m.render();
  assert.notEqual(m.shown(tree)?.props.item.ref, "response");
  assert.equal(journey.journeyProgress(all).open.office, 1);
  m.h.unmount();
});

test("the end screen only says done when no required answer waits on the applicant", async () => {
  const open = deck.buildDeck(blank(), [], { includeDone: true }).find((i) => i.kind === "paperwork")!.paperworkRows!.find((i) => i.key === "field-owner")!;
  const h = await componentHarness(new URL("./QuestionDeck.tsx", import.meta.url), "JourneyEnd", { "./journey": journey, "./icons": { Icon24: "icon" } });
  let tree = await h.render({ items: [open], onJump() {}, onReview() {}, standard: false, product: false });
  assert.match(text(tree), /1 still need you/);
  assert.doesNotMatch(text(tree), /Your part is done/);
  tree = await h.render({ items: [{ ...open, done: true }], onJump() {}, onReview() {}, standard: true, product: false });
  assert.match(text(tree), /Your part is done/);
  assert.match(text(tree), /usual permit documents/);
  assert.equal(nodes(tree, (node) => node.type?.name === "OkRow")[0].props.label, "See my application");
  h.unmount();
});

test("the designer list is copyable and office questions are listed without answer controls", async () => {
  const item = deck.buildDeck(blank(), [], { includeDone: true }).find((i) => i.kind === "paperwork")!.paperworkRows!.find((i) => i.key === "field-owner")!;
  let copied = "";
  const h = await componentHarness(new URL("./QuestionDeck.tsx", import.meta.url), "JourneyEnd", { "./journey": journey, "./icons": { Icon24: "icon" } }, { navigator: { clipboard: { writeText: async (value) => { copied = value; } } } });
  let tree = await h.render({ items: [{ ...item, answerer: "designer", title: "Part 4 design?", done: true, settled: true }, { ...item, key: "response", answerer: "office", title: "Fire response time?" }], onJump() {}, onReview() {}, standard: false, product: false });
  assert.match(text(tree), /Your part is done/);
  assert.match(text(tree), /For your designer/);
  assert.match(text(tree), /To confirm with the office/);
  nodes(tree, (node) => node.type === "button" && text(node) === "Copy questions")[0].props.onClick();
  tree = await h.render();
  assert.equal(copied, "• Part 4 design?");
  assert.match(text(tree), /Copied/);
  h.unmount();
});

test("Ask my designer uses the existing planner uncertainty and records the assignment", async () => {
  const m = await mounted(plannedCase("unknown", ["part4_design"]));
  let tree = await m.render();
  assert.match(text(tree), /Usually your designer knows/);
  m.shown(tree).props.onPick("designer");
  tree = await m.render();
  assert.notEqual(m.shown(tree)?.props.item.ref, "intake.part4_design");
  const saved = JSON.parse(JSON.stringify(m.case()));
  assert.ok(saved.intake.record.plan.not_sure.includes("intake.part4_design"));
  assert.equal(journey.journeyAnswers(saved).get("plan-intake.part4_design")?.answerer, "designer");
  assert.ok(!deck.buildDeck(saved, []).some((i) => i.ref === "intake.part4_design"));
  assert.equal(journey.journeyProgress(deck.buildDeck(saved, [], { includeDone: true })).open.designer, 1);
  m.h.unmount();
});

test("a rejected planner save keeps the question and permits a retry", async () => {
  const m = await mounted(plannedCase("unknown", ["part4_design"]), null, "Answer was not saved.");
  let tree = await m.render();
  m.shown(tree).props.onPick("designer");
  tree = await m.render();
  assert.equal(m.shown(tree).props.item.ref, "intake.part4_design");
  assert.equal(m.shown(tree).props.planNote, "Answer was not saved.");
  assert.equal(journey.journeyAnswers(m.case()).size, 0);
  m.shown(tree).props.onPick("yes");
  await m.render();
  assert.equal(journey.journeyAnswers(m.case()).size, 0);
  m.h.unmount();
});

test("Something is different opens its text question before project questions", async () => {
  const m = await mounted(plannedCase("not_indicated", ["sprinklered"]));
  let tree = await m.render();
  assert.equal(m.shown(tree).props.item.kind, "route");
  m.shown(tree).props.onPick("different");
  tree = await m.render();
  assert.equal(m.shown(tree).props.item.kind, "route-detail");
  assert.equal(journey.routeChoice(m.case()), "different");
  m.h.unmount();
});

test("a legacy role link opens the role row in the sheet and Done advances", async () => {
  const m = await mounted(blank(), "role");
  let tree = await m.render();
  const body = m.shown(tree);
  assert.equal(body.props.item.kind, "paperwork");
  assert.equal(body.props.focusRow, "role");
  const row = body.props.item.paperworkRows.find((row) => row.key === "role");
  assert.ok(row.choices.some((choice) => choice.value === "designer"));
  body.props.onPaperworkDone();
  tree = await m.render();
  assert.notEqual(m.shown(tree)?.props.item.kind, "paperwork");
  m.h.unmount();
});

test("an office link opens the office row in the sheet", async () => {
  const m = await mounted(blank(), "authority");
  const tree = await m.render();
  const body = m.shown(tree);
  assert.equal(body.props.item.kind, "paperwork");
  assert.equal(body.props.focusRow, "authority");
  assert.ok(body.props.item.paperworkRows.some((row) => row.kind === "authority"));
  m.h.unmount();
});

test("a rule card shows Continue once No or Not sure is picked, not only the keyboard shortcut", async () => {
  const rule = {
    id: "B:9.10.15.4.", provision_id: "9.10.15.4.", division: "B", title: "Glazed openings", role: "unresolved", disposition: "review",
    applicability: "unknown", human_confirmed: false, confirmation_fingerprint: null, confirmation_reason: null, confirmed_at: null,
    needs_review: true, source_status: "verified", citation: "NBC(AE) 2023 p2, Div B, Article 9.10.15.4.", quote: "Glazed openings.",
    quote_provision_id: "9.10.15.4.(1)", pdf_page: 1, pdf_page_end: null, source_sha256: "abc", discoveries: [], evidence: [],
    evidence_ids: [], conditions: [], review_reasons: [],
  };
  const identify = { mode: "live", narrowed: false, committed: [], choices: [], decisions: {}, articles: [], questions: [], requirements: [rule] };
  const m = await mounted({ ...plannedCase("likely"), identify } as unknown as Case, `req-${rule.id}`);
  for (const answer of ["does-not-apply", "not-sure"]) {
    let tree = await m.render();
    assert.equal(m.shown(tree).props.item.kind, "requirement");
    m.shown(tree).props.onPick(answer);
    tree = await m.render();
    assert.equal(nodes(tree, (node) => node.type?.name === "OkRow")[0].props.primary, true, `${answer} waits for a reason and a visible Continue`);
  }
  m.h.unmount();
});

test("a reading row can be corrected without restoring the old value on confirmation", async () => {
  let c = plannedCase();
  const read = field("storeys", 2);
  c = { ...c, facts: [read], intake: { ...c.intake!, facts: [read], factIds: [read.id] } };
  const h = await componentHarness(new URL("./ReadCards.tsx", import.meta.url), "UnderstoodFacts", {
    "../store": { useCase: () => ({ c, dispatch: (action) => { c = reducer(c, action); } }) },
    "../model": await import("../model.ts"), "../intakeView": await import("../intakeView.ts"),
    "./journey": journey, "./icons": { Icon24: "icon" },
  });
  const render = () => h.render({ item: deck.buildDeck(c, [], { includeDone: true }).find((i) => i.kind === "understood") });
  const click = (node) => node.props.onClick({ currentTarget: { closest: () => ({ open: true }) } });
  let tree = await render();
  click(nodes(tree, (node) => node.type === "button" && text(node) === "No, something else")[0]);
  tree = await render();
  nodes(tree, (node) => node.type === "input")[0].props.onChange({ target: { value: "3" } });
  tree = await render();
  click(nodes(tree, (node) => node.type === "button" && text(node) === "Save")[0]);
  tree = await render();
  assert.equal(c.facts.find((f) => f.field === "storeys")?.value, 3);
  assert.match(text(tree), /3 storeys/);
  click(nodes(tree, (node) => node.type === "button" && text(node) === "Yes, 3 storeys")[0]);
  assert.equal(c.facts.find((f) => f.field === "storeys")?.value, 3);
  click(nodes(tree, (node) => node.type === "button" && text(node) === "Not sure")[0]);
  tree = await render();
  assert.ok(!c.facts.some((f) => f.field === "storeys"));
  const open = journey.journeyProgress(deck.buildDeck(c, [], { includeDone: true })).open;
  assert.equal(open.you + open.batatis > 0, true);
  assert.match(text(tree), /Not sure/);
  h.unmount();
});
