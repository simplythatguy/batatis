import type { WordingDraft, Case as EngineCase } from "./api/types.gen";
import { latestLocalFacts, localField } from "./intakeFields";
import { factSignature } from "./rules";
import type { Case, Fact } from "./types";

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
