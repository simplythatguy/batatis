import { decidePath } from "./pathDecision";
import type { Case, Fact } from "./types";
import { localField } from "./intakeFields";

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
const UNRESOLVED_ANSWERS = new Set(["not sure", "not_sure", "not sure (the officer decides)", "not_engaged_yet", "not_engaged", "no professional engaged yet"]);
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
  if (UNRESOLVED_ANSWERS.has(fact.value.trim().toLowerCase().replace(/\s+/g, " "))) return null;
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

/** `unscoped` slots were detached by a reference withdrawal and never count for this task. */
export function evidenceLinked(facts: ProfessionalFact[], itemId: string, unscoped: readonly string[] = []): boolean {
  return facts.some((fact) => {
    const field = fact.field;
    const own = field.startsWith(`evidence.${itemId}.`) || field.startsWith(`evidence.${itemId}~`);
    if (!own) return false;
    if (unscoped.includes(field.split(".")[1])) return false;
    if (fact.status && fact.status !== "confirmed") return false;
    if (fact.kind === "proposed") return false;
    return field.endsWith(".file_ref") || field.endsWith(".title") || field.endsWith(".responsible_party");
  });
}

export type ProfessionalQuestionKind = "bool" | "number" | "occupancy" | "role" | "text";
export interface ProfessionalQuestion {
  field: string;
  label: string;
  kind: ProfessionalQuestionKind;
  value: Fact["value"] | undefined;
  known: boolean;
  deferred: boolean;
}

const QUESTIONS: { field: string; label: string; kind: ProfessionalQuestionKind }[] = [
  { field: "occupancy", label: "What is the building used for?", kind: "occupancy" },
  { field: "storeys", label: "How many storeys is the building?", kind: "number" },
  { field: "building_area_m2", label: "What is the building area (the footprint)?", kind: "number" },
  { field: "gross_area_per_floor_m2", label: "What gross area applies to each floor?", kind: "number" },
  { field: "total_unit_count", label: "How many homes are there, including secondary suites?", kind: "number" },
  { field: "engineer_engaged", label: "Is a registered engineer engaged?", kind: "bool" },
  { field: "principal_dwelling_units", label: "How many principal homes, excluding qualifying secondary suites?", kind: "number" },
  { field: "farm_public_use", label: "Is the farm building for public use?", kind: "bool" },
  { field: "part4_design", label: "Is any design carried out under Part 4?", kind: "bool" },
  { field: "roof_trusses", label: "Are wood roof trusses or truss connections included?", kind: "bool" },
  { field: "preserved_wood_foundation_part4", label: "Is there a preserved wood foundation designed under Part 4?", kind: "bool" },
  { field: "fire_suppression", label: "Is a fire suppression system being installed?", kind: "bool" },
  { field: "fire_alarm", label: "Is a fire alarm system being installed?", kind: "bool" },
  { field: "prescriptive_route_confirmed", label: "Does the design follow the prescriptive route?", kind: "bool" },
  { field: "professional_judgement_required", label: "Does the design need reserved professional judgement?", kind: "bool" },
  { field: "role", label: "Who is the registered professional for this scope?", kind: "role" },
  { field: "registration_number", label: "Professional registration number", kind: "text" },
  { field: "seal", label: "Seal confirmed by your professional", kind: "text" },
];

/** Latest across intake and professional aliases, including withdrawals; never revives an older answer. */
export function professionalValue(c: Case, fieldId: string): Fact["value"] | undefined {
  const field = fieldId.replace(/^professional\./, "");
  const names = [field, `professional.${field}`];
  if (field === "registration_number") names.push(...REGISTRATION_FIELDS);
  if (field === "seal") names.push(...SEAL_FIELDS);
  if (field === "role") names.push("registered_professional.role");
  const fact = [...c.facts].reverse().find((fact) => names.includes(localField(fact.field)));
  if (!fact || fact.status !== "confirmed" || fact.kind === "proposed" || fact.value == null || fact.value === "") return undefined;
  if (["role", "registration_number", "seal"].includes(field) && !APPLICANT_SOURCES.has(fact.source.type)) return undefined;
  return fact.value;
}

export function professionalAnswerer(fieldId: string): "you" | "designer" {
  const field = fieldId.replace(/^professional\./, "");
  return ["registration_number", "registration", "apega_number", "aaa_number", "seal", "part4_design", "preserved_wood_foundation_part4", "roof_trusses", "prescriptive_route_confirmed", "professional_judgement_required", "professional_scope_resolved"].includes(field)
    || /registration|seal|judgement|judgment|fire_resistance|hazard|assembly/.test(field) ? "designer" : "you";
}

