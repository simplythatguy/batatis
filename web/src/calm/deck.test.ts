import assert from "node:assert/strict";
import test from "node:test";
import { emptyCase } from "../intake.ts";
import { getGaps, reducer } from "../model.ts";
import type { Case } from "../types.ts";
import { aliasKey, alternativeChoice, buildDeck, choicesFor, deckProgress, gapKey, preCaseState, sectionProgress } from "./deck.ts";
import { calmHref, resolveRoute } from "./routes.ts";

const NORTHCORE =
  "We make NorthCore CX, a foil-faced rigid board that goes on the outside of the studs as continuous insulation and replaces the housewrap. We want builders to use it on houses and townhomes anywhere in Alberta.";

function described(text = NORTHCORE): Case {
  return reducer(emptyCase("manufacturer"), { type: "setDescription", text });
}

test("legacy hrefs translate to calm routes", () => {
  assert.equal(calmHref("#/describe"), "#/");
  assert.equal(calmHref("#/code-check"), "#/questions?first=code");
  assert.equal(calmHref("#/code-check?focus=cand-desc-subject-0"), "#/questions?focus=cand-desc-subject-0");
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

test("every local gap that routes to questions has a card", () => {
  const c = described();
  const gaps = getGaps(c);
  const deck = buildDeck(c, gaps);
  const keys = new Set(deck.map((i) => i.key));
  for (const gap of gaps) {
    const key = gapKey(c, gap);
    if (key) assert.ok(keys.has(key), `no card for gap ${gap.id} -> ${key}`);
  }
});

test("deck order follows the form: Section A, B, C, then D (the applicant's own case last)", () => {
  const deck = buildDeck(described(), []);
  const order = deck.map((i) => i.section).join("");
  assert.equal(order, [...order].sort().join(""), `sections out of order: ${order}`);
  const kinds = deck.map((i) => i.kind);
  assert.equal(deck.find((i) => i.section !== "A")?.kind, "authority", "Section B opens with the reviewing authority");
  assert.ok(kinds.lastIndexOf("detail") < kinds.indexOf("candidate"));
  assert.ok(kinds.lastIndexOf("candidate") < kinds.indexOf("process"));
  assert.equal(deck.filter((i) => i.kind === "process").length, 6);
});

test("the reviewing authority is asked, Not sure yet is an answer, and nothing is picked silently", () => {
  const c = described();
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
    assert.ok(!state.items.some((i) => (i.kind as string) === "describe" || (i.kind as string) === "role"));
    assert.doesNotMatch(state.line, /\?$/, "a quiet line, not a question");
  }
  assert.equal(preCaseState("").action, "Describe your project");
  assert.equal(preCaseState("We build hempcrete walls.").action, "Continue describing");
});

test("once described, no card asks again what the applicant is building", () => {
  for (const role of ["manufacturer", "contractor", "homebuilder"] as const) {
    const c = reducer(emptyCase(role), { type: "setDescription", text: NORTHCORE });
    const deck = buildDeck(c, getGaps(c), { includeDone: true });
    for (const i of deck) assert.doesNotMatch(i.title, /what are you building|what is the product called/i, `${role}: ${i.key} re-asks the description`);
    assert.ok(!getGaps(c).some((g) => g.id === "question-q-product" || g.id === "question-q-job"), `${role}: the description answers the starter question`);
  }
  // Without a description the starter question is still open (nothing is assumed).
  assert.ok(getGaps(emptyCase("contractor")).some((g) => g.id === "question-q-job"));
});

test("the proposed alternative offers the description instead of asking for it again", () => {
  let c = described();
  let card = buildDeck(c, getGaps(c)).find((i) => i.key === "field-alternative")!;
  assert.equal(card.title, "Is this the alternative you’re proposing?");
  assert.ok(card.quote && NORTHCORE.startsWith(card.quote.replace(/…$/, "")));
  assert.deepEqual(choicesFor(card).map((x) => x.label), ["Yes, use my description", "No, I’ll write it"]);
  assert.equal(card.done, false, "nothing is filled until the applicant says yes");
  c = reducer(c, { type: "setDetail", field: "alternative", value: c.description.trim(), section: "B" });
  card = buildDeck(c, getGaps(c), { includeDone: true }).find((i) => i.key === "field-alternative")!;
  assert.equal(card.done, true);
  assert.equal(alternativeChoice(c.description, NORTHCORE), "confirm");
  assert.equal(alternativeChoice(c.description, "A rainscreen instead of housewrap."), "dismiss");
  assert.equal(alternativeChoice(c.description, " "), undefined);
});

test("section progress counts tracked cards per section", () => {
  const deck = buildDeck(described(), [], { includeDone: true });
  const secs = sectionProgress(deck);
  assert.deepEqual(secs.map((s) => s.id), ["A", "B", "C", "D"]);
  assert.equal(secs.reduce((n, s) => n + s.items.length, 0), deckProgress(deck).total);
});

test("answered cards leave the open deck and count as done", () => {
  let c = described();
  const card = buildDeck(c, getGaps(c)).find((i) => i.kind === "candidate")!;
  c = reducer(c, { type: "answerCandidate", id: card.ref, answer: "no" });
  assert.ok(!buildDeck(c, getGaps(c)).some((i) => i.key === card.key));
  const all = buildDeck(c, getGaps(c), { includeDone: true });
  assert.equal(all.find((i) => i.key === card.key)?.done, true);
  const before = deckProgress(buildDeck(described(), [], { includeDone: true }));
  const after = deckProgress(all);
  assert.equal(after.total, before.total);
  assert.equal(after.done, before.done + 1);
});

test("a proposed address is confirmed on its field card, and Not right turns it into an input", () => {
  let c = described("The house is at 123 Example Street NW in Edmonton. We replace the housewrap.");
  const unconfirmed = c.facts.find((f) => f.field === "municipalAddress" && f.status === "unconfirmed");
  assert.ok(unconfirmed, "an unlabelled address is a proposal");
  let card = buildDeck(c, getGaps(c)).find((i) => i.key === "field-municipalAddress")!;
  assert.equal(card.kind, "fact");
  c = reducer(c, { type: "dismissFact", id: unconfirmed!.id });
  card = buildDeck(c, getGaps(c)).find((i) => i.key === "field-municipalAddress")!;
  assert.equal(card.kind, "detail");
});

test("permit is optional and offered once", () => {
  const c = described();
  const permit = buildDeck(c, []).find((i) => i.key === "field-permit")!;
  assert.equal(permit.optional, true);
  assert.equal(buildDeck(c, [], { seen: new Set(["field-permit"]) }).some((i) => i.key === "field-permit"), false);
});

test("Not sure on a code card keeps its clarifying question on that card", () => {
  let c = described();
  const card = buildDeck(c, getGaps(c)).find((i) => i.kind === "candidate")!;
  c = reducer(c, { type: "answerCandidate", id: card.ref, answer: "not-sure" });
  const gap = getGaps(c).find((g) => g.id === `question-q-from-${card.ref}`)!;
  assert.equal(gapKey(c, gap), card.key);
  assert.equal(aliasKey(c, `q-q-from-${card.ref}`), card.key);
  assert.ok(!buildDeck(c, getGaps(c)).some((i) => i.key === `q-q-from-${card.ref}`));
  // Not sure is an answer: the card is done and Continue is not locked by the officer question.
  assert.equal(buildDeck(c, getGaps(c), { includeDone: true }).find((i) => i.key === card.key)?.done, true);
});

test("storeys Not sure is an answer too", () => {
  let c = described("We replace the housewrap.");
  c = reducer(c, { type: "setStoreyCount", value: "" });
  const storeys = buildDeck(c, getGaps(c), { includeDone: true }).find((i) => i.key === "cand-desc-storeys");
  assert.equal(storeys?.kind, "storeys");
  assert.equal(storeys?.done, true);
});

test("Section D joins the deck with a real reference and stays open while its gaps remain", () => {
  let c = described();
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
  const code = buildDeck(c, []).find((i) => i.key === "cand-search-9.27.3.4.(1)")!;
  assert.equal(code.provision, "9.27.3.4.(1)");
});

test("proposed facts ask in plain words, with sentence-case sources and answers that say what they mean", () => {
  const c = described("We are building a two-storey house with hempcrete walls.");
  const card = buildDeck(c, getGaps(c)).find((i) => i.kind === "fact" && i.title.includes("storeys"))!;
  assert.equal(card.title, "How many storeys is the building?");
  assert.equal(card.context, "Your description says “two-storey”.");
  assert.deepEqual(choicesFor(card).map((x) => x.label), ["Yes, 2 storeys", "No, something else"]);
  const addr = described("The house is at 123 Example Street NW in Edmonton. We replace the housewrap.");
  const a = buildDeck(addr, getGaps(addr)).find((i) => i.key === "field-municipalAddress")!;
  assert.equal(a.title, "What is the site’s municipal address?");
  assert.match(a.context, /^Your description says “/);
  assert.match(choicesFor(a)[0].label, /^Yes, 123 Example Street/);
  for (const i of [card, a]) assert.doesNotMatch(i.title + i.context, /From Your|your storeys/);
});
