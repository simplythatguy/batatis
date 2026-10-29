import assert from "node:assert/strict";
import test from "node:test";
import type { IdentifyResult, RequirementRecord } from "../api/types.gen.ts";
import { emptyCase } from "../intake.ts";
import { getGaps, reducer } from "../model.ts";
import type { Case } from "../types.ts";
import { buildDeck } from "./deck.ts";
import { APPLIES_REASON, requirementDecision, requirementQueue } from "./requirements.ts";
import { identifyCandidates } from "../intakeView.ts";

/**
 * A stored requirement-ledger result: the shape `screen: "requirements"` returns.
 * `committed` and `choices` are empty; every candidate lives in `requirements`.
 */
const DESCRIPTION = "Two-storey infill house in Edmonton, about 210 m², with a window close to the property line.";

function record(over: Partial<RequirementRecord> & Pick<RequirementRecord, "id" | "provision_id">): RequirementRecord {
  return {
    division: "B",
    title: `Rule ${over.provision_id}`,
    role: "unresolved",
    disposition: "review",
    applicability: "unknown",
    human_confirmed: false,
    confirmation_fingerprint: null,
    confirmation_reason: null,
    confirmed_at: null,
    needs_review: true,
    source_status: "verified",
    citation: `NBC(AE) 2023 p2, Div B, Article ${over.provision_id}`,
    quote: `The requirement in ${over.provision_id} applies.`,
    quote_provision_id: `${over.provision_id}(1)`,
    pdf_page: 100,
    pdf_page_end: null,
    source_sha256: "abc",
    discoveries: [{ kind: "lexical", detail: "A full-text match.", evidence: null, evidence_id: null, evidence_ids: [], from_requirement: null, path: [over.id] }],
    evidence: [],
    evidence_ids: [],
    conditions: [],
    review_reasons: ["Discovery does not establish applicability or a departure."],
    ...over,
  };
}

function ledger(over: Partial<IdentifyResult> = {}): IdentifyResult {
  const rows = [
    record({ id: "B:9.10.14.4.", provision_id: "9.10.14.4." }),
    record({ id: "B:9.10.14.5.", provision_id: "9.10.14.5.", title: "Construction of exposing building face" }),
    record({ id: "B:3.1.6.8.", provision_id: "3.1.6.8.", title: "Combustible window sashes and frames" }),
    record({ id: "B:3.2.3.8.", provision_id: "3.2.3.8." }),
    record({ id: "B:9.10.11.2.", provision_id: "9.10.11.2." }),
    record({ id: "B:9.10.12.4.", provision_id: "9.10.12.4." }),
    record({ id: "B:9.10.14.2.", provision_id: "9.10.14.2." }),
    record({ id: "B:3.2.3.1.", provision_id: "3.2.3.1." }),
    record({ id: "B:3.2.3.6.", provision_id: "3.2.3.6." }),
    record({ id: "B:9.10.12.3.", provision_id: "9.10.12.3." }),
    record({ id: "B:9.10.15.1.", provision_id: "9.10.15.1." }),
    record({ id: "B:9.10.15.2.", provision_id: "9.10.15.2." }),
    record({
      id: "B:9.10.15.5.", provision_id: "9.10.15.5.", role: "supporting", disposition: "include",
      applicability: "confirmed", human_confirmed: true, confirmed_at: "2026-10-27T00:00:00Z",
      confirmation_reason: "The applicant confirmed this rule applies to this project.",
    }),
    record({
      id: "B:9.10.15.6.", provision_id: "9.10.15.6.", disposition: "exclude",
      human_confirmed: true, confirmed_at: "2026-10-27T00:00:00Z", confirmation_reason: "The wall has no openings here.",
    }),
    record({ id: "A:1.2.1.1.", provision_id: "1.2.1.1.", division: "A", role: "admin", title: "Alternative solution process" }),
  ];
  return {
    mode: "live",
    source: "codedb requirement discovery",
    label: "Full-text and reference discovery; candidates require human review.",
    narrowed: false,
    message: "Review the requirement ledger and its coverage gaps. Discovery does not determine a variance or technical compliance.",
    cached: false,
    case_version: 9,
    committed: [],
    choices: [],
    decisions: {},
    articles: [],
    questions: [],
    open_questions: [],
    requirements: rows,
    requirement_status: "needs_review",
    requirement_evidence: [],
    requirement_links: [],
    requirement_coverage: {
      source: null, scan_status: "scanned", graph_status: "traversed_with_gaps", applicability_status: "not_determined",
      exhaustive: false, articles_by_division: { A: 300, B: 1864, C: 40 }, provisions_scanned: 9000, notes_scanned: 0,
      query_chunks: 4, discovered: rows.length, human_confirmed: 2, gaps: [], limits: [], provider_requests: 0,
    },
    scope_assessments: [],
    input_fingerprint: "fp",
    benchmark: { identified: false, basis: "none", provision: null, provision_id: null, citation: null, sentence: null, departure: null, departure_status: "none", question: null, objectives: [], functions: [], attribution_missing: false },
    process_refs: [],
    model_ids: { screen: null, rerank: null, verifier: null },
    commit_policy: { status: "human_review" },
    engineering_required: "depends",
    title: null,
    scored_at: "2026-10-27T00:00:00Z",
    description_sha256: "sha",
    input_sha256: "sha",
    input_coverage_gaps: [],
    stale: false,
    persisted: true,
    trace: {
      articles_expected: 1864, articles_scored: 0, config: {}, config_hash: "h", dropped: [], exhaustive: false,
      fallback_reason: null, picks: [], ranker: "full-text and explicit-reference requirement discovery",
      seconds: 0.1, spend: {}, stages: [], usd: 0,
      verifier: "not run: human applicability review required",
    },
    ...over,
  } as unknown as IdentifyResult;
}

