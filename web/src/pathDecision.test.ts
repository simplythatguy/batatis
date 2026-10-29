import assert from "node:assert/strict";
import test from "node:test";
import { emptyCase } from "./intake.ts";
import { decidePath } from "./pathDecision.ts";
import type { Case, Fact } from "./types.ts";

let n = 0;
function fact(field: string, value: Fact["value"]): Fact {
  n += 1;
  return { id: `p${n}`, field, value, kind: "pointed", status: "confirmed", source: { type: "user_text", ref: "test", quote: String(value) } };
}

function soffit(overrides: Record<string, Fact["value"]> = {}): Case {
  const values: Record<string, Fact["value"]> = {
    storeys: 2, building_area_m2: 150, occupancy: "single_family", soffit_projects: true,
    soffit_to_property_line_m: 0.1, faces_public_way: false, limiting_distance_m: 0.3, ...overrides,
  };
  const facts = Object.entries(values).filter(([, value]) => value != null).map(([field, value]) => fact(field, value));
  return { ...emptyCase(), description: "Aluminum soffit along the north wall.", facts };
}

test("a firm departure still opens the variance package", () => {
  const decision = decidePath(soffit());
  assert.equal(decision.path, "alternative");
  assert.equal(decision.firm, true);
  assert.equal(decision.article, "9.10.15.5.(8)");
});

test("a rule that does not apply to the building does not decide the path", () => {
  const decision = decidePath(soffit({ storeys: 5, building_area_m2: 100 }));
  assert.equal(decision.path, "unresolved");
  assert.equal(decision.firm, false);
  assert.equal(decision.source, "unresolved");
});

test("the deck's demo house is no longer stopped by a rule meant for larger buildings", () => {
  const description = "Two-storey infill house in Edmonton, about 210 m². The east wall is 1.2 m from the property line, "
    + "and we want more window area facing the neighbour than the acceptable solution allows for unprotected openings.";
  const facts = [fact("storeys", 2), fact("building_area_m2", 210), fact("limiting_distance_m", 1.2), fact("occupancy", "single_family")];
  const decision = decidePath({ ...emptyCase(), description, facts });
  assert.notEqual(decision.path, "not_applicable");
  assert.equal(decision.asksRuleInputs, true, "it asks the inputs of the house rules that are still in play");
  assert.ok(decision.missing.includes("glazed_area_m2"));
});

test("a rule that does not apply still lets a variance request open the package", () => {
  const c = soffit({ storeys: 5, building_area_m2: 100 });
  const decision = decidePath({ ...c, facts: [...c.facts, fact("variance_requested", true)] });
  assert.equal(decision.path, "alternative");
  assert.equal(decision.source, "recorded");
});

test("a keyword inside a negation does not stop a real project", () => {
  const description = "We are the developer of a ten-storey building with seven levels of underground parking. "
    + "The exit stairwell doors and frames were installed with a wide gap between the frame and the concrete opening, "
    + "filled with foam and sealed with firestop sealant. We had a small-scale fire test done with the door swinging "
    + "into the furnace and no glazing. We want approval to keep them.";
  assert.notEqual(decidePath({ ...emptyCase(), description }).path, "not_applicable");
});
