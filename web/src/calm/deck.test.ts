import assert from "node:assert/strict";
import test from "node:test";
import type { IdentifyResult, IntakeResult } from "../api/types.gen.ts";
import { emptyCase } from "../intake.ts";
import { readGroups, snippet, spokenValue } from "../intakeView.ts";
import { DETAIL_IDS, factFor, getGaps, NOT_RIGHT, reducer } from "../model.ts";
import type { Case } from "../types.ts";
import { aliasKey, alternativeChoice, buildDeck, choicesFor, deckProgress, gapKey, preCaseState, sectionProgress } from "./deck.ts";
import { calmHref, resolveRoute } from "./routes.ts";

/* —— Fixtures: the demo description as the engine's intake and identify routes return it (fake providers). —— */

const DEMO =
  "Two-storey infill house in Edmonton, about 210 m². The east wall is 1.2 m from the property line, and we want more window area facing the neighbour than the acceptable solution allows for unprotected openings.\nOwner: Jordan Lee\nMunicipal address: 10234 84 Avenue NW, Edmonton";
const DEPARTURE = "The east wall is 1.2 m from the property line, and we want more window area facing the neighbour than the acceptable solution allows for unprotected openings.";

const span = (words: string) => ({ start: DEMO.indexOf(words), end: DEMO.indexOf(words) + words.length });

function fact(id: string, field: string, value: string | number, quote: string, confidence = 0.9) {
  return {
    id, field, value, kind: "pointed" as const, confidence, status: "unconfirmed" as const, formula: null, inputs: [],
    source: { type: "user_text" as const, ref: "intake:description", page: null, bbox: null, quote },
  };
}

const READ = [
  fact("fact_storeys", "storeys", 2, "Two-storey"),
  fact("fact_occ", "occupancy", "single_family", "house", 0.6),
  fact("fact_muni", "municipality", "Edmonton", "Edmonton"),
  fact("fact_area", "building_area_m2", 210, "210 m²", 0.7),
  fact("fact_alt", "alternative_description", DEPARTURE, DEPARTURE, 0.6),
  fact("fact_ld", "limiting_distance_m", 1.2, "1.2 m from the property line", 0.75),
  fact("fact_owner", "owner_name", "Jordan Lee", "Jordan Lee", 0.95),
  fact("fact_addr", "municipal_address", "10234 84 Avenue NW, Edmonton", "10234 84 Avenue NW, Edmonton", 0.95),
  fact("fact_stmt", "statement.ec976b07c7", DEPARTURE, DEPARTURE, 0.6),
];

const POINTERS = READ.map((f) => ({ fact_id: f.id, field: f.field, method: "rules" as const, source_ref: "description", page: null, verified: true, ...span(f.source.quote) }));

const HALVES = [
  { id: "variance_request" as const, label: "Request for variance", basis: "Safety Codes Act, s.38", who: "Issued by a safety codes officer or an Administrator, who may set conditions", what: "The legal authorization to build in a way the code does not prescribe" },
  { id: "alternative_solution" as const, label: "Alternative solution (Div C 2.3.1)", basis: "NBC(AE) Division C, 2.3.1", who: "Prepared by the proponent, usually a design professional", what: "The technical evidence" },
];

const question = (field: string, text: string, priority: "critical" | "administrative" = "critical") => ({
  id: `intake.${field}`, field, text, why: `Why ${field}.`, unblocks: [], splits: [], priority, kind: "missing" as const, provision: null,
});

