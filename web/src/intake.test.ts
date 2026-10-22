import assert from "node:assert/strict";
import test from "node:test";
import { emptyCase } from "./intake.ts";
import { reducer } from "./model.ts";

const TEXT = "Two-storey infill house in Edmonton, about 210 m².\nOwner: Jordan Lee\nMunicipal address: 10234 84 Avenue NW, Edmonton";

test("the description is the applicant's own confirmed words; nothing is guessed from it in the browser", () => {
  const c = reducer(emptyCase("homebuilder"), { type: "setDescription", text: TEXT });
  assert.equal(c.description, TEXT);
  assert.deepEqual(c.facts.map((f) => [f.field, f.status]), [["project.description", "confirmed"]]);
  assert.equal(c.candidates.length, 0, "no keyword card: code identification offers the code questions");
  assert.equal(c.questions.length, 0, "no starter question: the intake planner asks what is missing");
  assert.equal(c.title, "Two-storey infill house in Edmonton, about 210 m².");
});

test("clearing the description clears its fact and title", () => {
  let c = reducer(emptyCase("contractor"), { type: "setDescription", text: TEXT });
  c = reducer(c, { type: "setDescription", text: "" });
  assert.equal(c.facts.length, 0);
  assert.equal(c.title, "New construction application");
});
