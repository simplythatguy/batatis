import type { DraftingRecord, WordingDraft, Case as EngineCase } from "./api/types.gen";
import type { AccountPhase } from "./calm/account";
import { latestLocalFacts, localField } from "./intakeFields";
import { PROCESS_FACT, PROCESS_FIELDS } from "./model";
import { factSignature } from "./rules";
import type { Case, Fact, ProcessFieldId } from "./types";

export type ApplicantDraftCommand =
  | { kind: "generate" }
  | { kind: "decide"; draftId: string; decision: "accept" | "reject" };

export type ApplicantDraftActivity =
  | { kind: "idle" }
  | { kind: "generating" }
  | { kind: "deciding"; draftId: string };

export function applicantDraftHref(field: string): string {
  return `#/review?${new URLSearchParams({ focus: `draft:${field}` })}`;
}

/** Place a disclosure beside each literal claim without changing the accepted wording. */
export function draftPassages(draft: Pick<WordingDraft, "text" | "claims">) {
  let cursor = 0;
  const passages: { before: string; prefix: string; claim: WordingDraft["claims"][number] }[] = [];
  for (const claim of draft.claims) {
    if (!claim.text) return null;
    const at = draft.text.indexOf(claim.text, cursor);
    if (at < 0) return null;
    let before = draft.text.slice(cursor, at);
    const line = before.slice(before.lastIndexOf("\n") + 1);
    const marker = claim.kind === "assumption" ? "Assumption:" : claim.kind === "plan" ? "Plan:" : "";
    const prefix = marker && line.trim() === marker ? line : "";
    if (prefix) before = before.slice(0, -prefix.length);
    passages.push({ before, prefix, claim });
    cursor = at + claim.text.length;
  }
  return passages.length ? { passages, after: draft.text.slice(cursor) } : null;
}

/** Local edits make saved writing stale immediately, before an autosave or a server read. */
export function applicantDraftInputKey(c: Case): string {
  return JSON.stringify([
    c.description, c.authority,
    c.facts.filter(f => !f.source.ref.startsWith("applicant-draft:"))
      .map(f => [localField(f.field), factSignature(f)]).sort(),
    c.candidates.map(a => [a.provision, a.answer, Boolean(a.pending)]).sort(),
    c.files.map(f => [f.engineId ?? f.id, f.sha256 ?? ""]).sort(),
  ]);
}

/** Only the canonical fact actually acknowledged by the acceptance route can become an answer. */
export function acceptedApplicantFact(saved: EngineCase, draftId: string): Fact | undefined {
  const draft = saved.drafting?.drafts.find(d => d.id === draftId && d.status === "accepted");
  if (!draft) return undefined;
  const fact = latestLocalFacts(saved.facts).find(f => f.field === localField(draft.field));
  return fact?.kind === "pointed" && fact.status === "confirmed" && fact.source.type === "user_click"
    && fact.source.ref === `applicant-draft:${draftId}` && fact.value === draft.text && fact.source.quote === draft.text
    ? fact : undefined;
}

/** Compare the field alone so accepting writing cannot replace an answer typed while waiting. */
export function unchangedDraftField(before: Case, current: Case, field: string): boolean {
  const signature = (c: Case) => {
    const fact = latestLocalFacts(c.facts).find(f => f.field === localField(field));
    return fact ? factSignature(fact) : null;
  };
  return signature(before) === signature(current);
}

/** The latest draft for each process statement, in the form's order (absent when none was drafted). */
export function statementDrafts(record: Pick<DraftingRecord, "drafts"> | null): Map<ProcessFieldId, WordingDraft> {
  const out = new Map<ProcessFieldId, WordingDraft>();
  for (const p of PROCESS_FIELDS) {
    const draft = record?.drafts.filter(d => localField(d.field) === localField(PROCESS_FACT[p.id])).at(-1);
    if (draft) out.set(p.id, draft);
  }
  return out;
}

/**
 * The six statements are reviewed on one screen while drafting can run. Signed out, a saved
 * (read-only) application, or a drafting request that failed or returned nothing for them falls
 * back to one card per statement.
 */
export function statementReview(s: { phase: AccountPhase; readOnly: boolean; drafting: Pick<DraftingRecord, "drafts" | "stale"> | null; error: string }): boolean {
  if ((s.phase !== "signed-in" && s.phase !== "probing") || s.readOnly) return false;
  const drafted = statementDrafts(s.drafting).size > 0;
  if (s.error && !drafted) return false;
  return drafted || !s.drafting || s.drafting.stale;
}
