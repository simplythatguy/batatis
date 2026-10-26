import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import type { Case as EngineCase, IdentifyResult, IntakeResult } from "../api/types.gen.ts";
import { toViewRow } from "../api/sectionC.ts";
import { engineField } from "../intakeFields.ts";
import { displayValue, factFor, getGaps, reducer } from "../model.ts";
import { professionalConfirmed } from "../professional.ts";
import { caseFromEngine, latestFacts, openedCase, reviewedDescription, selectedArticles } from "./openCase.ts";

const fact = (id: string, field: string, value: string, ref = "Typed in Section A") => ({
  id, field, value, kind: "pointed" as const, status: "confirmed" as const, confidence: null, formula: null, inputs: [],
  source: { type: "user_text" as const, ref, quote: value, page: null, bbox: null },
});

const saved = (over: Partial<EngineCase> = {}): EngineCase => ({
  id: "case_abc", title: "NorthCore CX exterior sheathing board", version: 7, created_at: "", updated_at: "",
  evidence: [], gaps: [], section_c: [], relevance: null, provisions: ["9.27.3.4.(1)"], selected_articles: null,
  jurisdiction: { id: "edmonton", name: "Edmonton", authority: null } as EngineCase["jurisdiction"],
  facts: [
    fact("f1", "owner", "NorthCore Building Products Ltd."),
    fact("f2", "owner", "NorthCore Ltd."),
    fact("f3", "representative", "Dana"),
    { ...fact("f3-withdrawn", "representative", ""), status: "unconfirmed" as const, source: { type: "user_click" as const, ref: "Answer withdrawn by applicant", quote: "", page: null, bbox: null } },
    fact("desc-description", "project.description", "We make NorthCore CX and it replaces the housewrap.", "Your description"),
    fact("f4", "process.risk_assessment", "Moisture could collect.", "Typed on the alternative path"),
  ] as EngineCase["facts"],
  ...over,
});

const REVIEWED_TEXT = "SYNTHETIC original review description.";
const REVIEWED_HASH = "50b5342dae7a3003937d752b1abe92ef2fb8a93aba6ab9e6e06c0df7c3e0904d";
const reviewResult = (hash: string | null): IntakeResult => ({
  case_id: "case_abc", case_version: 7, facts: [],
  record: {
    text_sha256: hash, ran_at: "", review: null, plan: null, pointers: [], files: [], conflicts: [], unresolved_citations: [],
    model: { status: "off", model: null, reason: null, pointed: 0, proposed: 0, dropped: 0, input_tokens: 0, output_tokens: 0 },
  },
});

test("a reopened intake keeps a verified description, but never substitutes edited text for the reviewed input", async () => {
  const result = reviewResult(REVIEWED_HASH);
  const original = saved({ facts: [fact("description", "project.description", REVIEWED_TEXT)] });
  const text = await reviewedDescription(original, result.record);
  assert.equal(text, REVIEWED_TEXT);
  const current = openedCase(original, "manufacturer", { intake: result, identify: null, reviewedText: text });
  assert.equal(current.intake?.text, current.description.trim());
  const edited = saved({ facts: [fact("description", "project.description", "SYNTHETIC edited proposal.")] });
  const reviewedText = await reviewedDescription(edited, result.record);
  const stale = openedCase(edited, "manufacturer", { intake: result, identify: null, reviewedText });
  assert.equal(stale.description, "SYNTHETIC edited proposal.");
  assert.equal(stale.intake?.text, null, "the screen and Start both require rereading an unmatched saved input");
  assert.notEqual(stale.intake?.text, stale.description.trim());
  assert.equal(await reviewedDescription(original, reviewResult(null).record), null, "legacy records without a hash stay unverified");
  assert.equal(openedCase(original, "manufacturer", { intake: result, identify: null }).intake?.text, null);
});

