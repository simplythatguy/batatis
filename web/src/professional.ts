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
];
const SEAL_FIELDS = ["professional.seal", "professional_seal", "registered_professional.seal"];
const REGISTRATION_FIELDS = [
  "professional.registration_number",
  "professional.registration",
  "registered_professional.registration_number",
  "apega_number",
  "aaa_number",
];
const ROLE_VALUES = new Set([
  "engineer",
  "architect",
  "professional engineer",
  "registered engineer",
  "professional architect",
  "registered architect",
]);

export const SCOPE_FIELDS = ["prescriptive_route_confirmed", "professional_judgement_required"] as const;
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

function roleConfirmed(value: string): boolean {
  const tokens: string[] = value.toLowerCase().match(/[a-z]+/g) ?? [];
  if (tokens.includes("sales")) return false;
  return ROLE_VALUES.has(tokens.join(" "));
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
