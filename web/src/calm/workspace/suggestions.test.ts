import assert from "node:assert/strict";
import test from "node:test";
import { emptyCase } from "../../intake.ts";
import { reducer } from "../../model.ts";
import { blockForField, buildDocument } from "./document.ts";
import { acceptSuggestion, changedWords, draftSuggestions, freshSuggestions, rejectSuggestion, rewriteSuggestion } from "./suggestions.ts";

const result = { replacement: "detach", cited: [], removed_citations: [], notice: null };
test("a selected rewrite preserves every word outside its range and is stale after any newer edit", () => {
  let c = reducer(emptyCase("homebuilder"), { type: "setProcess", field: "risk", value: "Panels fall in wind." });
  const block = blockForField(buildDocument(c, []), "risk")!;
  const s = rewriteSuggestion("r", { blockId: block.id, text: block.text, start: 7, end: 11 }, result);
  assert.equal(s.after, "Panels detach in wind.");
  const action = acceptSuggestion(s, block);
  assert.ok(action);
  c = reducer(c, action);
  assert.equal(c.process.risk, "Panels detach in wind.");
  assert.deepEqual(freshSuggestions([s], buildDocument(c, []).flatMap(s => s.blocks)), []);
  assert.equal(acceptSuggestion(s, blockForField(buildDocument(c, []), "risk")!), null);
  assert.throws(() => rewriteSuggestion("bad", { blockId: block.id, text: "x", start: 0, end: 2 }, result));
});
test("whole-block rewrites use start=end and draft reject dismisses exactly its proposed fact", () => {
  const c = reducer(emptyCase("homebuilder"), { type: "setProcess", field: "risk", value: "Known risk" });
  c.facts.push({ id: "writing-1", field: "process.risk", value: "Draft risk", kind: "proposed", status: "unconfirmed", source: { type: "user_text", ref: "Writing draft" } });
  const sections = buildDocument(c, []), [s] = draftSuggestions(c, sections);
  assert.deepEqual([s.before, s.after, s.factId], ["Known risk", "Draft risk", "writing-1"]);
  const reject = rejectSuggestion(s);
  assert.deepEqual(reject, { type: "dismissFact", id: "writing-1" });
  assert.equal(draftSuggestions(reducer(c, reject!), sections).length, 0);
  assert.equal(rewriteSuggestion("whole", { blockId: s.blockId, text: "Known risk", start: 0, end: 0 }, result).after, "detach");
  assert.equal(rejectSuggestion({ ...s, origin: "rewrite", factId: undefined }), null);
});
test("tracked changes preserve whitespace and the unchanged prefix and suffix", () => {
  assert.deepEqual(changedWords("high wind and fall.", "high wind and detach."), { prefix: "high wind and ", removed: "fall", added: "detach", suffix: "." });
  assert.deepEqual(changedWords("", "New words"), { prefix: "", removed: "", added: "New words", suffix: "" });
});
