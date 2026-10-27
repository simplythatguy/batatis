import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";
import type { CaseChecklist, CaseChecklists, CaseRules } from "../api/types.gen.ts";
import { emptyCase } from "../intake.ts";
import { reducer } from "../model.ts";
import type { RuleDef, RuleIndex } from "../rules/evaluate.ts";
import type { Candidate, Case, Fact } from "../types.ts";
import { conditionChoices, coveredByOption, followedInFull, matchingChecklists, otherOptions, tallyLine } from "./checklistView.ts";
import { buildDeck, caseRules, choicesFor, PACKAGE_YES, RULE_ADD, type DeckOptions } from "./deck.ts";
import { BUILDING_WIDE, caseRuleResults, numbersUsed, plainResult, readNumber, ruleFacts, ruleInPlay, type RuleData } from "./rulesView.ts";
import { journeyAnswerAction } from "./journey.ts";

const ROOT = join(dirname(fileURLToPath(import.meta.url)), "../../..");
/** Load a checked-in JSON fixture relative to the repository root. */
const read = (path: string) => JSON.parse(readFileSync(join(ROOT, path), "utf8"));
const index: RuleIndex = read("engine/data/rules/index.json");
const rules: Record<string, RuleDef> = Object.fromEntries(index.rules.map((id) => [id, read(`engine/data/rules/${id}.json`)]));
const DATA: RuleData = { index, rules };

let n = 0;
/** Create a pointed fixture fact with a unique id and explicit confirmation and source. */
function fact(field: string, value: Fact["value"], status: "confirmed" | "unconfirmed" = "confirmed", ref = "intake:description"): Fact {
  n += 1;
  return { id: `f${n}`, field, value, kind: "pointed", status, source: { type: "user_text", ref, quote: String(value) } };
}

/** The demo house as intake reads it: two storeys, 210 m², a wall 1.2 m from the line (not confirmed yet). */
function demo(extra: Fact[] = []): Case {
  const c = emptyCase("homebuilder");
  return {
    ...c,
    description: "Two-storey infill house in Edmonton, about 210 m². The east wall is 1.2 m from the property line.",
    facts: [fact("storeys", 2), fact("occupancy", "single_family"), fact("building_area_m2", 210), fact("limiting_distance_m", 1.2, "unconfirmed"), ...extra],
  };
}

/** Create a confirmed fixture answer with coded-rule provenance. */
const answered = (field: string, value: number | boolean | string) => fact(field, value, "confirmed", "rules:glazed-openings-houses");
const NUMBERS = [answered("ebf_area_m2", 30), answered("glazed_area_m2", 4)];
const NO_EXCEPTIONS = ["sprinklered", "fire_response_over_10_min", "glass_blocks", "faces_own_detached_garage"].map((f) => answered(f, f === "sprinklered" ? "no" : false));

/** Build deck fixture options with rule data and answered cards included by default. */
const opts = (extra: Partial<DeckOptions> = {}): DeckOptions => ({ rules: DATA, includeDone: true, confirmAuthority: true, ...extra });
/** Read the derived card keys for a case and its deck options. */
const keys = (c: Case, o: DeckOptions = opts()) => buildDeck(c, [], o).map((i) => i.key);

test("building-wide facts alone never put a rule in play (a house that is not sprinklered asks no wall questions)", () => {
  for (const f of BUILDING_WIDE) assert.ok(f in index.inputs, f);
  const c = { ...demo(), facts: demo().facts.filter((f) => f.field !== "limiting_distance_m").concat(fact("sprinklered", "no"), fact("fire_response_over_10_min", false)) };
  assert.deepEqual(caseRuleResults(c, DATA).filter((r) => ruleInPlay(c, DATA, r)).map((r) => r.rule_id), []);
  assert.ok(!buildDeck(c, [], opts()).some((i) => i.kind === "rule-input"));
});

test("a known limiting distance puts the window and soffit rules in play, not the duct or firewall rules", () => {
  const c = demo();
  const inPlay = caseRuleResults(c, DATA).filter((r) => ruleInPlay(c, DATA, r)).map((r) => r.rule_id);
  assert.ok(inPlay.includes("glazed-openings-houses"));
  assert.ok(inPlay.includes("soffits-houses"));
  assert.ok(!inPlay.includes("fire-dampers"));
  assert.ok(!inPlay.includes("firewall-suite-rowhouses"));
  // A house: the other-buildings rule is not applicable and asks nothing.
  assert.ok(!keys(c).some((k) => k.startsWith("rulein-opening_area")));
});