function caseWith(result: IdentifyResult = ledger()): Case {
  let c = reducer(emptyCase("homebuilder"), { type: "setDescription", text: DESCRIPTION });
  return reducer(c, { type: "noteIdentify", result });
}

test("a requirement-ledger run offers a bounded batch of applicability questions", () => {
  const deck = buildDeck(caseWith(), getGaps(caseWith()));
  const cards = deck.filter((i) => i.kind === "requirement");
  assert.equal(cards.length, 6, "six closest rules, not 1,864 cards");
  assert.equal(cards[0].provision, "9.10.14.4.");
  assert.equal(cards[0].title, "Does this rule apply to your project?");
  assert.equal(cards[0].optional, true, "review never blocks the rest of the application");
  assert.ok(deck.some((i) => i.kind === "code-ledger"), "the counts and the library link stay reachable");
});

test("an answered rule is not asked again but its card stays to change; an included rule asks about the departure", () => {
  const c = caseWith();
  assert.ok(!buildDeck(c, getGaps(c)).some((i) => i.kind === "requirement" && ["9.10.15.5.", "9.10.15.6."].includes(i.provision ?? "")), "answered rules are not asked twice");
  const deck = buildDeck(c, getGaps(c), { includeDone: true });
  const included = deck.find((i) => i.kind === "requirement" && i.provision === "9.10.15.5.");
  const excluded = deck.find((i) => i.kind === "requirement" && i.provision === "9.10.15.6.");
  assert.equal(included?.done, true, "an included rule is answered, and its card can still change the answer");
  assert.equal(excluded?.done, true, "an excluded rule is answered, and its card can still change the answer");
  assert.equal(deck.filter((i) => i.kind === "requirement" && !i.done).length, 6, "the open batch is unchanged");
  const cards = identifyCandidates(ledger(), []);
  const card = cards.find((a) => a.provision === "9.10.15.5.(1)");
  assert.ok(card, "an included rule becomes a departure card on the sentence it was quoted by");
  assert.equal(card.suggestion, "identify");
  assert.ok(!cards.some((a) => a.provision.startsWith("9.10.15.6.")), "an excluded rule never becomes a departure");
});