function intakeResult(over: { plan?: Partial<NonNullable<IntakeResult["record"]["plan"]>>; facts?: IntakeResult["facts"] } = {}): IntakeResult {
  return {
    case_id: "case_demo",
    case_version: 3,
    facts: over.facts ?? READ,
    record: {
      ran_at: "2026-10-21T00:00:00Z", text_sha256: null, pointers: POINTERS, files: [], conflicts: [], unresolved_citations: [],
      model: { status: "fake", model: null, reason: null, pointed: 1, proposed: 0, dropped: 0, input_tokens: 0, output_tokens: 0 },
      plan: {
        next: "questions",
        scope: { status: "in_scope", regime: null, message: null, cue: null, start: null, end: null, scores: {}, override_allowed: true },
        fork: { variance_needed: "unknown", explanation: "It is not clear yet whether the design departs from an acceptable solution. The questions below help decide; nothing is assumed.", cues: [], halves: HALVES },
        questions: [
          question("part4_design", "Is a registered engineer designing the structure under Part 4?"),
          question("assembly.description", "What is the wall, floor or roof assembly made of, layer by layer?"),
          question("sprinklered", "Is the building sprinklered?"),
          question("legal_description", "What is the legal description (lot, block and plan, or ATS)?", "administrative"),
          question("mailing_address", "What mailing address should the officer use?", "administrative"),
        ],
        not_sure: [],
        pre_application: { jurisdiction_id: "edmonton", jurisdiction_name: "City of Edmonton", resolved_by: "description", steps: [] },
        route_notice: null,
        candidates_seen: 0,
        ...over.plan,
      },
    },
  };
}

const choice = (provision: string, title: string, part: number) => ({
  id: `choice_${provision}`, provision, provision_id: `${provision}(1)`, title, part, citation: `NBC(AE) 2023 p2, Div B, Sentence ${provision}(1)`,
  quote: "1) Except as provided in Sentences (6) to (10), the maximum aggregate area of", question: "The code says: ...",
});

function identifyResult(over: Partial<IdentifyResult> = {}): IdentifyResult {
  const articles = ["9.10.14.4.", "9.10.14.5.", "3.1.6.8.", "3.2.3.8.", "9.10.11.2.", "9.10.12.4.", "9.10.14.2.", "3.2.3.1.", "3.2.3.6.", "9.10.12.3."].map((provision, i) => ({
    provision, provision_id: `${provision}(1)`, title: `Article ${provision}`, rank: i + 1, part: Number(provision.split(".")[0]), status: i < 3 ? "choice" : "candidate",
  }));
  return {
    mode: "fake", label: "All 2080 Division B articles were scored.", narrowed: true, message: null, committed: [], decisions: {}, case_version: 4,
    choices: [choice("9.10.14.4.", "Openings in Exposing Building Face", 9), choice("9.10.14.5.", "Construction of Exposing Building Face", 9), choice("3.1.6.8.", "Combustible Window Sashes and Frames", 3)],
    articles, open_questions: [], questions: [],
    ...over,
  } as unknown as IdentifyResult;
}

function demoCase(type: Case["applicantType"] = "homebuilder"): Case {
  let c = reducer(emptyCase(type), { type: "setDescription", text: DEMO });
  c = reducer(c, { type: "noteIntake", result: intakeResult(), text: DEMO });
  return c;
}

/* —— Routes —— */

test("legacy hrefs translate to calm routes", () => {
  assert.equal(calmHref("#/describe"), "#/");
  assert.equal(calmHref("#/code-check"), "#/questions?first=code");
  assert.equal(calmHref("#/code-check?focus=cand-x"), "#/questions?focus=cand-x");
  assert.equal(calmHref("#/section-c"), "#/references");
  assert.equal(calmHref("#/application?tab=A&focus=field-owner"), "#/questions?focus=field-owner");
  assert.equal(calmHref("#/application?tab=alt&focus=field-risk"), "#/questions?focus=field-risk");
  assert.equal(calmHref("#/application?tab=D&focus=prof-role"), "#/questions?focus=section-d");
  assert.equal(calmHref("#/application?tab=D"), "#/questions?focus=section-d");
  assert.equal(calmHref("#/application?download=1"), "#/application?download=options");
  assert.equal(calmHref("#/application?review=1"), "#/review");
  assert.equal(calmHref("#/describe?focus=authority"), "#/questions?focus=authority");
  assert.equal(resolveRoute("/application", new URLSearchParams()).screen, "application");
  assert.equal(resolveRoute("/nowhere", new URLSearchParams()).screen, "start");
});

