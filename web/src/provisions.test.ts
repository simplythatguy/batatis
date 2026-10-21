import assert from "node:assert/strict";
import test from "node:test";
import { emptyCase } from "./intake.ts";
import { lookupBasis, reducer } from "./model.ts";
import { confirmedProvisions } from "./provisions.ts";
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
