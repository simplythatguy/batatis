import type { Case } from "./types";
import places from "../../engine/data/jurisdictions/place_names.json" with { type: "json" };
import calgaryPack from "../../engine/data/jurisdictions/packs/calgary.json" with { type: "json" };
import edmontonPack from "../../engine/data/jurisdictions/packs/edmonton.json" with { type: "json" };
import fallbackPack from "../../engine/data/jurisdictions/packs/alberta-other.json" with { type: "json" };

/** NBC edition this product cites. One string, used by intake, examples, and screen headers. */
export const CODE_EDITION = "NBC(AE) 2023, 2nd printing";

/**
 * Authorities the applicant can pick. The engine case stays without a jurisdiction
 * until one of these is chosen.
 */
export const AUTHORITIES = places.places.map((name) => ({ id: name.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, ""), name }));
const LOCAL_PACKS = [calgaryPack, edmontonPack];
export const OFFICE_CHOICE_FIELD = "office.choice";

/** A place is a jurisdiction, never an invented reviewer account code. Free text stays intact. */
export function resolveOffice(value: string): { id: string; name: string; packId: string; reviewerCode: string | null } | null {
  const raw = value.trim().replace(/\s+/g, " ");
  if (!raw || /^(?:unsure|not[ _]sure)$/i.test(raw)) return null;
  const key = raw.toLowerCase();
  const pack = LOCAL_PACKS.find((pack) => [pack.id, pack.name, ...pack.match.ids, ...pack.match.names].some((name) => name.toLowerCase() === key));
  const place = AUTHORITIES.find((place) => place.id === key || place.name.toLowerCase() === key);
  return { id: pack?.id ?? place?.id ?? raw, name: place?.name ?? pack?.name ?? raw, packId: pack?.id ?? fallbackPack.id, reviewerCode: pack?.authority.reviewer_code ?? null };
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

export function officeSuggestion(c: Case): { id: string; name: string } | null {
  const municipality = [...c.facts].reverse().find((fact) => fact.field === "municipality");
  if (typeof municipality?.value === "string" && municipality.value.trim()) {
    const office = resolveOffice(municipality.value);
    if (office) return office;
  }
  const address = [...c.facts].reverse().find((fact) => ["municipalAddress", "municipal_address", "civic_address", "address"].includes(fact.field));
  if (typeof address?.value !== "string") return null;
  const text = address.value.toLowerCase();
  return AUTHORITIES.find((place) => new RegExp(`(?:^|[^a-z])${place.name.toLowerCase().replace(/[.*+?^${}()|[\]\\]/g, "\\$&")}(?:$|[^a-z])`).test(text)) ?? null;
}

export function submissionOfficeReason(c: Case): string {
  if (!c.authority) return "Choose a reviewing office.";
  return resolveOffice(c.authority)?.reviewerCode ? "" : "This office receives your PDF outside Batatis. Export it below.";
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