/* —— What we read —— */

test("what intake read becomes one confirm card per thing, with the applicant's words marked", () => {
  const c = demoCase();
  const groups = readGroups(c, DETAIL_IDS);
  // Nine facts, eight cards: the model's statement of the departure joins the rules fact of the same words.
  assert.equal(groups.length, 8);
  const alt = groups.find((g) => g.fact.field === "alternative")!;
  assert.deepEqual(alt.ids.sort(), ["fact_alt", "fact_stmt"]);
  assert.equal(alt.key, "field-alternative", "Section B's alternative is confirmed on its own field card");
  // Engine export keys are the browser's field ids.
  assert.ok(c.facts.some((f) => f.field === "owner" && f.status === "unconfirmed"));
  assert.ok(!c.facts.some((f) => f.field === "owner_name"));
  const deck = buildDeck(c, getGaps(c));
  const storeys = deck.find((i) => i.ref === "fact_storeys")!;
  assert.equal(storeys.kind, "fact");
  assert.equal(storeys.title, "How many storeys is the building?");
  assert.deepEqual(choicesFor(storeys).map((x) => x.label), ["Yes, 2 storeys", "No, something else"]);
  assert.equal(storeys.read?.source, "Your description");
  assert.equal(storeys.read?.sure.text, "Read from your words.");
  assert.equal(storeys.read?.words?.mark, "Two-storey");
  assert.equal(spokenValue("occupancy", "single_family"), "a single-family house");
  assert.equal(spokenValue("building_area_m2", 210), "210 m²");
});

test("the marked words stay inside their sentence and line", () => {
  const owner = snippet(DEMO, DEMO.indexOf("Jordan Lee"), DEMO.indexOf("Jordan Lee") + 10)!;
  assert.deepEqual(owner, { before: "Owner: ", mark: "Jordan Lee", after: "" });
  const area = snippet(DEMO, DEMO.indexOf("210 m²"), DEMO.indexOf("210 m²") + 6)!;
  assert.equal(area.before, "Two-storey infill house in Edmonton, about ");
  assert.equal(area.after, ".");
  assert.equal(snippet(DEMO, null, null), null);
});

test("one click confirms every fact of a card, and the export never sees a proposed value as confirmed", () => {
  let c = demoCase();
  const alt = buildDeck(c, getGaps(c)).find((i) => i.key === "field-alternative")!;
  c = reducer(c, { type: "confirmFacts", ids: alt.ids! });
  assert.ok(!c.facts.some((f) => alt.ids!.includes(f.id)), "the read facts are replaced by the applicant's click");
  const confirmed = c.facts.filter((f) => f.status === "confirmed" && f.source.type === "user_click" && f.value === DEPARTURE);
  assert.equal(confirmed.length, 2, "the departure and its statement twin");
  assert.ok(!getGaps(c).some((g) => g.id === "confirm-fact_alt" || g.id === "confirm-fact_stmt"));
  assert.ok(!buildDeck(c, getGaps(c)).some((i) => i.kind === "detail" && i.key === "field-alternative"), "never asked again");
});

test("Not right is the applicant's answer: recorded as a confirmed empty value, and the field is asked again", () => {
  let c = demoCase();
  c = reducer(c, { type: "rejectFacts", ids: ["fact_addr"] });
  const addr = factFor(c, "municipalAddress")!;
  assert.equal(addr.status, "confirmed");
  assert.equal(addr.value, null);
  assert.equal(addr.source.ref, NOT_RIGHT);
  const card = buildDeck(c, getGaps(c)).find((i) => i.key === "field-municipalAddress")!;
  assert.equal(card.kind, "detail", "the form card asks for the right address");
});

