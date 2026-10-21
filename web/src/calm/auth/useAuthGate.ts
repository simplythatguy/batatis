/**
 * The auth gate and the account actions behind the sign-in, onboarding, settings and sign-out
 * screens. State lives in calm/account.ts; this file only reads it and moves it forward.
 */
import { useEffect } from "react";
import { auth, type OnboardingRequest, type User } from "../../api/accounts";
import type { Route } from "../../router";
import { bootAccount, getAccountState, refreshApplications, setAccountState, useAccount } from "../account";
import { gateRedirect, gateStatus, homeFor, returnTarget, type GateStatus } from "./gate";

const RETURN_KEY = "batatis.returnTo";

function readReturn(): string | null {
  try {
    return sessionStorage.getItem(RETURN_KEY);
  } catch {
    return null;
  }
}

/** The place the visitor was sent to sign in from, if any. */
export const rememberedReturn = readReturn;

function writeReturn(hash: string | null) {
  try {
    if (hash) sessionStorage.setItem(RETURN_KEY, hash);
    else sessionStorage.removeItem(RETURN_KEY);
  } catch {
    /* private mode: no return-to, the home route still works */
  }
}

/** Status for App: loading, signed-out, needs-onboarding or ready (ready with no user = no accounts on this server). */
export function useAuthGate(): { status: GateStatus; user: User | null } {
  useEffect(() => {
    bootAccount();
  }, []);
  const a = useAccount();
  return { status: gateStatus(a.phase, a.user), user: a.user };
}

/**
 * Sends the visitor where the gate says (sign-in, onboarding, or home after signing in).
 * Returns true while a redirect is pending or the session is still loading, so App can render
 * nothing instead of flashing the wrong screen.
 */
export function useAuthRedirect(route: Route): boolean {
  const { status, user } = useAuthGate();
  const target = gateRedirect(status, user, route.path, readReturn());
  useEffect(() => {
    if (!target) return;
    // A screen may already have navigated on (sign-in sends the person to their return place).
    if ((location.hash.replace(/^#/, "").split("?")[0] || "/") !== (route.path || "/")) return;
    if (target === "#/signin") writeReturn(returnTarget(location.hash));
    else if (status === "ready") writeReturn(null);
    location.replace(target);
  }, [target, status, route.path]);
  return status === "loading" || target !== null;
}

/** After sign-in or sign-up: onboarding first, otherwise the remembered place or home. */
export function afterSignIn(user: User): string {
  if (!user.onboarded) return "#/onboarding";
  const back = readReturn();
  writeReturn(null);
  return back ?? homeFor(user);
}

function signedIn(user: User) {
  setAccountState({ phase: "signed-in", user, applications: null, listError: "" });
  if (user.onboarded && user.role !== "reviewer") void refreshApplications();
}

export async function signIn(email: string, password: string): Promise<User> {
  const user = await auth.login({ email: email.trim(), password });
  signedIn(user);
  return user;
}

export async function signUp(name: string, email: string, password: string): Promise<User> {
  const user = await auth.signup({ name: name.trim(), email: email.trim(), password });
  signedIn(user);
  return user;
}

/** Onboarding and the settings role change share this endpoint. */
export async function saveOnboarding(body: OnboardingRequest): Promise<User> {
  const user = await auth.onboarding(body);
  signedIn(user);
  return user;
}

/** Ends the server session, then reloads on the sign-in page so no previous case stays in memory. */
export async function signOut(): Promise<void> {
  try {
    await auth.logout();
  } finally {
    writeReturn(null);
    setAccountState({ phase: "signed-out", user: null, applications: null });
    location.hash = "#/signin";
    location.reload();
  }
}

export function currentUser(): User | null {
  return getAccountState().user;
}