test("file edits invalidate the review even when every file is removed; a new intake resets that state", () => {
  const result = reviewResult(REVIEWED_HASH);
  let current = openedCase(saved(), "manufacturer", { intake: result, identify: null, reviewedText: REVIEWED_TEXT });
  current = reducer(current, { type: "addFiles", files: [{ id: "attachment", name: "UNIT-FIXTURE.pdf" }] });
  assert.equal(current.intake?.filesChanged, true);
  current = reducer(current, { type: "noteIntake", result, text: REVIEWED_TEXT });
  assert.equal(current.intake?.filesChanged, undefined);
  current = reducer(current, { type: "removeFile", id: "attachment" });
  assert.equal(current.files.length, 0);
  assert.equal(current.intake?.filesChanged, true);
  current = reducer(current, { type: "noteIntake", result, text: REVIEWED_TEXT });
  assert.equal(current.intake?.filesChanged, undefined);
});

test("latest answer per field wins and withdrawn answers are dropped", () => {
  const f = latestFacts(saved().facts);
  assert.equal(f.find((x) => x.field === "owner")?.value, "NorthCore Ltd.");
  assert.equal(f.some((x) => x.field === "representative"), false);
});

test("a saved case reopens with its answers, authority, process text and confirmed references", () => {
  const c = caseFromEngine(saved(), "manufacturer");
  assert.equal(c.title, "NorthCore CX exterior sheathing board");
  assert.equal(c.authority, "edmonton");
  assert.equal(c.description, "We make NorthCore CX and it replaces the housewrap.");
  assert.equal(c.process.risk, "Moisture could collect.");
  assert.equal(c.facts.find((f) => f.field === "project.description")?.id, "desc-description", "the saved fact is kept, so it is not re-sent");
  assert.equal(c.candidates.find((a) => a.provision === "9.27.3.4.(1)")?.answer, "yes");
  assert.ok(!c.candidates.some((a) => a.id.startsWith("desc-")), "no card is guessed from the description; intake and identify are read back from the engine");
  assert.equal(c.files.length, 0, "file names are not invented");
});

test("intake facts reopen under the browser's field names and stay unconfirmed until clicked", () => {
  const read = (id: string, field: string, value: string | number) => ({
    ...fact(id, field, String(value), "intake:description"), value, status: "unconfirmed" as const,
  });
  const c = caseFromEngine(saved({ provisions: [], facts: [...saved().facts, read("i1", "owner_name", "Jordan Lee"), read("i2", "storeys", 2), read("i3", "municipal_address", "10234 84 Avenue NW")] as EngineCase["facts"] }), "homebuilder");
  // The newest owner answer wins across the two names (owner, owner_name): the engine treats them as one field.
  assert.equal(c.facts.find((f) => f.field === "owner")?.id, "i1");
  assert.equal(c.facts.some((f) => f.field === "owner_name"), false);
  assert.equal(c.facts.find((f) => f.field === "municipalAddress")?.status, "unconfirmed");
  assert.equal(c.facts.find((f) => f.field === "storeys")?.value, 2);
});

/* —— Server-supported field names (engine/completeness.py _CORE, engine/process_fields.py PROCESS_ALIASES) —— */

/** GET /cases/case_01e74005fad8 from a local engine over the synthetic one-way HTTP fixture (status returned, 0 blocking gaps on the server). */
const API_CASE = JSON.parse(readFileSync(new URL("./fixtures/reopen-api-case.json", import.meta.url), "utf8")) as EngineCase;

const blocking = (c: ReturnType<typeof caseFromEngine>) => getGaps(c).filter((g) => g.severity === "blocking").map((g) => g.field);

test("the API fixture reopens complete: canonical names hydrate the date, address and every process answer", () => {
  let c = caseFromEngine(API_CASE, "manufacturer");
  assert.equal(c.facts.find((f) => f.field === "date")?.value, "2026-10-20");
  assert.equal(c.facts.find((f) => f.field === "municipalAddress")?.value, "000 Synthetic Street");
  assert.equal(c.process.rationale, "SYNTHETIC applicant rationale for the fixture.");
  assert.equal(c.process.qualifications, "SYNTHETIC document author role, no licence or competence asserted.");
  // The confirmed reference resolves through the deterministic lookup, as the browser does after opening.
  const card = c.candidates.find((a) => a.provision === "9.10.9.16.(1)")!;
  c = reducer(c, { type: "noteSectionC", rows: API_CASE.section_c.map((r) => toViewRow(r, card.id)) });
  assert.deepEqual(blocking(c), [], "no false missing fields after a complete case is reopened");
});

