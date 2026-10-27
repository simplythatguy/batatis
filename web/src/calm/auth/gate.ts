/**
 * Who may see which route, as pure functions over the account state. The hooks in
 * useAuthGate.ts apply them; App only asks "where should this visitor be?".
 */
import type { User } from "../../api/accounts";
import type { AccountPhase } from "../account";

export type GateStatus = "loading" | "signed-out" | "needs-onboarding" | "ready";

/** Pages for visitors who are not signed in. */
export const AUTH_PATHS: ReadonlySet<string> = new Set(["/signin", "/signup"]);

/**
 * `anonymous` means the server has no accounts routes (or the browser cannot send credentials):
 * the single-visit flow keeps working, so the gate is open with no user.
 */
export function gateStatus(phase: AccountPhase, user: User | null): GateStatus {
  if (phase === "probing") return "loading";
  if (phase === "signed-out") return "signed-out";
  if (phase === "anonymous") return "ready";
  if (!user) return "signed-out";
  return user.onboarded ? "ready" : "needs-onboarding";
}

/** Where a signed-in, onboarded person starts. */
export function homeFor(user: User | null): string {
  return user?.role === "reviewer" ? "#/review" : "#/";
}

/** A hash worth coming back to after signing in (never the auth pages themselves). */
export function returnTarget(hash: string): string | null {
  const raw = hash.replace(/^#/, "") || "/";
  const path = raw.split("?")[0] || "/";
  if (AUTH_PATHS.has(path) || path === "/onboarding" || path === "/") return null;
  return `#${raw}`;
}

/**
 * The hash this visitor should be sent to, or null to stay. `path` is the router path
 * ("/review/abc"), `returnTo` the remembered place from before sign-in.
 */
export function gateRedirect(status: GateStatus, user: User | null, path: string, returnTo: string | null = null): string | null {
  const p = path || "/";
  switch (status) {
    case "loading":
      return null;
    case "signed-out":
      return p === "/" || AUTH_PATHS.has(p) ? null : "#/signin";
    case "needs-onboarding":
      return p === "/onboarding" ? null : "#/onboarding";
    case "ready":
      if (!user) return AUTH_PATHS.has(p) || p === "/onboarding" ? "#/" : null;
      if (AUTH_PATHS.has(p) || p === "/onboarding") return returnTo ?? homeFor(user);
      if (user.role === "reviewer" && p === "/") return "#/review";
      return null;
  }
}
