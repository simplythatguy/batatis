/**
 * Saved API and intake facts share the engine's aliases (engine/export/scc.py `_ALIASES`,
 * engine/completeness.py `_CORE`, engine/process_fields.py `PROCESS_ALIASES`). Resolve them at
 * the browser boundary, including in sync's already-posted record, so reopening never writes
 * renamed copies. Only the field changes; ids, values, confirmation and provenance stay intact.
 */
import type { Fact } from "./types";

const FIELD_ALIASES: Readonly<Record<string, readonly string[]>> = {
  storeys: ["building.storeys"],
  owner: ["owner_name", "section_a.owner_name"],
  representative: ["owner_rep_name", "applicant_name", "section_a.representative"],
  mailingAddress: ["mailing_address", "section_a.mailing_address"],
  municipalAddress: ["municipal_address", "civic_address", "address"],
  legalDescription: ["legal_description", "section_b.legal_description"],
  permit: ["permit_number", "section_b.permit_number"],
  date: ["request_date", "application_date", "section_a.date"],
  alternative: ["alternative_description"],
  "process.rationale": ["rationale"],
  "process.risk_assessment": ["risk_assessment", "risk", "process.risk"],
  "process.mitigating_measures": ["mitigating_measures", "mitigation", "process.mitigation"],
  "process.assumptions_and_limits": ["assumptions_and_limits", "assumptions_limits", "assumptions", "process.assumptions_limits", "process.assumptions"],
  "process.maintenance_operation": ["maintenance_operation", "operation_maintenance", "process.operation_maintenance"],
  "process.qualifications": ["qualifications"],
  "professional.role": ["registered_professional.role"],
  "professional.discipline": ["registered_professional.discipline"],
  "professional.registration_number": ["professional.registration", "registered_professional.registration_number", "apega_number", "aaa_number"],
  "professional.seal": ["professional_seal", "registered_professional.seal"],
  // Engagement and a professional role are separate facts, not interchangeable credentials.
  "professional.status": ["professional_status"],
};

const ENGINE_TO_LOCAL: Readonly<Record<string, string>> = Object.fromEntries(
  Object.entries(FIELD_ALIASES).flatMap(([local, aliases]) => aliases.map((alias) => [alias, local])),
);

// Intake answers keep their established export keys, independent of the saved-case aliases.
const LOCAL_TO_ENGINE: Readonly<Record<string, string>> = {
  owner: "owner_name", representative: "owner_rep_name", mailingAddress: "mailing_address",
  municipalAddress: "municipal_address", legalDescription: "legal_description", permit: "permit_number",
  date: "request_date", alternative: "alternative_description",
};

/**
 * The other names the engine reads as the same field (engine/completeness.py `_CORE`,
 * engine/process_fields.py `PROCESS_ALIASES`). Read only: saved answers under any of them open on
 * the browser's one card, and the newest across them wins, as on the engine. The browser still
 * writes the names above, so adding a name here never changes what a save sends.
 */
const READ_ALIASES: Readonly<Record<string, string>> = {
  "section_a.owner_name": "owner",
  applicant_name: "representative",
  application_date: "date",
  "section_a.date": "date",
  civic_address: "municipalAddress",
  address: "municipalAddress",
  "section_b.legal_description": "legalDescription",
  ...processAliases({
    rationale: ["rationale"],
    risk_assessment: ["risk_assessment", "risk"],
    mitigating_measures: ["mitigating_measures", "mitigation"],
    assumptions_and_limits: ["assumptions_and_limits", "assumptions_limits", "assumptions"],
    maintenance_operation: ["maintenance_operation", "operation_maintenance"],
    qualifications: ["qualifications"],
  }),
};

/** `process.<name>` and the bare name both read as the canonical `process.<id>`. */
function processAliases(names: Record<string, string[]>): Record<string, string> {
  return Object.fromEntries(Object.entries(names).flatMap(([id, all]) => all.flatMap((n) => [[n, `process.${id}`], [`process.${n}`, `process.${id}`]])));
}

/** The browser's field name for an engine fact field. */
export const localField = (field: string): string => ENGINE_TO_LOCAL[field] ?? READ_ALIASES[field] ?? field;

/** The engine's intake field for a browser field (the planner asks by this name). */
export const engineField = (field: string): string => LOCAL_TO_ENGINE[field] ?? field;

/** A fact with its field renamed for the browser; everything else (id, value, source) is kept. */
export function asLocal<T extends { field: string }>(fact: T): T {
  const field = localField(fact.field);
  return field === fact.field ? fact : { ...fact, field };
}

/** Select the newest revision across aliases before checking status, even when it is blank. */
export function latestLocalFacts<T extends { field: string }>(facts: readonly T[]): T[] {
  const latest = new Map(facts.map((fact) => [localField(fact.field), fact]));
  return facts.filter((fact) => latest.get(localField(fact.field)) === fact).map(asLocal);
}

/** A saved clear must suppress older aliases and must not be posted again when reopening. */
export function answerWithdrawn(fact: { value: unknown; status?: string; source?: { ref?: string } }): boolean {
  return fact.source?.ref === "Answer withdrawn by applicant" || (fact.value === "" && fact.status === "unconfirmed");
}

/** Only an authoritative latest answer can satisfy another question. A reading still needs a click. */
export function confirmedAnswer(facts: readonly Fact[], field: string): Fact | undefined {
  const f = latestLocalFacts(facts).find((x) => x.field === localField(field));
  if (!f || f.status !== "confirmed" || f.kind === "proposed" || f.kind === "computed" || answerWithdrawn(f)) return undefined;
  const text = f.value == null ? "" : String(f.value).trim();
  if (!text || /^(?:not[-_ ]sure|unsure|unknown|don.t know|do not know)$/i.test(text)) return undefined;
  if (localField(field) === "storeys" && (!Number.isInteger(Number(text)) || Number(text) <= 0)) return undefined;
  return f;
}