test("confirming the site's municipality answers the reviewing authority (never picked silently otherwise)", () => {
  let c = demoCase();
  assert.equal(c.authority, "");
  c = reducer(c, { type: "confirmFacts", ids: ["fact_muni"] });
  assert.equal(c.authority, "edmonton");
  assert.equal(buildDeck(c, getGaps(c), { includeDone: true }).find((i) => i.key === "authority")?.done, true);
});

test("a value already confirmed is not asked again when the description is read again", () => {
  let c = demoCase();
  c = reducer(c, { type: "confirmFacts", ids: ["fact_owner"] });
  const again = intakeResult({ facts: [fact("fact_owner_2", "owner_name", "Jordan Lee", "Jordan Lee")] });
  c = reducer(c, { type: "noteIntake", result: again, text: DEMO });
  assert.equal(factFor(c, "owner")?.status, "confirmed");
  assert.ok(!buildDeck(c, getGaps(c)).some((i) => i.kind === "fact" && i.title === "Who is the owner?"));
  // The earlier run's unconfirmed facts are gone (the engine removes them too).
  assert.ok(!c.facts.some((f) => f.id === "fact_storeys"));
});

/* —— The deck's order and the plan —— */

test("deck order: what we read, then the planner, then the remaining A/B details, code, your case, Section D", () => {
  let c = demoCase();
  c = reducer(c, { type: "noteIdentify", result: identifyResult() });
  const deck = buildDeck(c, getGaps(c));
  const first = (kind: string) => deck.findIndex((i) => i.kind === kind);
  const last = (kind: string) => deck.map((i) => i.kind).lastIndexOf(kind as never);
  assert.equal(deck[0].kind, "fact");
  assert.ok(last("fact") < first("plan"));
  assert.ok(last("plan") < first("authority"));
  assert.ok(first("authority") < first("candidate"));
  assert.ok(last("detail") < first("candidate"));
  assert.ok(last("candidate") < first("process"));
  assert.equal(deck.filter((i) => i.kind === "process").length, 6);
});

test("the planner asks at most five questions, ranked as the API ranks them, and its fields are not asked twice", () => {
  const c = demoCase();
  const deck = buildDeck(c, getGaps(c));
  const plan = deck.filter((i) => i.kind === "plan");
  assert.deepEqual(plan.map((i) => i.ref), ["intake.part4_design", "intake.assembly.description", "intake.sprinklered", "intake.legal_description", "intake.mailing_address"]);
  assert.equal(plan[0].context, "Why part4_design.", "each question shows why it is asked");
  assert.deepEqual(choicesFor(plan[2]).map((x) => x.label), ["Yes", "No", "Partly", "Not sure"]);
  // Legal description and mailing address are planner cards, so their form cards wait.
  assert.ok(!deck.some((i) => i.key === "field-legalDescription" || i.key === "field-mailingAddress"));
  assert.equal(plan.find((i) => i.ref === "intake.legal_description")?.section, "B");
  assert.equal(plan.find((i) => i.ref === "intake.mailing_address")?.section, "A");
});

test("Not sure on a planner question never blocks and is not asked again on its form card", () => {
  let c = demoCase();
  const record = intakeResult({ plan: { not_sure: ["intake.mailing_address"] } }).record;
  c = reducer(c, { type: "noteIntakeRecord", record });
  const gaps = getGaps(c);
  const all = buildDeck(c, gaps, { includeDone: true });
  assert.equal(all.find((i) => i.ref === "intake.mailing_address")?.done, true);
  const form = all.find((i) => i.key === "field-mailingAddress")!;
  assert.equal(form.done, true, "a blocking gap stays on the review, but the card is settled");
  assert.ok(gaps.some((g) => g.id === "detail-mailingAddress"));
  assert.ok(!buildDeck(c, gaps).some((i) => i.key === "field-mailingAddress"));
});

test("an answered planner field is done (the engine's fact, under the browser's name)", () => {
  let c = demoCase();
  c = reducer(c, { type: "adoptFacts", facts: [{ id: "ans", field: "sprinklered", value: "no", kind: "pointed", status: "confirmed", source: { type: "user_text", ref: "intake answer", quote: "no" } }] });
  assert.equal(buildDeck(c, getGaps(c), { includeDone: true }).find((i) => i.ref === "intake.sprinklered")?.done, true);
});

