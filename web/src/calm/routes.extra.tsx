/**
 * Extension point for the accounts UI (sign-in, onboarding, settings, notifications, reviewer).
 * The accounts branch owns this file and replaces these stubs; the applicant shell only imports
 * the three exports below.
 *
 * - `extraRoutes(route)`: a full page for routes the applicant flow does not know
 *   (for example `#/sign-in`, `#/settings`, `#/review-queue`), or null to fall through.
 * - `NotificationsPanel`: the rail's bell (unread dot) and its panel. Renders nothing until filled.
 * - `AccountMenu`: the rail's avatar and account menu. Until filled it shows the plain avatar.
 */
import type { ReactNode } from "react";
import type { Route } from "../router";

export function extraRoutes(_route: Route): ReactNode | null {
  return null;
}

export function NotificationsPanel(): ReactNode {
  return null;
}

export function AccountMenu({ fallback }: { fallback: ReactNode }): ReactNode {
  return fallback;
}
