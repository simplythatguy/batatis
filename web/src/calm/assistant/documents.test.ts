import assert from "node:assert/strict";
import { test } from "node:test";
import type { AssistContextBinding, AssistResponse } from "../../api/accounts";
import { matchesDocumentReply } from "./documents";

const binding: AssistContextBinding = { user_id: "A", case_id: "case-A", case_version: 7, context_id: "ctx_0123456789abcdef", revision: 3, attachment_ids: ["file-A"] };
const reply = (): AssistResponse => ({ answer: "Exact excerpt.", cited: [], removed_citations: [], notice: null, context: { ...binding }, attachments: [{ case_id: "case-A", file_id: "file-A", name: "report.pdf", content_state: "text_excerpt", pages: [1], truncated: true }], document_references: [{ case_id: "case-A", file_id: "file-A", page: 1, quote: "An exact excerpt." }] });

test("every document binding field must match; missing coverage and legacy replies fail closed", () => {
  assert.equal(matchesDocumentReply(reply(), binding), true);
  for (const field of ["user_id", "case_id", "context_id", "case_version", "revision", "attachment_ids"] as const) {
    const r = reply(); Object.assign(r.context!, { [field]: field === "attachment_ids" ? ["other"] : typeof binding[field] === "number" ? 99 : "other" });
    assert.equal(matchesDocumentReply(r, binding), false, field);
  }
  assert.equal(matchesDocumentReply({ ...reply(), context: null }, binding), false);
  assert.equal(matchesDocumentReply({ ...reply(), attachments: [] }, binding), false);
});

test("references cannot point outside the selected, supplied file and page", () => {
  for (const patch of [{ case_id: "other" }, { file_id: "other" }, { page: 2 }, { quote: "" }]) {
    const r = reply(); Object.assign(r.document_references![0], patch); assert.equal(matchesDocumentReply(r, binding), false);
  }
  const unread = reply(); unread.attachments![0].content_state = "not_read";
  assert.equal(matchesDocumentReply(unread, binding), false);
  unread.document_references = []; assert.equal(matchesDocumentReply(unread, binding), true);
});

test("navigation reads no documents and carries no invented document coverage", () => {
  const r = reply(); r.navigation = { destination: "settings" };
  assert.equal(matchesDocumentReply(r, binding), false);
  r.attachments = []; r.document_references = []; assert.equal(matchesDocumentReply(r, binding), true);
});
