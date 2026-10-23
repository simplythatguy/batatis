import type { AssistContextBinding, AssistResponse } from "../../api/accounts";

export const sameIds = (a: readonly string[], b: readonly string[]) => a.length === b.length && a.every((id, i) => id === b[i]);

/** Echoed identities are guards, never permission. The server remains the source of authorization. */
export function matchesDocumentReply(reply: AssistResponse, expected: AssistContextBinding): boolean {
  const b = reply.context;
  if (!b || b.user_id !== expected.user_id || b.case_id !== expected.case_id || b.case_version !== expected.case_version || b.context_id !== expected.context_id || b.revision !== expected.revision || !Array.isArray(b.attachment_ids) || !sameIds(b.attachment_ids, expected.attachment_ids)) return false;
  if (!Array.isArray(reply.attachments) || !Array.isArray(reply.document_references)) return false;
  // A navigation plan reads no documents. Otherwise every selected file needs actual coverage.
  if (reply.navigation) return reply.attachments.length === 0 && reply.document_references.length === 0;
  if (!sameIds(reply.attachments.map((a) => a.file_id), expected.attachment_ids)) return false;
  if (!reply.attachments.every((a) => a.case_id === expected.case_id && (a.content_state === "not_read" || a.content_state === "text_excerpt") && Array.isArray(a.pages) && a.pages.every((p) => Number.isInteger(p) && p > 0))) return false;
  return reply.document_references.every((r) => r.case_id === expected.case_id && typeof r.quote === "string" && r.quote.length >= 8 && r.quote.length <= 600 && reply.attachments!.some((a) => a.file_id === r.file_id && a.content_state === "text_excerpt" && a.pages.includes(r.page)));
}