test("one applies answer makes one departure card, titled for its sentence only when another card shares the rule", () => {
  const c = caseWith();
  const deck = buildDeck(c, getGaps(c));
  const code = deck.filter((i) => i.kind === "candidate" && i.provision?.startsWith("9.10.15.5."));
  assert.equal(code.length, 1, "one card, not one per sentence of the article");
  assert.equal(code[0].provision, "9.10.15.5.(1)");
  assert.equal(code[0].title, "Does your design do something different from the rule on rule 9.10.15.5.?");
  // A second sentence of the same rule (from the code library) makes each title name its sentence.
  const two = reducer(c, { type: "addCandidate", candidate: { ...c.candidates[0], id: "search-9.10.15.5.(2)", provision: "9.10.15.5.(2)", suggestion: "search", answer: null } });
  const titles = buildDeck(two, getGaps(two)).filter((i) => i.kind === "candidate" && i.provision?.startsWith("9.10.15.5.")).map((i) => i.title);
  assert.deepEqual(titles, [
    "Does your design do something different from sentence (1) of the rule on rule 9.10.15.5.?",
    "Is your design different from what sentence (2) of this rule asks for?",
  ]);
});

test("a rule already added from the code library gets no second departure card", () => {
  const stored = ledger();
  const added = { ...identifyCandidates(stored, [])[0], id: "search-9.10.15.5.(3)", provision: "9.10.15.5.(3)", suggestion: "search" as const, answer: "yes" as const };
  assert.deepEqual(identifyCandidates(stored, [added]).map((a) => a.provision), [], "the library card already covers the rule");
  // The rule's own card, once made, stays even after a library card on another of its sentences.
  const own = identifyCandidates(stored, [])[0];
  assert.deepEqual(identifyCandidates(stored, [own, added]).map((a) => a.id), ["id-9.10.15.5.(1)"]);
});

test("the dead-end ledger note is replaced, not repeated", () => {
  const deck = buildDeck(caseWith(), getGaps(caseWith()));
  assert.equal(deck.find((i) => i.kind === "code-note"), undefined);
  const summary = deck.find((i) => i.kind === "code-ledger")!;
  assert.equal(summary.title, "Rules that may apply");
  assert.equal(summary.optional, true);
});

test("a non-ledger result keeps the existing code-note behavior", () => {
  const wide = caseWith(ledger({ requirements: [], requirement_status: "not_run", narrowed: false, message: "I could not narrow this down. Answer the questions so the next check can." }));
  assert.equal(buildDeck(wide, getGaps(wide)).find((i) => i.kind === "code-note")?.title, "I could not narrow this down.");
});

test("reopening or re-running rebuilds the included cards and keeps their departure answer", () => {
  const stored = ledger();
  let c = caseWith(stored);
  const created = identifyCandidates(stored, []);
  assert.equal(created.length, 1, "only the included rule becomes a card");
  assert.equal(created[0].id, "id-9.10.15.5.(1)");
  c = reducer(c, { type: "answerCandidate", id: created[0].id, answer: "yes" });
  c = reducer(c, { type: "noteIdentify", result: stored });
  const again = identifyCandidates(stored, c.candidates);
  assert.equal(again.length, 1);
  assert.equal(again[0].id, "id-9.10.15.5.(1)", "the id a saved selection stores is stable");
  assert.equal(again[0].answer, "yes", "a Yes on the departure is not lost");
  assert.ok(!c.candidates.some((a) => a.provision === "9.10.15.6."), "an excluded rule never comes back");
});

test("one answer per rule: applicability never borrows the departure, and a reason is required", () => {
  const [first] = requirementQueue(ledger()).batch;
  assert.equal(first.provision_id, "9.10.14.4.");
  assert.deepEqual(requirementDecision(first, "applies"), { disposition: "include", role: "supporting", reason: APPLIES_REASON });
  assert.deepEqual(requirementDecision(first, "does-not-apply", "  The wall has no windows. "), {
    disposition: "exclude", role: "unresolved", reason: "The wall has no windows.",
  });
  assert.deepEqual(requirementDecision(first, "not-sure", "Need the designer's answer."), {
    disposition: "review", role: "unresolved", reason: "Need the designer's answer.",
  });
  assert.throws(() => requirementDecision(first, "does-not-apply", "   "), /reason is required/i);
  // An unresolved condition keeps the rule conditional, never silently applicable.
  const conditional = requirementQueue(ledger({
    requirements: [record({ id: "B:9.10.15.1.", provision_id: "9.10.15.1.", conditions: [{ field: "opening.area", status: "unknown", fact_ids: [] }] })],
  })).batch[0];
  assert.equal(requirementDecision(conditional, "applies").role, "conditional");
});
