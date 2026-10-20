import assert from "node:assert/strict";
import test from "node:test";
import { emptyCase } from "./intake.ts";
import { codeCheckLabel, displayValue, factLabel, gapLabel, getGaps, plainFactStatus, reducer, shownProcessAnswer } from "./model.ts";
import { evidenceRecorded, practiceFromReview, professionalConfirmed, roleConfirmed, sectionDIssueStatus } from "./professional.ts";
import type { Fact } from "./types.ts";

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

test("a later evidence save keeps the earlier document as text", () => {
  let c = reducer(emptyCase("contractor"), {
    type: "saveEvidence",
    itemId: "wall",
    document: "First report",
    responsible: "Example Applicant",
    date: "2020-01-01",
    evidenceType: "manufacturer's literature",
    provisionId: "9.10.15.5.(8)",
  });
  c = reducer(c, {
    type: "saveEvidence",
    itemId: "wall",
    document: "Second report",
    responsible: "Example Applicant",
    date: "2021-06-01",
    evidenceType: "engineering review",
    provisionId: "9.10.15.5.(8)",
  });
  const titles = c.facts.filter((fact) => fact.field.endsWith(".title")).map((fact) => fact.value);
  assert.deepEqual(titles, ["First report", "Second report"]);
  assert.equal(c.facts.some((fact) => fact.field.endsWith(".file_ref") || fact.source.type === "file"), false);
  assert.equal(c.listedEvidence?.length, 2);
  assert.equal(c.listedEvidence?.[1].evidenceType, "engineering review");
});

test("not sure and not engaged yet stay open and block export", () => {
  let c = reducer(emptyCase("contractor"), { type: "notePractice", value: true });
  c = reducer(c, { type: "deferProfessional", field: "role", choice: "not_sure", label: "Who is the registered professional?" });
  assert.equal(c.facts.find((fact) => fact.field === "professional.role")?.status, "unconfirmed");
  assert.ok(getGaps(c).some((gap) => gap.id === "professional-not-engaged"));
  assert.ok(getGaps(c).some((gap) => gap.id === "needs-professional"));
  c = reducer(emptyCase("contractor"), {
    type: "deferProfessional",
    field: "seal",
    choice: "not_engaged_yet",
    label: "Seal that professional confirmed",
  });
  assert.ok(getGaps(c).some((gap) => gap.id === "professional-not-engaged"));
  assert.equal(c.facts.some((fact) => fact.source.type === "file"), false);
});

function confirmed(field: string, value: string | boolean, sourceType: "user_text" | "user_click" | "file" = "user_text"): Fact {
  const text = typeof value === "string" ? value : value ? "true" : "false";
  return {
    id: field,
    field,
    value,
    kind: "pointed",
    status: "confirmed",
    source: { type: sourceType, ref: sourceType === "file" ? text : "applicant", quote: text },
  };
}

test("a registered professional clears the gap and a commercial or file claim does not", () => {
  assert.equal(roleConfirmed("structural engineer"), true);
  assert.equal(roleConfirmed("P.Eng."), true);
  assert.equal(roleConfirmed("P Eng"), true);
  assert.equal(roleConfirmed("registered architect"), true);
  assert.equal(roleConfirmed("sales rep"), false);
  assert.equal(roleConfirmed("supplier"), false);

  let c = reducer(emptyCase("contractor"), { type: "notePractice", value: true });
  c = reducer(c, { type: "setProfessionalFact", field: "role", value: "structural engineer" });
  c = reducer(c, { type: "setProfessionalFact", field: "seal", value: "seal on file" });
  assert.equal(getGaps(c).some((gap) => gap.id === "needs-professional"), false);

  c = reducer(emptyCase("contractor"), { type: "notePractice", value: true });
  c = reducer(c, { type: "setProfessionalFact", field: "role", value: "P.Eng." });
  c = reducer(c, { type: "setProfessionalFact", field: "registration_number", value: "APEGA-1000" });
  assert.equal(getGaps(c).some((gap) => gap.id === "needs-professional"), false);

  c = reducer(emptyCase("contractor"), { type: "notePractice", value: true });
  c = reducer(c, { type: "setProfessionalFact", field: "role", value: "sales rep" });
  c = reducer(c, { type: "setProfessionalFact", field: "seal", value: "company stamp" });
  assert.ok(getGaps(c).some((gap) => gap.id === "needs-professional"));

  const named = {
    ...emptyCase("contractor"),
    practiceOfEngineering: true as const,
    facts: [
      confirmed("professional.role", "professional engineer", "file"),
      confirmed("professional.seal", "copied stamp", "file"),
    ],
  };
  assert.equal(professionalConfirmed(named.facts), false);
  assert.ok(getGaps(named).some((gap) => gap.id === "needs-professional"));

  c = reducer(emptyCase("homebuilder"), { type: "notePractice", value: true });
  c = reducer(c, { type: "setProfessionalFact", field: "prescriptive_route_confirmed", value: true });
  c = reducer(c, { type: "setProfessionalFact", field: "professional_judgement_required", value: false });
  assert.ok(getGaps(c).some((gap) => gap.id === "needs-professional"));
  assert.equal(professionalConfirmed(c.facts), false);
});

test("a code-check gap names the question", () => {
  assert.equal(
    codeCheckLabel("Using the board to hold the siding"),
    "Code check: answer whether your design relies on the board to hold the siding",
  );
  assert.equal(
    codeCheckLabel("What you described", "What would the acceptable solution have required here?"),
    "Code check: What would the acceptable solution have required here?",
  );
  assert.equal(plainFactStatus("pointed", "confirmed"), "from what you entered");
  assert.doesNotMatch(plainFactStatus("pointed", "confirmed"), /pointed|confirmed/);
});

test("labels name the question and hide raw fact keys", () => {
  assert.equal(factLabel("professional.part4_design").includes("professional.part4_design"), false);
  assert.equal(factLabel("evidence.ev_e58a.file_ref").includes("ev_e58a"), false);
  assert.equal(factLabel("evidence.ev_e58a.file_ref").includes("file_ref"), false);
  const no = displayValue(confirmed("professional.part4_design", false));
  assert.equal(no, "No");
  const house = displayValue(confirmed("professional.occupancy", "single_family"));
  assert.equal(house, "Single-family house");
  const label = gapLabel("Facts needed to resolve professional involvement.", "Is a fire alarm system being installed?");
  assert.match(label, /fire alarm/);
  assert.equal(gapLabel("Already asks: Is a fire alarm system being installed?", "Is a fire alarm system being installed?"), "Already asks: Is a fire alarm system being installed?");
});

test("a process answer just typed shows before the engine copy arrives", () => {
  const blank = emptyCase("contractor");
  const typed = reducer(blank, { type: "setProcess", field: "risk", value: "Water at the joint." });
  assert.equal(shownProcessAnswer("risk_assessment", null, typed.process), "Water at the joint.");
  assert.equal(shownProcessAnswer("risk_assessment", "stale engine text", typed.process), "Water at the joint.");
  assert.equal(shownProcessAnswer("risk_assessment", null, blank.process), "");
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
