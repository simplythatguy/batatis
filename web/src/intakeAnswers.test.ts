import assert from "node:assert/strict";
import test from "node:test";
import { readFileSync } from "node:fs";
import { emptyCase } from "./intake.ts";
import { planFactAnswer, planInput } from "./intakeView.ts";
import { reducer } from "./model.ts";
import { ruleFacts } from "./calm/rulesView.ts";
import type { RuleIndex } from "./rules/evaluate.ts";

test("distance and the other side of the wall save independent facts used by the existing rules", () => {
  let c = emptyCase("owner");
  for (const [field, raw] of [["limiting_distance_m", "4 feet"], ["faces_public_way", "lane"]]) {
    const answer = planFactAnswer(field, raw);
    assert.ok(answer && "value" in answer);
    c = reducer(c, { type: "setRuleInput", field, value: answer.value, quote: answer.quote, rule: "intake" });
  }
  const index: RuleIndex = JSON.parse(readFileSync(new URL("../../engine/data/rules/index.json", import.meta.url), "utf8"));
  const facts = ruleFacts(c, index);
  assert.equal(facts.get("limiting_distance_m")?.value, 1.2192);
  assert.equal(facts.get("limiting_distance_m")?.source.quote, "4 feet");
  assert.equal(facts.get("faces_public_way")?.value, true);
  assert.equal(facts.get("faces_public_way")?.source.quote, "A lane");
  assert.equal(planFactAnswer("faces_public_way", "neighbour")?.value, false);
  assert.deepEqual(planInput("faces_public_way").choices?.map((choice) => choice.label), ["Neighbour’s lot", "A lane", "A street"]);
});

test("bad units produce an inline error instead of a fact", () => {
  assert.ok("error" in (planFactAnswer("building_area_m2", "140 bananas") ?? {}));
  assert.equal(planInput("building_area_m2").unit, "m²");
});
