import assert from "node:assert/strict";
import test from "node:test";
import { emptyCase } from "./intake.ts";
import { reducer } from "./model.ts";
import { professionalAnswerer, professionalEvidenceCount, professionalOfficeQuestions, professionalOpenCount, professionalQuestions, professionalValue, professionalWorkBasis, professionalWorkCurrent } from "./professional.ts";
import type { Case, Fact } from "./types.ts";

function fact(field: string, value: Fact["value"]): Fact {
  return { id: field, field, value, kind: "pointed", status: "confirmed", source: { type: "user_text", ref: "intake answer", quote: String(value) } };
}
function house(): Case {
  return { ...emptyCase("owner"), description: "A house with larger side windows.", facts: [fact("occupancy", "single_family"), fact("storeys", 2), fact("building_area_m2", 140), fact("part4_design", false)] };
}

test("intake's existing project facts are known and the house is asked only its missing professional questions", () => {
  const c = house();
  for (const field of ["occupancy", "storeys", "building_area_m2", "part4_design"]) assert.equal(professionalQuestions(c).find((question) => question.field === field)?.known, true, field);
  assert.deepEqual(professionalQuestions(c).filter((question) => !question.known).map((question) => question.field), ["professional_judgement_required", "role", "registration_number"]);
  assert.equal(professionalOpenCount(c), 3);
  assert.equal(professionalOpenCount(emptyCase("owner")), 0);
});

test("farm, trusses, foundations and unit counts appear only in their project scope", () => {
  const c = house();
  const farm = { ...c, facts: [...c.facts, fact("occupancy", "farm")] };
  assert.ok(professionalQuestions(farm).some((question) => question.field === "farm_public_use"));
  const trusses = { ...c, description: "A house roof truss connection." };
  assert.ok(professionalQuestions(trusses).some((question) => question.field === "roof_trusses"));
  assert.ok(!professionalQuestions(trusses).some((question) => question.field === "preserved_wood_foundation_part4"));
  const foundation = { ...c, description: "A preserved wood foundation." };
  assert.ok(professionalQuestions(foundation).some((question) => question.field === "preserved_wood_foundation_part4"));
  const apartment = { ...c, facts: [...c.facts, fact("occupancy", "multi_family"), fact("dwelling_units", 4)] };
  assert.ok(professionalQuestions(apartment).some((question) => question.field === "principal_dwelling_units" && !question.known), "total units never silently exclude secondary suites");
  const part3 = { ...trusses, facts: [...c.facts, fact("storeys", 5), fact("part4_design", true)] };
  assert.ok(!professionalQuestions(part3).some((question) => ["roof_trusses", "preserved_wood_foundation_part4", "farm_public_use"].includes(question.field)));
});

test("a withdrawal, unconfirmed edit or false value is read as the engine reads it", () => {
  const c = house();
  assert.equal(professionalValue(c, "part4_design"), false);
  const edited = { ...c, facts: [...c.facts, { ...fact("professional.storeys", 4), status: "unconfirmed" as const }] };
  assert.equal(professionalValue(edited, "storeys"), undefined);
  assert.equal(professionalQuestions(edited).find((question) => question.field === "storeys")?.known, false);
  const alias = { ...c, facts: [fact("building.storeys", 2)] };
  assert.equal(professionalValue(alias, "storeys"), 2);
});

test("the engine's missing fields restrict prompts; office-only decisions never become applicant controls", () => {
  const c = house();
  assert.deepEqual(professionalQuestions(c, ["professional.role", "professional.registration_number or professional.seal"]).filter((question) => !question.known).map((question) => question.field), ["role", "registration_number"]);
  assert.equal(professionalOfficeQuestions(c).length, 3);
  assert.ok(!professionalQuestions(c).some((question) => ["ahj_requires_professional", "special_safety_concerns", "professional_scope_resolved"].includes(question.field)));
  const reported = reducer(c, { type: "answerScope", field: "ahj_requires_professional", answer: "yes" });
  assert.equal(professionalOfficeQuestions(reported).length, 3, "an applicant report does not supply the office's reserved confirmation");
  assert.ok(professionalQuestions(c, ["gross_area_per_floor_m2"]).some((question) => question.field === "gross_area_per_floor_m2" && !question.known));
});

test("designer answers are recorded once and do not turn off engineer-required state", () => {
  let c = { ...house(), practiceOfEngineering: true as const };
  c = reducer(c, { type: "deferProfessional", field: "professional_judgement_required", choice: "not_sure", label: "Does the design need judgement?" }) as typeof c;
  assert.equal(professionalOpenCount(c), 2);
  assert.equal(professionalQuestions(c).find((question) => question.field === "professional_judgement_required")?.deferred, true);
  assert.equal(c.practiceOfEngineering, true);
  for (const field of ["part4_design", "professional.registration_number", "seal", "professional_judgement_required"]) assert.equal(professionalAnswerer(field), "designer");
  assert.equal(professionalAnswerer("occupancy"), "you");
  assert.equal(professionalAnswerer("farm_public_use"), "you");
  const notEngaged = reducer(c, { type: "deferProfessional", field: "role", choice: "not_engaged_yet", label: "Professional" });
  assert.ok(!professionalQuestions(notEngaged, ["professional.role", "professional.registration_number or professional.seal"]).some((question) => ["registration_number", "seal"].includes(question.field)));
});

test("an authoritative nested plan counts every evidence task, including two tasks on one sentence", () => {
  let c = house();
  const professional = { required: "yes" as const, general_required: "no" as const, reasons: [], questions: [], missing_facts: ["professional.role", "professional.registration_number or professional.seal"], scope_note: "Synthetic fixture" };
  const task = { provision_id: "9.10.15.5.(8)", citation: "Synthetic", objective: "OS1.2", function: "F03", performance_issue: "Synthetic", recommended_types: [], attachments: [], status: "needed" as const };
  c = reducer(c, { type: "noteProfessionalWork", work: { basis: professionalWorkBasis(c), professional, plan: { items: [{ ...task, id: "one" }, { ...task, id: "two" }], notices: [] } } });
  assert.equal(professionalWorkCurrent(c), true);
  assert.equal(professionalEvidenceCount(c), 2);
  assert.equal(professionalOpenCount(c), 4, "role + credential + two independent evidence tasks");
  const answered = reducer(c, { type: "setProfessionalFact", field: "role", value: "engineer" });
  assert.equal(professionalWorkCurrent(answered), false, "the footer can label an outdated plan as pending");
});

test("answered fixture counts exclude deferred credentials and include known evidence work", () => {
  let c = house();
  c = reducer(c, { type: "setProfessionalFact", field: "role", value: "engineer" });
  c = reducer(c, { type: "setProfessionalFact", field: "registration_number", value: "SYNTHETIC-123" });
  c = reducer(c, { type: "setProfessionalFact", field: "professional_judgement_required", value: true });
  assert.equal(professionalOpenCount(c), 0);
  c = reducer(c, { type: "noteProfessionalWork", work: { basis: professionalWorkBasis(c), professional: { required: "yes", general_required: "no", reasons: [], questions: [], missing_facts: [], scope_note: "Synthetic" }, plan: { items: [{ id: "known", provision_id: "9.10.15.5.(8)", citation: "Synthetic", status: "evidence_listed", objective: null, function: null, performance_issue: "Synthetic", recommended_types: [], attachments: [{ id: "doc", title: "Synthetic report" }] }], notices: [] } } });
  assert.equal(professionalOpenCount(c), 0);
});