function deferredProfessional(c: Case, field: string): boolean {
  const value = professionalValue(c, field);
  return (typeof value === "string" && UNRESOLVED_ANSWERS.has(value.trim().toLowerCase()))
    || c.questions.some((question) => question.id === `q-scope-${field}` && !question.answer);
}

/** This chooses controls, never whether a professional is required; the engine retains that decision. */
export function professionalQuestions(c: Case, missing?: readonly string[]): ProfessionalQuestion[] {
  if (!c.description.trim() && !c.facts.length && !c.candidates.length) return [];
  const get = (field: string) => professionalValue(c, field);
  const occupancy = get("occupancy");
  const storeys = get("storeys");
  const area = get("building_area_m2");
  const provisions = c.candidates.filter((candidate) => candidate.answer === "yes" || candidate.benchmark).map((candidate) => candidate.provision);
  const part3 = (typeof storeys === "number" && storeys > 3) || (typeof area === "number" && area > 600)
    || ["assembly", "care", "treatment", "detention"].includes(String(occupancy)) || provisions.some((provision) => provision.startsWith("3."));
  const part9 = !part3 && (["single_family", "multi_family", "farm", "hotel", "business", "mercantile", "industrial", "relocatable_industrial_camp"].includes(String(occupancy)) || provisions.some((provision) => provision.startsWith("9.")));
  const text = [c.description, ...c.facts.filter((fact) => fact.status === "confirmed" && ["alternative", "alternative_description", "project.description"].includes(localField(fact.field))).map((fact) => String(fact.value))].join(" ").toLowerCase();
  const fireOnly = /fire[ -]?(?:stop|separation)|penetration/.test(text) && !provisions.some((provision) => /^(?:4\.|9\.(?:4|15|23)\.)/.test(provision));
  const onAcceptablePath = decidePath(c).path === "acceptable";
  const needed = missing && new Set(missing.flatMap((name) => name.split(" or ")).map((name) => name.replace(/^professional\./, "")));
  const exception = ["single_family", "relocatable_industrial_camp"].includes(String(occupancy)) || (occupancy === "farm" && get("farm_public_use") === false);
  const roleDeferred = deferredProfessional(c, "role");
  const resolvedNotRequired = c.practiceOfEngineering !== true && professionalWorkCurrent(c) && c.professionalWork?.professional.required === "no";
  return QUESTIONS.filter((question) => {
    const field = question.field;
    if (["registration_number", "seal"].includes(field) && roleDeferred && get(field) === undefined) return false;
    if (field === "seal") return get(field) !== undefined || Boolean(needed?.has(field) && !needed.has("registration_number"));
    if (needed?.has(field)) return true;
    if (["gross_area_per_floor_m2", "total_unit_count", "engineer_engaged"].includes(field)) return get(field) !== undefined;
    if (field === "principal_dwelling_units") return occupancy === "multi_family";
    if (field === "farm_public_use") return occupancy === "farm";
    if (field === "roof_trusses") return get(field) !== undefined || (part9 && !fireOnly && (get("part4_design") === true || /\btruss/.test(text) || provisions.some((provision) => provision.startsWith("9.23.14"))));
    if (field === "preserved_wood_foundation_part4") return get(field) !== undefined || (part9 && !fireOnly && (get("part4_design") === true || /preserved[ -]wood|wood foundation/.test(text) || provisions.some((provision) => provision.startsWith("9.15.2"))));
    if (field === "part4_design") return get(field) !== undefined || !fireOnly;
    if (field === "fire_suppression" || field === "fire_alarm") return get(field) !== undefined || !exception || needed?.has(field);
    if (field === "prescriptive_route_confirmed") return onAcceptablePath;
    if (field === "role" && resolvedNotRequired) return false;
    if (field === "registration_number") return get(field) !== undefined || (!resolvedNotRequired && !roleDeferred && !professionalConfirmed(c.facts));
    return true;
  }).map((question) => {
    const value = get(question.field);
    const deferred = deferredProfessional(c, question.field);
    const valid = question.kind === "bool" ? typeof value === "boolean"
      : question.kind === "number" ? typeof value === "number" && Number.isFinite(value) && value > 0 && (question.field.endsWith("_m2") || Number.isSafeInteger(value))
      : question.kind === "role" ? typeof value === "string" && roleConfirmed(value)
      : typeof value === "string" && Boolean(value.trim());
    return { ...question, value, deferred, known: valid && !deferred };
  }).filter((question) => !needed || question.known || question.deferred || ["role", "registration_number"].includes(question.field) || needed.has(question.field));
}

