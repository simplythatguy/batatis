import assert from "node:assert/strict";
import test from "node:test";
import { emptyCase } from "./intake.ts";
import { getGaps, reducer } from "./model.ts";
import { evidenceRecorded, practiceFromReview, sectionDIssueStatus } from "./professional.ts";

test("prescriptive yes and reserved judgement no leave needs_professional open", () => {
  let c = reducer(emptyCase("homebuilder"), { type: "notePractice", value: true });
  c = reducer(c, { type: "answerScope", field: "prescriptive_route_confirmed", answer: "yes" });
  c = reducer(c, { type: "answerScope", field: "professional_judgement_required", answer: "no" });
  assert.ok(getGaps(c).some((gap) => gap.id === "needs-professional"));
  assert.equal(
    sectionDIssueStatus({ practice: true, facts: c.facts, evidenceLinked: true }),
    "needs_professional",
  );

  c = reducer(c, { type: "setProfessionalFact", field: "role", value: "architect" });
  c = reducer(c, { type: "setProfessionalFact", field: "registration_number", value: "AAA-2048" });
  assert.equal(getGaps(c).some((gap) => gap.id === "needs-professional"), false);
  assert.equal(
    sectionDIssueStatus({ practice: true, facts: c.facts, evidenceLinked: true }),
    "evidence_listed",
  );
});

test("applicant No/Yes/Yes/No does not clear needs-professional", () => {
  let c = reducer(emptyCase("contractor"), { type: "notePractice", value: true });
  const answers = [
    ["part4_design", "no"],
    ["ahj_requires_professional", "yes"],
    ["special_safety_concerns", "yes"],
    ["roof_trusses", "no"],
  ] as const;
  for (const [field, answer] of answers) {
    c = reducer(c, { type: "answerScope", field, answer });
  }
  assert.ok(getGaps(c).some((gap) => gap.id === "needs-professional"));
  assert.equal(c.practiceOfEngineering, true);
  for (const [field] of answers) {
    const fact = c.facts.find((item) => item.field === `professional.${field}`);
    assert.equal(fact?.status, "unconfirmed");
  }
  assert.equal(practiceFromReview(true, "no", false), true);
  assert.equal(practiceFromReview(undefined, "no", false), "unknown");
  assert.equal(evidenceRecorded("provided"), true);
  assert.equal(evidenceRecorded("evidence_listed"), true);
  assert.equal(evidenceRecorded("not provided"), false);
});

test("a later evidence save keeps the earlier document", () => {
  let c = reducer(emptyCase("contractor"), {
    type: "saveEvidence",
    itemId: "wall",
    document: "First report",
    responsible: "Example Applicant",
    date: "2020-01-01",
  });
  c = reducer(c, {
    type: "saveEvidence",
    itemId: "wall",
    document: "Second report",
    responsible: "Example Applicant",
    date: "2021-06-01",
  });
  const titles = c.facts.filter((fact) => fact.field.endsWith(".title")).map((fact) => fact.value);
  assert.deepEqual(titles, ["First report", "Second report"]);
});

test("not sure on the prescriptive route stays an open question", () => {
  const c = reducer(emptyCase("homebuilder"), {
    type: "answerScope",
    field: "prescriptive_route_confirmed",
    answer: "not-sure",
  });
  const question = c.questions.find((item) => item.id === "q-scope-prescriptive_route_confirmed");
  assert.equal(question?.answer, undefined);
  assert.match(question?.why ?? "", /officer/);
  assert.ok(getGaps(c).some((gap) => gap.id === "question-q-scope-prescriptive_route_confirmed"));
  assert.equal(
    c.facts.some((fact) => fact.field === "professional.prescriptive_route_confirmed"),
    false,
  );
});
