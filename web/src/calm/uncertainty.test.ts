import assert from "node:assert/strict";
import test from "node:test";
import { emptyCase } from "../intake.ts";
import { reducer } from "../model.ts";
import { isUncertainAnswer, requestedUncertaintyRow } from "./uncertainty.ts";

test("saved abstentions remain open and explicit responses await the officer", () => {
  const item = { field: "clarification.oq_saved", gap_id: "oq_saved", note: "Which wall is affected?" };
  let c = { ...emptyCase("contractor"), questions: [{ id: "return-clarification.oq_saved", field: item.field, text: item.note, why: "Requested by the officer" }] };
  for (const answer of ["Not sure", "not-sure", "not_sure", "Unknown", "I don't know", "?"]) {
    c = reducer(c, { type: "answerQuestion", id: c.questions[0].id, answer });
    assert.equal(requestedUncertaintyRow(c, item, true)?.state, "open", answer);
  }
  c = reducer(c, { type: "answerQuestion", id: c.questions[0].id, answer: "The west wall." });
  assert.equal(requestedUncertaintyRow(c, item, false)?.state, "unsaved");
  assert.equal(requestedUncertaintyRow(c, item, true)?.state, "pending");
  assert.match(requestedUncertaintyRow(c, item, true)!.href, /q-return-clarification\.oq_saved$/);
});

test("an unavailable or officer-owned request does not pretend it has an applicant fix card", () => {
  const c = emptyCase("contractor");
  assert.equal(requestedUncertaintyRow(c, { field: "codecheck.desc-legacy", gap_id: "q-from-desc-legacy", note: "Clarify the assembly" }, true)?.state, "review");
  assert.equal(requestedUncertaintyRow(c, { field: "professional_requirement", gap_id: "professional:professional_requirement", note: "Officer determination" }, true), null);
  assert.equal(isUncertainAnswer(false), false);
  assert.equal(isUncertainAnswer("No"), false);
});