/** These belong to the office; the professional screen never asks applicants to invent a decision. */
export function professionalOfficeQuestions(c: Case): { field: string; label: string }[] {
  return [
    { field: "ahj_requires_professional", label: "Whether the office requires a registered professional" },
    { field: "special_safety_concerns", label: "Whether size or complexity needs professional involvement" },
    { field: "professional_scope_resolved", label: "Local submission and professional scope requirements" },
  ].filter((question) => {
    const fact = [...c.facts].reverse().find((fact) => [question.field, `professional.${question.field}`].includes(fact.field));
    return !fact || fact.status !== "confirmed" || fact.kind === "proposed" || !["officer", "professional", "code"].includes(fact.source.type)
      || typeof fact.value !== "boolean" || (question.field === "professional_scope_resolved" && !fact.value);
  });
}

/** Exact for a current engine plan; the local projection is provisional while that plan loads. */
export function professionalEvidenceCount(c: Case): number {
  if (professionalWorkCurrent(c) && c.professionalWork) return c.professionalWork.plan.items.filter((item) => !evidenceRecorded(item.status)).length;
  const withdrawn = new Set([...(c.unscopedEvidence ?? []), ...(c.deletedEvidence ?? [])]);
  const latest = new Map(c.facts.map((fact) => [fact.field, fact]));
  const saved = (field: string) => {
    const fact = latest.get(field);
    return fact?.status === "confirmed" && fact.kind !== "proposed" ? fact.value : undefined;
  };
  const scopes = new Set<string>();
  for (const fact of latest.values()) {
    const slot = fact.field.match(/^evidence\.([^.]+)\.title$/)?.[1];
    if (!slot || withdrawn.has(slot) || !saved(fact.field) || !saved(`evidence.${slot}.evidence_type`)) continue;
    const provision = saved(`evidence.${slot}.provision_id`);
    if (typeof provision !== "string") continue;
    scopes.add(JSON.stringify([provision, saved(`evidence.${slot}.function`) ?? null, saved(`evidence.${slot}.objective`) ?? null]));
  }
  const tasks = new Set<string>();
  for (const row of c.sectionC) {
    if (!row.pairs.length) tasks.add(JSON.stringify([row.provision, null, null]));
    for (const pair of row.pairs) for (const fn of pair.functions) for (const objective of pair.objectives) tasks.add(JSON.stringify([row.provision, fn, objective]));
  }
  return [...tasks].filter((task) => !scopes.has(task)).length;
}

/** Questions still needing an applicant response. Deferred answers stay open with their answerer. */
export function professionalOpenCount(c: Case): number {
  const missing = professionalWorkCurrent(c) ? c.professionalWork?.professional.missing_facts : undefined;
  return professionalQuestions(c, missing).filter((question) => !question.known && !question.deferred).length + professionalEvidenceCount(c);
}

export function professionalWorkBasis(c: Case): string {
  return JSON.stringify([c.title, c.description, c.authority, c.facts, c.candidates, c.sectionC, c.listedEvidence ?? [], c.deletedEvidence ?? [], c.unscopedEvidence ?? [], c.questions]);
}

/** The footer can show a pending count until the engine has supplied this snapshot's nested work. */
export function professionalWorkCurrent(c: Case): boolean {
  return c.professionalWork?.basis === professionalWorkBasis(c);
}

/** Open and answered professional and evidence questions by who answers them, for honest progress. */
export function professionalCounts(c: Case): Partial<Record<"you" | "designer", { open: number; done: number }>> {
  const missing = professionalWorkCurrent(c) ? c.professionalWork?.professional.missing_facts : undefined;
  const counts: Partial<Record<"you" | "designer", { open: number; done: number }>> = {};
  const add = (who: "you" | "designer", open: boolean) => {
    const row = counts[who] ?? { open: 0, done: 0 };
    if (open) row.open += 1; else row.done += 1;
    counts[who] = row;
  };
  for (const question of professionalQuestions(c, missing)) add(question.deferred ? "designer" : professionalAnswerer(question.field), !question.known);
  for (let i = 0; i < professionalEvidenceCount(c); i += 1) add("designer", true);
  return counts;
}