test("missing inputs become Section C deck questions, one card per field, in rule order", () => {
  const items = buildDeck(demo(), [], opts());
  const inputs = items.filter((i) => i.kind === "rule-input");
  assert.deepEqual(inputs.map((i) => i.key), ["rulein-ebf_area_m2", "rulein-glazed_area_m2", "rulein-soffit_projects"]);
  assert.ok(inputs.every((i) => i.section === "C" && !i.done && !i.optional));
  assert.equal(inputs[0].title, index.inputs.ebf_area_m2.question);
  // Not sure records uncertainty without supplying a boolean answer.
  assert.deepEqual(choicesFor(inputs[2]).map((x) => x.label), ["Yes", "No", "Not sure"]);
  assert.deepEqual(choicesFor(inputs[0]), []);
  // No result card while the rule still needs answers.
  assert.ok(!items.some((i) => i.kind === "rule"));
});

test("the demo numbers depart from 9.10.15.4.(1): a plain result card that offers to add the rule", () => {
  const c = demo([...NUMBERS, ...NO_EXCEPTIONS]);
  const card = buildDeck(c, [], opts()).find((i) => i.key === "rule-glazed-openings-houses")!;
  assert.equal(card.kind, "rule");
  assert.equal(card.rule?.state, "departs");
  assert.equal(card.title, "Your window area is more than the code’s table allows at 1.2 m.");
  assert.match(card.context, /departure .*acceptable solution.*alternative solution/);
  assert.equal(card.optional, false);
  assert.equal(choicesFor(card)[0].value, RULE_ADD);
  // The numbers used, plain names first, with where each came from and the limit compared with.
  const rows = numbersUsed(card.rule!, index);
  assert.deepEqual(rows.map((r) => [r.label, r.value]), [
    ["Distance to the property line (limiting distance)", "1.2 m"],
    ["Wall area (exposing building face)", "30 m²"],
    ["Window area (glazed openings)", "4 m²"],
    ["Most window area the code’s table allows", "2.1 m²"],
  ]);
  assert.equal(rows[0].origin, "from your description, not confirmed yet");
  assert.equal(rows[1].origin, "your answer");
  assert.deepEqual(card.rule!.unconfirmed_inputs, ["limiting_distance_m"]);
  // Inputs answered on rule cards stay in the deck as answered cards.
  assert.equal(buildDeck(c, [], opts()).find((i) => i.key === "rulein-ebf_area_m2")?.done, true);
});

test("a departure with a code-check card for the same article sits on that card, not on a second one", () => {
  const cand: Candidate = {
    id: "search-9.10.15.4.(1)", topic: "Openings", provision: "9.10.15.4.(1)", part: 9, benchmark: false, identified: true, suggestion: "search",
    quote: { text: "", citation: "", source: "code" }, departure: "x", clarifyingQuestion: "y", answer: null,
  };
  const c = { ...demo([...NUMBERS, ...NO_EXCEPTIONS]), candidates: [cand] };
  const items = buildDeck(c, [], opts());
  assert.ok(!items.some((i) => i.key === "rule-glazed-openings-houses"));
  const card = items.find((i) => i.key === `cand-${cand.id}`)!;
  assert.equal(card.rule?.state, "departs");
  // Its inputs come right before it.
  const at = (k: string) => items.findIndex((i) => i.key === k);
  assert.ok(at("rulein-glazed_area_m2") < at(`cand-${cand.id}`));
  // Answered No, the card no longer links the rule: it is shown on its own again.
  const no = { ...c, candidates: [{ ...cand, answer: "no" as const }] };
  assert.ok(keys(no).includes("rule-glazed-openings-houses"));
});

