import assert from "node:assert/strict";
import test from "node:test";
import { typeahead } from "./typeahead.ts";

const labels = ["Section A · Applicant", "Section B · Project", "Alternative-path documentation · Rationale", "Section C · Code references"];

test("a typed letter finds the next word that starts with it, then wraps to the top", () => {
  assert.equal(typeahead(labels, 0, "p"), 1, "Project, by its second word");
  assert.equal(typeahead(labels, 1, "s"), 3);
  assert.equal(typeahead(labels, 3, "s"), 0, "past the end it wraps around");
  assert.equal(typeahead(labels, 2, "R"), 3, "case-insensitive, starting after the current option");
  assert.equal(typeahead(labels, 3, "r"), 2, "wraps to Rationale");
});

test("with no word match it falls back to any option containing the letter, and -1 for none", () => {
  assert.equal(typeahead(labels, 0, "j"), 1, "Pro-j-ect");
  assert.equal(typeahead(labels, 0, "z"), -1);
  assert.equal(typeahead([], 0, "a"), -1);
});
