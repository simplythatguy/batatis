import assert from "node:assert/strict";
import test from "node:test";
import { emptyCase } from "./intake.ts";
import { caseForRole, initialVisit } from "./visit.ts";
import type { Case, Fact } from "./types.ts";

function previousUser(): Case {
  const fact: Fact = {
    id: "f-prev",
    field: "owner",
    value: "Ada Previous",
    kind: "pointed",
    status: "confirmed",
    source: { type: "user_text", ref: "earlier session" },
  };
  return {
    ...emptyCase("manufacturer"),
    description: "Previous user hempcrete wall",
    authority: "edmonton",
    facts: [fact],
    files: [{ id: "file-1", name: "secret.pdf", read: false }],
    exampleId: "hempcrete",
    candidates: [
      {
        id: "cand-1",
        topic: "Hempcrete walls",
        provision: "9.27.5.1.",
        part: 9,
        benchmark: false,
        identified: false,
        suggestion: "search",
        quote: { text: "secret quote", citation: "none" },
        departure: "use hempcrete",
        clarifyingQuestion: "Which wall?",
        answer: "yes",
      },
    ],
  };
}

test("a cold visit does not open the previous user's case", () => {
  const stored = JSON.stringify({ phase: "case", case: previousUser(), note: "keep me" });
  const visit = initialVisit(stored);
  assert.equal(visit.phase, "who");
  assert.equal(visit.note, "");
  assert.equal(visit.case.applicantType, "homebuilder");
  assert.equal(visit.case.description, "");
  assert.equal(visit.case.authority, "");
  assert.equal(visit.case.facts.length, 0);
  assert.equal(visit.case.files.length, 0);
  assert.equal(visit.case.candidates.length, 0);
  assert.equal(visit.case.exampleId, undefined);
  const blob = JSON.stringify(visit);
  assert.equal(blob.includes("Previous user"), false);
  assert.equal(blob.includes("Ada Previous"), false);
  assert.equal(blob.includes("secret.pdf"), false);
  assert.equal(blob.includes("edmonton"), false);
  assert.equal(blob.includes("hempcrete"), false);
  assert.equal(blob.includes("9.27.5.1"), false);
});

test("a role switch starts a fresh case", () => {
  const previous = previousUser();
  const next = caseForRole("contractor", previous);
  assert.equal(next.applicantType, "contractor");
  assert.notEqual(next.id, previous.id);
  assert.equal(next.description, "");
  assert.equal(next.authority, "");
  assert.equal(next.facts.length, 0);
  assert.equal(next.files.length, 0);
  assert.equal(next.candidates.length, 0);
  assert.equal(next.exampleId, undefined);
  assert.deepEqual(next.questions, [], "the intake planner asks once the description is read");
  const blob = JSON.stringify(next);
  assert.equal(blob.includes("NorthCore"), false);
  assert.equal(blob.includes("Previous user"), false);
  assert.equal(blob.includes("Ada Previous"), false);
  assert.equal(blob.includes("secret.pdf"), false);
  assert.equal(blob.includes("edmonton"), false);
  assert.equal(blob.includes("hempcrete"), false);
});