test("following numbers give an optional note; never 'complies'", () => {
  const c = demo([answered("ebf_area_m2", 30), answered("glazed_area_m2", 2), ...NO_EXCEPTIONS]);
  const card = buildDeck(c, [], opts()).find((i) => i.key === "rule-glazed-openings-houses")!;
  assert.equal(card.rule?.state, "follows");
  assert.equal(card.optional, true);
  for (const r of caseRuleResults(c, DATA)) {
    const p = plainResult(r);
    assert.doesNotMatch(`${p.title} ${p.line}`, /compl(y|ies|iant)|safe|approved|adequate/i);
  }
});

test("the engine's stored result wins when it read the same inputs; a newer local answer stays live", () => {
  const c = demo([...NUMBERS, ...NO_EXCEPTIONS]);
  const live = caseRuleResults(c, DATA);
  const stored: CaseRules = {
    case_id: "case_1", case_version: 9, edition: index.edition as unknown as string, notice: "",
    results: live.map((r) => ({ ...r, message: "STORED", unconfirmed_inputs: [], inputs: r.inputs.map((i) => ({ ...i, fact_id: null, fact_status: null })) })),
  };
  assert.equal(caseRuleResults(c, DATA, stored).find((r) => r.rule_id === "glazed-openings-houses")?.message, "STORED");
  const changed = reducer(c, { type: "setRuleInput", field: "glazed_area_m2", value: 5, rule: "glazed-openings-houses", quote: "5 m²" });
  const r = caseRuleResults(changed, DATA, stored).find((x) => x.rule_id === "glazed-openings-houses")!;
  assert.notEqual(r.message, "STORED");
  assert.equal(r.stored, false);
});

test("withdrawn planner counts never survive as live rule inputs or stale stored outcomes", () => {
  for (const count of [2, 4]) {
    const c = demo([...NUMBERS, ...NO_EXCEPTIONS, fact("storeys", count, "confirmed", "intake answer")]);
    const before = caseRuleResults(c, DATA);
    assert.equal(before[0].state, count === 2 ? "departs" : "not_applicable");
    const stored: CaseRules = {
      case_id: "case_1", case_version: 1, edition: "NBC(AE) 2023, 2nd printing", notice: "",
      results: before.map((r) => ({ ...r, inputs: r.inputs.map((i) => ({ ...i, fact_id: null, fact_status: null })) })),
    };
    const withdrawn = { ...c, facts: [...c.facts, fact("storeys", null, "confirmed", "intake answer")] };
    assert.equal(ruleFacts(withdrawn, index).has("storeys"), false);
    const after = caseRuleResults(withdrawn, DATA, stored);
    for (const rule of after) assert.equal(rule.inputs.find((i) => i.field === "storeys")?.value ?? null, null);
    assert.equal(after[0].stored, false, "the older stored outcome has different inputs");
    assert.equal(after[0].state, "departs");
    assert.equal(after[0].outcome_id, "departs");
    assert.ok(after[0].assumptions.length > 0);
  }
});

test("live rules resolve aliases and confirmation only after choosing the latest fact", () => {
  for (const [oldField, newField] of [["storeys", "storeys"], ["building.storeys", "storeys"], ["storeys", "building.storeys"]]) {
    const c = { ...emptyCase("homebuilder"), facts: [fact(oldField, 2)] };
    assert.equal(ruleFacts(c, index).get("storeys")?.value, 2);
    c.facts.push(fact(newField, null));
    assert.equal(ruleFacts(c, index).has("storeys"), false);
    c.facts.push(fact(newField, 3, "unconfirmed"));
    assert.equal(ruleFacts(c, index).get("storeys")?.value, 3);
    assert.equal(ruleFacts(c, index).get("storeys")?.status, "unconfirmed");
    c.facts.push({ ...fact(newField, 4, "unconfirmed"), kind: "proposed" });
    assert.equal(ruleFacts(c, index).has("storeys"), false);
  }
});