test("while intake reads, the deck holds one waiting card; a failed read can be skipped", () => {
  const c = reducer(emptyCase("homebuilder"), { type: "setDescription", text: DEMO });
  assert.deepEqual(buildDeck(c, getGaps(c), { intake: "running" }).map((i) => i.kind), ["reading"]);
  const failed = buildDeck(c, getGaps(c), { intake: "error", intakeNote: "Batatis could not be reached." });
  assert.equal(failed[0].kind, "reading");
  assert.equal(failed[0].optional, true);
  assert.ok(failed.some((i) => i.key === "field-owner"), "every A/B detail is still asked");
});

test("another regime shows only the redirect page until the applicant says it is a building-code question", () => {
  let c = reducer(emptyCase("contractor"), { type: "setDescription", text: "Plumbing contractor. We want an air admittance valve instead of a vent through the roof." });
  const redirect = {
    ...fact("fact_scope", "scope.redirect", "plumbing", "air admittance valve"),
    kind: "computed" as const, formula: 'scope check: "air admittance valve" reads as plumbing', inputs: ["desc"],
  };
  const result = intakeResult({
    facts: [redirect],
    plan: {
      next: "redirect", questions: [],
      scope: { status: "redirect", regime: { id: "plumbing", name: "plumbing", framework: "national_model_code", coverage: "roadmap", code: "National Plumbing Code", route: "the plumbing safety codes officer" }, message: "This reads as a plumbing question.", cue: "air admittance valve", start: 32, end: 52, scores: {}, override_allowed: true },
    },
  });
  c = reducer(c, { type: "noteIntake", result, text: c.description });
  const gaps = getGaps(c);
  assert.deepEqual(buildDeck(c, gaps).map((i) => i.kind), ["scope"]);
  const gap = gaps.find((g) => g.field === "scope.redirect")!;
  assert.equal(gap.severity, "blocking", "export waits for the applicant's choice");
  assert.equal(gapKey(c, gap), "scope");
  // The override is the applicant's confirmed click; the redirect fact goes.
  c = reducer(c, { type: "adoptFacts", facts: [{ id: "ov", field: "scope.redirect", value: "overridden", kind: "pointed", status: "confirmed", source: { type: "user_click", ref: "intake:scope", quote: "This is a building-code question." } }], drop: ["fact_scope"] });
  assert.ok(!buildDeck(c, getGaps(c)).some((i) => i.kind === "scope"));
  assert.ok(!getGaps(c).some((g) => g.field === "scope.redirect"));
});

/* —— Code identification —— */

test("code identification offers at most three quoted choices; the rest of the ranking stays in the library", () => {
  let c = demoCase();
  c = reducer(c, { type: "noteIdentify", result: identifyResult() });
  const deck = buildDeck(c, getGaps(c));
  const code = deck.filter((i) => i.section === "C");
  assert.ok(code.length <= 5, `Section C has ${code.length} cards`);
  assert.deepEqual(code.map((i) => i.provision), ["9.10.14.4.(1)", "9.10.14.5.(1)", "3.1.6.8.(1)"]);
  const card = code[0];
  assert.equal(card.title, "Does your design do something different from the rule on openings in exposing building face?");
  assert.doesNotMatch(card.title + card.context, /\d+\.\d+\.\d+/, "the article number stays behind Show the code");
  assert.deepEqual(choicesFor(card).map((x) => x.label), ["Yes, it differs", "No, it follows", "Not sure"]);
  assert.ok(!c.candidates.some((a) => a.provision.startsWith("3.2.3.8")), "ranked articles are not cards");
});

