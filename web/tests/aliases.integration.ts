/** J10: saved API case -> applicant edits -> real sync -> officer/PDF value projection.
 * Run by scripts/test-sync.py against its disposable SQLite engine, with live AI disabled.
 */
import assert from "node:assert/strict";
import { execFileSync } from "node:child_process";
import { fileURLToPath } from "node:url";
import { createEngine, type Engine } from "../src/api/client.ts";
import type { Case as EngineCase } from "../src/api/types.gen.ts";
import * as sync from "../src/api/sync.ts";
import { caseFromEngine } from "../src/calm/openCase.ts";
import { sheetFromEngine } from "../src/calm/reviewer/sheet.ts";
import { factFor, reducer } from "../src/model.ts";
import { professionalConfirmed } from "../src/professional.ts";

const fact = (id: string, field: string, value: string, withdrawn = false): EngineCase["facts"][number] => ({
  id, field, value, kind: "pointed", status: withdrawn ? "unconfirmed" : "confirmed",
  confidence: null, formula: null, inputs: [],
  source: { type: "user_text", ref: withdrawn ? "Answer withdrawn by applicant" : "SYNTHETIC API passage", quote: value, page: null, bbox: null },
});

const value = (rows: { label: string; value: string | null }[], label: string) => rows.find((r) => r.label === label)?.value;

/** The actual PDF export selector, run on the case read back from the HTTP API. */
function pdfValues(saved: EngineCase): Record<string, unknown> {
  const output = execFileSync(fileURLToPath(new URL("../../.venv/bin/python", import.meta.url)), ["-c", [
    "import json, sys",
    "from engine.models import Case",
    "from engine.export.scc import confirmed_values",
    "print(json.dumps(confirmed_values(Case.model_validate_json(sys.stdin.read()))))",
  ].join("\n")], {
    cwd: fileURLToPath(new URL("../../", import.meta.url)), input: JSON.stringify(saved), encoding: "utf8",
    env: { ...process.env, BATATIS_LIVE: "0", PYTHONDONTWRITEBYTECODE: "1" },
  });
  return JSON.parse(output);
}

type Check = (name: string, run: () => Promise<void>) => Promise<void>;

