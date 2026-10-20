/**
 * Whether a Section D issue still needs a registered professional.
 * Matches the confirmation rule on PR #26: an applicant's own yes/no,
 * including the prescriptive route and reserved judgement, does not clear it.
 * A document that merely names a person or a seal does not either.
 */

export interface ProfessionalFact {
  field: string;
  value: unknown;
  status?: string;
  kind?: string;
  source?: { type?: string };
}

const APPLICANT_SOURCES = new Set(["user_text", "user_click"]);
const ROLE_FIELDS = [
  "professional.role",
  "professional.discipline",
  "registered_professional.role",
  "registered_professional.discipline",
  "professional_name",
  "responsible_professional",
  "professional.name",
];
const SEAL_FIELDS = ["professional.seal", "professional_seal", "registered_professional.seal"];
const REGISTRATION_FIELDS = [
  "professional.registration_number",
  "professional.registration",
  "registered_professional.registration_number",
  "apega_number",
  "aaa_number",
];
const REJECT_ROLE = new Set(["sales", "rep", "supplier", "manufacturer", "salesperson", "vendor"]);

export const SCOPE_FIELDS = ["prescriptive_route_confirmed", "professional_judgement_required"] as const;
/** What the authority decided. Not sure on these is an open question for the officer. */
export const AUTHORITY_DECISION_FIELDS = [
  "ahj_requires_professional",
  "special_safety_concerns",
  "professional_scope_resolved",
] as const;
/** An authority's own requirement. It does not name an engineer or architect. */
export const AUTHORITY_ONLY_FIELDS = ["ahj_requires_professional", "special_safety_concerns"] as const;
export type ScopeField = (typeof SCOPE_FIELDS)[number];

export const SCOPE_HELP: Record<ScopeField, string> = {
  prescriptive_route_confirmed:
    "Yes means the design stays on the written prescriptive rules. No means it does not. Neither answer removes a need for a registered professional.",
  professional_judgement_required:
    "Yes means the design needs a judgement reserved to an engineer or architect. No means you believe it does not. Neither answer removes that need.",
};

export function isScopeField(field: string): field is ScopeField {
  return (SCOPE_FIELDS as readonly string[]).includes(field);
}

function latest(facts: ProfessionalFact[], fields: string[]): ProfessionalFact | undefined {
  for (let i = facts.length - 1; i >= 0; i--) {
    if (fields.includes(facts[i].field)) return facts[i];
  }
  return undefined;
}

/** Confirmed applicant text. A file, a proposal, or an empty value does not qualify. */
function applicantText(facts: ProfessionalFact[], fields: string[]): string | null {
  const fact = latest(facts, fields);
  if (!fact || fact.status !== "confirmed" || fact.kind === "proposed") return null;
  if (!fact.source?.type || !APPLICANT_SOURCES.has(fact.source.type)) return null;
  if (typeof fact.value !== "string" || !fact.value.trim()) return null;
  return fact.value.trim();
}

/** Same rule as PR #26. Punctuation is ignored. A commercial role never confirms. */
export function roleConfirmed(value: string): boolean {
  const tokens = value
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, " ")
    .split(/\s+/)
    .filter(Boolean);
  if (tokens.some((token) => REJECT_ROLE.has(token))) return false;
  if (tokens.includes("peng") || (tokens.includes("p") && tokens.includes("eng"))) return true;
  return tokens.includes("engineer") || tokens.includes("architect");
}

/**
 * An applicant's Yes or No cannot turn practice off.
 * The engine's "no", which is computed from those answers, cannot either.
 * A seal or registration number is what clears the gap.
 */
export function practiceFromReview(
  current: true | false | "unknown" | undefined,
  required: "yes" | "no" | "depends",
  issueSaysYes: boolean,
): true | "unknown" {
  if (issueSaysYes || required === "yes" || current === true) return true;
  return "unknown";
}

/** #23 will rename gap status `provided` to `evidence_listed`. Both mean the applicant listed evidence. */
export function evidenceRecorded(status: string | null | undefined): boolean {
  return status === "provided" || status === "evidence_listed";
}

/** Engineer or architect, plus a seal or registration number, confirmed by the applicant. */
export function professionalConfirmed(facts: ProfessionalFact[]): boolean {
  const role = applicantText(facts, ROLE_FIELDS);
  if (!role || !roleConfirmed(role)) return false;
  return applicantText(facts, SEAL_FIELDS) !== null || applicantText(facts, REGISTRATION_FIELDS) !== null;
}

export type IssueStatus = "open" | "evidence_listed" | "needs_professional";

/** Self-answers are not an input. They cannot move a true practice flag off needs_professional. */
export function sectionDIssueStatus(input: {
  practice: true | false | "unknown";
  facts: ProfessionalFact[];
  evidenceLinked: boolean;
}): IssueStatus {
  if (input.practice === "unknown") return "open";
  if (input.practice === true && !professionalConfirmed(input.facts)) return "needs_professional";
  if (input.evidenceLinked) return "evidence_listed";
  return "open";
}

export function evidenceLinked(facts: ProfessionalFact[], itemId: string): boolean {
  return facts.some((fact) => {
    const field = fact.field;
    const own = field.startsWith(`evidence.${itemId}.`) || field.startsWith(`evidence.${itemId}~`);
    if (!own) return false;
    if (fact.status && fact.status !== "confirmed") return false;
    if (fact.kind === "proposed") return false;
    return field.endsWith(".file_ref") || field.endsWith(".title") || field.endsWith(".responsible_party");
  });
}