test("committed articles come first, decisions come back from the stored result, and a new run keeps answers", () => {
  let c = demoCase();
  c = reducer(c, { type: "noteIdentify", result: identifyResult({ committed: ["9.10.14.2."], decisions: { "9.10.14.4.": { decision: "yes", decided_at: "", open_question_id: null } } }) });
  const ids = c.candidates.map((a) => [a.provision, a.rank, a.answer]);
  assert.deepEqual(ids[0], ["9.10.14.2.(1)", "committed", null]);
  assert.deepEqual(ids[1], ["9.10.14.4.(1)", "choice", "yes"]);
  c = reducer(c, { type: "noteIdentify", result: identifyResult() });
  assert.equal(c.candidates.find((a) => a.provision === "9.10.14.4.(1)")?.answer, "yes", "a re-run keeps the earlier answer");
  assert.ok(!c.candidates.some((a) => a.provision === "9.10.14.2.(1)"), "no longer offered");
});

test("the code check shows its progress until identification is back, and says so when it cannot narrow", () => {
  const c = demoCase();
  const running = buildDeck(c, getGaps(c), { identify: "running" }).find((i) => i.kind === "code-run")!;
  assert.equal(running.title, "Checking the code for your project…");
  assert.equal(running.optional, true, "it never blocks the applicant");
  const wide = reducer(c, { type: "noteIdentify", result: identifyResult({ narrowed: false, message: "I could not narrow this down. Answer the questions so the next check can.", choices: [] }) });
  const note = buildDeck(wide, getGaps(wide)).find((i) => i.kind === "code-note")!;
  assert.equal(note.title, "I could not narrow this down.");
  const fallback = reducer(c, { type: "noteIdentify", result: identifyResult({ mode: "bm25_fallback" }) });
  assert.equal(buildDeck(fallback, getGaps(fallback)).find((i) => i.kind === "code-note")?.title, "This list comes from a keyword search.");
});

test("Not sure on a code card keeps its clarifying question on that card", () => {
  let c = demoCase();
  c = reducer(c, { type: "noteIdentify", result: identifyResult() });
  const card = buildDeck(c, getGaps(c)).find((i) => i.kind === "candidate")!;
  c = reducer(c, { type: "answerCandidate", id: card.ref, answer: "not-sure" });
  const gap = getGaps(c).find((g) => g.id === `question-q-from-${card.ref}`)!;
  assert.equal(gapKey(c, gap), card.key);
  assert.equal(aliasKey(c, `q-q-from-${card.ref}`), card.key);
  assert.equal(buildDeck(c, getGaps(c), { includeDone: true }).find((i) => i.key === card.key)?.done, true);
});

/* —— Unchanged rules —— */

test("every local gap that routes to questions has a card", () => {
  let c = demoCase();
  c = reducer(c, { type: "noteIdentify", result: identifyResult() });
  const gaps = getGaps(c);
  const keys = new Set(buildDeck(c, gaps, { includeDone: true }).map((i) => i.key));
  for (const gap of gaps) {
    const key = gapKey(c, gap);
    if (key) assert.ok(keys.has(key), `no card for gap ${gap.id} -> ${key}`);
  }
});

test("the reviewing authority is asked, Not sure yet is an answer, and nothing is picked silently", () => {
  const c = demoCase();
  const card = buildDeck(c, []).find((i) => i.key === "authority")!;
  assert.equal(c.authority, "");
  assert.equal(card.done, false);
  assert.deepEqual(choicesFor(card).map((x) => x.value), ["calgary", "edmonton", "unsure"]);
  const gap = { id: "jurisdiction", severity: "blocking" as const, label: "Reviewing authority", href: "#/describe?focus=authority" };
  assert.equal(gapKey(c, gap), "authority");
  assert.equal(buildDeck(c, [gap], { seen: new Set(["authority"]), includeDone: true }).find((i) => i.key === "authority")?.done, true);
});

