import type { Case } from "./types";
import calgaryPack from "../../engine/data/jurisdictions/packs/calgary.json" with { type: "json" };
import edmontonPack from "../../engine/data/jurisdictions/packs/edmonton.json" with { type: "json" };
import fallbackPack from "../../engine/data/jurisdictions/packs/alberta-other.json" with { type: "json" };

/** NBC edition this product cites. One string, used by intake, examples, and screen headers. */
export const CODE_EDITION = "NBC(AE) 2023, 2nd printing";

/** The registry's key rule: case, accents, periods, apostrophes and spacing do not matter ("Calgary, AB"). */
const fold = (s: string) => s.normalize("NFKD").replace(/[\u0300-\u036f]/g, "").replace(/[.'\u2018\u2019]/g, "").replace(/\s+/g, " ").trim().toLowerCase();

/**
 * The offices Batatis prepares applications for: the City of Calgary and the City of Edmonton, whose own steps
 * their packs record. Every other place is a draft (engine/data/jurisdictions/places), off in the app.
 */
const LOCAL_PACKS = [calgaryPack, edmontonPack];
/** Each office by its short name ("Calgary"), found by every name its pack matches. */
export const AUTHORITIES = LOCAL_PACKS.map((pack) => ({
  id: pack.id,
  name: pack.match.names.find((n) => n !== pack.name && fold(pack.name).includes(fold(n))) ?? pack.name,
  aliases: [pack.name, ...pack.match.names],
}));
export const OFFICE_CHOICE_FIELD = "office.choice";

/** A place is a jurisdiction, never an invented reviewer account code. Free text stays intact. */
export function resolveOffice(value: string): { id: string; name: string; packId: string; reviewerCode: string | null } | null {
  const raw = value.trim().replace(/\s+/g, " ");
  if (!raw || /^(?:unsure|not[ _]sure)$/i.test(raw)) return null;
  const key = fold(raw);
  const head = raw.includes(",") ? fold(raw.split(",")[0]) : key;   // "Calgary, AB"
  const pack = LOCAL_PACKS.find((pack) => [pack.id, pack.name, ...pack.match.ids, ...pack.match.names].some((name) => [key, head].includes(fold(name))));
  const shown = AUTHORITIES.find((a) => a.id === pack?.id)?.name;
  return { id: pack?.id ?? raw, name: shown ?? raw, packId: pack?.id ?? fallbackPack.id, reviewerCode: pack?.authority.reviewer_code ?? null };
}

/** The office a typed name means when Batatis prepares its applications (Calgary, Edmonton); null for any other place. */
export function knownPlace(value: string): { id: string; name: string } | null {
  const office = resolveOffice(value);
  return office && office.packId !== fallbackPack.id ? { id: office.id, name: office.name } : null;
}

/** Whether Batatis prepares applications for a chosen office; null while no office is chosen. */
export function officeCovered(value: string): boolean | null {
  const office = resolveOffice(value);
  return office ? office.packId !== fallbackPack.id : null;
}

export function authorityUnsure(c: Case): boolean {
  const choice = [...c.facts].reverse().find((fact) => fact.field === OFFICE_CHOICE_FIELD);
  return !c.authority && choice?.status === "confirmed" && choice.kind !== "proposed" && choice.value === "not_sure";
}

/** Persisted alongside the jurisdiction using the existing fact writer. */
export function officeChoiceAction(value: string) {
  const office = resolveOffice(value);
  return { type: "setRuleInput", field: OFFICE_CHOICE_FIELD, value: office?.id ?? "not_sure", rule: "office", quote: office?.name ?? "Not sure" } as const;
}

/** The office the site names, when it is one Batatis prepares applications for. */
export function officeSuggestion(c: Case): { id: string; name: string } | null {
  const municipality = [...c.facts].reverse().find((fact) => fact.field === "municipality");
  if (typeof municipality?.value === "string" && municipality.value.trim()) {
    const office = knownPlace(municipality.value);
    if (office) return office;
  }
  const address = [...c.facts].reverse().find((fact) => ["municipalAddress", "municipal_address", "civic_address", "address"].includes(fact.field));
  if (typeof address?.value !== "string") return null;
  // The city is its own part after the street, so a street named after the other city ("0000 Calgary Trail NW,
  // Edmonton, AB") never picks it. Read from the end, past the province and postal code.
  const parts = address.value.split(",").map((part) => part.trim()).filter(Boolean);
  for (const part of parts.slice(1).reverse()) {
    const office = knownPlace(part.replace(/\s*\b(?:AB|Alta\.?|Alberta)\b\s*(?:[A-Z]\d[A-Z]\s?\d[A-Z]\d)?$/i, ""));
    if (office) return office;
  }
  if (parts.length > 1) return null;
  // Without commas, the city mentioned last ("0000 Calgary Trail NW Edmonton AB").
  const text = fold(address.value);
  const last = (place: { name: string }) => Math.max(-1, ...[...text.matchAll(new RegExp(`(?:^|[^a-z])${fold(place.name).replace(/[.*+?^${}()|[\]\\]/g, "\\$&")}(?=$|[^a-z])`, "g"))].map((m) => m.index));
  return AUTHORITIES.filter((place) => last(place) >= 0).sort((a, b) => last(b) - last(a))[0] ?? null;
}

export function submissionOfficeReason(c: Case): string {
  if (!c.authority) return "Choose a reviewing office.";
  const office = resolveOffice(c.authority);
  if (!officeCovered(c.authority)) return `Batatis does not prepare applications for ${office?.name ?? c.authority}.`;
  return office?.reviewerCode ? "" : "This office receives your PDF outside Batatis. Export it below.";
}

/** Exit-count sentences. 9.9.4.4 is openings near exterior exit stairs, not this. */
export const EXIT_COUNT = {
  part3: "3.4.2.1.(1)",
  part9: "9.9.8.2.(1)",
} as const;

/**
 * NRC credit shown next to code text. The printing selector is explicit; the bare publication URL defaults to the first printing.
 * The intent supplement link is the README's source record.
 */
export const NRC_CREDIT = "© National Research Council of Canada";
export const NRC_SOURCES = {
  code: {
    title: CODE_EDITION,
    url: "https://nrc-publications.canada.ca/eng/view/ft/?id=0316d953-0d55-4311-af69-cad55efec499&dp=2&dsl=en",
  },
  intent: {
    title: "Supplement to the NBC 2020: Intent Statements",
    url: "https://nrc-publications.canada.ca/eng/view/object/?id=de0e0ec9-a452-4337-bc84-002a230c9d66",
  },
} as const;
