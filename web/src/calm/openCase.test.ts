import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import type { Case as EngineCase } from "../api/types.gen.ts";
import { toViewRow } from "../api/sectionC.ts";
import { engineField } from "../intakeFields.ts";
import { getGaps, reducer } from "../model.ts";
import { caseFromEngine, latestFacts } from "./openCase.ts";

const fact = (id: string, field: string, value: string, ref = "Typed in Section A") => ({
  id, field, value, kind: "pointed" as const, status: "confirmed" as const, confidence: null, formula: null, inputs: [],
  source: { type: "user_text" as const, ref, quote: value, page: null, bbox: null },
});

const saved = (over: Partial<EngineCase> = {}): EngineCase => ({
  id: "case_abc", title: "NorthCore CX exterior sheathing board", version: 7, created_at: "", updated_at: "",
  evidence: [], gaps: [], section_c: [], relevance: null, provisions: ["9.27.3.4.(1)"],
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
