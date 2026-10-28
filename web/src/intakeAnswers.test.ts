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

test("a storey count has to be a whole number", () => {
  assert.equal(planFactAnswer("storeys", "20"), null);
  assert.equal(planFactAnswer("storeys", "20 you")?.error, "Enter a whole number.");
  assert.equal(planFactAnswer("dwelling_units", "2.5")?.error, "Enter a whole number.");
});

test("bad units produce an inline error instead of a fact", () => {
  assert.ok("error" in (planFactAnswer("building_area_m2", "140 bananas") ?? {}));
  assert.equal(planInput("building_area_m2").unit, "m²");
});

test("a conflict between readings is settled by the applicant's typed answer, not by another reading", async () => {
  const { planQuestions } = await import("./intakeView.ts");
  const q = { id: "intake.building_area_m2", field: "building_area_m2", kind: "conflict", text: "What is the building area?", why: "", unblocks: [], splits: [], priority: "critical", provision: null };
  const c = { ...emptyCase(null), intake: { text: "", facts: [], factIds: [], record: { plan: { scope: { status: "in_scope" }, questions: [q], asked: [q], not_sure: [] } } } } as never;
  const read = { ...c as object, facts: [{ id: "r", field: "building_area_m2", value: 31.5, kind: "pointed", status: "confirmed", source: { type: "file", ref: "plans", quote: "31.5 m²" } }] } as never;
  assert.equal(planQuestions(read)[0].done, false, "a reading does not settle its own conflict");
  const answered = reducer(read, { type: "setRuleInput", field: "building_area_m2", value: 148, rule: "intake", quote: "148 m²" });
  assert.equal(planQuestions(answered)[0].done, true);
});

test("lot, block and plan read as parts join into one legal description", async () => {
  const { legalFromParts } = await import("./intakeView.ts");
  assert.equal(legalFromParts({ lot: "4", block: "12", plan: "0721234" }), "Lot 4, Block 12, Plan 0721234");
  assert.equal(legalFromParts({ ats_qtr: "SW", ats_sec: "12", ats_twp: "34", ats_rge: "5", ats_mer: "4" }), "SW-12-34-5-W4");
  assert.equal(legalFromParts({}), "");
});