test("a rule input answer is a confirmed applicant fact; Not sure is settled and not asked again", () => {
  const c = reducer(demo(), { type: "setRuleInput", field: "soffit_projects", value: false, rule: "soffits-houses", quote: "No" });
  const f = c.facts.find((x) => x.field === "soffit_projects")!;
  assert.deepEqual([f.value, f.status, f.source.ref, f.source.type], [false, "confirmed", "rules:soffits-houses", "user_click"]);
  assert.equal(buildDeck(c, [], opts()).find((i) => i.key === "rulein-soffit_projects")?.done, true);
  const unanswered = demo();
  const question = buildDeck(unanswered, [], opts()).find((i) => i.key === "rulein-soffit_projects")!;
  const deferred = JSON.parse(JSON.stringify(reducer(unanswered, journeyAnswerAction(question, "not_sure"))));
  assert.ok(!deferred.facts.some((f) => f.field === "soffit_projects"), "Not sure never becomes a boolean answer");
  assert.ok(!buildDeck(deferred, [], opts({ includeDone: false })).some((i) => i.key === question.key), "a new visit never asks it again");
  assert.equal(buildDeck(deferred, [], opts()).find((i) => i.key === question.key)?.settled, true, "it remains open for Review");
  // Clearing the answer removes the fact.
  assert.ok(!reducer(c, { type: "setRuleInput", field: "soffit_projects", value: null, rule: "soffits-houses", quote: "" }).facts.some((x) => x.field === "soffit_projects"));
});

test("typed numbers are checked against the input's type and range", () => {
  assert.deepEqual(readNumber(index.inputs.glazed_area_m2, " 4,5 "), { value: 4.5 });
  assert.ok("error" in readNumber(index.inputs.glazed_area_m2, "four"));
  assert.ok("error" in readNumber(index.inputs.glazed_area_m2, "-1"));
  assert.ok("error" in readNumber(index.inputs.storeys, "2.5"));
});

/* —— Standing packages —— */

const SPV001 = read("engine/data/jurisdictions/checklists/calgary-spv-001.json");

/** Build a checklist response from the published fixture and supplied condition answers. */
function checklist(answers: Record<string, { state: "confirmed" | "not_yet" | "does_not_apply"; reason?: string }> = {}): CaseChecklist {
  const conditions = SPV001.conditions.map((row: Record<string, unknown>) => ({
    when: null, one_of: null, option: null, ...row,
    source: { label: null, lead_in: null, diagram: null, ...(row.source as object) },
    answer: answers[row.id as string] ? { ...answers[row.id as string], reason: answers[row.id as string].reason ?? null, fact_id: "f" } : null,
  }));
  const count = (s: string) => conditions.filter((x: { answer: { state: string } | null }) => x.answer?.state === s).length;
  return {
    id: SPV001.id, jurisdiction: "calgary", package: SPV001.package, code: SPV001.code, title: SPV001.title, revision: SPV001.revision, issued: SPV001.issued,
    summary: SPV001.summary, reviewed: false, source: SPV001.source, groups: SPV001.groups, source_notes: SPV001.source_notes,
    notice: "A checklist is never a determination.", conditions,
    counts: { total: conditions.length, confirmed: count("confirmed"), not_yet: count("not_yet"), does_not_apply: count("does_not_apply"), unanswered: conditions.filter((x: { answer: unknown }) => !x.answer).length },
    provisions: ["9.10.15.5.(8)", "9.10.15.5.(9)"], matches_case_provisions: false,
  } as unknown as CaseChecklist;
}
/** Wrap a checklist fixture in the case response shape consumed by the deck. */
const list = (cl: CaseChecklist): CaseChecklists => ({ case_id: "c", case_version: 3, checklists: [cl], historical: [], jurisdiction: "calgary", matched_by: "id", none_reason: null, notice: cl.notice });

const ZERO = { ...emptyCase("homebuilder"), description: "Single-family house in Calgary on a zero lot line, two storeys." };

test("a package matches by its name in the description, or a card on a provision it varies; not otherwise", () => {
  assert.equal(matchingChecklists(ZERO, list(checklist())).length, 1);
  assert.equal(matchingChecklists({ ...ZERO, description: "A two-storey house in Calgary." }, list(checklist())).length, 0);
  const soffit: Candidate = { id: "s", topic: "Soffits", provision: "9.10.15.5.(8)", part: 9, benchmark: false, identified: true, suggestion: "search", quote: { text: "", citation: "", source: "code" }, departure: "x", clarifyingQuestion: "y", answer: null };
  assert.equal(matchingChecklists({ ...ZERO, description: "A house.", candidates: [soffit] }, list(checklist())).length, 1);
  assert.equal(matchingChecklists({ ...ZERO, description: "A house.", candidates: [{ ...soffit, provision: "9.10.15.5.(2)" }] }, list(checklist())).length, 0);
});