test("before an application exists the Questions stage has no describe card (Start asks it once)", () => {
  for (const draft of ["", "We build hempcrete walls."]) {
    const state = preCaseState(draft);
    assert.deepEqual(state.items, [], "nothing to ask before a description");
    assert.doesNotMatch(state.line, /\?$/, "a quiet line, not a question");
  }
  assert.equal(preCaseState("").action, "Describe your project");
  assert.equal(preCaseState("We build hempcrete walls.").action, "Continue describing");
});

test("once described, no card asks again what the applicant is building", () => {
  for (const role of ["manufacturer", "contractor", "homebuilder"] as const) {
    const c = demoCase(role);
    for (const i of buildDeck(c, getGaps(c), { includeDone: true })) assert.doesNotMatch(i.title, /what are you building|what is the product called/i, `${role}: ${i.key}`);
  }
});

test("without a departure read, the proposed alternative offers the description instead of asking for it again", () => {
  let c = reducer(emptyCase("homebuilder"), { type: "setDescription", text: DEMO });
  let card = buildDeck(c, getGaps(c)).find((i) => i.key === "field-alternative")!;
  assert.equal(card.title, "Is this what you want to do differently?");
  assert.deepEqual(choicesFor(card).map((x) => x.label), ["Yes, use my description", "No, I’ll write it"]);
  c = reducer(c, { type: "setDetail", field: "alternative", value: c.description.trim(), section: "B" });
  card = buildDeck(c, getGaps(c), { includeDone: true }).find((i) => i.key === "field-alternative")!;
  assert.equal(card.done, true);
  assert.equal(alternativeChoice(c.description, DEMO), "confirm");
  assert.equal(alternativeChoice(c.description, "A rainscreen instead of housewrap."), "dismiss");
  assert.equal(alternativeChoice(c.description, " "), undefined);
});

test("section progress counts tracked cards per section", () => {
  const deck = buildDeck(demoCase(), [], { includeDone: true });
  const secs = sectionProgress(deck);
  assert.deepEqual(secs.map((s) => s.id), ["A", "B", "C", "D"]);
  assert.equal(secs.reduce((n, s) => n + s.items.length, 0), deckProgress(deck).total);
});

test("answered read cards stay in the progress as done", () => {
  let c = demoCase();
  const before = deckProgress(buildDeck(c, getGaps(c), { includeDone: true }));
  c = reducer(c, { type: "confirmFacts", ids: ["fact_storeys"] });
  const after = deckProgress(buildDeck(c, getGaps(c), { includeDone: true }));
  assert.equal(after.total, before.total);
  assert.equal(after.done, before.done + 1);
});

test("permit is optional and offered once", () => {
  const c = demoCase();
  const permit = buildDeck(c, []).find((i) => i.key === "field-permit")!;
  assert.equal(permit.optional, true);
  assert.equal(buildDeck(c, [], { seen: new Set(["field-permit"]) }).some((i) => i.key === "field-permit"), false);
});

test("Section D joins the deck with a real reference and stays open while its gaps remain", () => {
  let c = demoCase();
  assert.ok(!buildDeck(c, []).some((i) => i.kind === "section-d"));
  c = reducer(c, {
    type: "addCandidate",
    candidate: {
      id: "search-9.27.3.4.(1)", topic: "Insulating sheathing", provision: "9.27.3.4.(1)", part: 9, benchmark: false,
      identified: true, suggestion: "search", quote: { text: "", citation: "", source: "code" },
      departure: "x", clarifyingQuestion: "y", answer: null,
    },
  });
  const seen = new Set(["section-d"]);
  assert.equal(buildDeck(c, [], { seen, includeDone: true }).find((i) => i.kind === "section-d")?.done, true);
  const gap = { id: "needs-professional", severity: "blocking" as const, label: "x", href: "#/application?tab=D&focus=prof-role" };
  assert.equal(buildDeck(c, [gap], { seen, includeDone: true }).find((i) => i.kind === "section-d")?.done, false);
  assert.equal(buildDeck(c, []).find((i) => i.key === "cand-search-9.27.3.4.(1)")?.provision, "9.27.3.4.(1)");
});

