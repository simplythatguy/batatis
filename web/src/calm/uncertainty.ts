/** A gap/check cannot answer an officer's contextual request. Only a saved applicant response can. */
import type { MessageItem } from "../api/accounts";
import { answerWithdrawn } from "../intakeFields";
import type { Case } from "../types";

export const clarificationQuestionId = (field: string) => `return-${field}`;

export function isUncertainAnswer(value: unknown): boolean {
  const text = String(value ?? "").trim().toLowerCase().replace(/[_-]/g, " ").replace(/[.!?]+$/, "").trim();
  return !text || /^(not sure(?: yet)?|unsure|unknown|(?:i )?(?:don[’']?t know|do not know)|no idea|idk|n\/?a)$/.test(text);
}

/** Structurally compatible with J07 RequestedItemRow. Null leaves unrelated J07 routing intact. */
export function requestedUncertaintyRow(c: Case, item: MessageItem, saved: boolean): {
  label: string; href: string; state: "open" | "unsaved" | "pending" | "review";
  status: string; tone: "blocking" | "warning" | "pending";
} | null {
  const field = item.field ?? "";
  const contextual = /^(clarification\.|codecheck\.|identify\.)/.test(field) || item.gap_id?.startsWith("intake.");
  if (!contextual) return null;
  const question = c.questions.find(q => q.field === field);
  const candidate = field.startsWith("codecheck.") ? c.candidates.find(a => a.id === field.slice("codecheck.".length))
    : field.startsWith("identify.") ? c.candidates.find(a => a.provision.startsWith(field.slice("identify.".length))) : undefined;
  const href = question ? `#/questions?focus=${encodeURIComponent(`q-${question.id}`)}`
    : candidate ? `#/questions?focus=${encodeURIComponent(`cand-${candidate.id}`)}` : "#/application";
  const base = { label: item.note?.trim() || question?.text || "Applicant clarification", href };
  if (!question && !candidate) return { ...base, state: "review", status: "Officer clarification needed", tone: "warning" };
  const fact = [...c.facts].reverse().find(f => f.field === field);
  const value = candidate ? candidate.answer : fact?.value;
  const answered = candidate ? Boolean(value && !candidate.pending && !isUncertainAnswer(value))
    : Boolean(fact?.status === "confirmed" && fact.kind !== "proposed" && !answerWithdrawn(fact) && !isUncertainAnswer(value));
  if (!answered) return { ...base, state: "open", status: "Still to clarify", tone: "warning" };
  if (!saved) return { ...base, state: "unsaved", status: "Save clarification before resubmitting", tone: "pending" };
  return { ...base, state: "pending", status: "Awaiting officer confirmation", tone: "pending" };
}
