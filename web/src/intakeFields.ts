/**
 * The engine's intake writes Section A and B facts under the SCC export keys (`owner_name`,
 * `municipal_address`, ...); the web's form cards use their own ids (`owner`, `municipalAddress`).
 * The engine treats both names as one logical field (engine/export/scc.py `_ALIASES`,
 * engine/completeness.py `_CORE`), so the browser renames at the boundary and keeps one card per
 * field. Every other intake field (storeys, building_area_m2, ...) keeps the engine's name.
 */
const ENGINE_TO_LOCAL: Readonly<Record<string, string>> = {
  owner_name: "owner",
  owner_rep_name: "representative",
  mailing_address: "mailingAddress",
  municipal_address: "municipalAddress",
  legal_description: "legalDescription",
  permit_number: "permit",
  request_date: "date",
  alternative_description: "alternative",
};

const LOCAL_TO_ENGINE: Readonly<Record<string, string>> = Object.fromEntries(Object.entries(ENGINE_TO_LOCAL).map(([e, l]) => [l, e]));

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
