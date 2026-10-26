import assert from "node:assert/strict";
import test from "node:test";
import { emptyCase } from "../../intake.ts";
import { reducer } from "../../model.ts";
import type { Fact, Gap } from "../../types.ts";
import { blockAction, blockForField, buildDocument, listedDocuments } from "./document.ts";

const fact = (field: string, value: string | null, extra: Partial<Fact> = {}): Fact => ({ id: field, field, value, kind: "pointed", status: "confirmed", source: { type: "user_text", ref: "Applicant" }, ...extra });

test("the paper follows A, B, case, C, D, derives alias values, and writes through store actions", () => {
  let c = emptyCase("homebuilder");
  c.facts = [fact("owner_name", "Owner Ltd."), fact("owner_name", "AI name", { id: "draft", kind: "proposed", status: "unconfirmed" })];
  const sections = buildDocument(c, []);
  assert.deepEqual(sections.map(s => s.id), ["A", "B", "case", "C", "D"]);
  const owner = blockForField(sections, "field-owner");
  assert.equal(owner?.id, "owner_name");
  assert.equal(owner?.text, "Owner Ltd.", "proposed facts are never applicant text");
  assert.equal(owner?.missing, false, "the workspace does not invent completeness findings");
  const action = blockAction(owner!, "New owner");
  assert.ok(action);
  c = reducer(c, action);
  assert.equal(blockForField(buildDocument(c, []), "section_a.owner_name")?.text, "New owner");
  const risk = blockForField(sections, "risk_assessment")!;
  assert.deepEqual(blockAction(risk, "Risk described"), { type: "setProcess", field: "risk", value: "Risk described" });
});

test("shared gaps and officer requests resolve through aliases and legacy focus ids", () => {
  const c = emptyCase("homebuilder");
  const gap: Gap = { id: "risk-needed", field: "process.risk", severity: "blocking", label: "Risk missing", href: "#/application?tab=alt&focus=field-risk" };
  const sections = buildDocument(c, [gap], [{ id: "msg-1:0", field: "risk_assessment", note: "Explain the effect on neighbours." }]);
  const risk = blockForField(sections, "field-risk")!;
  assert.equal(risk.missing, true);
  assert.deepEqual(risk.requests, [{ id: "msg-1:0", note: "Explain the effect on neighbours." }]);
  assert.equal(sections.flatMap(s => s.blocks).filter(b => b.missing).length, 1);
});

test("non-text values and applicant N/A reasons link to their exact question", () => {
  const c = emptyCase("homebuilder");
  c.facts = [fact("not_applicable.owner_rep", "Owner applies directly")];
  const sections = buildDocument(c, []);
  const rep = blockForField(sections, "owner_rep_name")!;
  assert.equal(rep.notApplicable, "Owner applies directly");
  assert.deepEqual(rep.target, { kind: "card", href: "#/questions?focus=field-representative" });
  assert.equal(blockAction(rep, "new"), null);
  assert.equal(blockForField(sections, "scope")?.target.kind, "card");
  assert.equal(blockForField(sections, "request_date")?.target.kind, "card");
});

test("Section C lookup stays immutable and its explanation is separate applicant/AI text", () => {
  const c = emptyCase("homebuilder");
  c.sectionC = [{ candidateId: "c", provision: "9.1.1.1.(1)", citation: "Source citation", pairs: [], attributionStatus: "no-row", intent: [], differs: false, explanation: "A draft explanation" }];
  const sections = buildDocument(c, []);
  const reference = blockForField(sections, "section_c.9.1.1.1.(1)")!;
  const explanation = blockForField(sections, "section_c.9.1.1.1.(1).explanation")!;
  assert.equal(reference.target.kind, "card");
  assert.equal(explanation.text, "");
  assert.equal(explanation.draft, "A draft explanation");
  assert.deepEqual(blockAction(explanation, "Applicant explanation"), { type: "setDetail", field: explanation.id, section: "C", value: "Applicant explanation" });
});

test("withdrawn document titles and unscoped listings cannot survive as attached-package labels", () => {
  const c = emptyCase("homebuilder");
  c.facts = [fact("evidence.one.title", "Old"), fact("evidence.one.title", ""), fact("evidence.two.title", "Kept elsewhere"), fact("evidence.three.title", "Report")];
  c.unscopedEvidence = ["two"];
  assert.deepEqual(listedDocuments(c), [{ id: "three", title: "Report" }]);
});
