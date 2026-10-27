import assert from "node:assert/strict";
import test from "node:test";
import { emptyCase } from "../intake";
import type { Fact } from "../types";
import { reconcileDraft, type ReconciliationInput } from "./reconcileDraft";

const fact = (id: string, field: string, value: string) => ({ id, field, value, status: "confirmed", kind: "pointed",
  source: { type: "user_text", ref: "evidence", quote: value }, confidence: null, formula: null, inputs: [] }) as unknown as Fact;

test("a document saved in several revisions and untouched elsewhere is not reported as changed on another device", () => {
  const first = fact("doc-1", "evidence.report.description", "Fire report draft");
  const second = fact("doc-2", "evidence.report.description", "Fire report");
  const local = { ...emptyCase("homebuilder"), listedEvidence: [{ id: "report", rev: 2, operation: "update" as const, taskId: "task",
    provisionId: "9.10.9.6", evidenceType: "report", description: "Fire report, revised locally" }] };
  const remote = { ...emptyCase("homebuilder"), facts: [second] };
  const draft = { role: "homebuilder", question_text: {}, choices: {}, skipped: [], seen: [], authority_unsure: false,
    packages: {}, rule_unsure: [], evidence_drafts: {} } as ReconciliationInput["draft"];
  const input: ReconciliationInput = { local, remote, draft, savedDraft: draft, baselineDraft: draft,
    localFacts: new Map(), remoteFacts: new Map(), baselineAuthority: null, baselineEvidence: [first, second],
    localSelectionChanged: false, remoteSelectionChanged: false };
  const merged = reconcileDraft(input);
  assert.deepEqual(merged.conflicts, []);
  assert.deepEqual(merged.listedEvidence.map(item => item.description), ["Fire report, revised locally"]);

  const changed = reconcileDraft({ ...input, remote: { ...remote, facts: [fact("doc-3", "evidence.report.description", "Other device report")] } });
  assert.deepEqual(changed.conflicts.map(item => item.id), ["document:report"]);
});
