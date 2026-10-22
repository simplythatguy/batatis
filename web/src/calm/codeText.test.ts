import assert from "node:assert/strict";
import test from "node:test";
import { parseArticle, previewOf } from "./codeText.ts";

const OPENINGS = [
  "1) Except as provided in Sentences (6) to (10), the maximum aggregate area of",
  "unprotected openings in an exposing building face shall",
  "a) conform to Table 9.10.14.4.-A,",
  "b) conform to Subsection 3.2.3., or",
  "c) where the limiting distance is not less than 1.2 m, be equal to or less than",
  "i) the limiting distance squared, for residential occupancies,",
  "business and personal services occupancies, and",
  "ii) half the limiting distance squared, for mercantile occupancies.",
  "2) Openings in a wall having a limiting distance of less than 1.2 m shall be protected",
  "by closures. (See Table 9.10.13.1.)",
].join("\n");

test("an article splits into numbered sentences, clauses and subclauses without changing a word", () => {
  const a = parseArticle(OPENINGS);
  assert.equal(a.intro, "");
  assert.deepEqual(a.sentences.map((s) => s.n), ["1", "2"]);
  const [one, two] = a.sentences;
  assert.equal(one.lead, "Except as provided in Sentences (6) to (10), the maximum aggregate area of unprotected openings in an exposing building face shall");
  assert.deepEqual(one.clauses.map((c) => c.mark), ["a", "b", "c"]);
  assert.deepEqual(one.clauses[2].sub.map((c) => c.mark), ["i", "ii"]);
  assert.equal(one.clauses[2].sub[0].text, "the limiting distance squared, for residential occupancies, business and personal services occupancies, and");
  assert.equal(two.clauses.length, 0);
  assert.equal(two.lead, "Openings in a wall having a limiting distance of less than 1.2 m shall be protected by closures. (See Table 9.10.13.1.)");
  // Every word of the source survives, in order.
  const words = (t: string) => t.replace(/^\(?(\d+|[a-z]+)\)\s*/gm, "").split(/\s+/).filter(Boolean);
  const rebuilt = a.sentences.flatMap((s) => [s.lead, ...s.clauses.flatMap((c) => [c.text, ...c.sub.map((x) => x.text)])]).join(" ");
  assert.deepEqual(words(rebuilt), words(OPENINGS));
});

test("\"i)\" after \"h)\" is a clause, and a number that is not the next sentence stays in the text", () => {
  const letters = "abcdefgh".split("").map((l) => `${l}) item ${l},`).join("\n");
  const a = parseArticle(`1) The following apply:\n${letters}\ni) item i.\n3) not a sentence marker`);
  assert.equal(a.sentences.length, 1);
  assert.deepEqual(a.sentences[0].clauses.map((c) => c.mark).join(""), "abcdefghi");
  assert.match(a.sentences[0].clauses[8].text, /item i\. 3\) not a sentence marker$/);
});

test("a heading with no numbered sentences keeps its words as the intro", () => {
  const a = parseArticle("This Subsection applies to\nall buildings.");
  assert.equal(a.sentences.length, 0);
  assert.equal(a.intro, "This Subsection applies to all buildings.");
});

test("the collapsed row previews the lead, or the first clause when the lead is empty", () => {
  const a = parseArticle("1) Shall be\na) one, or\nb) two.\n2)\na) only a clause.");
  assert.equal(previewOf(a.sentences[0]), "Shall be");
  assert.equal(previewOf(a.sentences[1]), "only a clause.");
});

test("a wrapped cross-reference such as \"(b) and (c) of Sentence (2)\" stays in its clause", () => {
  const a = parseArticle("1) Doors shall\na) comply with Clauses\n(b) and (c) of Sentence (2), or\nb) be tested.");
  assert.deepEqual(a.sentences[0].clauses.map((c) => c.mark), ["a", "b"]);
  assert.equal(a.sentences[0].clauses[0].text, "comply with Clauses (b) and (c) of Sentence (2), or");
});
