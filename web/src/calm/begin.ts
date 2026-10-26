/**
 * Starting an application from the prepared draft (Start and the pre-application deck share it),
 * and the application row the open case belongs to. A new application has no applicant type;
 * the person's part in the project is answered later, with the paperwork.
 */
import type { ApplicationSummary, User } from "../api/accounts";
import { useCase } from "../store";
import type { ApplicantType } from "../types";
import { useAccount } from "./account";
import { readOnly } from "./applications";
import { getSession, resetSession } from "./session";

/** The applicant type from onboarding, or null when the user has none (or nobody is signed in). */
export function roleOf(user: User | null | undefined): ApplicantType | null {
  const t = user?.applicant_type;
  return t === "manufacturer" || t === "contractor" || t === "homebuilder" ? t : null;
}

export function useBegin() {
  const { beginEmpty, dispatch } = useCase();
  const account = useAccount();
  return {
    /** Start from text or files, once sign-in is ready. No role is inferred from the account. */
    begin(): boolean {
      const s = getSession();
      if (account.phase !== "anonymous" && (account.phase !== "signed-in" || !account.user?.onboarded || account.user.role === "reviewer")) return false;
      if (s.draftFilesLost || (!s.draft.trim() && !s.draftFiles.length)) return false;
      const files = s.draftFiles;
      beginEmpty(null);
      dispatch({ type: "setDescription", text: s.draft });
      if (files.length) dispatch({ type: "addFiles", files: files.map((f) => ({ id: f.id, name: f.file.name })) });
      resetSession({ held: files, readAfterStart: true });
      location.hash = "#/questions";
      return true;
    },
  };
}

/**
 * The account's row for the open case (status, authority, reviewer), or null without one.
 * `readOnly`: the saved application itself is sent or closed, and screens show it as such.
 * `locked`: nothing may be edited now. Also true while a dispatched submission is on its way: the
 * application is not read-only yet, so its editing controls stay mounted and paused (App's edit lock).
 */
export function useCurrentApplication(): { app: ApplicationSummary | null; locked: boolean; readOnly: boolean } {
  const { engineId, applicationStatus, submissionDispatched } = useCase();
  const account = useAccount();
  const app = (engineId && account.applications?.find((a) => a.id === engineId)) || null;
  const saved = readOnly(app?.status ?? applicationStatus);
  return { app, locked: submissionDispatched || saved, readOnly: saved };
}
