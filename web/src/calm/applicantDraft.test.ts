import assert from "node:assert/strict";
import test from "node:test";
import { applicantDraft, evidenceDrafts } from "./applicantDraft";
import { emptyCase } from "../intake";
import { reducer } from "../model";
import { questionDrafts } from "./questionDrafts";
import { resetSession } from "./session";

test("unfinished attached-document edits preserve retain, removal and replacement across server draft serialization", () => {
  resetSession(); questionDrafts.clear();
  let c = emptyCase("homebuilder");
  for (const [itemId, fileRef] of [["retain", undefined], ["remove", null], ["file", "uploaded-pdf"]] as const) {
    c = reducer(c, { type: "editEvidenceDraft", itemId, patch: { document: "Renamed document", editing: "attached-slot", fileRef } });
  }
  const wire = applicantDraft(c, "account", 1, "case");
  assert.deepEqual(wire.evidence_drafts.retain.file_binding, { kind: "retain" });
  assert.deepEqual(wire.evidence_drafts.remove.file_binding, { kind: "remove" });
  assert.deepEqual(wire.evidence_drafts.file.file_binding, { kind: "file", file_id: "uploaded-pdf" });
  assert.equal(Object.values(wire.evidence_drafts).some(draft => "fileRef" in draft), false);
  const restored = evidenceDrafts(structuredClone(wire));
  assert.equal("fileRef" in restored.retain, false);
  assert.equal(restored.remove.fileRef, null);
  assert.equal(restored.file.fileRef, "uploaded-pdf");
  for (const itemId of ["retain", "remove", "file"]) {
    const draft = restored[itemId];
    const next = reducer({ ...c, evidenceDrafts: restored }, { type: "saveEvidence", itemId,
      document: draft.document, responsible: draft.responsible, date: draft.date, evidenceType: "evaluation", provisionId: "9.25.2.2.(1)",
      slot: draft.editing, fileRef: draft.fileRef });
    assert.equal(next.listedEvidence?.at(-1)?.fileRef, restored[itemId].fileRef, `${itemId} reaches the evidence save with its original semantics`);
  }
});
