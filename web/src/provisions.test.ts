import assert from "node:assert/strict";
import test from "node:test";
import { emptyCase } from "./intake.ts";
import { lookupBasis, reducer } from "./model.ts";
import { confirmedProvisions, reconcileSectionC, sameCards } from "./provisions.ts";
import type { Candidate, SectionCRow } from "./types.ts";

const candidate = (provision: string): Candidate => ({
  id: `c-${provision}`, provision, answer: "yes", identified: true, suggestion: "search", part: 3, benchmark: true,
  topic: "Firestops", quote: { text: "", citation: "CodeDB" }, departure: "depart", clarifyingQuestion: "Which part?",
} as Candidate);
const row = (provision: string): SectionCRow => ({ candidateId: `c-${provision}`, provision } as SectionCRow);

test("a lookup for an older candidate list cannot reorder or drop a newer draft", () => {
  let c = reducer(emptyCase("contractor"), { type: "addCandidate", candidate: candidate("3.1.9.1.(1)") });
  const basis = lookupBasis(c);
  c = reducer(c, { type: "addCandidate", candidate: candidate("3.1.9.1.(2)") });
  const late = reducer(c, { type: "reconcileSectionC", rows: [row("3.1.9.1.(1)")], basis });
  assert.equal(late, c, "rows computed for the older list are ignored");
  const current = reducer(c, { type: "reconcileSectionC", rows: [row("3.1.9.1.(1)"), row("3.1.9.1.(2)")], basis: lookupBasis(c) });
  assert.deepEqual(confirmedProvisions(current), ["3.1.9.1.(1)", "3.1.9.1.(2)"]);
});

test("a reopened case whose lookup only re-orders its cards is not an edit", () => {
  const card = (id: string, provision: string, answer: Candidate["answer"]): Candidate => ({
    id, topic: provision, provision, part: 9, benchmark: false, identified: true,
    quote: { text: "", citation: "", source: "code" }, departure: "x", clarifyingQuestion: "y", answer,
  });
  const c = { ...emptyCase("homebuilder"), candidates: [card("search-9.10.9.16.(1)", "9.10.9.16.(1)", "yes"), card("desc-x", "desc", null)] };
  const row = { provision: "9.10.9.16.(1)", citation: "NBC(AE) 2023 Div. B 9.10.9.16.(1)", pairs: [] } as unknown as SectionCRow;
  const next = reconcileSectionC(c, [row]);
  assert.notEqual(JSON.stringify(next.candidates), JSON.stringify(c.candidates), "the lookup moves the card");
  assert.ok(sameCards(next.candidates, c.candidates));
  assert.ok(!sameCards([{ ...c.candidates[0], answer: null }, c.candidates[1]], c.candidates));
});
