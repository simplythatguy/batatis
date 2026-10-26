import type { Case, EvidenceDraft } from "../types";
import type { ApplicantDraft, DraftFileBinding, RemoveFileBinding, RetainFileBinding } from "../api/types.gen";
import { questionDrafts } from "./questionDrafts";
import { getSession, resetSession, updateSavedSession, type Session } from "./session";

export type { ApplicantDraft } from "../api/types.gen";
export const DESCRIPTION_DRAFT = "description-editor";

type FileBinding = DraftFileBinding | RemoveFileBinding | RetainFileBinding;
const fileBinding = (fileRef: EvidenceDraft["fileRef"]): FileBinding => fileRef === undefined ? { kind: "retain" }
  : fileRef === null ? { kind: "remove" } : { kind: "file", file_id: fileRef };

function restoreFileBinding(value: unknown): Pick<EvidenceDraft, "fileRef"> {
  if (!value || typeof value !== "object" || !("kind" in value)) return {};
  if (value.kind === "remove") return { fileRef: null };
  if (value.kind === "file" && "file_id" in value && typeof value.file_id === "string") return { fileRef: value.file_id };
  return {};
}

export function draftAccount(user: { id: string; role: string | null; authority?: string | null } | null): string | null {
  return user ? JSON.stringify([user.id, user.role, user.authority]) : null;
}

export function sessionDraft(s: Session) {
  return { skipped: s.skipped, seen: s.seen, authority_unsure: s.authorityUnsure, packages: s.packages, rule_unsure: s.ruleUnsure };
}

export function applicantDraft(c: Case, account: string | null, generation: number, id: string | null): ApplicantDraft {
  const editors = questionDrafts.snapshot(questionDrafts.scope(account, generation, id));
  return {
    role: c.applicantType,
    intake_file_ids: c.files.flatMap(file => file.engineId ? [file.engineId] : []),
    ...editors,
    question_text: { ...editors.question_text, [DESCRIPTION_DRAFT]: { base: c.description.trim(), value: c.description } },
    ...sessionDraft(getSession()),
    evidence_drafts: Object.fromEntries(Object.entries(c.evidenceDrafts ?? {}).map(([key, value]) => {
      const { fileRef, ...rest } = value;
      return [key, { ...rest, step: value.step ?? null, editing: value.editing ?? null, file_binding: fileBinding(fileRef) }];
    })),
  };
}

/** Optional nulls in the server schema become omitted editor options, retaining fileRef's null withdrawal. */
export function evidenceDrafts(saved: ApplicantDraft | null | undefined): Record<string, EvidenceDraft> {
  return Object.fromEntries(Object.entries(saved?.evidence_drafts ?? {}).map(([key, value]) => {
    const { step, editing, file_binding, ...rest } = value;
    return [key, { ...rest, ...restoreFileBinding(file_binding), ...(step == null ? {} : { step }), ...(editing == null ? {} : { editing }) }];
  }));
}

export function restoreApplicantDraft(saved: ApplicantDraft | null | undefined, account: string | null, generation: number, id: string, preserveSession = false) {
  const scope = questionDrafts.scope(account, generation, id);
  questionDrafts.restore(scope, { question_text: saved?.question_text ?? {}, choices: saved?.choices ?? {} });
  const patch = saved ? {
    skipped: saved.skipped, seen: saved.seen, authorityUnsure: saved.authority_unsure,
    packages: saved.packages, ruleUnsure: saved.rule_unsure,
  } : { skipped: [], seen: [], authorityUnsure: false, packages: {}, ruleUnsure: [] };
  if (preserveSession) updateSavedSession(patch);
  else resetSession(patch);
}