const confirmed = (id: string, field: string, value: string) => fact(id, field, value, "Typed on the alternative path");
const withdrawn = (id: string, field: string) => ({ ...fact(id, field, ""), status: "unconfirmed" as const, source: { type: "user_click" as const, ref: "Answer withdrawn by applicant", quote: "", page: null, bbox: null } });
const open = (facts: unknown[]) => caseFromEngine(saved({ provisions: [], facts: facts as EngineCase["facts"] }), "manufacturer");

test("every server name for a process answer reopens it, and the newest across names wins", () => {
  for (const [field, id] of [
    ["process.risk_assessment", "risk"], ["risk_assessment", "risk"], ["risk", "risk"], ["process.risk", "risk"],
    ["mitigating_measures", "mitigation"], ["mitigation", "mitigation"], ["process.mitigation", "mitigation"],
    ["assumptions_and_limits", "assumptions"], ["assumptions_limits", "assumptions"], ["assumptions", "assumptions"],
    ["maintenance_operation", "maintenance"], ["operation_maintenance", "maintenance"], ["rationale", "rationale"], ["qualifications", "qualifications"],
  ] as const) {
    const c = open([confirmed("p1", field, `Text under ${field}`)]);
    assert.equal(c.process[id], `Text under ${field}`, field);
  }
  const c = open([confirmed("old", "process.rationale", "Older prefixed"), confirmed("new", "rationale", "Newer bare")]);
  assert.equal(c.process.rationale, "Newer bare");
  assert.deepEqual(c.facts.filter((f) => f.field === "process.rationale").map((f) => f.id), ["new"], "one fact per logical field, the saved one");
  assert.equal(open([confirmed("old", "rationale", "Older bare"), confirmed("new", "process.rationale", "Newer prefixed")]).process.rationale, "Newer prefixed");
});

test("a newer withdrawal, empty or unconfirmed answer under another name never revives the older text", () => {
  assert.equal(open([confirmed("old", "rationale", "Older"), withdrawn("w", "process.rationale")]).process.rationale, "");
  assert.equal(open([confirmed("old", "process.rationale", "Older"), { ...confirmed("e", "rationale", ""), status: "unconfirmed" }]).process.rationale, "");
  const unconfirmed = open([confirmed("old", "rationale", "Older"), { ...confirmed("u", "process.rationale", "Read, not confirmed"), status: "unconfirmed" }]);
  assert.equal(unconfirmed.process.rationale, "", "like the engine, only a confirmed answer counts");
  assert.equal(unconfirmed.facts.find((f) => f.field === "process.rationale")?.id, "u", "the saved fact itself is kept as it is");
  assert.equal(open([{ ...confirmed("p", "rationale", "Proposed"), kind: "proposed" }]).process.rationale, "");
  // Section A and B: the newest name wins too, with its status kept for the confirm step.
  const date = open([confirmed("d1", "request_date", "2026-01-01"), { ...confirmed("d2", "application_date", "2026-10-20"), status: "unconfirmed" }]);
  assert.deepEqual(date.facts.filter((f) => f.field === "date").map((f) => [f.id, f.value, f.status]), [["d2", "2026-10-20", "unconfirmed"]]);
  assert.equal(open([confirmed("a1", "civic_address", "1 Old St"), withdrawn("a2", "municipal_address")]).facts.some((f) => f.field === "municipalAddress"), false);
  for (const [field, local] of [["application_date", "date"], ["section_a.date", "date"], ["civic_address", "municipalAddress"], ["address", "municipalAddress"], ["section_a.owner_name", "owner"], ["section_b.legal_description", "legalDescription"], ["applicant_name", "representative"]] as const) {
    const c = open([confirmed("x", field, "Value")]);
    assert.deepEqual(c.facts.filter((f) => f.field === local).map((f) => [f.id, f.value]), [["x", "Value"]], field);
  }
});

