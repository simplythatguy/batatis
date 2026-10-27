/** The applicant draft's wire shape, without browser state, so the engine's Node checks can load openCase. */
import type { ApplicantDraft, DraftFileBinding, RemoveFileBinding, RetainFileBinding } from "../api/types.gen";
import type { EvidenceDraft } from "../types";

export const DESCRIPTION_DRAFT = "description-editor";

type FileBinding = DraftFileBinding | RemoveFileBinding | RetainFileBinding;
export const fileBinding = (fileRef: EvidenceDraft["fileRef"]): FileBinding => fileRef === undefined ? { kind: "retain" }
  : fileRef === null ? { kind: "remove" } : { kind: "file", file_id: fileRef };

function restoreFileBinding(value: unknown): Pick<EvidenceDraft, "fileRef"> {
  if (!value || typeof value !== "object" || !("kind" in value)) return {};
  if (value.kind === "remove") return { fileRef: null };
  if (value.kind === "file" && "file_id" in value && typeof value.file_id === "string") return { fileRef: value.file_id };
  return {};
}

/** Optional nulls in the server schema become omitted editor options, retaining fileRef's null withdrawal. */
export function evidenceDrafts(saved: ApplicantDraft | null | undefined): Record<string, EvidenceDraft> {
  return Object.fromEntries(Object.entries(saved?.evidence_drafts ?? {}).map(([key, value]) => {
    const { step, editing, file_binding, ...rest } = value;
    return [key, { ...rest, ...restoreFileBinding(file_binding), ...(step == null ? {} : { step }), ...(editing == null ? {} : { editing }) }];
  }));
}
