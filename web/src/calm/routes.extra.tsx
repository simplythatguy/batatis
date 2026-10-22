/**
 * Account, reviewer, settings and notification routes (U2), plus the rail footer slots and the
 * auth gate. App asks `extraRoutes(route)` before its own switch:
 *   - standalone pages (sign-in, sign-up, onboarding) render without the shell (`isStandaloneRoute`);
 *   - the others render inside the shell's main area without the application header or list;
 *     each page draws its own header.
 * `#/review` is the reviewer queue only for reviewers; applicants keep their own Review screen.
 */
import type { ReactNode } from "react";
import { AccuracyPage } from "../accuracy/AccuracyPage";
import type { Route } from "../router";
import { getAccountState } from "./account";
import { AccountButton } from "./auth/AccountButton";
import { AuthPage } from "./auth/AuthPage";
import { Onboarding } from "./auth/Onboarding";
import { NotificationsBell, NotificationsLink, NotificationsPage } from "./notifications/NotificationsBell";
import { ReviewDetail } from "./reviewer/ReviewDetail";
import { ReviewQueue } from "./reviewer/ReviewQueue";
import { Settings } from "./settings/Settings";
import "./accounts.css";

export { AccountButton, NotificationsBell };
export { useAuthGate, useAuthRedirect } from "./auth/useAuthGate";
export { gateRedirect, gateStatus, homeFor, type GateStatus } from "./auth/gate";

const STANDALONE = new Set(["/signin", "/signup", "/onboarding"]);

/** Sign-in, sign-up and onboarding fill the window; render them without the shell. So does the
 * public accuracy report for a visitor who is not signed in. */
export function isStandaloneRoute(route: Route): boolean {
  return STANDALONE.has(route.path) || (route.path === "/accuracy" && getAccountState().phase === "signed-out");
}

function reviewId(path: string): string | null {
  const m = /^\/review\/(.+)$/.exec(path);
  if (!m) return null;
  try {
    return decodeURIComponent(m[1]) || null;
  } catch {
    return null;
  }
}

/** On phones the rail is hidden, so in-app pages carry the bell (as a link) and the account menu. */
const phoneTools = (
  <>
    <NotificationsLink />
    <AccountButton />
  </>
);

/** The page for a U2 route, or null when the route belongs to the applicant flow. */
export function extraRoutes(route: Route): ReactNode | null {
  const { path } = route;
  switch (path) {
    case "/signin":
      return <AuthPage mode="signin" />;
    case "/signup":
      return <AuthPage mode="signup" />;
    case "/onboarding":
      return <Onboarding />;
    case "/settings":
      return <Settings phoneTools={phoneTools} />;
    case "/accuracy":
      return getAccountState().phase === "signed-out"
        ? <AccuracyPage right={<a className="cf-btn is-sm" href="#/signin">Sign in</a>} />
        : <AccuracyPage phoneTools={phoneTools} />;
    case "/notifications":
      return <NotificationsPage phoneTools={phoneTools} />;
    case "/review":
      return getAccountState().user?.role === "reviewer" ? <ReviewQueue phoneTools={phoneTools} /> : null;
  }
  const id = getAccountState().user?.role === "reviewer" ? reviewId(path) : null;
  if (id) return <ReviewDetail key={id} caseId={id} phoneTools={phoneTools} />;
  return null;
}
