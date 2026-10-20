import assert from "node:assert/strict";
import test from "node:test";
import { notSureQuestions } from "./humanReview.ts";
import { emptyCase } from "./intake.ts";
import { codeCheckLabel, displayValue, evidenceDocuments, factLabel, gapLabel, getGaps, plainFactStatus, reducer, sectionDRefreshKey, sectionDWhileRefreshing, shownProcessAnswer } from "./model.ts";
import { AUTHORITY_DECISION_FIELDS, evidenceRecorded, practiceFromReview, professionalConfirmed, roleConfirmed, sectionDIssueStatus } from "./professional.ts";
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
    assert.equal(fact?.status, "confirmed");
    assert.equal(fact?.source.type, "user_click");
  }
  assert.equal(professionalConfirmed(c.facts), false);
  assert.equal(practiceFromReview(true, "no", false), true);
  assert.equal(practiceFromReview(false, "no", false), "unknown");
  assert.equal(practiceFromReview(undefined, "no", false), "unknown");
  const cleared = reducer(c, { type: "notePractice", value: false });
  assert.equal(cleared.practiceOfEngineering, true);
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

test("authority-only yes is routed to the officer and can be withdrawn", () => {
  let c = reducer(emptyCase("homebuilder"), { type: "notePractice", value: true });
  c = reducer(c, { type: "answerScope", field: "ahj_requires_professional", answer: "yes", text: "Has the authority required a registered professional?" });
  assert.ok(getGaps(c).some((gap) => gap.id === "needs-professional"));
  assert.equal(professionalConfirmed(c.facts), false);
  const routed = notSureQuestions(c.questions);
  assert.ok(routed.some((question) => question.id === "q-prof-ahj_requires_professional"));
  assert.match(routed.find((question) => question.id === "q-prof-ahj_requires_professional")?.why ?? "", /officer/);
  c = reducer(c, { type: "answerScope", field: "ahj_requires_professional", answer: "clear" });
  assert.equal(c.facts.some((fact) => fact.field === "professional.ahj_requires_professional"), false);
  assert.equal(c.questions.some((question) => question.id === "q-prof-ahj_requires_professional"), false);
  assert.ok(getGaps(c).some((gap) => gap.id === "needs-professional"));
});

test("a registered professional answer can be withdrawn", () => {
  let c = reducer(emptyCase("contractor"), { type: "notePractice", value: true });
  c = reducer(c, { type: "setProfessionalFact", field: "role", value: "architect" });
  c = reducer(c, { type: "setProfessionalFact", field: "seal", value: "seal 19" });
  assert.equal(professionalConfirmed(c.facts), true);
  c = reducer(c, { type: "answerScope", field: "role", answer: "clear" });
  c = reducer(c, { type: "answerScope", field: "seal", answer: "clear" });
  assert.equal(professionalConfirmed(c.facts), false);
  assert.ok(getGaps(c).some((gap) => gap.id === "needs-professional"));
});

test("removing one evidence document keeps the other and queues a deletion", () => {
  let c = reducer(emptyCase("homebuilder"), {
    type: "saveEvidence",
    itemId: "wall",
    document: "First report",
    responsible: "Ada Applicant",
    date: "2026-10-01",
    evidenceType: "engineering review",
    provisionId: "9.10.15.5.",
  });
  c = reducer(c, {
    type: "saveEvidence",
    itemId: "wall",
    document: "Second report",
    responsible: "Ben Engineer",
    date: "",
    evidenceType: "CCMC",
    provisionId: "9.10.15.5.",
  });
  assert.equal(evidenceDocuments(c, "wall").length, 2);
  const second = evidenceDocuments(c, "wall")[1];
  const before = sectionDRefreshKey(c);
  c = reducer(c, { type: "removeEvidence", id: "wall" });
  assert.deepEqual(evidenceDocuments(c, "wall").map((item) => item.title), ["Second report"]);
  assert.deepEqual(c.deletedEvidence, ["wall"]);
  assert.equal(c.listedEvidence?.some((item) => item.id === "wall"), false);
  assert.equal(c.listedEvidence?.some((item) => item.id === second.id), true);
  assert.notEqual(sectionDRefreshKey(c), before);
  c = reducer(c, { type: "ackEvidenceDeletion", ids: ["wall"] });
  assert.deepEqual(c.deletedEvidence, []);
});

test("authority decisions offer Not sure and cannot set practice to false", () => {
  let c = reducer(emptyCase("homebuilder"), { type: "notePractice", value: true });
  for (const field of AUTHORITY_DECISION_FIELDS) {
    c = reducer(c, { type: "answerScope", field, answer: "not-sure", text: `Question about ${field}` });
    const question = c.questions.find((item) => item.id === `q-scope-${field}`);
    assert.ok(question);
    assert.match(question?.why ?? "", /officer/);
    assert.equal(c.facts.some((fact) => fact.field === `professional.${field}`), false);
    assert.ok(notSureQuestions(c.questions).some((item) => item.id === `q-scope-${field}`));
  }
  assert.equal(c.practiceOfEngineering, true);
  assert.ok(getGaps(c).some((gap) => gap.id === "needs-professional"));

  c = reducer(emptyCase("homebuilder"), { type: "notePractice", value: true });
  c = reducer(c, { type: "answerScope", field: "prescriptive_route_confirmed", answer: "yes" });
  c = reducer(c, { type: "answerScope", field: "professional_judgement_required", answer: "no" });
  for (const field of AUTHORITY_DECISION_FIELDS) {
    const answer = field === "professional_scope_resolved" ? "yes" : "no";
    c = reducer(c, { type: "answerScope", field, answer });
  }
  c = reducer(c, { type: "notePractice", value: false });
  assert.equal(c.practiceOfEngineering, true);
  assert.equal(professionalConfirmed(c.facts), false);
  assert.ok(getGaps(c).some((gap) => gap.id === "needs-professional"));
});

test("a Section D refresh keeps the plan and the professional screen", () => {
  const plan = { items: [{ id: "wall", status: "not provided" }] };
  const professional = { required: "depends" as const };
  const issues = [{ id: "unresolved-9.10.15.5" }];
  const next = sectionDWhileRefreshing({
    phase: "live" as const,
    note: "old",
    plan,
    issues,
    professional,
    fields: [{ id: "risk_assessment" }],
    issuesNote: null,
  });
  assert.equal(next.phase, "loading");
  assert.equal(next.note, "Updating Section D…");
  assert.equal(next.plan, plan);
  assert.equal(next.issues, issues);
  assert.equal(next.professional, professional);
  const first = sectionDWhileRefreshing({
    phase: "idle" as const,
    note: "",
    plan: null,
    issues: null,
    professional: null,
    fields: [],
    issuesNote: null,
  });
  assert.equal(first.note, "Loading Section D…");
  assert.equal(first.plan, null);
});

test("a Section D answer changes the refresh key", () => {
  const start = emptyCase("contractor");
  const answered = reducer(start, { type: "answerScope", field: "part4_design", answer: "no" });
  assert.notEqual(sectionDRefreshKey(answered), sectionDRefreshKey(start));
  assert.equal(professionalConfirmed(answered.facts), false);
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
