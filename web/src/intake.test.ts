import assert from "node:assert/strict";
import test from "node:test";
import { emptyCase } from "./intake.ts";
import { reducer } from "./model.ts";

test("narrative addresses stop before the next sentence and need confirmation", () => {
  for (const address of ["0000 Example Way NW, Calgary", "123 St. Albert Rd. NW, St. Albert", "123 Example Ave. NW, Edmonton"]) {
    const text = `The site is ${address}. The firestop at the level 2 riser was installed by the plumbing sub.`;
    const c = reducer(emptyCase("contractor"), { type: "setDescription", text });
    const fact = c.facts.find(f => f.field === "municipalAddress");
    assert.equal(fact?.value, address);
    assert.equal(fact?.status, "unconfirmed");
    assert.equal(c.description, text);
    assert.equal(c.facts.find(f => f.field === "project.description")?.value, text);
  }
});

test("labelled address preserves abbreviations and stops at a field or sentence separator", () => {
  for (const suffix of ["\nThe firestop is incomplete.", "; Permit: BP-123", ". The firestop is incomplete."]) {
    const c = reducer(emptyCase("contractor"), { type: "setDescription", text: `Address: 123 St. Albert Rd. NW, St. Albert${suffix}` });
    const fact = c.facts.find(f => f.field === "municipalAddress");
    assert.equal(fact?.value, "123 St. Albert Rd. NW, St. Albert");
    assert.equal(fact?.status, "confirmed");
  }
  for (const text of ["Address: 123 Main St.", "Address: 123 Main St. The firestop is incomplete."]) {
    const c = reducer(emptyCase("contractor"), { type: "setDescription", text });
    assert.match(String(c.facts.find(f => f.field === "municipalAddress")?.value), /^123 Main St\.?$/);
    assert.equal(c.description, text);
  }
});

test("pasted text fills owner, address, legal description, and permit", () => {
  const text = [
    "Owner: Example Owner",
    "Address: 0000 Example Avenue NW, Edmonton",
    "Legal description: Lot 1, Block 1, Plan EXAMPLE",
    "Permit: BP-0000-00000",
    "We are replacing the firestop at the corridor wall.",
  ].join("\n");
  const c = reducer(emptyCase("contractor"), { type: "setDescription", text });
  const value = (field: string) => c.facts.find((fact) => fact.field === field)?.value;
  assert.equal(value("owner"), "Example Owner");
  assert.equal(value("municipalAddress"), "0000 Example Avenue NW, Edmonton");
  assert.equal(value("legalDescription"), "Lot 1, Block 1, Plan EXAMPLE");
  assert.equal(value("permit"), "BP-0000-00000");
  assert.equal(value("project.description"), text.trim());
  assert.equal(value("alternative"), undefined);
});

test("a labeled proposed alternative is the only paste that fills that field", () => {
  const text = ["Owner: Example Owner", "Proposed alternative: rated firestop at the corridor wall", "The rest of the brief stays in the description."].join("\n");
  const c = reducer(emptyCase("contractor"), { type: "setDescription", text });
  const value = (field: string) => c.facts.find((fact) => fact.field === field)?.value;
  assert.equal(value("alternative"), "rated firestop at the corridor wall");
  assert.equal(value("owner"), "Example Owner");
  assert.notEqual(value("alternative"), text.trim());
});
