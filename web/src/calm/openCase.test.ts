import assert from "node:assert/strict";
import test from "node:test";
import type { Case as EngineCase } from "../api/types.gen.ts";
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