test("new cards join the queue in form order, and unreached planner cards follow the latest ranking", async () => {
  const { mergeQueue, rankAhead } = await import("./deck.ts");
  const order = ["fact-a", "plan-x", "plan-y", "authority", "cand-1", "field-risk"];
  assert.deepEqual(mergeQueue(["fact-a", "authority", "field-risk"], ["cand-1"], order), ["fact-a", "authority", "cand-1", "field-risk"]);
  assert.deepEqual(rankAhead(["fact-a", "plan-y", "plan-x", "authority"], 0, order, (k) => k.startsWith("plan-")), ["fact-a", "plan-x", "plan-y", "authority"]);
  // The card on screen (and anything before it) keeps its place.
  assert.deepEqual(rankAhead(["fact-a", "plan-y", "plan-x"], 1, order, (k) => k.startsWith("plan-")), ["fact-a", "plan-y", "plan-x"]);
});

/* —— Review fixes: pending decisions, reopened references, page counts —— */

test("an answer the engine has not stored stays open in the deck", () => {
  let c = reducer(demoCase(), { type: "noteIdentify", result: identifyResult() });
  const card = c.candidates.find((x) => x.suggestion === "identify")!;
  c = reducer(c, { type: "answerCandidate", id: card.id, answer: "no" });
  c = reducer(c, { type: "markDecisionPending", id: card.id, pending: true });
  const open = buildDeck(c, getGaps(c)).find((i) => i.key === `cand-${card.id}`);
  assert.ok(open && !open.done, "a failed No is asked again");
  c = reducer(c, { type: "markDecisionPending", id: card.id, pending: false });
  assert.equal(buildDeck(c, getGaps(c)).find((i) => i.key === `cand-${card.id}`), undefined);
});

test("a reopened sentence-level reference is one card with its identify Yes, and only for that article", () => {
  let c = reducer(demoCase(), { type: "noteIdentify", result: identifyResult() });
  const [first, second] = c.candidates.filter((x) => x.suggestion === "identify");
  const sentence = (p: string) => `${p.match(/^\d+\.\d+\.\d+\.\d+\./)![0]}(1)`;
  const saved = (p: string, id: string) => ({ ...first, id, provision: sentence(p), suggestion: "search" as const, answer: "yes" as const });
  c = { ...c, candidates: [...c.candidates, saved(first.provision, "search-a"), saved(second.provision, "search-b")] };
  c = reducer(c, { type: "answerCandidate", id: first.id, answer: "yes" });
  c = reducer(c, { type: "noteIdentify", result: identifyResult() });
  const ids = c.candidates.map((x) => x.id);
  assert.equal(c.candidates.find((x) => x.id === first.id)?.answer, "yes", "the Yes survives the rebuild");
  assert.ok(!ids.includes("search-a"), "the same article is not shown twice");
  assert.ok(ids.includes("search-b"), "a Yes on one article never removes another article's saved card");
});

test("page counts read 1 page and 3 pages", async () => {
  const { pagesLabel } = await import("../intakeView.ts");
  assert.equal(pagesLabel(1), "1 page");
  assert.equal(pagesLabel(3), "3 pages");
});

test("a rebuilt card keeps a pending answer the engine never stored", () => {
  let c = reducer(demoCase(), { type: "noteIdentify", result: identifyResult() });
  const card = c.candidates.find((x) => x.suggestion === "identify")!;
  c = reducer(c, { type: "answerCandidate", id: card.id, answer: "not-sure" });
  c = reducer(c, { type: "markDecisionPending", id: card.id, pending: true });
  c = reducer(c, { type: "noteIdentify", result: identifyResult() });
  const rebuilt = c.candidates.find((x) => x.id === card.id)!;
  assert.equal(rebuilt.answer, "not-sure");
  assert.equal(rebuilt.pending, true);
  assert.ok(buildDeck(c, getGaps(c)).some((i) => i.key === `cand-${card.id}` && !i.done));
});
