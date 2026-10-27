/**
 * Starting an application from the prepared draft (Start and the pre-application deck share it),
 * and the application row the open case belongs to. The role comes from the signed-in user's
 * onboarding; without one the deck asks it. Nothing is assumed for either.
 */
import type { ApplicationSummary, User } from "../api/accounts";
import { useCase } from "../store";
import type { ApplicantType } from "../types";
import { useAccount } from "./account";
import { readOnly } from "./applications";
import { getSession, resetSession } from "./session";
import { useApplicationEditsPaused } from "./applicationEditing";

const ROLES: ReadonlySet<string> = new Set(["manufacturer", "contractor", "homebuilder"]);

/** The applicant type from onboarding, or null when the user has none (or nobody is signed in). */
export function roleOf(user: User | null | undefined): ApplicantType | null {
  const t = user?.applicant_type ?? "";
  return ROLES.has(t) ? (t as ApplicantType) : null;
}

export function useBegin() {
  const { beginEmpty, dispatch } = useCase();
  const account = useAccount();
  const userRole = account.phase === "signed-in" ? roleOf(account.user) : null;
  return {
    userRole,
    /** Start from the session draft. False while the description or the role is still missing. */
    begin(role?: ApplicantType | null): boolean {
      const s = getSession();
      const r = role ?? userRole ?? s.role;
      if (!r || !s.draft.trim()) return false;
      const files = s.draftFiles;
      beginEmpty(r);
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
  const paused = useApplicationEditsPaused();
  const account = useAccount();
  const app = (engineId && account.applications?.find((a) => a.id === engineId)) || null;
  const saved = readOnly(app?.status ?? applicationStatus);
  return { app, locked: paused || submissionDispatched || saved, readOnly: saved };
}