export async function checkSavedAliases(check: Check, api: Engine) {
  await check("J10: raw API answers reopen without duplicate writes and edits agree with officer/PDF", async () => {
    let saved = await api.createCase({ title: "SYNTHETIC raw API aliases", jurisdiction: { id: "edmonton", name: "Edmonton", authority: null } });
    for (const [field, text] of Object.entries({
      owner_name: "SYNTHETIC API owner", application_date: "2026-10-22", civic_address: "SYNTHETIC site",
      legal_description: "SYNTHETIC Lot 2 Block 3 Plan 4", representative: "SYNTHETIC representative",
      mailing_address: "SYNTHETIC mailing", alternative_description: "SYNTHETIC alternative", scope: "site",
      rationale: "SYNTHETIC rationale", risk_assessment: "SYNTHETIC risk", mitigating_measures: "SYNTHETIC mitigation",
      assumptions_and_limits: "SYNTHETIC limits", maintenance_operation: "SYNTHETIC upkeep", qualifications: "SYNTHETIC qualifications",
      professional_status: "not_engaged", "custom.authority_note": "SYNTHETIC data to preserve",
      "project.description": "SYNTHETIC saved description",
    })) {
      const f = fact(`api-${field}`, field, text);
      if (field === "project.description" || field === "owner_name") f.source.ref = "Your description";
      saved = await api.addFact(saved.id, f);
    }
    const original = structuredClone(saved);
    const missing = (await api.gaps(saved.id)).filter((g) => ["owner_name", "application_date", "civic_address", "legal_description", "risk_assessment"].includes(g.field));
    assert.deepEqual(missing, [], "the server already has these required answers");
    let c = caseFromEngine(saved, "homebuilder");
    assert.equal(factFor(c, "date")?.value, "2026-10-22", "the applicant must see the API date");
    assert.equal(factFor(c, "municipalAddress")?.value, "SYNTHETIC site");
    assert.equal(c.process.risk, "SYNTHETIC risk");
    sync.clearEngineSession();
    sync.adoptEngineCase(saved);
    assert.equal(await sync.pushFacts(saved.id, c.facts), null);
    await sync.syncJurisdiction(saved.id, c.authority, c.title);
    assert.deepEqual(await api.getCase(saved.id), original, "opening and saving unchanged aliases sends no writes");

    c = reducer(c, { type: "setDetail", field: "owner", value: "SYNTHETIC edited owner", section: "A" });
    c = reducer(c, { type: "setDetail", field: "legalDescription", value: "SYNTHETIC edited legal description", section: "B" });
    c = reducer(c, { type: "setProcess", field: "risk", value: "SYNTHETIC edited risks" });
    assert.equal(await sync.pushFacts(saved.id, c.facts), null);
    saved = await api.getCase(saved.id);
    assert.deepEqual(saved.facts.slice(0, original.facts.length), original.facts, "edits retain all existing API facts and provenance");
    assert.equal(saved.facts.length, original.facts.length + 3, "only the three edited facts are posted");
    const sheet = sheetFromEngine(saved);
    const pdf = pdfValues(saved);
    assert.equal(value(sheet.applicant, "Owner"), pdf.owner_name);
    assert.equal(pdf.owner_name, "SYNTHETIC edited owner");
    assert.equal(value(sheet.applicant, "Date of request"), pdf.request_date);
    assert.equal(value(sheet.supporting, "Registered professional"), "Not engaged yet");
    assert.equal(value(sheet.project, "Legal description"), pdf.legal_description);
    assert.equal(value(sheet.process, "Risk assessment"), pdf["process.risk_assessment"]);
    c = caseFromEngine(saved, "homebuilder");
    assert.equal(factFor(c, "owner")?.value, pdf.owner_name);
    assert.equal(factFor(c, "legalDescription")?.value, pdf.legal_description);
    assert.equal(c.process.risk, pdf["process.risk_assessment"]);
  });

  await check("J10: mixed aliases and withdrawals never resurrect or silently resubmit answers", async () => {
    let saved = await api.createCase({ title: "SYNTHETIC mixed alias withdrawals", authority: "calgary" });
    for (const f of [
      fact("owner-first", "owner_name", "SYNTHETIC old owner"),
      fact("date-first", "request_date", "2026-10-20"),
      fact("risk-first", "process.risk_assessment", "SYNTHETIC old risk"),
      fact("owner-second", "owner", "SYNTHETIC newer owner"),
      fact("date-second", "application_date", "2026-10-21"),
      fact("risk-second", "risk", "SYNTHETIC newer risk"),
      fact("owner-withdrawn", "section_a.owner_name", "", true),
      { ...fact("date-empty", "date", ""), status: "unconfirmed" as const },
      fact("risk-withdrawn", "risk_assessment", "", true),
      fact("scope-first", "scope", "jurisdiction"),
      fact("scope-withdrawn", "scope", "", true),
      fact("other", "custom.authority_note", "SYNTHETIC retained API data"),
    ]) saved = await api.addFact(saved.id, f);
    let c = caseFromEngine(saved, "contractor");
    assert.equal(factFor(c, "owner"), undefined, "newest owner withdrawal beats every older alias");
    assert.equal(factFor(c, "date"), undefined);
    assert.equal(factFor(c, "scope"), undefined);
    assert.equal(c.process.risk, "");
    assert.equal(c.authority, "calgary", "the application authority survives without a jurisdiction object");
    sync.clearEngineSession();
    sync.adoptEngineCase(saved);
    assert.equal(await sync.pushFacts(saved.id, c.facts), null);
    await sync.syncJurisdiction(saved.id, c.authority, c.title);
    assert.deepEqual(await api.getCase(saved.id), saved, "withdrawals and blank revisions are already saved");
    c = reducer(c, { type: "setDetail", field: "owner", value: "SYNTHETIC restored owner", section: "A" });
    c = reducer(c, { type: "setProcess", field: "risk", value: "SYNTHETIC restored risk" });
    assert.equal(await sync.pushFacts(saved.id, c.facts), null);
    let stored = await api.getCase(saved.id);
    assert.equal(pdfValues(stored).owner_name, "SYNTHETIC restored owner");
    c = reducer(c, { type: "setDetail", field: "owner", value: "", section: "A" });
    c = reducer(c, { type: "setProcess", field: "risk", value: "", });
    assert.equal(await sync.pushFacts(saved.id, c.facts), null);
    stored = await api.getCase(saved.id);
    assert.deepEqual(stored.facts.slice(0, saved.facts.length), saved.facts);
    const pdf = pdfValues(stored);
    assert.equal(pdf.owner_name, undefined);
    assert.equal(pdf["process.risk_assessment"], undefined);
    assert.equal(value(sheetFromEngine(stored).applicant, "Owner"), null);
    assert.equal(value(sheetFromEngine(stored).process, "Risk assessment"), null);
    c = caseFromEngine(stored, "contractor");
    assert.equal(factFor(c, "owner"), undefined);
    assert.equal(c.process.risk, "");
    assert.equal(factFor(c, "custom.authority_note")?.value, "SYNTHETIC retained API data");
    sync.clearEngineSession();
    sync.adoptEngineCase(stored);
    assert.equal(await sync.pushFacts(stored.id, c.facts), null);
    assert.deepEqual(await api.getCase(stored.id), stored, "reopening a withdrawal never creates another revision");
  });

  await check("J10: reopening an API jurisdiction outside the picker preserves its routing data", async () => {
    const saved = await api.createCase({ title: "SYNTHETIC portable authority", jurisdiction: { id: "red-deer", name: "Red Deer", authority: "City of Red Deer" } });
    const c = caseFromEngine(saved, "homebuilder");
    sync.clearEngineSession();
    sync.adoptEngineCase(saved);
    assert.equal(await sync.pushFacts(saved.id, c.facts), null);
    await sync.syncJurisdiction(saved.id, c.authority, c.title);
    assert.deepEqual(await api.getCase(saved.id), saved, "saving unrelated answers must not clear an API jurisdiction");
    assert.equal(c.authority, saved.jurisdiction?.id);
  });

  await check("J10: professional aliases retain provenance and a withdrawn registration stays withdrawn", async () => {
    let saved = await api.createCase({ title: "SYNTHETIC professional aliases" });
    for (const f of [
      fact("professional-role", "registered_professional.role", "SYNTHETIC engineer"),
      fact("registration-old", "apega_number", "SYNTHETIC supplied number"),
      fact("registration-withdrawn", "professional.registration", "", true),
      fact("status", "professional.status", "not_engaged"),
    ]) saved = await api.addFact(saved.id, f);
    let c = caseFromEngine(saved, "contractor");
    assert.equal(factFor(c, "professional.role")?.id, "professional-role");
    assert.equal(factFor(c, "professional.registration_number"), undefined);
    assert.equal(professionalConfirmed(c.facts), false, "engagement is separate from credentials");
    assert.equal(value(sheetFromEngine(saved).supporting, "Registration or seal"), null);
    const seal = fact("seal", "registered_professional.seal", "SYNTHETIC supplied seal reference");
    saved = await api.addFact(saved.id, seal);
    c = caseFromEngine(saved, "contractor");
    assert.deepEqual(factFor(c, "professional.seal"), { ...saved.facts.at(-1), field: "professional.seal" });
    assert.equal(value(sheetFromEngine(saved).supporting, "Registration or seal"), seal.value);
    sync.clearEngineSession();
    sync.adoptEngineCase(saved);
    assert.equal(await sync.pushFacts(saved.id, c.facts), null);
    assert.deepEqual(await api.getCase(saved.id), saved);
  });
}

// Focused mode uses the same disposable engine as the full sync suite.
if (process.argv[1] === fileURLToPath(import.meta.url)) {
  const base = process.env.SYNC_TEST_BASE;
  assert.match(base ?? "", /^http:\/\/(127\.0\.0\.1|localhost):\d+$/);
  const entries = new Map<string, string>();
  globalThis.sessionStorage = {
    get length() { return entries.size; }, key: (i) => [...entries.keys()][i] ?? null,
    getItem: (k) => entries.get(k) ?? null, setItem: (k, v) => { entries.set(k, String(v)); },
    removeItem: (k) => { entries.delete(k); }, clear: () => entries.clear(),
  };
  const originalFetch = globalThis.fetch;
  globalThis.fetch = (input, init) => originalFetch(typeof input === "string" && input.startsWith("/api") ? base + input.slice(4) : input, init);
  let failed = 0;
  try {
    await checkSavedAliases(async (name, run) => {
      try { await run(); console.log("PASS", name); }
      catch (e) { failed++; console.error("FAIL", name, e); }
    }, createEngine(base!));
  } finally {
    globalThis.fetch = originalFetch;
  }
  process.exitCode = failed ? 1 : 0;
}
