import assert from "node:assert/strict";
import test from "node:test";
import { acceptedApplicantFact, applicantDraftHref, applicantDraftInputKey, draftPassages, unchangedDraftField } from "./applicantDrafts.ts";
import { emptyCase } from "./intake.ts";
import { asLocal } from "./intakeFields.ts";
import { reducer } from "./model.ts";
import { caseFromEngine } from "./calm/openCase.ts";
import { resolveRoute } from "./calm/routes.ts";
import type { Fact } from "./types.ts";
import { draft, pointed, savedDraftCase } from "../tests/applicant-drafts.fixture.ts";

test("acceptance adopts only the server-confirmed canonical fact and updates the process answer", async () => {
  const saved = await savedDraftCase();
  saved.drafting.drafts[0].status = "accepted";
  saved.facts.push({ ...pointed(draft.field, draft.text, "accepted-risk"), source: { type: "user_click", ref: `applicant-draft:${draft.id}`, quote: draft.text } });
  const fact = acceptedApplicantFact(saved, draft.id);
  assert.ok(fact);
  const local = caseFromEngine(saved, "homebuilder");
  const before = { ...local, process: { ...local.process, risk: "Old manual answer" },
    evidenceDrafts: { evidence: { document: "Unfinished listing", responsible: "", date: "", evidenceType: "", note: "" } },
    listedEvidence: [], files: [{ id: "local-file", name: "Unuploaded.pdf", read: false }],
  };
  const after = reducer(before, { type: "adoptApplicantDraft", fact });
  assert.equal(after.process.risk, draft.text);
  assert.equal(after.facts.filter(f => f.field === draft.field).length, 1);
  assert.equal(after.facts.find(f => f.field === "owner")?.value, "Unit owner");
  for (const field of ["candidates", "questions", "sectionC", "files", "evidenceDrafts", "listedEvidence"]) assert.equal(after[field], before[field], field);
  const reopened = caseFromEngine(saved, "homebuilder");
  assert.equal(reopened.process.risk, draft.text);
  assert.deepEqual(reopened.facts.find(f => f.field === draft.field)?.source, fact.source);
  for (const invalid of [
    { ...saved, drafting: { ...saved.drafting, drafts: [draft] } },
    { ...saved, facts: [...saved.facts, pointed(draft.field, "Later manual answer")] },
    { ...saved, facts: saved.facts.map(f => f.id === fact.id ? { ...f, source: { ...f.source, quote: "wrong excerpt" } } : f) },
  ]) assert.equal(acceptedApplicantFact(invalid, draft.id), undefined);
});

test("draft input keys catch description, facts, code and files; generated prose is not evidence", () => {
  const base = emptyCase("homebuilder");
  const key = applicantDraftInputKey(base);
  for (const changed of [
    { ...base, description: "Edited description" },
    { ...base, facts: [pointed("owner", "Edited owner")] },
    { ...base, files: [{ id: "added", name: "new.pdf", read: false }] },
    reducer(base, { type: "setProcess", field: "risk", value: "New risk" }),
  ]) assert.notEqual(applicantDraftInputKey(changed), key);
  const accepted = { ...pointed(draft.field, draft.text), source: { type: "user_click", ref: `applicant-draft:${draft.id}`, quote: draft.text } } satisfies Fact;
  assert.equal(applicantDraftInputKey({ ...base, facts: [accepted] }), key);
  assert.equal(unchangedDraftField(base, { ...base, facts: [pointed("owner", "New owner")] }, draft.field), true);
  assert.equal(unchangedDraftField(base, { ...base, facts: [pointed(draft.field, "Later answer")] }, draft.field), false);
  assert.equal(asLocal(pointed("alternative_description", "Alternative")).field, "alternative");
});

test("claim disclosures preserve the literal accepted wording and draft links stay in Review", () => {
  const wording = draftPassages(draft);
  assert.ok(wording);
  assert.equal(wording.passages.map(p => p.before + p.prefix + p.claim.text).join("") + wording.after, draft.text);
  const assembled = { ...draft, text: `Assumption: ${draft.claims[0].text}\n\nPlan: ${draft.claims[1].text}` };
  const prefixed = draftPassages(assembled);
  assert.ok(prefixed);
  assert.equal(prefixed.passages.map(p => p.before + p.prefix + p.claim.text).join("") + prefixed.after, assembled.text);
  assert.deepEqual(prefixed.passages.map(p => p.prefix), ["Assumption: ", "Plan: "]);
  assert.equal(prefixed.passages.some(p => /Assumption:|Plan:/.test(p.before)), false);
  assert.equal(draftPassages({ ...draft, text: "A different paragraph" }), null, "unmatched wording stays available in full");
  for (const field of ["alternative_description", "process.rationale", "section_c.9.1.1.1.(1).explanation", "evidence_plan"]) {
    const href = applicantDraftHref(field);
    assert.equal(resolveRoute("/review", new URLSearchParams(href.split("?")[1])).canonical, href);
  }
});