test("read names never change the field the browser writes", () => {
  assert.equal(engineField("date"), "request_date");
  assert.equal(engineField("municipalAddress"), "municipal_address");
  assert.equal(engineField("owner"), "owner_name");
  assert.equal(engineField("representative"), "owner_rep_name");
  assert.equal(engineField("legalDescription"), "legal_description");
  assert.equal(engineField("process.rationale"), "process.rationale");
});

test("reopening the API fixture and saving at once sends nothing: no re-post, no withdrawal", async () => {
  const store = new Map<string, string>();
  const requests: string[] = [];
  Object.assign(globalThis, {
    sessionStorage: { getItem: (k: string) => store.get(k) ?? null, setItem: (k: string, v: string) => store.set(k, v), removeItem: (k: string) => store.delete(k) },
    fetch: async (url: string, init?: { method?: string; body?: string }) => { requests.push(`${init?.method ?? "GET"} ${url} ${init?.body ?? ""}`); return new Response("{}", { status: 500 }); },
  });
  const sync = await import("../api/sync.ts");
  sync.clearEngineSession();
  sync.adoptEngineCase(API_CASE);
  const c = caseFromEngine(API_CASE, "manufacturer");
  assert.equal(await sync.pushFacts(API_CASE.id, c.facts), null);
  assert.deepEqual(requests, []);
});

/* —— Saved code-check selections (docs/api/selected-articles.md) —— */

const pick = (id: string, provision: string, answer: "yes" | "no" | "not-sure" | null = null, pending = false) => ({ id, provision, answer, pending });

test("a saved selection reopens every card in order with its answer, including unanswered and pending ones", () => {
  const c = caseFromEngine(saved({
    provisions: [],
    selected_articles: [pick("search-9.25.2.2.", "9.25.2.2."), pick("search-9.27.3.4.(1)", "9.27.3.4.(1)", "no"), pick("id-9.10.9.16.", "9.10.9.16.", "not-sure"), pick("search-9.36.2.6.", "9.36.2.6.", "yes", true)],
  }), "manufacturer");
  assert.deepEqual(c.candidates.map((a) => [a.id, a.provision, a.answer, Boolean(a.pending)]), [
    ["search-9.25.2.2.", "9.25.2.2.", null, false],
    ["search-9.27.3.4.(1)", "9.27.3.4.(1)", "no", false],
    ["id-9.10.9.16.", "9.10.9.16.", "not-sure", false],
    ["search-9.36.2.6.", "9.36.2.6.", "yes", true],
  ]);
  assert.ok(c.questions.some((q) => q.cardId === "id-9.10.9.16."), "Not sure keeps its open question for the officer");
});

test("the saved selection comes back with the same ids, so reopening and saving sends the same list", () => {
  const list = [pick("search-9.25.2.2.", "9.25.2.2."), pick("provision-9.27.3.4.(2)", "9.27.3.4.(2)", "not-sure"), pick("search-9.36.2.6.", "9.36.2.6.", "yes", true)];
  assert.deepEqual(selectedArticles(caseFromEngine(saved({ selected_articles: list }), "manufacturer")), list);
});

test("an explicitly empty selection stays empty; only a never-saved one falls back to confirmed references", () => {
  assert.deepEqual(caseFromEngine(saved({ selected_articles: [] }), "manufacturer").candidates.filter((a) => a.provision.match(/^\d/)), [], "a removed reference is not refilled");
  assert.deepEqual(caseFromEngine(saved({ selected_articles: null }), "manufacturer").candidates.map((a) => [a.id, a.answer]), [["search-9.27.3.4.(1)", "yes"]]);
});

