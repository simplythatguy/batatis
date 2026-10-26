import assert from "node:assert/strict";
import test from "node:test";
import { emptyCase } from "./intake.ts";
import { factFor, reducer } from "./model.ts";

const TEXT = "Two-storey infill house in Edmonton, about 210 m².\nOwner: Jordan Lee\nMunicipal address: 10234 84 Avenue NW, Edmonton";

test("the description is the applicant's own confirmed words; nothing is guessed from it in the browser", () => {
  const c = reducer(emptyCase("homebuilder"), { type: "setDescription", text: TEXT });
  assert.equal(c.description, TEXT);
  assert.deepEqual(c.facts.map((f) => [f.field, f.status]), [["project.description", "confirmed"]]);
  assert.equal(c.candidates.length, 0, "no keyword card: code identification offers the code questions");
  assert.equal(c.questions.length, 0, "no starter question: the intake planner asks what is missing");
  assert.equal(c.title, "New house application", "a sentence (with its city) is not a name; the engine names the case");
});

test("a name the applicant chose, or a saved one, survives description edits", () => {
  let c = reducer(emptyCase("homebuilder"), { type: "renameCase", title: "Infill sheathing" });
  c = reducer(c, { type: "setDescription", text: TEXT });
  assert.equal(c.title, "Infill sheathing");
  assert.equal(c.titleKept, true);
  c = reducer(c, { type: "setDescription", text: "" });
  assert.equal(c.title, "Infill sheathing", "clearing the description keeps the chosen name");
});

test("clearing the description clears its fact and title", () => {
  let c = reducer(emptyCase("contractor"), { type: "setDescription", text: TEXT });
  c = reducer(c, { type: "setDescription", text: "" });
  assert.equal(c.facts.length, 0);
  assert.equal(c.title, "New construction application");
});

test("an evidence acknowledgement that changes nothing keeps the same case, so autosave does not loop", () => {
  // Every save acknowledges the stored evidence ledger. A new object with the same content re-armed
  // the 500 ms autosave, whose save bumped the facts epoch and re-read rules, checklists and the pack
  // twice a second while idle.
  const ledger = [{ id: "f-ev", field: "evidence.ev-1.title", value: "SYNTHETIC test report", kind: "pointed" as const, status: "confirmed" as const, confidence: null, formula: null, inputs: [], source: { type: "engine" as const, ref: "ledger", quote: "" } }];
  let c = reducer(emptyCase("homebuilder"), { type: "setDescription", text: TEXT });
  c = reducer(c, { type: "ackEvidence", acked: [], deleted: [], rejected: [], facts: ledger, error: null });
  const again = reducer(c, { type: "ackEvidence", acked: [], deleted: [], rejected: [], facts: ledger.map((f) => ({ ...f })), error: null });
  assert.equal(again, c, "an unchanged acknowledgement returns the same case");
  const changed = reducer(c, { type: "ackEvidence", acked: [], deleted: [], rejected: [], facts: [{ ...ledger[0], value: "SYNTHETIC revised report" }], error: null });
  assert.notEqual(changed, c);
  assert.equal(changed.facts.find((f) => f.field === "evidence.ev-1.title")?.value, "SYNTHETIC revised report");
});

test("values the engine confirmed while reading become the case's values, as a reopened case loads them", () => {
  const c = emptyCase(null);
  const record = { ran_at: "2026-10-26", text_sha256: null, pointers: [], files: [], conflicts: [], unresolved_citations: [], model: { status: "off" } } as never;
  const result = { case_id: "c1", case_version: 2, record, facts: [
    { id: "f1", field: "owner_name", value: "Dana Whitfield", kind: "pointed", status: "confirmed", confidence: 0.8, source: { type: "user_text", ref: "intake:description", quote: "Dana Whitfield" } },
    { id: "f2", field: "storeys", value: 3, kind: "proposed", status: "unconfirmed", confidence: 0.4, source: { type: "file", ref: "photo", quote: "Three storeys" } },
  ] } as never;
  const next = reducer(c, { type: "noteIntake", result, text: "A house for Dana Whitfield." });
  assert.equal(factFor(next, "owner")?.value, "Dana Whitfield");
  assert.equal(factFor(next, "owner")?.status, "confirmed");
  assert.equal(factFor(next, "storeys")?.status, "unconfirmed");
});
