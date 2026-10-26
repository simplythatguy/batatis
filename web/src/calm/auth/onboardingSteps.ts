/** Onboarding questions as data: which question comes next and what the server receives. Pure. */
import type { ApplicantKind, AuthorityKey, OnboardingRequest, Role } from "../../api/accounts";

export type StepId = "use" | "authority" | "code";

export interface Answers {
  use?: Role;
  authority?: AuthorityKey;
  code: string;
}

export interface Choice<T extends string> {
  value: T;
  label: string;
  sub?: string;
}

export const USE_CHOICES: Choice<Role>[] = [
  { value: "applicant", label: "I have a building project", sub: "Owner, designer, builder, engineer or manufacturer" },
  { value: "reviewer", label: "I review applications for an authority", sub: "Safety Codes Officer. Needs your authority’s access code." },
];

export const APPLICANT_CHOICES: Choice<ApplicantKind>[] = [
  { value: "manufacturer", label: "Manufacturer" },
  { value: "contractor", label: "General contractor" },
  { value: "homebuilder", label: "Homebuilder" },
];

export const AUTHORITY_CHOICES: Choice<AuthorityKey>[] = [
  { value: "calgary", label: "Calgary" },
  { value: "edmonton", label: "Edmonton" },
];

export const APPLICANT_LABEL: Record<string, string> = { manufacturer: "Manufacturer", contractor: "General contractor", homebuilder: "Homebuilder" };

/** Letter keys for choices: A, B, C… */
export const KEYS = "ABCDEFGH";

export function stepsFor(a: Answers): StepId[] {
  if (a.use === "reviewer") return ["use", "authority", "code"];
  return ["use"];
}

export function answered(step: StepId, a: Answers): boolean {
  switch (step) {
    case "use":
      return Boolean(a.use);
    case "authority":
      return Boolean(a.authority);
    case "code":
      return a.code.trim().length > 0;
  }
}

/** The step after `step`, or null when this answer completes onboarding. */
export function nextStep(step: StepId, a: Answers): StepId | null {
  const steps = stepsFor(a);
  const i = steps.indexOf(step);
  return i >= 0 && i < steps.length - 1 ? steps[i + 1] : null;
}

export function previousStep(step: StepId, a: Answers): StepId | null {
  const steps = stepsFor(a);
  const i = steps.indexOf(step);
  return i > 0 ? steps[i - 1] : null;
}

/** The POST /auth/onboarding body once every question is answered; null before that. */
export function onboardingPayload(a: Answers): OnboardingRequest | null {
  if (a.use === "applicant") return { role: "applicant" };
  if (a.use === "reviewer" && a.authority && a.code.trim()) return { role: "reviewer", authority: a.authority, access_code: a.code.trim() };
  return null;
}

/**
 * Settings role change. Becoming a reviewer needs the target authority's code; leaving the reviewer
 * role needs the current authority's code (server rule). Returns the code requirement or null.
 */
export function codeNeeded(current: { role: Role | null; authority: string | null }, target: Role, targetAuthority?: string | null): { authority: string } | null {
  if (target === "reviewer" && targetAuthority) return { authority: targetAuthority };
  if (target === "applicant" && current.role === "reviewer" && current.authority) return { authority: current.authority };
  return null;
}