test("a selected, unanswered or pending card never becomes a confirmed benchmark when reopened", () => {
  const c = caseFromEngine(saved({ provisions: [], selected_articles: [pick("search-9.25.2.2.", "9.25.2.2."), pick("search-9.36.2.6.", "9.36.2.6.", "yes", true), pick("search-9.27.3.4.(1)", "9.27.3.4.(1)", "not-sure")] }), "manufacturer");
  assert.deepEqual(c.candidates.map((a) => [a.id, a.benchmark]), [["search-9.25.2.2.", false], ["search-9.36.2.6.", false], ["search-9.27.3.4.(1)", false]]);
  assert.deepEqual(c.sectionC, [], "nothing reaches Section C until its deterministic lookup returns");
});

const identified = (decisions: Record<string, string> = {}) => ({
  mode: "fake", label: "", narrowed: true, message: null, committed: [], case_version: 3, open_questions: [], questions: [],
  decisions: Object.fromEntries(Object.entries(decisions).map(([k, decision]) => [k, { decision }])),
  articles: [],
  choices: ["9.10.14.4.", "9.10.14.5."].map((provision) => ({ provision, provision_id: `${provision}(1)`, title: `Article ${provision}`, part: 9, quote: "1) Synthetic quote.", citation: null })),
}) as unknown as IdentifyResult;

test("with a saved selection, the stored identification never refills a removed card and keeps pending answers", () => {
  const list = [pick("search-9.25.2.2.", "9.25.2.2."), pick("id-9.10.14.4.(1)", "9.10.14.4.(1)", "no", true)];
  const c = openedCase(saved({ provisions: [], selected_articles: list }), "manufacturer", { intake: null, identify: identified({ "9.10.14.4.": "yes" }) });
  assert.deepEqual(c.candidates.map((a) => [a.id, a.answer, Boolean(a.pending), a.suggestion]), [
    ["search-9.25.2.2.", null, false, "search"],
    ["id-9.10.14.4.(1)", "no", true, "identify"],
  ], "9.10.14.5. was removed; the pending No is not replaced by the older stored Yes");
  assert.equal(c.candidates[1].quote.text, "1) Synthetic quote.", "the identified card keeps the stored wording");
  assert.deepEqual(selectedArticles(c), list);
});

test("an acknowledged identification decision stays the answer of its card; a legacy case keeps every identified card", () => {
  const c = openedCase(saved({ provisions: [], selected_articles: [pick("id-9.10.14.4.(1)", "9.10.14.4.(1)")] }), "manufacturer", { intake: null, identify: identified({ "9.10.14.4.": "yes" }) });
  assert.deepEqual(c.candidates.map((a) => [a.id, a.answer]), [["id-9.10.14.4.(1)", "yes"]]);
  const legacy = openedCase(saved({ provisions: [], selected_articles: null }), "manufacturer", { intake: null, identify: identified() });
  assert.deepEqual(legacy.candidates.map((a) => [a.id, a.answer]), [["id-9.10.14.4.(1)", null], ["id-9.10.14.5.(1)", null]]);
});

