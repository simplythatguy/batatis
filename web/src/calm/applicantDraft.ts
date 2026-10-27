import type { Case } from "../types";
import type { ApplicantDraft } from "../api/types.gen";
import { DESCRIPTION_DRAFT, fileBinding } from "./draftWire";
import { questionDrafts } from "./questionDrafts";
import { getSession, resetSavedSession, updateSavedSession, type Session } from "./session";

export type { ApplicantDraft } from "../api/types.gen";

export function draftAccount(user: { id: string; role: string | null; authority?: string | null } | null): string | null {
  return user ? JSON.stringify([user.id, user.role, user.authority]) : null;
}

export function sessionDraft(s: Session) {
  // Skips are gone, and Not sure answers are recorded on the case itself; the draft keeps only what is visit state.
  return { skipped: [], seen: s.seen, authority_unsure: false, packages: s.packages, rule_unsure: [] };
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

export function restoreApplicantDraft(saved: ApplicantDraft | null | undefined, account: string | null, generation: number, id: string, preserveSession = false) {
  const scope = questionDrafts.scope(account, generation, id);
  questionDrafts.restore(scope, { question_text: saved?.question_text ?? {}, choices: saved?.choices ?? {} });
  const patch = saved ? { seen: saved.seen, packages: saved.packages } : { seen: [], packages: {} };
  if (preserveSession) updateSavedSession(patch);
  else resetSavedSession(patch);
}
