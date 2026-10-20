import assert from "node:assert/strict";
import test from "node:test";
import { emptyCase } from "./intake.ts";
import { reducer } from "./model.ts";

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