test("a raw API application reopens every applicant field without changing saved provenance", () => {
  const api = saved({ jurisdiction: null, authority: "calgary", facts: [
    fact("owner-api", "section_a.owner_name", "API owner"),
    fact("rep-api", "applicant_name", "API representative"),
    fact("mail-api", "mailing_address", "API mailing address"),
    fact("date-api", "application_date", "2026-10-22"),
    fact("site-api", "civic_address", "API site address"),
    fact("legal-api", "section_b.legal_description", "Lot 1 Block 2 Plan 3"),
    fact("permit-api", "section_b.permit_number", "API permit"),
    fact("alternative-api", "alternative_description", "API proposed alternative"),
    fact("scope-api", "scope", "jurisdiction"),
    fact("rationale-api", "rationale", "Applicant rationale"),
    fact("risk-api", "risk_assessment", "Applicant risks"),
    fact("mitigation-api", "mitigation", "Applicant measures"),
    fact("assumptions-api", "process.assumptions_limits", "Applicant limits"),
    fact("maintenance-api", "operation_maintenance", "Applicant upkeep"),
    fact("qualifications-api", "qualifications", "Applicant qualifications"),
    fact("status-api", "professional_status", "not_engaged"),
    fact("registration-api", "apega_number", "Applicant supplied registration"),
  ] });
  const original = structuredClone(api);
  const c = caseFromEngine(api, "homebuilder");
  assert.equal(c.authority, "calgary");
  for (const [field, id] of Object.entries({
    owner: "owner-api", representative: "rep-api", mailingAddress: "mail-api", date: "date-api",
    municipalAddress: "site-api", legalDescription: "legal-api", permit: "permit-api",
    alternative: "alternative-api", scope: "scope-api", "professional.status": "status-api",
    "professional.registration_number": "registration-api",
  })) {
    const actual = factFor(c, field);
    const stored = api.facts.find((f) => f.id === id)!;
    assert.deepEqual(actual, { ...stored, field }, `${field} retains its original id, status and source`);
  }
  assert.deepEqual(c.process, { rationale: "Applicant rationale", risk: "Applicant risks", mitigation: "Applicant measures", assumptions: "Applicant limits", maintenance: "Applicant upkeep", qualifications: "Applicant qualifications" });
  assert.equal(displayValue(factFor(c, "professional.status")!), "Not engaged yet");
  assert.equal(factFor(c, "professional.role"), undefined, "engagement status is not a professional role");
  assert.equal(professionalConfirmed(c.facts), false);
  assert.deepEqual(api, original, "rehydration never mutates the API case");
});

test("the newest alias controls, including withdrawals and unconfirmed revisions", () => {
  const c = caseFromEngine(saved({ facts: [
    fact("owner-old", "owner_name", "Old owner"),
    fact("date-old", "request_date", "2026-10-20"),
    fact("risk-old", "process.risk_assessment", "Old risks"),
    fact("mitigation-old", "mitigation", "Old measures"),
    fact("owner-new", "owner", "New owner"),
    { ...fact("risk-new", "risk", "Unconfirmed new risks", "Applicant PDF"), status: "unconfirmed", confidence: .8 },
    { ...fact("owner-withdrawn", "section_a.owner_name", "", "Answer withdrawn by applicant"), status: "unconfirmed" },
    { ...fact("date-empty", "application_date", ""), status: "unconfirmed" },
    { ...fact("mitigation-withdrawn", "process.mitigating_measures", "", "Answer withdrawn by applicant"), status: "unconfirmed" },
    fact("other", "custom.authority_note", "API data to keep"),
  ] as EngineCase["facts"] }), "homebuilder");
  assert.equal(factFor(c, "owner"), undefined);
  assert.equal(factFor(c, "date"), undefined);
  assert.equal(c.process.mitigation, "");
  // As engine/process_fields.py: an unconfirmed reading is kept as a fact but is not the applicant's answer.
  assert.equal(c.process.risk, "");
  assert.equal(factFor(c, "process.risk_assessment")?.id, "risk-new");
  assert.equal(factFor(c, "process.risk_assessment")?.status, "unconfirmed");
  assert.equal(factFor(c, "custom.authority_note")?.value, "API data to keep");
});

test("rehydration keeps saved alias facts pointing at the same description source", () => {
  const api = saved({ facts: [
    fact("description", "project.description", "Applicant description", "Your description"),
    fact("owner-from-description", "owner_name", "Applicant owner", "Your description"),
  ] });
  const c = caseFromEngine(api, "homebuilder");
  assert.deepEqual(factFor(c, "owner"), { ...api.facts[1], field: "owner" });
  assert.equal(factFor(c, "project.description")?.id, "description");
});

test("a saved reviewing authority is preserved beyond the current picker choices", () => {
  const c = caseFromEngine(saved({ authority: null, jurisdiction: { id: "red-deer", name: "Red Deer", authority: "City of Red Deer" } }), "homebuilder");
  assert.equal(c.authority, "red-deer");
});
