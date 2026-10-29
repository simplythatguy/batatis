import type { Case } from "./types";
import places from "../../engine/data/jurisdictions/place_names.json" with { type: "json" };
import placeIndex from "../../engine/data/jurisdictions/place_index.json" with { type: "json" };
import calgaryPack from "../../engine/data/jurisdictions/packs/calgary.json" with { type: "json" };
import edmontonPack from "../../engine/data/jurisdictions/packs/edmonton.json" with { type: "json" };
import fallbackPack from "../../engine/data/jurisdictions/packs/alberta-other.json" with { type: "json" };

/** NBC edition this product cites. One string, used by intake, examples, and screen headers. */
export const CODE_EDITION = "NBC(AE) 2023, 2nd printing";

type PlaceRow = { id: string; name: string; aliases: string[]; province: string; kind: string; covered: boolean; office: string };
/** Every place the engine knows (generated from the jurisdiction research; see engine/jurisdictions/places_build.py). */
const PLACES: PlaceRow[] = placeIndex.places;
/** In Alberta the short name when it is unambiguous ("Red Deer"), else the legal name; elsewhere the full name ("Ontario"). */
const shown = (p: PlaceRow) => (p.province === "AB" ? p.aliases[0] ?? p.name : p.name);
/** The registry's key rule: case, accents, periods, apostrophes and spacing do not matter ("St. Johns"). */
const fold = (s: string) => s.normalize("NFKD").replace(/[\u0300-\u036f]/g, "").replace(/[.'\u2018\u2019]/g, "").replace(/\s+/g, " ").trim().toLowerCase();

/**
 * Places the applicant can pick: every Alberta place, then the places outside Alberta that Batatis
 * names but does not cover. The engine case stays without a jurisdiction until one is chosen.
 */
export const AUTHORITIES = PLACES.map((p) => ({ id: p.id, name: shown(p), aliases: [p.name, ...p.aliases] }));
const LOCAL_PACKS = [calgaryPack, edmontonPack];
export const OFFICE_CHOICE_FIELD = "office.choice";

function findPlace(key: string): PlaceRow | undefined {
  const k = fold(key);
  return PLACES.find((p) => p.id === k || fold(p.name) === k || p.aliases.some((a) => fold(a) === k));
}

/** A place is a jurisdiction, never an invented reviewer account code. Free text stays intact. */
export function resolveOffice(value: string): { id: string; name: string; packId: string; reviewerCode: string | null } | null {
  const raw = value.trim().replace(/\s+/g, " ");
  if (!raw || /^(?:unsure|not[ _]sure)$/i.test(raw)) return null;
  const key = fold(raw);
  const head = raw.includes(",") ? fold(raw.split(",")[0]) : key;   // "Toronto, ON", "Red Deer, AB"
  const pack = LOCAL_PACKS.find((pack) => [pack.id, pack.name, ...pack.match.ids, ...pack.match.names].some((name) => [key, head].includes(fold(name))));
  const place = findPlace(pack?.id ?? key) ?? findPlace(key) ?? findPlace(head);
  return { id: pack?.id ?? place?.id ?? raw, name: place ? shown(place) : pack?.name ?? raw, packId: pack?.id ?? place?.id ?? fallbackPack.id, reviewerCode: pack?.authority.reviewer_code ?? null };
}

/** The place a typed name means, when the engine knows it; null for a name it does not (a hamlet, a typo). */
export function knownPlace(value: string): { id: string; name: string } | null {
  const office = resolveOffice(value);
  return office && office.packId !== fallbackPack.id ? { id: office.id, name: office.name } : null;
}

/** Who reviews building work at a chosen place, and whether Batatis prepares applications there; null for a place it does not know. */
export function placeOffice(value: string): { office: string; differs: boolean; covered: boolean } | null {
  const office = resolveOffice(value);
  const place = office && PLACES.find((p) => p.id === office.packId);
  return place ? { office: place.office, differs: place.office !== place.name, covered: place.covered } : null;
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

/** Names searched for in a typed address: the curated list, so a street name never picks one of four hundred places. */
const SUGGESTIONS = places.places.map((name) => knownPlace(name) ?? { id: name.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, ""), name });

export function officeSuggestion(c: Case): { id: string; name: string } | null {
  const municipality = [...c.facts].reverse().find((fact) => fact.field === "municipality");
  if (typeof municipality?.value === "string" && municipality.value.trim()) {
    const office = resolveOffice(municipality.value);
    if (office) return office;
  }
  const address = [...c.facts].reverse().find((fact) => ["municipalAddress", "municipal_address", "civic_address", "address"].includes(fact.field));
  if (typeof address?.value !== "string") return null;
  const text = address.value.toLowerCase();
  return SUGGESTIONS.find((place) => new RegExp(`(?:^|[^a-z])${place.name.toLowerCase().replace(/[.*+?^${}()|[\]\\]/g, "\\$&")}(?:$|[^a-z])`).test(text)) ?? null;
}

export function submissionOfficeReason(c: Case): string {
  if (!c.authority) return "Choose a reviewing office.";
  const office = resolveOffice(c.authority);
  if (office && PLACES.some((p) => p.id === office.packId && !p.covered)) return `Batatis does not prepare applications for ${office.name}.`;
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