test("the package is offered once; accepted, its conditions come one at a time, then the tally", () => {
  const offer = buildDeck(ZERO, [], opts({ checklists: list(checklist()) }));
  const pkg = offer.find((i) => i.kind === "package")!;
  assert.equal(pkg.title, "Your city has a pre-reviewed path for this kind of project.");
  assert.equal(pkg.optional, false);
  assert.equal(choicesFor(pkg)[0].value, PACKAGE_YES);
  assert.ok(!offer.some((i) => i.kind === "condition"));

  const yes = buildDeck(ZERO, [], opts({ checklists: list(checklist()), packages: { [SPV001.id]: "yes" } }));
  const rows = yes.filter((i) => i.kind === "condition");
  assert.equal(rows.length, SPV001.conditions.length);
  assert.ok(rows.every((r) => r.section === "C" && !r.optional && !r.done));
  assert.ok(yes.findIndex((i) => i.kind === "package-end") > yes.findIndex((i) => i.kind === "condition"));
  // An always-applies row has no "does not apply" choice.
  const always = SPV001.conditions.find((r: { may_not_apply: boolean }) => !r.may_not_apply);
  assert.deepEqual(conditionChoices({ ...always, answer: null }).map((x) => x.value), ["confirmed", "not_yet"]);
});

test("a confirmed option hides the other options of its choice; 'not yet' means not followed in full", () => {
  const options = SPV001.conditions.filter((r: { one_of?: string }) => r.one_of);
  assert.ok(options.length >= 2);
  const first = options[0];
  const cl = checklist({ [first.id]: { state: "confirmed" } });
  const sibling = cl.conditions.find((x) => x.one_of === first.one_of && x.id !== first.id && x.option !== first.option)!;
  assert.equal(coveredByOption(cl, sibling), true);
  assert.ok(otherOptions(cl, cl.conditions.find((x) => x.id === first.id)!).some((x) => x.id === sibling.id));
  const items = buildDeck(ZERO, [], opts({ checklists: list(cl), packages: { [SPV001.id]: "yes" } }));
  assert.ok(!items.some((i) => i.key === `pkgc-${SPV001.id}-${sibling.id}`));

  const all = Object.fromEntries(SPV001.conditions.map((r: { id: string }) => [r.id, { state: "confirmed" as const }]));
  assert.equal(followedInFull(checklist(all)), true);
  assert.equal(followedInFull(checklist({ ...all, [first.id]: { state: "not_yet" } })), false);
  assert.doesNotMatch(tallyLine(checklist(all)), /complete|pass/i);
  // An answered package needs no offer answer to show its conditions (a reopened application);
  // "No, build my own case" removes them even after an answer.
  assert.ok(buildDeck(ZERO, [], opts({ checklists: list(cl) })).some((i) => i.kind === "condition"));
  assert.ok(!buildDeck(ZERO, [], opts({ checklists: list(cl), packages: { [SPV001.id]: "no" } })).some((i) => i.kind === "condition" || i.kind === "package-end"));
});

test("an authority read from the site is confirmed once on its card; unanswered it is required", () => {
  const set = { ...demo(), authority: "edmonton" as const };
  const card = buildDeck(set, [], opts()).find((i) => i.kind === "paperwork")?.paperworkRows?.find((i) => i.key === "authority")!;
  assert.deepEqual([card.done, card.optional], [false, true]);
  assert.equal(buildDeck(set, [], opts({ seen: new Set(["authority"]) })).find((i) => i.kind === "paperwork")?.paperworkRows?.find((i) => i.key === "authority")?.done, true);
  const open = buildDeck(demo(), [], opts()).find((i) => i.kind === "paperwork")?.paperworkRows?.find((i) => i.key === "authority")!;
  assert.deepEqual([open.done, open.optional], [false, false]);
});

test("caseRules lists the rules in play (a not-applicable one asks nothing and shows no result)", () => {
  assert.deepEqual(caseRules(demo(), opts()).map((r) => [r.rule_id, r.state]), [["glazed-openings-houses", "needs_info"], ["unprotected-openings", "not_applicable"], ["soffits-houses", "needs_info"]]);
  assert.deepEqual(caseRules(demo(), {}), []);
});
