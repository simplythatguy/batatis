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

/** The browser's field name for an engine fact field. */
export const localField = (field: string): string => ENGINE_TO_LOCAL[field] ?? field;

/** The engine's intake field for a browser field (the planner asks by this name). */
export const engineField = (field: string): string => LOCAL_TO_ENGINE[field] ?? field;

/** A fact with its field renamed for the browser; everything else (id, value, source) is kept. */
export function asLocal<T extends { field: string }>(fact: T): T {
  const field = localField(fact.field);
  return field === fact.field ? fact : { ...fact, field };
}
